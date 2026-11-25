"""
Operações de leitura e escrita para notificações (ADR-N2 / Onda 3b / Onda 7a).
"""

from typing import Optional

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet

from core.models import Block, Mute, Notification, UserProfile
from core.utils.visibility import can_view_post

# Mapeamento de tipo → categoria para filtros da Central de Notificações
CATEGORY_MAP = {
    "likes": [Notification.Type.LIKE],
    "comments": [Notification.Type.REPLY],
    "follows": [Notification.Type.FOLLOW],
    "mentions": [Notification.Type.MENTION],
}

# -----------------------------------------------------------------------------
# Consultas de Notificações
# -----------------------------------------------------------------------------


def get_user_notifications(
    *,
    user,
    limit: int = 50,
    category: str = "all",
    unread_only: bool = False,
) -> QuerySet:
    """Retorna notificações do usuário com filtros de categoria e leitura.

    Exclui remetentes bloqueados ou silenciados (ADR-N24).
    """
    blocked_by_user = Block.objects.filter(blocker=user, blocked=OuterRef("sender"))
    blocker_of_user = Block.objects.filter(blocker=OuterRef("sender"), blocked=user)
    muted_by_user = Mute.objects.filter(muter=user, muted=OuterRef("sender"))

    qs = (
        Notification.objects.filter(recipient=user)
        .exclude(Exists(blocked_by_user))
        .exclude(Exists(blocker_of_user))
        .exclude(Exists(muted_by_user))
        .select_related("sender", "sender__profile")
        .order_by("-created_at")
    )

    if unread_only:
        qs = qs.filter(read=False)

    if category and category != "all":
        types = CATEGORY_MAP.get(category, [])
        if types:
            qs = qs.filter(notification_type__in=types)
        else:
            qs = qs.none()

    return qs[:limit]


def get_unread_notifications_count(*, user) -> int:
    """Retorna a contagem de notificações não lidas.

    Exclui remetentes bloqueados ou silenciados (ADR-N24).
    """
    blocked_by_user = Block.objects.filter(blocker=user, blocked=OuterRef("sender"))
    blocker_of_user = Block.objects.filter(blocker=OuterRef("sender"), blocked=user)
    muted_by_user = Mute.objects.filter(muter=user, muted=OuterRef("sender"))

    return (
        Notification.objects.filter(recipient=user, read=False)
        .exclude(Exists(blocked_by_user))
        .exclude(Exists(blocker_of_user))
        .exclude(Exists(muted_by_user))
        .count()
    )


# -----------------------------------------------------------------------------
# Operações de Escrita (Mutações)
# -----------------------------------------------------------------------------


def create_notification(
    *,
    recipient,
    sender=None,
    notification_type: str = Notification.Type.SYSTEM,
    ref_id: Optional[str] = None,
) -> Optional[Notification]:
    """Cria uma notificação in-app (com chave de idempotência quando ref_id fornecido).

    Regra Onda 5: Quando o interruptor de notificação estiver desativado (False)
    no perfil do destinatário, nenhum registro Notification é criado no banco de dados.

    Onda 7a: Após criação, dispara push via transaction.on_commit se flag ativa.
    """
    try:
        profile = UserProfile.objects.filter(user=recipient).first()
    except Exception:
        profile = getattr(recipient, "profile", None)

    if profile is not None:
        if notification_type == Notification.Type.LIKE and not profile.notify_likes:
            return None
        if (
            notification_type in (Notification.Type.REPLY, "reply", "comment")
            and not profile.notify_comments
        ):
            return None
        if notification_type == Notification.Type.FOLLOW and not profile.notify_follows:
            return None
        if notification_type == Notification.Type.MENTION and not profile.notify_mentions:
            return None

    if ref_id is not None:
        notif, created = Notification.objects.get_or_create(
            recipient=recipient,
            notification_type=notification_type,
            ref_id=ref_id,
            defaults={"sender": sender},
        )
        if created:
            _schedule_push(notif)
        return notif

    notif = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        ref_id=None,
    )
    _schedule_push(notif)
    return notif


def _schedule_push(notification: Notification) -> None:
    """Agenda push via on_commit se flag push_notifications ativa."""
    try:
        from core.services.feature_flags import is_feature_enabled
        from core.tasks import send_push_notification_task

        if not is_feature_enabled("push_notifications", notification.recipient):
            return

        title, body = _build_push_payload(notification)

        def dispatch():
            send_push_notification_task.delay(
                notification.id,
                title=title,
                body=body,
                data={
                    "type": notification.notification_type,
                    "notification_id": str(notification.id),
                },
            )

        transaction.on_commit(dispatch)
    except Exception:
        pass  # Push nunca derruba fluxo principal


def _build_push_payload(notification: Notification) -> tuple[str, str]:
    """Constrói título/corpo genérico localizado — sem expor conteúdo privado."""
    from django.utils.translation import gettext as _

    type_map = {
        Notification.Type.LIKE: (
            _("Nova curtida"),
            _("Alguém curtiu sua publicação."),
        ),
        Notification.Type.REPLY: (
            _("Novo comentário"),
            _("Você recebeu um novo comentário."),
        ),
        Notification.Type.FOLLOW: (
            _("Novo seguidor"),
            _("Alguém começou a seguir você."),
        ),
        Notification.Type.MENTION: (
            _("Você foi mencionado"),
            _("Alguém mencionou você em uma publicação."),
        ),
    }
    return type_map.get(
        notification.notification_type,
        (_("Nova notificação"), _("Você tem uma nova notificação.")),
    )


def notify_user_followed(*, follower, followed) -> None:
    """
    Gera notificação de novo seguidor.
    Regras:
    - Executa em transaction.on_commit
    - Não notifica a si mesmo
    - Não notifica se houver bloqueio bilateral
    - Não notifica se recipient silenciou sender
    - Não notifica se followed desativou notify_follows (Onda 5)
    """
    if follower == followed:
        return

    try:
        profile = UserProfile.objects.filter(user=followed).first()
    except Exception:
        profile = getattr(followed, "profile", None)
    if profile is not None and not profile.notify_follows:
        return

    if Block.objects.filter(
        Q(blocker=followed, blocked=follower) | Q(blocker=follower, blocked=followed)
    ).exists():
        return

    if Mute.objects.filter(muter=followed, muted=follower).exists():
        return

    def _dispatch():
        create_notification(
            recipient=followed,
            sender=follower,
            notification_type=Notification.Type.FOLLOW,
            ref_id=None,
        )

    transaction.on_commit(_dispatch)


def notify_follow_request_accepted(*, follower, followed) -> None:
    """
    Notifica o solicitante (follower) que o usuário (followed) aceitou o pedido de seguir.
    Regras:
    - Executa em transaction.on_commit
    - Não notifica a si mesmo
    - Não notifica se houver bloqueio bilateral
    - Não notifica se recipient (follower) silenciou sender (followed)
    - Não notifica se follower desativou notify_follows (Onda 5)
    """
    if follower == followed:
        return

    try:
        profile = UserProfile.objects.filter(user=follower).first()
    except Exception:
        profile = getattr(follower, "profile", None)
    if profile is not None and not profile.notify_follows:
        return

    if Block.objects.filter(
        Q(blocker=follower, blocked=followed) | Q(blocker=followed, blocked=follower)
    ).exists():
        return

    if Mute.objects.filter(muter=follower, muted=followed).exists():
        return

    def _dispatch():
        create_notification(
            recipient=follower,
            sender=followed,
            notification_type=Notification.Type.FOLLOW,
            ref_id=None,
        )

    transaction.on_commit(_dispatch)


def notify_post_liked(*, sender, post) -> None:
    """
    Gera notificação de curtida em publicação.
    Regras:
    - Executa em transaction.on_commit
    - Não notifica o próprio autor
    - Não notifica se houver bloqueio bilateral
    - Não notifica se o autor silenciou o sender
    - Nunca notifica se sender ou recipient não puder ver o post
    - Não notifica se autor desativou notify_likes (Onda 5)
    """
    recipient = post.author
    if sender == recipient:
        return

    try:
        profile = UserProfile.objects.filter(user=recipient).first()
    except Exception:
        profile = getattr(recipient, "profile", None)
    if profile is not None and not profile.notify_likes:
        return

    # Checa bloqueio bilateral
    if Block.objects.filter(
        Q(blocker=recipient, blocked=sender) | Q(blocker=sender, blocked=recipient)
    ).exists():
        return

    # Checa silenciamento
    if Mute.objects.filter(muter=recipient, muted=sender).exists():
        return

    # Garante visibilidade do post
    if not can_view_post(sender, post) or not can_view_post(recipient, post):
        return

    def _dispatch():
        create_notification(
            recipient=recipient,
            sender=sender,
            notification_type=Notification.Type.LIKE,
            ref_id=str(post.id),
        )

    transaction.on_commit(_dispatch)


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
