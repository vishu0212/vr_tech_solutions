import os
from datetime import timedelta
from pathlib import Path
from sqlalchemy.engine import URL

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# =========================================================
# PROJECT PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

APP_DIR = BASE_DIR / "app"
STATIC_DIR = APP_DIR / "static"

# Private storage for uploaded resumes
RESUME_UPLOAD_FOLDER = BASE_DIR / "instance" / "uploads" / "resumes"

# Public assets such as service and project images
PUBLIC_UPLOAD_FOLDER = STATIC_DIR / "uploads"


# =========================================================
# ENVIRONMENT HELPERS
# =========================================================

def get_bool(name: str, default: bool = False) -> bool:
    """Read a Boolean value from environment variables."""
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int(name: str, default: int) -> int:
    """Read an integer from environment variables."""
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer."
        ) from exc


# =========================================================
# FLASK CONFIGURATION
# =========================================================

class Config:
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-key")

    # Application environment
    DEBUG = get_bool("FLASK_DEBUG", False)
    TESTING = False

    # =====================================================
    # MYSQL DATABASE CONFIGURATION
    # =====================================================

    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = get_int("DB_PORT", 3306)
    DB_NAME = os.getenv("DB_NAME", "vr_tech_solutions")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # An optional complete MySQL connection string can override
    # the individual database settings.
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = URL.create(
            drivername="mysql+pymysql",
            username=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            query={"charset": "utf8mb4"},
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_timeout": 30,
    }

    # =====================================================
    # FILE UPLOAD CONFIGURATION
    # =====================================================

    RESUME_UPLOAD_FOLDER = str(RESUME_UPLOAD_FOLDER)
    PUBLIC_UPLOAD_FOLDER = str(PUBLIC_UPLOAD_FOLDER)

    MAX_CONTENT_LENGTH = get_int(
        "MAX_CONTENT_LENGTH",
        5 * 1024 * 1024,  # 5 MB per request
    )

    ALLOWED_RESUME_EXTENSIONS = {"pdf", "doc", "docx"}

    # =====================================================
    # SESSION CONFIGURATION
    # =====================================================

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Set COOKIE_SECURE=true when your production website
    # is served over HTTPS.
    SESSION_COOKIE_SECURE = get_bool("COOKIE_SECURE", False)
    REMEMBER_COOKIE_SECURE = get_bool("COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # =====================================================
    # CSRF PROTECTION
    # =====================================================

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # =====================================================
    # GENERAL APPLICATION SETTINGS
    # =====================================================

    ITEMS_PER_PAGE = get_int("ITEMS_PER_PAGE", 12)

    # Set this to your actual public website URL in production.
    SITE_NAME = os.getenv("SITE_NAME", "VR Tech Solutions")
    SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:5000")