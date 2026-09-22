import json
import os
import re
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path

import bleach
import frontmatter
import markdown


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LOCAL_UPLOAD_PATTERN = re.compile(r"/media/uploads/[A-Za-z0-9_.-]+")


def _atomic_write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp:
            temp.write(value)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _atomic_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with source.open("rb") as input_file, os.fdopen(fd, "wb") as output_file:
            shutil.copyfileobj(input_file, output_file)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _copy_missing_tree(source, target):
    for source_path in source.rglob("*"):
        target_path = target / source_path.relative_to(source)
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        elif not target_path.exists():
            _atomic_copy(source_path, target_path)


def _validate_state(site_path, messages_path):
    expected_types = ((site_path, dict), (messages_path, list))
    values = []
    for path, expected_type in expected_types:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Geçersiz JSON dosyası: {path}") from error
        if not isinstance(value, expected_type):
            raise RuntimeError(f"Beklenmeyen JSON yapısı: {path}")
        values.append(value)

    site = values[0]
    required_sections = ("branding", "contact", "profile")
    invalid_sections = [name for name in required_sections if not isinstance(site.get(name), dict)]
    if invalid_sections:
        raise RuntimeError(f"Eksik site bölümleri: {', '.join(invalid_sections)}")


def initialize_storage(storage_root, seed_root):
    storage_root = Path(storage_root)
    seed_root = Path(seed_root)
    state_dir = storage_root / "state"
    blog_dir = storage_root / "blog"
    upload_dir = storage_root / "uploads"
    branding_dir = storage_root / "branding"

    for directory in (state_dir, blog_dir, upload_dir, branding_dir):
        directory.mkdir(parents=True, exist_ok=True)

    marker = storage_root / ".initialized"
    site_path = state_dir / "site.json"
    messages_path = state_dir / "messages.json"
    initializing = not marker.exists()

    if initializing:
        if not site_path.exists():
            _atomic_copy(seed_root / "site.json", site_path)
            site_path.chmod(0o600)
        if not messages_path.exists():
            _atomic_write_text(messages_path, "[]\n")
        _copy_missing_tree(seed_root / "blog", blog_dir)
        _copy_missing_tree(seed_root / "branding", branding_dir)

    required_files = (
        site_path,
        messages_path,
        branding_dir / "profile.png",
        branding_dir / "favicon.png",
    )
    missing = [str(path.relative_to(storage_root)) for path in required_files if not path.is_file()]
    if missing:
        raise RuntimeError(f"Kalıcı depolama eksik: {', '.join(missing)}")

    _validate_state(site_path, messages_path)

    try:
        fd, probe_name = tempfile.mkstemp(dir=storage_root, prefix=".write-test-")
        os.close(fd)
        os.unlink(probe_name)
    except OSError as error:
        raise RuntimeError(f"Kalıcı depolama yazılabilir değil: {storage_root}") from error

    if initializing:
        _atomic_write_text(marker, "1\n")


def slugify(value):
    replacements = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    value = value.translate(replacements).lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "yazi"


class ContentRepository:
    def __init__(self, root):
        self.root = Path(root)
        self.site_path = self.root / "state" / "site.json"
        self.messages_path = self.root / "state" / "messages.json"
        self.blog_dir = self.root / "blog"
        self.blog_dir.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default

    def _write_json(self, path, value):
        serialized = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        _atomic_write_text(path, serialized)

    def is_ready(self):
        try:
            _validate_state(self.site_path, self.messages_path)
        except (OSError, RuntimeError):
            return False
        return self.blog_dir.is_dir() and os.access(self.root, os.W_OK)

    def get_site(self):
        return self._read_json(self.site_path, {})

    def save_site(self, site):
        self._write_json(self.site_path, site)

    def get_messages(self):
        return self._read_json(self.messages_path, [])

    def add_message(self, payload):
        messages = self.get_messages()
        messages.insert(0, {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "created_at": datetime.now().isoformat(timespec="minutes"),
            "read": False,
            **payload,
        })
        self._write_json(self.messages_path, messages)

    def mark_message_read(self, message_id):
        messages = self.get_messages()
        for message in messages:
            if message["id"] == message_id:
                message["read"] = True
                break
        self._write_json(self.messages_path, messages)

    def delete_message(self, message_id):
        messages = [m for m in self.get_messages() if m["id"] != message_id]
        self._write_json(self.messages_path, messages)

    def list_posts(self, published_only=True):
        posts = []
        for path in self.blog_dir.glob("*.md"):
            post = self._load_post(path)
            if post and (not published_only or post["published"]):
                posts.append(post)
        return sorted(
            posts,
            key=lambda item: (item["date"], item["time"]),
            reverse=True,
        )

    def search_posts(self, query="", tag="", published_only=True):
        posts = self.list_posts(published_only=published_only)
        normalized_query = self._normalize(query)
        normalized_tag = self._normalize(tag)
        if normalized_tag:
            posts = [
                post for post in posts
                if normalized_tag in {self._normalize(item) for item in post["tags"]}
            ]
        if normalized_query:
            posts = [
                post for post in posts
                if normalized_query in self._normalize(" ".join([
                    post["title"], post["summary"], post["body"], *post["tags"],
                ]))
            ]
        return posts

    @staticmethod
    def _normalize(value):
        return str(value).translate(str.maketrans("IİŞĞÜÖÇ", "ıişğüöç")).casefold()

    def get_post(self, slug, published_only=True):
        if not SLUG_PATTERN.fullmatch(slug):
            return None
        path = self.blog_dir / f"{slug}.md"
        if not path.exists():
            return None
        post = self._load_post(path)
        if not post or (published_only and not post["published"]):
            return None
        return post

    def _load_post(self, path):
        try:
            source = frontmatter.load(path)
        except (OSError, UnicodeDecodeError):
            return None
        raw_date = source.get("date", date.today().isoformat())
        if isinstance(raw_date, (date, datetime)):
            raw_date = raw_date.isoformat()
        raw_time = str(source.get("time", "00:00"))
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", raw_time):
            raw_time = "00:00"
        clean_html = self.render_markdown(source.content)
        tags = source.get("tags", [])
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        return {
            "slug": path.stem,
            "title": source.get("title", path.stem.replace("-", " ").title()),
            "date": str(raw_date),
            "time": raw_time,
            "tags": tags,
            "summary": source.get("summary", ""),
            "cover": source.get("cover", ""),
            "published": bool(source.get("published", True)),
            "body": source.content,
            "html": clean_html,
            "images": sorted(set(LOCAL_UPLOAD_PATTERN.findall(source.content))),
        }

    def render_markdown(self, content):
        body_html = markdown.markdown(
            content,
            extensions=["extra", "sane_lists", "toc"],
        )
        allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS) | {
            "p", "h1", "h2", "h3", "h4", "pre", "code", "hr", "br",
            "img", "table", "thead", "tbody", "tr", "th", "td",
        }
        return bleach.clean(
            body_html,
            tags=allowed_tags,
            attributes={"a": ["href", "title"], "img": ["src", "alt", "title"]},
        )

    def save_post(self, original_slug, payload):
        slug = slugify(payload["slug"] or payload["title"])
        post = frontmatter.Post(payload["body"])
        post.metadata = {
            "title": payload["title"].strip(),
            "date": payload["date"],
            "time": payload.get("time", "00:00"),
            "tags": payload["tags"],
            "summary": payload["summary"].strip(),
            "cover": payload["cover"].strip(),
            "published": payload["published"],
        }
        target = self.blog_dir / f"{slug}.md"
        _atomic_write_text(target, frontmatter.dumps(post) + "\n")
        if original_slug and original_slug != slug:
            old_path = self.blog_dir / f"{original_slug}.md"
            if old_path.exists():
                old_path.unlink()
        return slug

    def delete_post(self, slug):
        if SLUG_PATTERN.fullmatch(slug):
            path = self.blog_dir / f"{slug}.md"
            if path.exists():
                path.unlink()

    def remove_post_image(self, slug, image_url):
        if not SLUG_PATTERN.fullmatch(slug) or not LOCAL_UPLOAD_PATTERN.fullmatch(image_url):
            return False
        path = self.blog_dir / f"{slug}.md"
        if not path.exists():
            return False
        source = frontmatter.load(path)
        markdown_image = re.compile(
            rf"!\[[^\]]*\]\(\s*{re.escape(image_url)}(?:\s+[\"'][^\"']*[\"'])?\s*\)"
        )
        source.content = markdown_image.sub("", source.content).strip()
        _atomic_write_text(path, frontmatter.dumps(source) + "\n")
        return True
