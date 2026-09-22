import json
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app import create_app


PROJECT_ROOT = Path(__file__).parent.parent


def make_test_config(storage_root):
    return {
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "ADMIN_USERNAME": "test-admin",
        "ADMIN_PASSWORD": "test-password",
        "SESSION_COOKIE_SECURE": False,
        "STORAGE_ROOT": storage_root,
        "SEED_ROOT": PROJECT_ROOT / "seed",
    }


@pytest.fixture()
def app(tmp_path):
    return create_app(make_test_config(tmp_path / "storage"))


@pytest.fixture()
def client(app):
    return app.test_client()


def test_runtime_credentials_are_required(monkeypatch):
    for name in ("SECRET_KEY", "ADMIN_USERNAME", "ADMIN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD"):
        create_app()


def test_production_credentials_enforce_minimum_strength(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "short")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "short-password")
    with pytest.raises(RuntimeError, match="SECRET_KEY en az 32"):
        create_app({
            "STORAGE_ROOT": tmp_path / "storage",
            "SEED_ROOT": PROJECT_ROOT / "seed",
        })


def test_healthcheck_and_seeded_media_are_ready(client, app):
    response = client.get("/healthz")
    assert response.status_code == 204
    assert "Set-Cookie" not in response.headers

    with Image.open(app.config["BRAND_ASSET_FOLDER"] / "favicon.png") as image:
        image.verify()

    media = client.get("/media/branding/favicon.png")
    assert media.status_code == 200
    assert "Set-Cookie" not in media.headers
    media.close()


def test_storage_is_seeded_once_and_persists(tmp_path):
    storage_root = tmp_path / "storage"
    config = make_test_config(storage_root)
    first_app = create_app(config)
    repository = first_app.extensions["content"]
    site = repository.get_site()
    site["profile"]["name"] = "Kalıcı Kullanıcı"
    repository.save_site(site)

    seeded_post = storage_root / "blog" / "mi-router-4c-openwrt-kurulumu.md"
    seeded_post.unlink()

    second_app = create_app(config)
    assert second_app.extensions["content"].get_site()["profile"]["name"] == "Kalıcı Kullanıcı"
    assert not seeded_post.exists()


def test_markerless_storage_does_not_overwrite_existing_files(tmp_path):
    storage_root = tmp_path / "storage"
    config = make_test_config(storage_root)
    create_app(config)
    (storage_root / ".initialized").unlink()
    post_path = storage_root / "blog" / "mi-router-4c-openwrt-kurulumu.md"
    post_path.write_text("özel içerik\n", encoding="utf-8")
    profile_path = storage_root / "branding" / "profile.png"
    profile_path.write_bytes(b"custom-profile")

    create_app(config)
    assert post_path.read_text(encoding="utf-8") == "özel içerik\n"
    assert profile_path.read_bytes() == b"custom-profile"


def test_corrupt_json_stops_startup(tmp_path):
    storage_root = tmp_path / "storage"
    config = make_test_config(storage_root)
    create_app(config)
    (storage_root / ".initialized").unlink()
    (storage_root / "state" / "site.json").write_text("{", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Geçersiz JSON dosyası"):
        create_app(config)

    assert not (storage_root / ".initialized").exists()


def test_healthcheck_rejects_invalid_site_schema(client, app):
    app.extensions["content"].save_site({})
    assert client.get("/healthz").status_code == 503


def test_session_cookie_has_production_security_flags(client, app):
    app.config["SESSION_COOKIE_SECURE"] = True
    response = client.get("/admin/giris", base_url="https://localhost")
    cookie = response.headers["Set-Cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert response.headers["Cache-Control"] == "no-store"


def csrf(client):
    with client.session_transaction() as session:
        return session["csrf_token"]


def login(client):
    client.get("/admin/giris")
    return client.post(
        "/admin/giris",
        data={"username": "test-admin", "password": "test-password", "csrf_token": csrf(client)},
        follow_redirects=True,
    )


def test_admin_login_rejects_wrong_username(client):
    client.get("/admin/giris")
    response = client.post(
        "/admin/giris",
        data={"username": "yanlis-admin", "password": "test-password", "csrf_token": csrf(client)},
        follow_redirects=True,
    )
    assert "Kullanıcı adı veya parola hatalı." in response.text
    assert "Genel bakış" not in response.text


def test_public_pages_render(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Mustafa Yücel" in response.text
    assert "Client" not in response.text
    assert "Pricing" not in response.text
    assert "Fun Facts" not in response.text
    assert "Yeni projelere açık" not in response.text
    assert "PDF indir" not in response.text
    assert 'href=""' not in response.text
    assert 'viewport-fit=cover' in response.text
    assert 'class="section-nav" aria-label="Ana menü"' in response.text
    assert 'class="portfolio-menu-toggle"' in response.text
    assert 'aria-controls="portfolio-menu"' in response.text
    assert 'id="portfolio-menu"' in response.text

    response = client.get("/blog")
    assert response.status_code == 200
    assert "Bloglarda ara" in response.text

    response = client.get("/blog/mi-router-4c-openwrt-kurulumu")
    assert response.status_code == 200
    assert "Başlamadan önce" in response.text


def test_blog_searches_body_and_filters_by_tag(client):
    response = client.get("/blog?q=katmanlara")
    assert response.status_code == 200
    assert "Ağ Sorunlarında Sistematik Yaklaşım" in response.text
    assert "Mi Router 4C" not in response.text

    response = client.get("/blog?etiket=OpenWrt")
    assert response.status_code == 200
    assert "Mi Router 4C" in response.text
    assert "Açık Kaynak Router" in response.text
    assert "Ağ Sorunlarında Sistematik" not in response.text

    live_response = client.get(
        "/blog?q=katmanlara",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert live_response.status_code == 200
    assert "Ağ Sorunlarında Sistematik Yaklaşım" in live_response.text
    assert "<!doctype html>" not in live_response.text


def test_public_blog_list_is_paginated_and_keeps_search(client, app):
    repository = app.extensions["content"]
    for number in range(1, 13):
        repository.save_post(None, {
            "title": f"Genel Sayfalama {number}",
            "slug": f"genel-sayfalama-{number}",
            "date": "2098-02-01",
            "time": f"{number:02d}:00",
            "tags": ["GenelSayfalama"],
            "summary": "Genel blog sayfalama testi",
            "cover": "",
            "published": True,
            "body": "Genel sayfalama içeriği.",
        })

    first_page = client.get("/blog?q=Genel+Sayfalama")
    assert first_page.status_code == 200
    assert first_page.text.count('class="post-card post-card--large"') == 10
    assert ">Genel Sayfalama 1</h2>" not in first_page.text
    assert "q=Genel+Sayfalama" in first_page.text
    assert "sayfa=2" in first_page.text

    second_page = client.get("/blog?q=Genel+Sayfalama&sayfa=2")
    assert second_page.status_code == 200
    assert ">Genel Sayfalama 1</h2>" in second_page.text
    assert 'aria-current="page">2</a>' in second_page.text


def test_home_projects_are_filtered_and_paginated_by_ten(client, app):
    repository = app.extensions["content"]
    site = repository.get_site()
    for number in range(1, 13):
        site["projects"].append({
            "title": f"Proje Sayfalama {number}",
            "description": "Proje sayfalama testi",
            "url": "",
            "image": "",
            "tags": ["ProjeSayfalama"],
        })
    repository.save_site(site)

    first_page = client.get("/?proje_etiket=ProjeSayfalama")
    assert first_page.status_code == 200
    assert first_page.text.count('class="project-card"') == 10
    assert "Proje Sayfalama 10" in first_page.text
    assert "Proje Sayfalama 11" not in first_page.text
    assert "proje_sayfa=2" in first_page.text

    second_page = client.get("/?proje_etiket=ProjeSayfalama&proje_sayfa=2")
    assert second_page.status_code == 200
    assert second_page.text.count('class="project-card"') == 2
    assert "Proje Sayfalama 11" in second_page.text
    assert "Proje Sayfalama 12" in second_page.text
    assert 'aria-current="page">2</a>' in second_page.text


def test_home_shows_six_latest_posts_and_marks_week_old_posts_as_new(client, app):
    repository = app.extensions["content"]
    for number in range(1, 8):
        repository.save_post(None, {
            "title": f"Yeni Ana Sayfa Yazısı {number}",
            "slug": f"yeni-ana-sayfa-yazisi-{number}",
            "date": date.today().isoformat(),
            "time": f"12:{number:02d}",
            "tags": ["Yeni"],
            "summary": "Ana sayfa yazı sınırı testi",
            "cover": "",
            "published": True,
            "body": "Test içeriği",
        })

    response = client.get("/")
    assert response.status_code == 200
    assert response.text.count('class="post-card"') == 6
    assert response.text.count('class="post-card__new"') == 6
    assert "Yeni Ana Sayfa Yazısı 7" in response.text
    assert "Yeni Ana Sayfa Yazısı 1" not in response.text


def test_contact_message_is_stored(client, app):
    client.get("/")
    response = client.post(
        "/iletisim",
        data={
            "csrf_token": csrf(client),
            "name": "Test Kullanıcı",
            "email": "test@example.com",
            "subject": "Proje",
            "message": "Birlikte çalışmak istiyorum.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Mesajınız kaydedildi" in response.text
    messages = app.extensions["content"].get_messages()
    assert messages[0]["email"] == "test@example.com"


def test_sidebar_shows_unread_message_badge(client, app):
    repository = app.extensions["content"]
    for message in repository.get_messages():
        repository.mark_message_read(message["id"])
    repository.add_message({
        "name": "Test Kullanıcı",
        "email": "test@example.com",
        "subject": "Bildirim",
        "message": "Okunmamış mesaj",
    })
    login(client)
    response = client.get("/admin/")
    assert response.status_code == 200
    assert 'class="message-badge"' in response.text
    assert 'aria-label="1 okunmamış mesaj"' in response.text


def test_admin_requires_authentication_and_can_login(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/giris" in response.headers["Location"]

    response = login(client)
    assert response.status_code == 200
    assert "Genel bakış" in response.text
    assert 'class="admin-menu-toggle"' in response.text
    assert 'aria-controls="admin-sidebar"' in response.text
    assert 'id="admin-sidebar"' in response.text


def test_admin_can_add_collection_item(client, app):
    login(client)
    page = client.get("/admin/liste/languages")
    assert 'data-collection-open' in page.text
    assert 'data-collection-dialog' in page.text
    assert 'data-editing="false"' in page.text
    assert 'data-open-on-load' not in page.text
    assert '/admin/liste/languages?yeni=1' in page.text
    response = client.post(
        "/admin/liste/languages",
        data={"csrf_token": csrf(client), "name": "Almanca", "level": "A1"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    site = json.loads((app.config["STORAGE_ROOT"] / "state" / "site.json").read_text())
    assert site["languages"][-1] == {"name": "Almanca", "level": "A1"}


def test_admin_collection_edit_opens_prefilled_dialog(client):
    login(client)
    response = client.get("/admin/liste/languages?duzenle=0")
    assert response.status_code == 200
    assert 'data-editing="true"' in response.text
    assert 'data-open-on-load' in response.text
    assert 'name="name" type="text" value="Türkçe"' in response.text
    assert 'id="collection-dialog-title">Kaydı düzenle</h2>' in response.text

    new_response = client.get("/admin/liste/languages?yeni=1")
    assert 'data-editing="false"' in new_response.text
    assert 'open data-open-on-load' in new_response.text
    assert 'id="collection-dialog-title">Yeni kayıt</h2>' in new_response.text


def test_admin_projects_are_paginated_by_ten_and_keep_global_indexes(client, app):
    login(client)
    repository = app.extensions["content"]
    site = repository.get_site()
    site["projects"] = [
        {
            "title": f"Yönetim Projesi {number}",
            "description": f"Açıklama {number}",
            "url": "",
            "image": "",
            "tags": ["Yönetim"],
        }
        for number in range(1, 13)
    ]
    repository.save_site(site)

    first_page = client.get("/admin/liste/projects")
    assert first_page.status_code == 200
    assert first_page.text.count('class="collection-index"') == 10
    assert "Yönetim Projesi 10" in first_page.text
    assert "Yönetim Projesi 11" not in first_page.text
    assert "sayfa=2" in first_page.text

    second_page = client.get("/admin/liste/projects?sayfa=2")
    assert second_page.status_code == 200
    assert second_page.text.count('class="collection-index"') == 2
    assert "Yönetim Projesi 11" in second_page.text
    assert "Yönetim Projesi 12" in second_page.text
    assert 'value="10"' in second_page.text
    assert 'aria-current="page">2</a>' in second_page.text

    edit_page = client.get("/admin/liste/projects?sayfa=2&duzenle=10")
    assert 'value="Yönetim Projesi 11"' in edit_page.text
    assert 'name="index" value="10"' in edit_page.text
    assert 'data-base-url="/admin/liste/projects?sayfa=2"' in edit_page.text


def test_admin_can_update_homepage_headline(client, app):
    login(client)
    site = app.extensions["content"].get_site()
    profile = site["profile"]
    profile.update({"hero_title": "Teknolojiyi anlar,", "hero_highlight": "sonuca ulaştırırım."})
    client.get("/admin/site-metinleri")
    response = client.post(
        "/admin/site-metinleri",
        data={
            "csrf_token": csrf(client),
            "eyebrow": profile["eyebrow"],
            "hero_title": profile["hero_title"],
            "hero_highlight": profile["hero_highlight"],
            "bio": profile["bio"],
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    homepage = client.get("/")
    assert "Teknolojiyi anlar," in homepage.text
    assert "sonuca ulaştırırım." in homepage.text


def test_profile_image_is_always_saved_as_single_png(client, app):
    login(client)
    profile = app.extensions["content"].get_site()["profile"]

    for color in ("red", "blue"):
        image_data = BytesIO()
        Image.new("RGB", (800, 800), color=color).save(image_data, format="JPEG")
        image_data.seek(0)
        client.get("/admin/profil")
        response = client.post(
            "/admin/profil",
            data={
                "csrf_token": csrf(client),
                **profile,
                "avatar": (image_data, "ayni-profil.jpg"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code == 200

    files = list(app.config["BRAND_ASSET_FOLDER"].glob("profile*"))
    assert [file.name for file in files] == ["profile.png"]
    assert app.extensions["content"].get_site()["profile"]["avatar"] == "/media/branding/profile.png"
    with Image.open(files[0]) as saved:
        assert saved.format == "PNG"
        assert saved.size == (600, 600)


def test_favicon_is_uploaded_and_used_in_admin_brand(client, app):
    login(client)
    profile = app.extensions["content"].get_site()["profile"]
    image_data = BytesIO()
    Image.new("RGB", (80, 120), color="green").save(image_data, format="WEBP")
    image_data.seek(0)
    client.get("/admin/profil")
    response = client.post(
        "/admin/profil",
        data={
            "csrf_token": csrf(client),
            **profile,
            "favicon": (image_data, "marka.webp"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    favicon = app.config["BRAND_ASSET_FOLDER"] / "favicon.png"
    assert favicon.exists()
    with Image.open(favicon) as saved:
        assert saved.format == "PNG"
        assert saved.size == (512, 512)
    dashboard = client.get("/admin/")
    assert 'class="admin-brand__icon"' in dashboard.text
    assert '/media/branding/favicon.png' in dashboard.text


def test_admin_can_change_site_color_theme(client, app):
    login(client)
    profile = app.extensions["content"].get_site()["profile"]
    client.get("/admin/profil")
    response = client.post(
        "/admin/profil",
        data={"csrf_token": csrf(client), **profile, "theme": "violet"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert app.extensions["content"].get_site()["branding"]["theme"] == "violet"
    assert 'data-theme="violet"' in client.get("/").text


def test_admin_can_create_markdown_post(client, app):
    login(client)
    client.get("/admin/blog/yeni")
    response = client.post(
        "/admin/blog/yeni",
        data={
            "csrf_token": csrf(client),
            "title": "Test Yazısı",
            "slug": "test-yazisi",
            "date": "2026-09-21",
            "time": "18:45",
            "tags": "Flask\nPython",
            "summary": "Kısa açıklama",
            "cover": "",
            "published": "on",
            "body": "## İçerik\n\nMarkdown gövdesi.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    path = app.config["STORAGE_ROOT"] / "blog" / "test-yazisi.md"
    assert path.exists()
    assert "Markdown gövdesi" in path.read_text()
    post = app.extensions["content"].get_post("test-yazisi")
    assert post["tags"] == ["Flask", "Python"]
    assert post["time"] == "18:45"


def test_blog_editor_can_upload_image_for_markdown(client, app):
    login(client)
    image_data = BytesIO()
    Image.new("RGB", (120, 80), color="purple").save(image_data, format="PNG")
    image_data.seek(0)
    editor = client.get("/admin/blog/yeni")
    assert 'data-editor-image-input' in editor.text
    response = client.post(
        "/admin/blog/gorsel-yukle",
        data={
            "csrf_token": csrf(client),
            "file": (image_data, "yazi-gorseli.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    image_url = response.get_json()["url"]
    assert image_url.startswith("/media/uploads/yazi-gorseli-")
    assert (app.config["UPLOAD_FOLDER"] / Path(image_url).name).exists()


def test_blog_editor_preview_renders_sanitized_markdown(client):
    login(client)
    client.get("/admin/blog/yeni")
    response = client.post(
        "/admin/blog/onizleme",
        data={
            "csrf_token": csrf(client),
            "body": "## Önizleme\n\n**Kalın metin**\n\n<script>alert(1)</script>",
        },
    )
    assert response.status_code == 200
    assert "<h2" in response.text
    assert "<strong>Kalın metin</strong>" in response.text
    assert "<script>" not in response.text


def test_blog_images_are_listed_deletable_and_removed_with_post(client, app):
    login(client)
    inline_data = BytesIO()
    Image.new("RGB", (80, 60), color="purple").save(inline_data, format="PNG")
    inline_data.seek(0)
    client.get("/admin/blog/yeni")
    upload_response = client.post(
        "/admin/blog/gorsel-yukle",
        data={"csrf_token": csrf(client), "file": (inline_data, "icerik.png")},
        content_type="multipart/form-data",
    )
    inline_url = upload_response.get_json()["url"]

    cover_data = BytesIO()
    Image.new("RGB", (160, 90), color="orange").save(cover_data, format="JPEG")
    cover_data.seek(0)
    response = client.post(
        "/admin/blog/yeni",
        data={
            "csrf_token": csrf(client),
            "title": "Görselli Yazı",
            "slug": "gorselli-yazi",
            "date": "2026-09-21",
            "time": "20:00",
            "tags": "Görsel",
            "summary": "Görsel testi",
            "cover": (cover_data, "kapak.jpg"),
            "published": "on",
            "body": f"![İçerik]({inline_url})\n\nYazı içeriği.",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    post = app.extensions["content"].get_post("gorselli-yazi")
    cover_path = app.config["UPLOAD_FOLDER"] / Path(post["cover"]).name
    inline_path = app.config["UPLOAD_FOLDER"] / Path(inline_url).name
    assert cover_path.exists() and inline_path.exists()
    assert inline_url in response.text
    assert 'data-copy-image=' in response.text

    delete_image = client.post(
        "/admin/blog/gorsel-sil",
        data={"csrf_token": csrf(client), "url": inline_url, "slug": "gorselli-yazi"},
    )
    assert delete_image.status_code == 200
    assert not inline_path.exists()
    assert inline_url not in app.extensions["content"].get_post("gorselli-yazi")["body"]

    saved_post = app.extensions["content"].get_post("gorselli-yazi")
    client.get("/admin/blog/gorselli-yazi/duzenle")
    remove_cover = client.post(
        "/admin/blog/gorselli-yazi/duzenle",
        data={
            "csrf_token": csrf(client),
            "title": saved_post["title"],
            "slug": saved_post["slug"],
            "date": saved_post["date"],
            "time": saved_post["time"],
            "tags": "\n".join(saved_post["tags"]),
            "summary": saved_post["summary"],
            "body": saved_post["body"],
            "published": "on",
            "remove_cover": "1",
        },
        follow_redirects=True,
    )
    assert remove_cover.status_code == 200
    assert not cover_path.exists()
    assert app.extensions["content"].get_post("gorselli-yazi")["cover"] == ""

    client.post(
        "/admin/blog/gorselli-yazi/sil",
        data={"csrf_token": csrf(client)},
        follow_redirects=True,
    )
    assert not cover_path.exists()


def test_project_image_is_replaced_and_deleted_with_project(client, app):
    login(client)
    site = app.extensions["content"].get_site()
    project_index = len(site["projects"])

    first_image = BytesIO()
    Image.new("RGB", (100, 70), color="red").save(first_image, format="PNG")
    first_image.seek(0)
    client.get("/admin/liste/projects")
    client.post(
        "/admin/liste/projects",
        data={
            "csrf_token": csrf(client),
            "title": "Görselli Proje",
            "description": "Proje açıklaması",
            "url": "",
            "tags": "Flask\nTest",
            "image": (first_image, "proje.png"),
        },
        content_type="multipart/form-data",
    )
    project = app.extensions["content"].get_site()["projects"][project_index]
    first_path = app.config["UPLOAD_FOLDER"] / Path(project["image"]).name
    assert first_path.exists()

    second_image = BytesIO()
    Image.new("RGB", (100, 70), color="blue").save(second_image, format="PNG")
    second_image.seek(0)
    client.get(f"/admin/liste/projects?duzenle={project_index}")
    client.post(
        "/admin/liste/projects",
        data={
            "csrf_token": csrf(client),
            "index": str(project_index),
            "title": "Görselli Proje",
            "description": "Yeni açıklama",
            "url": "",
            "tags": "Flask\nTest",
            "image": (second_image, "proje.png"),
        },
        content_type="multipart/form-data",
    )
    updated = app.extensions["content"].get_site()["projects"][project_index]
    second_path = app.config["UPLOAD_FOLDER"] / Path(updated["image"]).name
    assert second_path.exists()
    assert second_path != first_path
    assert not first_path.exists()

    client.get(f"/admin/liste/projects?duzenle={project_index}")
    client.post(
        "/admin/liste/projects",
        data={
            "csrf_token": csrf(client),
            "index": str(project_index),
            "title": "Görselli Proje",
            "description": "Yeni açıklama",
            "url": "",
            "tags": "Flask\nTest",
            "remove_image": "1",
        },
    )
    assert not second_path.exists()
    assert app.extensions["content"].get_site()["projects"][project_index]["image"] == ""

    client.post(
        "/admin/liste/projects",
        data={"csrf_token": csrf(client), "index": str(project_index), "action": "delete"},
    )
    assert not second_path.exists()


def test_dashboard_shows_three_latest_posts_and_blog_list_shows_all(client, app):
    repository = app.extensions["content"]
    for number, post_time in [(1, "10:15"), (2, "21:30")]:
        repository.save_post(None, {
            "title": f"Yeni Test Yazısı {number}",
            "slug": f"yeni-test-yazisi-{number}",
            "date": "2099-09-21",
            "time": post_time,
            "tags": ["Test"],
            "summary": "Test özeti",
            "cover": "",
            "published": True,
            "body": "Test içeriği.",
        })

    login(client)
    dashboard = client.get("/admin/")
    assert dashboard.status_code == 200
    assert "Yeni Test Yazısı 1" in dashboard.text
    assert "Yeni Test Yazısı 2" in dashboard.text
    assert dashboard.text.index("Yeni Test Yazısı 2") < dashboard.text.index("Yeni Test Yazısı 1")
    assert "Mi Router 4C" not in dashboard.text

    blog_list = client.get("/admin/blog")
    assert blog_list.status_code == 200
    assert "Yeni Test Yazısı 1" in blog_list.text
    assert "Yeni Test Yazısı 2" in blog_list.text
    older_posts = client.get("/admin/blog?sayfa=2")
    assert "Mi Router 4C" in older_posts.text


def test_admin_blog_list_is_paginated_by_ten(client, app):
    repository = app.extensions["content"]
    for number in range(1, 13):
        repository.save_post(None, {
            "title": f"Sayfalama Yazısı {number}",
            "slug": f"sayfalama-yazisi-{number}",
            "date": "2098-01-01",
            "time": f"{number:02d}:00",
            "tags": ["Sayfalama"],
            "summary": "Sayfalama testi",
            "cover": "",
            "published": True,
            "body": "Test içeriği.",
        })

    login(client)
    first_page = client.get("/admin/blog")
    assert first_page.status_code == 200
    assert first_page.text.count('class="list-icon"') == 10
    assert ">Sayfalama Yazısı 1</strong>" not in first_page.text
    assert 'aria-current="page">1</a>' in first_page.text

    second_page = client.get("/admin/blog?sayfa=2")
    assert second_page.status_code == 200
    assert ">Sayfalama Yazısı 1</strong>" in second_page.text
    assert 'aria-current="page">2</a>' in second_page.text


def test_same_named_uploads_get_unique_filenames(client, app):
    login(client)
    for color in ("red", "blue"):
        content = BytesIO()
        Image.new("RGB", (20, 20), color=color).save(content, format="JPEG")
        content.seek(0)
        client.get("/admin/blog/yeni")
        response = client.post(
            "/admin/blog/gorsel-yukle",
            data={
                "csrf_token": csrf(client),
                "file": (content, "proje.jpg"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 200

    files = list(app.config["UPLOAD_FOLDER"].glob("proje-*.jpg"))
    assert len(files) == 2
    assert files[0].name != files[1].name


def test_csrf_rejects_invalid_request(client):
    response = client.post("/iletisim", data={"name": "Test"})
    assert response.status_code == 400
