"""
Configurações Django — rede social generalista.

Valores sensíveis vêm exclusivamente de variáveis de ambiente.
Não comite este arquivo com secrets preenchidos.
"""

import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab

# ---------------------------------------------------------------------------
# Caminhos base
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Segurança
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ["SECRET_KEY"]

# Chave HMAC para hashing de IPs no AccessLog.
# DEVE ser separada da SECRET_KEY: trocar SECRET_KEY quebraria o histórico de hashes.
# Mínimo 32 bytes. O app falha ao iniciar se ausente.
ACCESS_LOG_HMAC_KEY = os.environ["ACCESS_LOG_HMAC_KEY"]

DEBUG = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

# ---------------------------------------------------------------------------
# Proxy reverso (Nginx)
# Permite que o Django confie no X-Forwarded-Proto enviado pelo Nginx.
# Sem isso, CSRF_TRUSTED_ORIGINS com https:// falha em produção.
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# ---------------------------------------------------------------------------
# Produto — nome configurável; não use literais de marca aqui
# ---------------------------------------------------------------------------
APP_NAME = os.environ.get("APP_NAME", "App")

# ---------------------------------------------------------------------------
# Aplicativos instalados
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceiros
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_celery_beat",
    # Domínio
    "accounts",
    "posts",
    "social",
    "feed",
    "notifications",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
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
        "DIRS": [BASE_DIR / "templates"],
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

# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "NAME": os.environ.get("POSTGRES_DB", "app_db"),
        "USER": os.environ.get("POSTGRES_USER", "app_user"),
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "sslmode": "prefer",
        },
    }
}

# ---------------------------------------------------------------------------
# Cache — Redis
# ---------------------------------------------------------------------------
_redis_host = os.environ.get("REDIS_HOST", "redis")
_redis_port = os.environ.get("REDIS_PORT", "6379")
_redis_password = os.environ.get("REDIS_PASSWORD", "")
_redis_url = (
    f"redis://:{_redis_password}@{_redis_host}:{_redis_port}/0"
    if _redis_password
    else f"redis://{_redis_host}:{_redis_port}/0"
)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _redis_url,
    }
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = _redis_url
CELERY_RESULT_BACKEND = _redis_url
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "America/Sao_Paulo"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_BEAT_SCHEDULE = {
    "flush-expired-tokens-daily": {
        "task": "accounts.flush_expired_tokens",
        "schedule": crontab(hour=3, minute=0),  # 03:00 America/Sao_Paulo todo dia
    },
}

# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"  # ativo em M1a

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# ---------------------------------------------------------------------------
# REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "120/minute",
        "login": "5/minute",
        "register": "3/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": int(os.environ.get("FEED_DEFAULT_LIMIT", "20")),
}

# ---------------------------------------------------------------------------
# SimpleJWT
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.environ.get("ACCESS_TOKEN_LIFETIME_MINUTES", "15"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.environ.get("REFRESH_TOKEN_LIFETIME_DAYS", "7"))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_COOKIE": "access_token",
    "AUTH_COOKIE_REFRESH": "refresh_token",
    "AUTH_COOKIE_SECURE": not DEBUG,
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_SAMESITE": "Lax",
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------
CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # frontend precisa ler o valor
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# ---------------------------------------------------------------------------
# Negócio
# ---------------------------------------------------------------------------
POST_MAX_CHARS = int(os.environ.get("POST_MAX_CHARS", "3000"))
FEED_FRESHNESS_HALFLIFE_HOURS = int(os.environ.get("FEED_FRESHNESS_HALFLIFE_HOURS", "48"))
FEED_SERVICE_URL = os.environ.get("FEED_SERVICE_URL", "http://feed:3000")

# ---------------------------------------------------------------------------
# Media / uploads
# ---------------------------------------------------------------------------
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
MEDIA_URL = "/protected-media/"  # servido via X-Accel-Redirect (N5)
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "10"))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024

# ---------------------------------------------------------------------------
# Internacionalização
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# ---------------------------------------------------------------------------
# Estáticos
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Padrão de PK
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Logging estruturado (structlog — N11)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
