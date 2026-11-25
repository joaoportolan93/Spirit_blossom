"""
Settings para suite de testes (pytest).
SQLite em memória — sem Postgres real, sem Redis, sem Celery.
NÃO usar em produção.
"""

from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "test-secret-key-only-for-tests-32chars!"
TESTING = True
ACCESS_LOG_HMAC_KEY = "test-hmac-key-exactly-32-bytes!!"  # 32 chars, apenas para testes
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.admin",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # Domínio
    "core",
    "comments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

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

ROOT_URLCONF = "config.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "core.User"

# Desabilita cache real para testes
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# JWT — cookies curtos para facilitar testes
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_COOKIE": "access_token",
    "AUTH_COOKIE_REFRESH": "refresh_token",
    "AUTH_COOKIE_SECURE": False,
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_SAMESITE": "Lax",
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "1000/minute",
        "user": "1000/minute",
        "login": "1000/minute",
        "register": "1000/minute",
        "password_reset": "1000/minute",
        "block": "1000/minute",
        "export_data": "1000/hour",
        "delete_account": "1000/hour",
        "device_registration": "1000/hour",
    },
}

# CSRF
CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_TRUSTED_ORIGINS = ["http://testserver"]

# Segurança
SECURE_PROXY_SSL_HEADER = None
USE_X_FORWARDED_HOST = False

# Negócio
POST_MAX_CHARS = 3000
FEED_FRESHNESS_HALFLIFE_HOURS = 48

# Internacionalização
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
LANGUAGES = [
    ("pt-br", "Português"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# Media / uploads
MEDIA_ROOT = "/tmp/test_media"
MEDIA_URL = "/protected-media/"
MAX_UPLOAD_MB = 10
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024

# Argon2 é lento — usar MD5 em testes para velocidade
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

STATIC_URL = "/static/"
APP_NAME = "TestApp"
CORS_ALLOWED_ORIGINS = ["http://testserver"]
CORS_ALLOW_CREDENTIALS = True
