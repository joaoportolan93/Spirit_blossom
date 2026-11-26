"""
Tarefas Celery do core.
"""

import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(name="core.flush_expired_tokens")
def flush_expired_tokens():
    """Remove tokens expirados da blacklist do SimpleJWT (tabela Postgres)."""
    call_command("flushexpiredtokens")


@shared_task(
    name="core.send_push_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def send_push_notification_task(
    self,
    notification_id: int,
    *,
    title: str,
    body: str,
    data: dict | None = None,
):
    """
    Envia push notification assíncrono para todos os dispositivos ativos do
    destinatário de uma notificação.

    Disparado exclusivamente via transaction.on_commit() após criação de
    notificação — garante que o banco commitou antes de qualquer envio FCM.
    """
    try:
        from core.models import Notification, PushDevice
        from core.services.push import send_push_notification

        try:
            notification = Notification.objects.select_related("recipient").get(pk=notification_id)
        except Notification.DoesNotExist:
            logger.warning("Notificação %s não encontrada para push.", notification_id)
            return

        tokens = list(
            PushDevice.objects.filter(
                user=notification.recipient,
                is_active=True,
            ).values_list("token", flat=True)
        )

        if not tokens:
            return

        result = send_push_notification(
            tokens=tokens,
            title=title,
            body=body,
            data=data or {},
        )
        logger.info(
            "Push enviado: notif=%s sent=%d removed=%d",
            notification_id,
            result["sent"],
            len(result["removed_tokens"]),
        )

    except Exception as exc:
        logger.error("Erro na task push %s: %s", notification_id, exc)
        raise self.retry(exc=exc)


@shared_task(name="core.expire_temporary_bans")
def expire_temporary_bans_task():
    """Restaura usuários cuja suspensão temporária já expirou."""
    from core.services.user_lifecycle import expire_temporary_bans

    restored = expire_temporary_bans()
    logger.info("Suspensões temporárias expiradas restauradas: %d", restored)
    return restored


@shared_task(name="core.purge_expired_banned_accounts")
def purge_expired_banned_accounts_task(dry_run: bool | None = None):
    """Expurgo periódico de contas banidas após prazo de recurso (Onda 8)."""
    from core.services.user_lifecycle import purge_expired_banned_accounts

    results = purge_expired_banned_accounts(dry_run=dry_run)
    logger.info("Expurgo de contas banidas processado: %d registros", len(results))
    return len(results)
