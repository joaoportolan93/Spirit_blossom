"""
Settings mínimas para makemigrations local (sem banco real, sem Celery, sem Redis).
NÃO usar em produção. Apenas para gerar arquivos de migration.
"""
import os

SECRET_KEY = "dev-only-not-for-production"
DEBUG = True
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework_simplejwt.token_blacklist",
    "accounts",
    "posts",
    "social",
    "feed",
    "notifications",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
# posts.Post.content_text valida contra esta setting
POST_MAX_CHARS = 3000
USE_TZ = True

