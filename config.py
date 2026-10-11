"""
Application configuration.

All secrets and environment-specific values are read from environment
variables (loaded from a local .env file via python-dotenv in app.py).
Nothing sensitive is hard-coded here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def resolve_project_path(path: str | Path) -> Path:
    resolved_path = Path(path)
    if not resolved_path.is_absolute():
        resolved_path = BASE_DIR / resolved_path
    return resolved_path.resolve()


def normalize_database_uri(database_uri: str, *, require_absolute_sqlite: bool = False) -> str:
    """Resolve relative SQLite files against the project, not the process CWD."""
    url = make_url(database_uri)
    if url.get_backend_name() != "sqlite" or not url.database:
        return database_uri

    database = url.database
    if database == ":memory:" or database.startswith("file:"):
        return database_uri

    database_path = Path(database)
    if not database_path.is_absolute():
        if require_absolute_sqlite:
            raise ValueError(
                "Production SQLite DATABASE_URL must use an absolute file path."
            )

    return url.set(database=str(resolve_project_path(database_path))).render_as_string(
        hide_password=False
    )


class Config:
    # --- Core Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-me")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    # --- Database ---
    # SQLite by default. To move to PostgreSQL later, just change DATABASE_URL
    # in .env to something like:
    #   postgresql://user:password@host:5432/dbname
    # No application code needs to change — SQLAlchemy handles the dialect.
    SQLALCHEMY_DATABASE_URI = normalize_database_uri(
        os.environ.get(
            "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'company.db'}"
        ),
        require_absolute_sqlite=os.environ.get("FLASK_ENV", "development") == "production",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Company / site info (used in emails & templates) ---
    COMPANY_NAME = os.environ.get("COMPANY_NAME", "Dee Coder Technologies")
    SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:5000")

    # --- Email (Gmail SMTP) ---
    GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
    NOTIFICATION_EMAIL = os.environ.get("NOTIFICATION_EMAIL") or "deecodertechnologiesworldwide@gmail.com"
    CONTACT_NOTIFICATION_EMAIL = (
        os.environ.get("CONTACT_NOTIFICATION_EMAIL") or "deecodertechnologiesworldwide@gmail.com"
    )
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "0") == "1"
    SMTP_TIMEOUT = int(os.environ.get("SMTP_TIMEOUT", "20"))

    # --- Uploads ---
    UPLOAD_FOLDER = str(
        resolve_project_path(os.environ.get("UPLOAD_FOLDER", BASE_DIR / "uploads"))
    )
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "5"))
    MAX_VIDEO_UPLOAD_MB = int(os.environ.get("MAX_VIDEO_UPLOAD_MB", "500"))
    VIDEO_UPLOAD_CHUNK_MB = int(os.environ.get("VIDEO_UPLOAD_CHUNK_MB", "8"))
    MAX_CONTENT_LENGTH = (max(MAX_UPLOAD_MB, MAX_VIDEO_UPLOAD_MB) + 1) * 1024 * 1024

    # --- Sessions / cookies ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set to True automatically once the app is served over HTTPS in production.
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    # --- WTForms CSRF ---
    WTF_CSRF_TIME_LIMIT = None
