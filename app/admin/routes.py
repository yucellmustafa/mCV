import hmac
import os
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps, UnidentifiedImageError

from ..content import LOCAL_UPLOAD_PATTERN
from . import bp


COLLECTIONS = {
    "services": {
        "title": "Hizmetler",
        "fields": [("icon", "İkon", "text"), ("title", "Başlık", "text"), ("description", "Açıklama", "textarea")],
    },
    "experiences": {
        "title": "İş deneyimleri",
        "fields": [("period", "Tarih", "text"), ("company", "Şirket", "text"), ("role", "Pozisyon", "text"), ("location", "Konum", "text"), ("description", "Açıklama", "textarea")],
    },
    "education": {
        "title": "Eğitim",
        "fields": [("period", "Tarih", "text"), ("institution", "Kurum", "text"), ("program", "Program", "text"), ("department", "Bölüm / fakülte", "text")],
    },
    "projects": {
        "title": "Projeler",
        "fields": [("title", "Proje adı", "text"), ("description", "Açıklama", "textarea"), ("url", "Bağlantı (isteğe bağlı)", "url"), ("image", "Proje görseli (isteğe bağlı)", "image"), ("tags", "Etiketler", "tags")],
    },
    "skills": {
        "title": "Yetenekler",
        "fields": [("name", "Yetenek", "text"), ("level", "Seviye (0-100)", "number"), ("group", "Grup", "text")],
    },
    "languages": {
        "title": "Diller",
        "fields": [("name", "Dil", "text"), ("level", "Seviye", "text")],
    },
    "interests": {
        "title": "Hobiler",
        "fields": [("icon", "İkon", "text"), ("name", "Hobi", "text")],
    },
    "socials": {
        "title": "Sosyal bağlantılar",
        "fields": [("icon", "İkon", "text"), ("label", "Etiket", "text"), ("url", "Bağlantı", "url")],
    },
    "certificates": {
        "title": "Sertifikalar",
        "fields": [("title", "Sertifika", "text"), ("issuer", "Veren kurum", "text"), ("date", "Tarih", "text"), ("url", "Bağlantı", "url")],
    },
}


def repository():
    return current_app.extensions["content"]


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def password_matches(password):
    return hmac.compare_digest(
        password.encode("utf-8"), current_app.config["ADMIN_PASSWORD"].encode("utf-8"),
    )


def credentials_match(username, password):
    expected_username = current_app.config["ADMIN_USERNAME"]
    username_matches = hmac.compare_digest(
        username.encode("utf-8"), expected_username.encode("utf-8"),
    )
    password_is_valid = password_matches(password)
    return username_matches and password_is_valid


@bp.after_request
def prevent_admin_caching(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def save_fixed_image(file, output_name, *, max_size=None, fit_size=None):
    filename = secure_filename(file.filename)
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in current_app.config["UPLOAD_EXTENSIONS"]:
        raise ValueError("Görsel PNG, JPG, WEBP veya GIF biçiminde olmalıdır.")

    upload_dir = Path(current_app.config["BRAND_ASSET_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / output_name
    temporary = upload_dir / f".{Path(output_name).stem}-{uuid4().hex}.png"
    try:
        with Image.open(file.stream) as source:
            image = ImageOps.exif_transpose(source)
            if fit_size:
                image = ImageOps.fit(image, fit_size, method=Image.Resampling.LANCZOS)
            elif max_size:
                image.thumbnail(max_size)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            image.save(temporary, format="PNG", optimize=True)
        os.replace(temporary, target)
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("Seçilen dosya geçerli bir görsel değil.") from error
    finally:
        temporary.unlink(missing_ok=True)
    return f"/media/branding/{output_name}"


def save_uploaded_image(file):
    filename = secure_filename(file.filename)
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in current_app.config["UPLOAD_EXTENSIONS"]:
        raise ValueError("Yalnızca PNG, JPG, WEBP ve GIF dosyaları yüklenebilir.")
    try:
        with Image.open(file.stream) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("Seçilen dosya geçerli bir görsel değil.") from error
    finally:
        file.stream.seek(0)

    stem = Path(filename).stem or "gorsel"
    unique_filename = f"{stem}-{uuid4().hex}.{extension}"
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    file.save(upload_dir / unique_filename)
    return f"/media/uploads/{unique_filename}"


def delete_uploaded_image(image_url):
    if not image_url or not LOCAL_UPLOAD_PATTERN.fullmatch(image_url):
        return False
    site = repository().get_site()
    if any(project.get("image") == image_url for project in site.get("projects", [])):
        return False
    for post in repository().list_posts(published_only=False):
        if post["cover"] == image_url or image_url in post["images"]:
            return False
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    target = (upload_dir / Path(image_url).name).resolve()
    if target.parent != upload_dir:
        return False
    target.unlink(missing_ok=True)
    return True


@bp.route("/giris", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if credentials_match(username, request.form.get("password", "")):
            session.clear()
            session["admin_authenticated"] = True
            session["admin_username"] = username
            flash("Yönetim paneline giriş yapıldı.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Kullanıcı adı veya parola hatalı.", "error")
    return render_template("admin/login.html")


@bp.post("/cikis")
@admin_required
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@bp.get("/")
@admin_required
def dashboard():
    posts = repository().list_posts(published_only=False)
    messages = repository().get_messages()
    return render_template(
        "admin/dashboard.html",
        site=repository().get_site(),
        posts=posts,
        messages=messages,
    )


@bp.route("/profil", methods=["GET", "POST"])
@admin_required
def profile():
    site = repository().get_site()
    if request.method == "POST":
        profile_data = site.setdefault("profile", {})
        avatar = request.files.get("avatar")
        if avatar and avatar.filename:
            try:
                profile_data["avatar"] = save_fixed_image(
                    avatar, "profile.png", max_size=(600, 600),
                )
            except ValueError as error:
                flash(str(error), "error")
                return redirect(url_for("admin.profile"))
        favicon = request.files.get("favicon")
        if favicon and favicon.filename:
            try:
                site.setdefault("branding", {})["favicon"] = save_fixed_image(
                    favicon, "favicon.png", fit_size=(512, 512),
                )
            except ValueError as error:
                flash(str(error), "error")
                return redirect(url_for("admin.profile"))
        for field in ["name", "title", "email", "phone", "location", "birthdate", "marital_status", "military_status", "driving_license"]:
            profile_data[field] = request.form.get(field, "").strip()
        selected_theme = request.form.get("theme", site.get("branding", {}).get("theme", "cobalt"))
        if selected_theme in {"cobalt", "emerald", "amber", "violet", "coral"}:
            site.setdefault("branding", {})["theme"] = selected_theme
        repository().save_site(site)
        flash("Profil bilgileri kaydedildi.", "success")
        return redirect(url_for("admin.profile"))
    return render_template("admin/profile.html", site=site)


@bp.route("/site-metinleri", methods=["GET", "POST"])
@admin_required
def site_texts():
    site = repository().get_site()
    if request.method == "POST":
        profile_data = site.setdefault("profile", {})
        for field in ["eyebrow", "hero_title", "hero_highlight", "bio"]:
            profile_data[field] = request.form.get(field, "").strip()
        repository().save_site(site)
        flash("Site metinleri kaydedildi.", "success")
        return redirect(url_for("admin.site_texts"))
    return render_template("admin/site_texts.html", site=site)


@bp.route("/liste/<name>", methods=["GET", "POST"])
@admin_required
def collection(name):
    config = COLLECTIONS.get(name)
    if not config:
        abort(404)
    site = repository().get_site()
    items = site.setdefault(name, [])
    edit_index = request.args.get("duzenle", type=int)
    return_page = request.form.get("sayfa", request.args.get("sayfa", 1), type=int)

    if request.method == "POST":
        action = request.form.get("action", "save")
        index = request.form.get("index", type=int)
        files_to_delete = []
        if action == "delete" and index is not None and 0 <= index < len(items):
            removed_item = items.pop(index)
            if name == "projects":
                files_to_delete.append(removed_item.get("image", ""))
            flash("Kayıt silindi.", "success")
        elif action in {"up", "down"} and index is not None and 0 <= index < len(items):
            target = index - 1 if action == "up" else index + 1
            if 0 <= target < len(items):
                items[index], items[target] = items[target], items[index]
        else:
            item = {}
            for key, _label, field_type in config["fields"]:
                if field_type == "image":
                    previous_value = items[index].get(key, "") if index is not None and 0 <= index < len(items) else ""
                    uploaded_file = request.files.get(key)
                    if uploaded_file and uploaded_file.filename:
                        try:
                            value = save_uploaded_image(uploaded_file)
                        except ValueError as error:
                            flash(str(error), "error")
                            return redirect(url_for("admin.collection", name=name, sayfa=return_page if name == "projects" else None))
                        files_to_delete.append(previous_value)
                    elif request.form.get(f"remove_{key}") == "1":
                        value = ""
                        files_to_delete.append(previous_value)
                    else:
                        value = previous_value
                else:
                    value = request.form.get(key, "").strip()
                if field_type == "number":
                    try:
                        value = max(0, min(100, int(value)))
                    except ValueError:
                        value = 0
                elif field_type == "tags":
                    value = [tag.strip() for tag in value.splitlines() if tag.strip()]
                item[key] = value
            if index is not None and 0 <= index < len(items):
                items[index] = item
                flash("Kayıt güncellendi.", "success")
            else:
                items.append(item)
                flash("Yeni kayıt eklendi.", "success")
        repository().save_site(site)
        for image_url in files_to_delete:
            delete_uploaded_image(image_url)
        return redirect(url_for("admin.collection", name=name, sayfa=return_page if name == "projects" else None))

    edit_item = items[edit_index] if edit_index is not None and 0 <= edit_index < len(items) else None
    collection_per_page = 10 if name == "projects" else max(1, len(items))
    collection_total_pages = max(1, (len(items) + collection_per_page - 1) // collection_per_page)
    collection_current_page = max(1, min(request.args.get("sayfa", 1, type=int), collection_total_pages))
    collection_start = (collection_current_page - 1) * collection_per_page
    displayed_items = list(enumerate(items))[collection_start:collection_start + collection_per_page]
    return render_template(
        "admin/collection.html",
        name=name,
        config=config,
        items=items,
        displayed_items=displayed_items,
        edit_index=edit_index,
        edit_item=edit_item,
        open_new=request.args.get("yeni") == "1",
        collection_current_page=collection_current_page,
        collection_total_pages=collection_total_pages,
    )


@bp.route("/blog/yeni", methods=["GET", "POST"])
@bp.route("/blog/<slug>/duzenle", methods=["GET", "POST"])
@admin_required
def blog_edit(slug=None):
    post = repository().get_post(slug, published_only=False) if slug else None
    if slug and not post:
        abort(404)
    if request.method == "POST":
        previous_images = set(post["images"] if post else [])
        previous_cover = post["cover"] if post else ""
        payload = {
            "title": request.form.get("title", "").strip(),
            "slug": request.form.get("slug", "").strip(),
            "date": request.form.get("date", date.today().isoformat()),
            "time": request.form.get("time", datetime.now().strftime("%H:%M")),
            "tags": [
                tag.strip() for tag in request.form.get("tags", "").splitlines()
                if tag.strip()
            ],
            "summary": request.form.get("summary", ""),
            "cover": previous_cover,
            "published": request.form.get("published") == "on",
            "body": request.form.get("body", "").strip(),
        }
        if not payload["title"] or not payload["body"]:
            flash("Başlık ve içerik zorunludur.", "error")
        else:
            cover_file = request.files.get("cover")
            if cover_file and cover_file.filename:
                try:
                    payload["cover"] = save_uploaded_image(cover_file)
                except ValueError as error:
                    flash(str(error), "error")
                    return redirect(url_for("admin.blog_edit", slug=slug) if slug else url_for("admin.blog_edit"))
            elif request.form.get("remove_cover") == "1":
                payload["cover"] = ""
            saved_slug = repository().save_post(slug, payload)
            current_images = set(LOCAL_UPLOAD_PATTERN.findall(payload["body"]))
            stale_images = previous_images - current_images
            if previous_cover and previous_cover != payload["cover"]:
                stale_images.add(previous_cover)
            for image_url in stale_images:
                delete_uploaded_image(image_url)
            flash("Blog yazısı kaydedildi.", "success")
            return redirect(url_for("admin.blog_edit", slug=saved_slug))
    return render_template(
        "admin/blog_edit.html",
        post=post,
        post_images=post["images"] if post else [],
        today=date.today().isoformat(),
        now_time=datetime.now().strftime("%H:%M"),
    )


@bp.get("/blog")
@admin_required
def blog_list():
    all_posts = repository().list_posts(published_only=False)
    per_page = 10
    total_pages = max(1, (len(all_posts) + per_page - 1) // per_page)
    current_page = max(1, min(request.args.get("sayfa", 1, type=int), total_pages))
    start = (current_page - 1) * per_page
    return render_template(
        "admin/blog_list.html",
        posts=all_posts[start:start + per_page],
        total_posts=len(all_posts),
        current_page=current_page,
        total_pages=total_pages,
    )


@bp.post("/blog/<slug>/sil")
@admin_required
def blog_delete(slug):
    post = repository().get_post(slug, published_only=False)
    repository().delete_post(slug)
    if post:
        for image_url in {*post["images"], post["cover"]}:
            delete_uploaded_image(image_url)
    flash("Blog yazısı silindi.", "success")
    return redirect(url_for("admin.blog_list"))


@bp.post("/blog/gorsel-yukle")
@admin_required
def blog_image_upload():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="Yüklenecek bir görsel seçin."), 400
    try:
        image_url = save_uploaded_image(file)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(url=image_url)


@bp.post("/blog/onizleme")
@admin_required
def blog_preview():
    body = request.form.get("body", "")
    return repository().render_markdown(body)


@bp.post("/blog/gorsel-sil")
@admin_required
def blog_image_delete():
    image_url = request.form.get("url", "")
    slug = request.form.get("slug", "")
    if not LOCAL_UPLOAD_PATTERN.fullmatch(image_url):
        return jsonify(error="Geçersiz görsel adresi."), 400
    if slug:
        repository().remove_post_image(slug, image_url)
    if not delete_uploaded_image(image_url):
        return jsonify(error="Bu görsel başka bir içerikte kullanıldığı için silinemedi."), 409
    return jsonify(deleted=True)


@bp.get("/mesajlar")
@admin_required
def messages():
    return render_template("admin/messages.html", messages=repository().get_messages())


@bp.post("/mesajlar/<message_id>/okundu")
@admin_required
def message_read(message_id):
    repository().mark_message_read(message_id)
    return redirect(url_for("admin.messages"))


@bp.post("/mesajlar/<message_id>/sil")
@admin_required
def message_delete(message_id):
    repository().delete_message(message_id)
    flash("Mesaj silindi.", "success")
    return redirect(url_for("admin.messages"))
