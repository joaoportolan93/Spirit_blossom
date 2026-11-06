"""
Operações de escrita para notificações (ADR-N2).
"""

from typing import Optional

from .models import Notification


def create_notification(
    *,
    recipient,
    sender=None,
    notification_type: str = Notification.Type.SYSTEM,
    ref_id: Optional[str] = None,
) -> Notification:
    """Cria uma notificação in-app."""
    return Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        ref_id=ref_id,
    )


def mark_notification_as_read(*, notification_id: int, user) -> bool:
    """Marca notificação como lida se pertencer ao usuário."""
    updated = Notification.objects.filter(
        pk=notification_id,
        recipient=user,
    ).update(read=True)
    return bool(updated)


def mark_all_notifications_as_read(*, user) -> int:
    """Marca todas as notificações não lidas do usuário como lidas."""
    return Notification.objects.filter(
        recipient=user,
        read=False,
    ).update(read=True)
