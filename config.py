"""
Application configuration.

All secrets and environment-specific values are read from environment
variables (loaded from a local .env file via python-dotenv in app.py).
Nothing sensitive is hard-coded here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # --- Core Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-me")
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # --- Database ---
    # SQLite by default. To move to PostgreSQL later, just change DATABASE_URL
    # in .env to something like:
    #   postgresql://user:password@host:5432/dbname
    # No application code needs to change — SQLAlchemy handles the dialect.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'company.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Company / site info (used in emails & templates) ---
    COMPANY_NAME = os.environ.get("COMPANY_NAME", "Dee Coder Technologies")
    SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:5000")

    # --- Email (Gmail SMTP) ---
    GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
    NOTIFICATION_EMAIL = os.environ.get("NOTIFICATION_EMAIL") or GMAIL_ADDRESS
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "0") == "1"

    # --- Uploads ---
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "5")) * 1024 * 1024

    # --- Sessions / cookies ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set to True automatically once the app is served over HTTPS in production.
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    # --- WTForms CSRF ---
    WTF_CSRF_TIME_LIMIT = None
