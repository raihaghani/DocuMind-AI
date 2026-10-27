"""
Django settings for DocuMind AI.

Configuration is driven by environment variables (loaded from a local `.env`
file in development via python-dotenv). See `.env.example` for the full list.
"""
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# ---------------------------------------------------------------------------
# Paths & environment loading
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from a .env file if present (development convenience).
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # python-dotenv is optional at runtime
    pass

import os  # noqa: E402  (import after load_dotenv so values are available)


def env(key, default=None):
    """Return an environment variable, falling back to `default`."""
    value = os.environ.get(key)
    return value if value not in (None, "") else default


def env_bool(key, default=False):
    value = env(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key, default):
    value = env(key)
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def env_float(key, default):
    value = env(key)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Core security settings
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [
    h.strip()
    for h in env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

if not DEBUG and SECRET_KEY.startswith("django-insecure"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a secure value when DEBUG is False."
    )

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "accounts",
    "workspace",
    "documents",
    "ai_assistant",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Default: SQLite (development). Set DATABASE_URL for PostgreSQL in production.
DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    # Minimal postgres://user:pass@host:port/name parser (avoids extra deps).
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_URL)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured(
            "Only postgres:// DATABASE_URLs are supported out of the box."
        )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation."
        "CommonPasswordValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation."
        "NumericPasswordValidator"
    },
]

# ---------------------------------------------------------------------------
# Internationalization / timezone
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
# Timezone used for display and for daily quota resets (documented in README).
TIME_ZONE = env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded documents are stored OUTSIDE the public static/media tree and are
# only ever served through authenticated, ownership-checked Django views.
PRIVATE_STORAGE_ROOT = BASE_DIR / "private_uploads"

# ---------------------------------------------------------------------------
# Authentication redirects
# ---------------------------------------------------------------------------
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "workspace:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DocuMind AI application settings
# ---------------------------------------------------------------------------
# Upload limits
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 10)
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = ["pdf", "txt"]

# Also cap Django's in-memory upload handling to the same ceiling.
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_BYTES + (1 * 1024 * 1024)

# Daily AI usage
DAILY_QUESTION_LIMIT = env_int("DAILY_QUESTION_LIMIT", 10)

# Text chunking (documented in docs/engineering-decisions.md)
CHUNK_SIZE = env_int("CHUNK_SIZE", 1000)
CHUNK_OVERLAP = env_int("CHUNK_OVERLAP", 150)

# Retrieval
RETRIEVAL_TOP_K = env_int("RETRIEVAL_TOP_K", 3)
RETRIEVAL_MIN_SCORE = env_float("RETRIEVAL_MIN_SCORE", 0.05)
MAX_QUESTION_LENGTH = env_int("MAX_QUESTION_LENGTH", 1000)

# AI provider
AI_PROVIDER = env("AI_PROVIDER", "mock").strip().lower()
AI_API_KEY = env("AI_API_KEY")
AI_MODEL = env("AI_MODEL", "gpt-4o-mini")
AI_BASE_URL = env("AI_BASE_URL", "https://api.openai.com/v1")
AI_REQUEST_TIMEOUT = env_int("AI_REQUEST_TIMEOUT", 30)

# ---------------------------------------------------------------------------
# Production security hardening (only applied when DEBUG is False)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Logging - technical errors to console/file, never raw document contents.
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "documind": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
