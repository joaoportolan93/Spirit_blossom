"""
Settings para desenvolvimento local (localhost) sem Docker / sem Postgres / sem Redis.
Usa SQLite local (db.sqlite3) com compatibilidade via patch.
"""

from pathlib import Path

from config.sqlite_compat import patch_sqlite

patch_sqlite()

from .settings_test import *

MEDIA_URL = "/media/"
APP_NAME = "Spirit Blossom (Dev)"

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

ALLOWED_HOSTS = ["*"]
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True

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

if "django.contrib.messages" not in INSTALLED_APPS:
    INSTALLED_APPS.append("django.contrib.messages")

if "django.contrib.messages.middleware.MessageMiddleware" not in MIDDLEWARE:
    MIDDLEWARE.append("django.contrib.messages.middleware.MessageMiddleware")
