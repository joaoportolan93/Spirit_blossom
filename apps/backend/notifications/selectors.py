"""
Queries de leitura para notificações (ADR-N2).
"""

from django.db.models import QuerySet

from .models import Notification


def get_user_notifications(*, user, limit: int = 50) -> QuerySet:
    """Retorna as notificações mais recentes de um usuário."""
    return (
        Notification.objects.filter(recipient=user)
        .select_related("sender")
        .order_by("-created_at")[:limit]
    )


def get_unread_notifications_count(*, user) -> int:
    """Retorna a contagem de notificações não lidas."""
    return Notification.objects.filter(recipient=user, read=False).count()
