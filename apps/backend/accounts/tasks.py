"""
Tarefas Celery do app accounts.
"""

from celery import shared_task
from django.core.management import call_command


@shared_task(name="accounts.flush_expired_tokens")
def flush_expired_tokens():
    """Remove tokens expirados da blacklist do SimpleJWT (tabela Postgres)."""
    call_command("flushexpiredtokens")
