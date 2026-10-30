"""
Configuração do Celery.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("app")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ── Beat schedule ────────────────────────────────────────────────────────────
app.conf.beat_schedule = {
    # Limpa tokens JWT expirados da blacklist do SimpleJWT (Postgres).
    # Evita crescimento ilimitado das tabelas OutstandingToken/BlacklistedToken.
    "flush-expired-jwt-tokens": {
        "task": "accounts.tasks.flush_expired_tokens",
        "schedule": crontab(hour=3, minute=30),  # 03:30 America/Sao_Paulo
    },
}
