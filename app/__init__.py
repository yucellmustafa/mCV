import os
import secrets
from pathlib import Path

from flask import Flask, abort, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

from .content import ContentRepository, initialize_storage


def create_app(test_config=None):
    app = Flask(__name__)
    root = Path(app.root_path).parent
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD"),
        DEBUG=False,
        SESSION_COOKIE_NAME="mcv_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=True,
        STORAGE_ROOT=root / "storage",
        SEED_ROOT=root / "seed",
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        UPLOAD_EXTENSIONS={"png", "jpg", "jpeg", "webp", "gif"},
    )
    if test_config is not None:
        app.config.update(test_config)

    required = ("SECRET_KEY", "ADMIN_USERNAME", "ADMIN_PASSWORD")
    missing = [name for name in required if not str(app.config.get(name) or "").strip()]
    if missing:
        raise RuntimeError(f"Zorunlu yapılandırma eksik: {', '.join(missing)}")
    if not app.config["TESTING"]:
        if len(app.config["SECRET_KEY"]) < 32:
            raise RuntimeError("SECRET_KEY en az 32 karakter olmalıdır.")
        if app.config["ADMIN_USERNAME"] != app.config["ADMIN_USERNAME"].strip():
            raise RuntimeError("ADMIN_USERNAME başında veya sonunda boşluk içeremez.")
        if len(app.config["ADMIN_PASSWORD"]) < 20:
            raise RuntimeError("ADMIN_PASSWORD en az 20 karakter olmalıdır.")

    storage_root = Path(app.config["STORAGE_ROOT"])
    app.config.update(
        UPLOAD_FOLDER=storage_root / "uploads",
        BRAND_ASSET_FOLDER=storage_root / "branding",
    )
    initialize_storage(storage_root, app.config["SEED_ROOT"])

    # Only the Coolify reverse proxy can reach the production container port.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
    app.extensions["content"] = ContentRepository(storage_root)

    from .admin import bp as admin_bp
    from .main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    @app.get("/healthz")
    def healthz():
        if not app.extensions["content"].is_ready():
            return {"status": "unavailable"}, 503
        return "", 204

    @app.before_request
    def csrf_protect():
        if request.endpoint in {"healthz", "static", "main.uploaded_media", "main.branding_media"}:
            return None
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(24)
        if request.method == "POST":
            token = request.form.get("csrf_token", "")
            if not secrets.compare_digest(token, session["csrf_token"]):
                abort(400, "Geçersiz form anahtarı. Sayfayı yenileyip tekrar deneyin.")

    @app.context_processor
    def inject_globals():
        messages = app.extensions["content"].get_messages()
        return {
            "csrf_token": session.get("csrf_token", ""),
            "site_content": app.extensions["content"].get_site(),
            "unread_message_count": sum(not message.get("read", False) for message in messages),
        }

    return app
