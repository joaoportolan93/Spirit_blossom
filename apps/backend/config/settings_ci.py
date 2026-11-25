"""
Settings para CI (GitHub Actions) com Postgres real.
Herda settings.py via variáveis de ambiente.
NÃO usar em produção.
"""

import os

os.environ.setdefault("POSTGRES_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "test_password"))
os.environ.setdefault("ACCESS_LOG_HMAC_KEY", "ci-hmac-key-32bytes-not-for-prod!")

from config.settings import *

TESTING = True

# Sobrescreve apenas o necessário para CI
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Throttles desabilitados/altos durante a suite de testes para evitar 429
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/minute",
        "user": "10000/minute",
        "login": "10000/minute",
        "register": "10000/minute",
        "password_reset": "10000/minute",
        "block": "10000/minute",
        "export_data": "10000/minute",
        "delete_account": "10000/minute",
        "device_registration": "10000/minute",
    },
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
