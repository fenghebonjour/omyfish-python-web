"""
Django settings for config project.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-dev-key-change-in-production")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# The REST contract (see ARCHITECTURE.md) uses no trailing slashes, matching
# the Java/.NET siblings — don't 301-redirect API clients onto a slash.
APPEND_SLASH = False


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "storages",
    "apps.accounts",
    "apps.species",
    "apps.observations",
    "apps.notifications",
    "apps.billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# Defaults to SQLite so `make run` works with zero external services (per
# BACKLOG.md pragmatic geo call). docker-compose points this at the shared
# Postgres/PostGIS instance via DATABASE_URL.

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}


AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Object storage — identify persists the uploaded image and returns a real
# storage key (see apps/species/views.py); observations reference it rather
# than re-uploading. Defaults to local disk for `make run`; docker-compose
# points this at the shared MinIO instance via MINIO_ENDPOINT_URL, mirroring
# the SQLite/Postgres dev-vs-docker split used for the DB above.

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

AWS_S3_ENDPOINT_URL = env("MINIO_ENDPOINT_URL", default=None)
if AWS_S3_ENDPOINT_URL:
    AWS_ACCESS_KEY_ID = env("MINIO_ACCESS_KEY", default="omyfish")
    AWS_SECRET_ACCESS_KEY = env("MINIO_SECRET_KEY", default="omyfish_dev")
    AWS_STORAGE_BUCKET_NAME = env("MINIO_BUCKET", default="omyfish-images")
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


# DRF / JWT
# Contract requires camelCase JSON everywhere and a fixed auth response
# shape ({token, refreshToken, userId, email, role}) — see apps/accounts.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": env("JWT_SECRET", default="dev-secret-change-in-production-32b"),
}


# CORS — open for local/dev, mirrors the Java/.NET gateways' allow_origins=["*"].

CORS_ALLOW_ALL_ORIGINS = True


# omyfish-ai integration (../omyfish-ai over HTTP — see apps/species/ai_client.py)

AI_SERVICE_URL = env("AI_SERVICE_URL", default="http://localhost:8000")
