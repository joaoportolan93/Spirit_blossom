"""
Settings para CI (GitHub Actions) com Postgres real.
Herda settings.py via variáveis de ambiente.
NÃO usar em produção.
"""
import os
os.environ.setdefault("POSTGRES_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "test_password"))
os.environ.setdefault("ACCESS_LOG_HMAC_KEY", "ci-hmac-key-32bytes-not-for-prod!")

from config.settings import *  # noqa: F401, F403

# Sobrescreve apenas o necessário para CI
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
