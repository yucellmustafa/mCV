import re
from datetime import date

from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for

from . import bp


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def repository():
    return current_app.extensions["content"]


@bp.get("/media/uploads/<path:filename>")
def uploaded_media(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, max_age=0)


@bp.get("/media/branding/<path:filename>")
def branding_media(filename):
    return send_from_directory(current_app.config["BRAND_ASSET_FOLDER"], filename, max_age=0)


@bp.get("/")
def home():
    posts = []
    for post in repository().list_posts()[:6]:
        post = dict(post)
        try:
            age_in_days = (date.today() - date.fromisoformat(post["date"])).days
            post["is_new"] = 0 <= age_in_days < 7
        except (TypeError, ValueError):
            post["is_new"] = False
        posts.append(post)
    site = repository().get_site()
    all_projects = site.get("projects", [])
    project_tags = sorted({tag for project in all_projects for tag in project.get("tags", [])})
    selected_project_tag = request.args.get("proje_etiket", "").strip()
    filtered_projects = [
        project for project in all_projects
        if not selected_project_tag or selected_project_tag in project.get("tags", [])
    ]
    projects_per_page = 10
    project_total_pages = max(1, (len(filtered_projects) + projects_per_page - 1) // projects_per_page)
    project_current_page = max(
        1,
        min(request.args.get("proje_sayfa", 1, type=int), project_total_pages),
    )
    project_start = (project_current_page - 1) * projects_per_page
    return render_template(
        "home.html",
        site=site,
        posts=posts,
        projects=filtered_projects[project_start:project_start + projects_per_page],
        project_tags=project_tags,
        selected_project_tag=selected_project_tag,
        project_current_page=project_current_page,
        project_total_pages=project_total_pages,
    )


@bp.get("/blog")
def blog():
    query = request.args.get("q", "").strip()
    selected_tag = request.args.get("etiket", "").strip()
    all_posts = repository().list_posts()
    tags = sorted({tag for post in all_posts for tag in post["tags"]})
    filtered_posts = repository().search_posts(query=query, tag=selected_tag)
    per_page = 10
    total_pages = max(1, (len(filtered_posts) + per_page - 1) // per_page)
    current_page = max(1, min(request.args.get("sayfa", 1, type=int), total_pages))
    start = (current_page - 1) * per_page
    context = {
        "posts": filtered_posts[start:start + per_page],
        "total_posts": len(filtered_posts),
        "current_page": current_page,
        "total_pages": total_pages,
        "query": query,
        "selected_tag": selected_tag,
        "tags": tags,
    }
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template("blog/_results.html", **context)
    return render_template(
        "blog/list.html", site=repository().get_site(), **context,
    )


@bp.get("/blog/<slug>")
def post(slug):
    article = repository().get_post(slug)
    if not article:
        abort(404)
    return render_template("blog/detail.html", site=repository().get_site(), post=article)


@bp.post("/iletisim")
def contact():
    data = {
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "subject": request.form.get("subject", "").strip(),
        "message": request.form.get("message", "").strip(),
    }
    if not data["name"] or not EMAIL_PATTERN.fullmatch(data["email"]) or not data["message"]:
        flash("Lütfen ad, geçerli e-posta ve mesaj alanlarını doldurun.", "error")
    else:
        repository().add_message(data)
        flash("Mesajınız kaydedildi. En kısa sürede dönüş yapacağım.", "success")
    return redirect(url_for("main.home", _anchor="contact"))
