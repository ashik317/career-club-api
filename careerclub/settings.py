import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv(BASE_DIR / ".env")


def env(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).lower() in ("1", "true", "yes", "on")


DEBUG = env_bool("DJANGO_DEBUG", True)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is off.")
    SECRET_KEY = "dev-only-insecure-key-change-me"

ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "careerclub.urls"

# REST API
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["portal.api.auth.TokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["portal.api.auth.Deny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_THROTTLE_RATES": {"auth": env("AUTH_THROTTLE_RATE", "20/min")},
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%z",
}
TOKEN_LIFETIME_DAYS = 7


# CORS_ALLOWED_ORIGINS=http://localhost:3000
CORS_ALLOWED_ORIGINS = [o for o in env("CORS_ALLOWED_ORIGINS").split(",") if o]


PAYMENT_RETURN_URL = env("PAYMENT_RETURN_URL")
WSGI_APPLICATION = "careerclub.wsgi.application"

# Database
if env("DB_ENGINE", "sqlite") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "career_club"),
            "USER": env("DB_USER", "postgres"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Passwords
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "portal.hashers.LegacySHA256PasswordHasher",
]

#Internationalisation
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

# Uploaded files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

MAX_CV_SIZE = 5 * 1024 * 1024
MAX_IMAGE_SIZE = 2 * 1024 * 1024

# Email
if env("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = int(env("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = env("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Career Club <no-reply@careerclub.local>")

# SSLCommerz payment gateway
SSLCOMMERZ_STORE_ID = env("SSLCOMMERZ_STORE_ID")
SSLCOMMERZ_STORE_PASSWORD = env("SSLCOMMERZ_STORE_PASSWORD")
SSLCOMMERZ_SANDBOX = env_bool("SSLCOMMERZ_SANDBOX", True)
PAYMENT_SIMULATION = DEBUG and not SSLCOMMERZ_STORE_ID

# Misc
ADMIN_SIGNUP_ENABLED = env_bool("ADMIN_SIGNUP_ENABLED", DEBUG)
BAN_DAYS = 7
