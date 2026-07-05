import os
from dotenv import load_dotenv

# Load .env if exists
load_dotenv()

class Config:
    """
    Central configuration for the Birthday Cafe Flask app.
    """

    # ---------- BASE PATH ----------
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # ---------- FLASK CORE ----------
    SECRET_KEY = os.environ.get("SECRET_KEY") or "replace-this-in-production"

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or f"sqlite:///{os.path.join(BASE_DIR, 'birthday_cafe.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG = FLASK_ENV != "production"
    TESTING = FLASK_ENV == "testing"

    # ---------- SESSION SECURITY ----------
    SESSION_COOKIE_SECURE = False if DEBUG else True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # ---------- EMAIL ----------
    MAIL_SERVER = os.environ.get("MAIL_SERVER") or "smtp.gmail.com"
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 587)
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL") or "admin@birthdaycafe.com"

    # ---------- WHATSAPP ----------
    WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
    WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
    ADMIN_WHATSAPP = os.environ.get("ADMIN_WHATSAPP")

    # ---------- UPLOADS / MEDIA ----------
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

    # Allow big uploads (for video)
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024   # 200 MB request limit

    # Allowed extensions
    ALLOWED_EXTENSIONS = {
        "png", "jpg", "jpeg", "gif", "webp",
        "mp4", "mov", "avi", "mkv", "webm", "ogg"
    }

    # Per-file soft limits
    MAX_PHOTO_SIZE = 12 * 1024 * 1024   # 12 MB
    MAX_VIDEO_SIZE = 80 * 1024 * 1024   # 80 MB

    # Maximum counts
    MAX_PHOTOS = 6
    MAX_VIDEOS = 3

    # Optional legacy combined limit
    MAX_FILES = MAX_PHOTOS + MAX_VIDEOS
