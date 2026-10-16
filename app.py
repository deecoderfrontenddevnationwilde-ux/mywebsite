import os
import tempfile
from datetime import timedelta
from urllib.parse import urlsplit

import click
from dotenv import load_dotenv
from flask import Flask, Request as FlaskRequest, current_app, jsonify, make_response, render_template, request, url_for
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

load_dotenv()  # reads .env into environment variables before Config is built

from config import Config, normalize_database_uri
from extensions import db, migrate, csrf


def seo_site_url(site_url):
    """Return the configured HTTPS origin only when it is suitable for indexing."""
    if not site_url:
        return None

    try:
        parsed = urlsplit(site_url.strip())
    except ValueError:
        return None
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or "." not in hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or hostname in {"localhost", "example.com", "example.net", "example.org"}
        or hostname.endswith(".example")
        or "your_" in hostname
        or "your-" in hostname
    ):
        return None

    return f"https://{parsed.netloc}"


class UploadAwareRequest(FlaskRequest):
    @property
    def max_content_length(self):
        is_video_upload = self.endpoint and self.endpoint.startswith("admin.videos_")
        is_video_chunk = self.endpoint == "admin.videos_upload_chunk"
        is_video_completion = self.endpoint == "admin.videos_upload_complete"
        limit_mb = (
            current_app.config["VIDEO_UPLOAD_CHUNK_MB"]
            if is_video_chunk
            else current_app.config["MAX_UPLOAD_MB"]
            if is_video_completion
            else current_app.config["MAX_VIDEO_UPLOAD_MB"]
            if is_video_upload
            else current_app.config["MAX_UPLOAD_MB"]
        )
        multipart_overhead = 1024 * 1024 if self.mimetype == "multipart/form-data" else 0
        return limit_mb * 1024 * 1024 + multipart_overhead


def create_app(config_class=Config):
    app = Flask(__name__)
    app.request_class = UploadAwareRequest
    app.config.from_object(config_class)
    app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_uri(
        app.config["SQLALCHEMY_DATABASE_URI"],
        require_absolute_sqlite=app.config.get("FLASK_ENV") == "production",
    )
    app.permanent_session_lifetime = timedelta(hours=8)

    database_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if database_uri.startswith("sqlite:"):
        from sqlalchemy.engine import make_url

        database_path = make_url(database_uri).database
        if database_path and database_path != ":memory:" and not database_path.startswith("file:"):
            os.makedirs(os.path.dirname(database_path), exist_ok=True)

    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    for upload_dir in ("news", "products", "projects", "videos", "video-thumbnails"):
        os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], upload_dir), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from models import (  # noqa: F401
        AdminUser,
        ContactMessage,
        ContactMessageActivity,
        FeaturedProject,
        News,
        Product,
        ProductVideo,
        ServiceOffer,
        Subscriber,
    )

    from routes.public import public_bp
    from routes.admin import admin_bp
    from routes.api import api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")
    csrf.exempt(api_bp)  # JSON API uses fetch(); CSRF is handled via same-origin + JSON content-type checks

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        limit_mb = (
            app.config["VIDEO_UPLOAD_CHUNK_MB"]
            if request.endpoint == "admin.videos_upload_chunk"
            else app.config["MAX_UPLOAD_MB"]
            if request.endpoint == "admin.videos_upload_complete"
            else app.config["MAX_VIDEO_UPLOAD_MB"]
            if request.endpoint and request.endpoint.startswith("admin.videos_")
            else app.config["MAX_UPLOAD_MB"]
        )
        message = f"Upload too large. The limit for this request is {limit_mb} MB."
        if request.endpoint in {"admin.videos_upload_chunk", "admin.videos_upload_complete"}:
            return jsonify(success=False, message=message), 413
        return render_template("413.html", message=message, limit_mb=limit_mb), 413

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        return render_template("500.html"), 500

    @app.route("/robots.txt")
    def robots_txt():
        site_url = seo_site_url(app.config.get("SITE_URL"))
        lines = [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /api/",
            "Disallow: /unsubscribe/",
            "Disallow: /uploads/",
        ]
        if site_url:
            lines.append(f"Sitemap: {site_url}/sitemap.xml")
        response = make_response("\n".join(lines) + "\n")
        response.mimetype = "text/plain"
        return response

    @app.route("/sitemap.xml")
    def sitemap_xml():
        site_url = seo_site_url(app.config.get("SITE_URL"))
        if not site_url:
            return "Configure SITE_URL with the official HTTPS domain to publish a sitemap.\n", 503

        pages = [
            ("/", None),
            ("/about", None),
            ("/contact", None),
            ("/news", None),
            ("/projects", None),
            ("/products", None),
            ("/videos", None),
            ("/terms", None),
            ("/privacy", None),
        ]
        from models import News, Product

        for article in News.query.filter_by(published=True).order_by(News.slug).all():
            modified = article.updated_at or article.published_at or article.created_at
            path = url_for("public.news_detail", slug=article.slug)
            pages.append((path, modified.date().isoformat() if modified else None))
        for product in Product.query.filter_by(published=True).order_by(Product.slug).all():
            modified = product.updated_at or product.published_at or product.created_at
            path = url_for("public.product_detail", slug=product.slug)
            pages.append((path, modified.date().isoformat() if modified else None))

        sitemap_entries = [
            {"loc": f"{site_url}{path}", "lastmod": lastmod}
            for path, lastmod in pages
        ]
        return render_template("sitemap.xml", sitemap_entries=sitemap_entries), 200, {
            "Content-Type": "application/xml; charset=utf-8"
        }

    @app.context_processor
    def inject_globals():
        site_url = seo_site_url(app.config.get("SITE_URL"))
        canonical_url = f"{site_url}{request.path}" if site_url else None
        organization_id = f"{site_url}/#organization" if site_url else None
        homepage_url = f"{site_url}/" if site_url else None
        organization_schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "@id": organization_id,
            "name": "DeeCoder Technologies",
            "alternateName": "DeeCoder",
            "url": homepage_url,
            "founder": {
                "@type": "Person",
                "name": "Donatus Chukwu Paul",
            },
            "logo": f"{site_url}{url_for('static', filename='images/DeeCoder_Technologies_icon.png')}",
            "description": (
                "DeeCoder Technologies builds websites, web applications, "
                "e-commerce platforms, and educational software for businesses, "
                "schools, and individuals."
            ),
            "sameAs": [
                "https://github.com/deecoderfrontenddevnationwilde-ux",
                "https://www.linkedin.com/in/dee-coder-front-end-dev-dee-coder-814a2b416",
                "https://www.tiktok.com/@deecoderfrontenddev",
            ],
            "contactPoint": {
                "@type": "ContactPoint",
                "contactType": "customer support",
                "email": "deecodertechnologiesworldwide@gmail.com",
                "telephone": "+2348075346224",
            },
        } if site_url else None
        website_schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "@id": f"{site_url}/#website",
            "name": "DeeCoder Technologies",
            "alternateName": "DeeCoder",
            "url": homepage_url,
            "publisher": {"@id": organization_id},
        } if site_url else None
        return {
            "company_name": app.config.get("COMPANY_NAME"),
            "seo_site_url": site_url,
            "canonical_url": canonical_url,
            "organization_schema": organization_schema,
            "website_schema": website_schema,
        }

    return app


app = create_app()


def database_schema_problems(engine, metadata):
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    expected_tables = set(metadata.tables)
    problems = [
        f"missing table {table_name}"
        for table_name in sorted(expected_tables - actual_tables)
    ]
    for table_name in sorted(expected_tables & actual_tables):
        expected_columns = {column.name for column in metadata.tables[table_name].columns}
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing_columns = sorted(expected_columns - actual_columns)
        if missing_columns:
            problems.append(f"{table_name} missing columns {', '.join(missing_columns)}")
    return problems


@app.cli.command("verify-deployment")
def verify_deployment_command():
    """Check that the selected database schema and persistent paths are ready."""
    schema_errors = database_schema_problems(db.engine, db.metadata)
    for error in schema_errors:
        click.echo(f"Schema check failed: {error}", err=True)

    engine_url = db.engine.url
    if engine_url.get_backend_name() == "sqlite":
        click.echo(f"SQLite database: {engine_url.database}")
    else:
        click.echo(f"Database backend: {engine_url.get_backend_name()}")

    storage_paths = {
        "instance": app.instance_path,
        "uploads": app.config["UPLOAD_FOLDER"],
        "news uploads": os.path.join(app.config["UPLOAD_FOLDER"], "news"),
        "product uploads": os.path.join(app.config["UPLOAD_FOLDER"], "products"),
        "project uploads": os.path.join(app.config["UPLOAD_FOLDER"], "projects"),
        "video uploads": os.path.join(app.config["UPLOAD_FOLDER"], "videos"),
        "video thumbnails": os.path.join(app.config["UPLOAD_FOLDER"], "video-thumbnails"),
    }
    storage_errors = []
    for label, path in storage_paths.items():
        try:
            os.makedirs(path, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix=".deployment-check-", dir=path, delete=True):
                pass
        except OSError as error:
            storage_errors.append(f"{label} is not writable ({type(error).__name__})")
    for error in storage_errors:
        click.echo(f"Storage check failed: {error}", err=True)

    if schema_errors or storage_errors:
        raise click.ClickException("Deployment checks failed; apply migrations or fix the listed paths.")
    click.echo(f"Database schema is present ({len(db.metadata.tables)} application tables).")
    click.echo("Persistent upload and instance directories are writable.")


@app.cli.command("check-smtp")
def check_smtp_command():
    """Check SMTP connectivity and authentication without sending an email."""
    from services.email_service import check_smtp_connection

    if not check_smtp_connection():
        raise click.ClickException(
            "SMTP connection/authentication failed. Check provider settings and server logs."
        )
    click.echo("SMTP connection and authentication succeeded; no email was sent.")


@app.cli.command("create-admin")
def create_admin_command():
    """Create an admin user interactively: flask create-admin"""
    import getpass
    from models import AdminUser

    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip()
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match. Aborted.")
        return
    if len(password) < 8:
        print("Password must be at least 8 characters. Aborted.")
        return
    if AdminUser.query.filter_by(username=username).first():
        print(f"An admin with username '{username}' already exists. Aborted.")
        return
    if AdminUser.query.filter_by(email=email).first():
        print("An admin with that email address already exists. Aborted.")
        return

    admin_user = AdminUser(username=username, email=email)
    admin_user.set_password(password)
    db.session.add(admin_user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        print("An admin with that username or email already exists. Aborted.")
        return
    print(f"Admin user '{username}' created successfully.")


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
