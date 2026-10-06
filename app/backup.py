import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import zipfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .content import _validate_state


BACKUP_FORMAT = "mcv-backup"
BACKUP_VERSION = 2
MANIFEST_NAME = "manifest.json"
BACKUP_DIRECTORIES = ("state", "blog", "uploads", "branding")
BACKUP_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
REQUIRED_FILES = {
    "state/site.json",
    "branding/profile.png",
    "branding/favicon.png",
}
_restore_lock = threading.Lock()


class BackupError(ValueError):
    pass


def _storage_files(storage_root):
    storage_root = Path(storage_root)
    for directory_name in BACKUP_DIRECTORIES:
        directory = storage_root / directory_name
        if not directory.is_dir() or directory.is_symlink() or getattr(directory, "is_junction", lambda: False)():
            raise BackupError(f"Yedeklenecek klasör bulunamadı: {directory_name}")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise BackupError(f"Sembolik bağlantı yedeklenemez: {path.name}")
            if path.is_file():
                archive_path = path.relative_to(storage_root).as_posix()
                _safe_archive_path(archive_path)
                yield path, archive_path


def create_backup(storage_root, output_file):
    files = list(_storage_files(storage_root))
    paths = {archive_path for _, archive_path in files}
    missing = sorted(REQUIRED_FILES - paths)
    if missing:
        raise BackupError(f"Zorunlu dosyalar eksik: {', '.join(missing)}")

    manifest_entries = []
    with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path, archive_path in files:
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as source, archive.open(archive_path, "w") as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
                    target.write(chunk)
            manifest_entries.append({
                "path": archive_path,
                "size": size,
                "sha256": digest.hexdigest(),
            })
        manifest = {
            "format": BACKUP_FORMAT,
            "version": BACKUP_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": manifest_entries,
        }
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    output_file.seek(0)
    return manifest


def _safe_archive_path(name):
    if "\\" in name:
        raise BackupError("Arşivde geçersiz bir dosya yolu var.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 2:
        raise BackupError("Arşivde geçersiz bir dosya yolu var.")
    if path.parts[0] not in BACKUP_DIRECTORIES:
        raise BackupError(f"Arşivde desteklenmeyen klasör var: {path.parts[0]}")
    filename = path.parts[1]
    if not BACKUP_FILENAME_PATTERN.fullmatch(filename) or filename.endswith((".", " ")):
        raise BackupError("Arşivde geçersiz bir dosya adı var.")
    directory = path.parts[0]
    if directory == "state" and name != "state/site.json":
        raise BackupError("Yedekte desteklenmeyen bir durum dosyası var.")
    if directory == "blog" and path.suffix.lower() != ".md":
        raise BackupError("Yedekte desteklenmeyen bir blog dosyası var.")
    if directory == "uploads" and path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise BackupError("Yedekte desteklenmeyen bir medya dosyası var.")
    if directory == "branding" and name not in {"branding/profile.png", "branding/favicon.png"}:
        raise BackupError("Yedekte desteklenmeyen bir marka dosyası var.")
    return path


def _validate_manifest(archive, max_files, max_uncompressed_size):
    infos = archive.infolist()
    if len(infos) > max_files + 1:
        raise BackupError(f"Yedek en fazla {max_files} dosya içerebilir.")

    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise BackupError("Yedekte yinelenen dosya adları var.")
    if len(names) != len({name.casefold() for name in names}):
        raise BackupError("Yedekte dosya sistemiyle çakışan adlar var.")
    if names.count(MANIFEST_NAME) != 1:
        raise BackupError("Yedek manifest dosyası eksik veya geçersiz.")

    manifest_info = archive.getinfo(MANIFEST_NAME)
    if manifest_info.is_dir() or manifest_info.flag_bits & 0x1:
        raise BackupError("Yedek manifest dosyası geçersiz.")
    if manifest_info.file_size > 2 * 1024 * 1024:
        raise BackupError("Yedek manifest dosyası çok büyük.")
    try:
        manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BackupError("Yedek manifest dosyası okunamadı.") from error

    if not isinstance(manifest, dict):
        raise BackupError("Yedek manifest dosyası geçersiz.")
    if manifest.get("format") != BACKUP_FORMAT or manifest.get("version") != BACKUP_VERSION:
        raise BackupError("Yedek formatı veya sürümü desteklenmiyor.")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise BackupError("Yedek dosya listesi geçersiz.")

    manifest_entries = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise BackupError("Yedek dosya listesi geçersiz.")
        path = entry.get("path")
        if not isinstance(path, str) or path in manifest_entries:
            raise BackupError("Yedek dosya listesinde yinelenen veya geçersiz bir yol var.")
        _safe_archive_path(path)
        size = entry.get("size")
        checksum = entry.get("sha256")
        if not isinstance(size, int) or size < 0:
            raise BackupError(f"Yedekte geçersiz dosya boyutu var: {path}")
        if not isinstance(checksum, str) or len(checksum) != 64:
            raise BackupError(f"Yedekte geçersiz sağlama toplamı var: {path}")
        manifest_entries[path] = entry

    archive_infos = {}
    total_size = 0
    for info in infos:
        if info.filename == MANIFEST_NAME:
            continue
        if info.is_dir() or info.flag_bits & 0x1:
            raise BackupError("Yedek şifreli dosya veya klasör girdisi içeremez.")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise BackupError("Yedek sembolik bağlantı içeremez.")
        _safe_archive_path(info.filename)
        if info.compress_size and info.file_size / info.compress_size > 200:
            raise BackupError(f"Yedekte güvenli olmayan sıkıştırma oranı var: {info.filename}")
        archive_infos[info.filename] = info
        total_size += info.file_size

    if total_size > max_uncompressed_size:
        raise BackupError("Yedeğin açılmış boyutu izin verilen sınırı aşıyor.")
    if set(archive_infos) != set(manifest_entries):
        raise BackupError("Yedek içeriği manifest ile eşleşmiyor.")
    missing = sorted(REQUIRED_FILES - set(archive_infos))
    if missing:
        raise BackupError(f"Yedekte zorunlu dosyalar eksik: {', '.join(missing)}")

    for path, info in archive_infos.items():
        if info.file_size != manifest_entries[path]["size"]:
            raise BackupError(f"Yedekte dosya boyutu eşleşmiyor: {path}")
    return manifest_entries, archive_infos


def _extract_and_validate(archive, destination, entries, infos):
    for archive_path, info in infos.items():
        target = destination.joinpath(*PurePosixPath(archive_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with archive.open(info) as source, target.open("wb") as output:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != entries[archive_path]["sha256"]:
            raise BackupError(f"Yedek bütünlük kontrolü başarısız: {archive_path}")

    for directory_name in BACKUP_DIRECTORIES:
        (destination / directory_name).mkdir(exist_ok=True)
    try:
        _validate_state(destination / "state" / "site.json")
    except (OSError, RuntimeError, UnicodeDecodeError) as error:
        raise BackupError("Yedekteki site verileri geçersiz.") from error


def restore_backup(storage_root, input_file, max_files=5000, max_uncompressed_size=512 * 1024 * 1024):
    storage_root = Path(storage_root).resolve()
    if not storage_root.is_dir():
        raise BackupError("Mevcut kalıcı depolama bulunamadı.")
    workspace = Path(tempfile.mkdtemp(prefix=".mcv-restore-", dir=storage_root))
    staging_root = workspace / "staging"
    rollback_root = workspace / "rollback"

    try:
        try:
            with zipfile.ZipFile(input_file) as archive:
                entries, infos = _validate_manifest(archive, max_files, max_uncompressed_size)
                _extract_and_validate(archive, staging_root, entries, infos)
        except (zipfile.BadZipFile, NotImplementedError, OSError, RuntimeError) as error:
            raise BackupError("Seçilen dosya geçerli bir mCV yedeği değil.") from error

        if not _restore_lock.acquire(blocking=False):
            raise BackupError("Başka bir geri yükleme işlemi halen devam ediyor.")
        try:
            rollback_root.mkdir()
            replaced = []
            try:
                for directory_name in BACKUP_DIRECTORIES:
                    current = storage_root / directory_name
                    previous = rollback_root / directory_name
                    replacement = staging_root / directory_name
                    os.replace(current, previous)
                    try:
                        os.replace(replacement, current)
                    except Exception:
                        os.replace(previous, current)
                        raise
                    replaced.append(directory_name)
            except Exception:
                for directory_name in reversed(replaced):
                    current = storage_root / directory_name
                    previous = rollback_root / directory_name
                    if current.exists():
                        shutil.rmtree(current)
                    os.replace(previous, current)
                raise
        finally:
            _restore_lock.release()
    finally:
        with suppress(OSError):
            shutil.rmtree(workspace)
