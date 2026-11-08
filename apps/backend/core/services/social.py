"""
Operações de escrita e consultas para interações sociais (ADR-N2).
"""

from typing import Optional, Tuple

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.http import Http404

from core.models import Block, Follow, Mute, UserProfile
from core.utils.visibility import (
    can_view_profile,
    get_profile_counters,
    get_relationship_status,
    is_user_blocked,
)

__all__ = [
    "follow_user",
    "unfollow_user",
    "block_user",
    "unblock_user",
    "mute_user",
    "unmute_user",
    "add_to_close_friends",
    "remove_from_close_friends",
    "can_view_profile",
    "get_profile_counters",
    "get_relationship_status",
    "is_user_blocked",
    "update_user_privacy",
    "list_follow_requests",
    "accept_follow_request",
    "reject_follow_request",
]


def follow_user(*, follower, target_user) -> Tuple[Follow, bool]:
    """
    Seguir usuário.
    Se a conta do usuário for privada, status inicia como 'pending'.
    Raises ValueError se tentar seguir a si mesmo ou já estiver seguindo / pedido pendente.
    """
    if follower == target_user:
        raise ValueError("Não é possível seguir a si mesmo.")

    profile = getattr(target_user, "profile", None)
    is_private = getattr(profile, "is_private", False)
    status_initial = Follow.Status.PENDING if is_private else Follow.Status.ACTIVE

    follow, created = Follow.objects.get_or_create(
        follower=follower,
        followed=target_user,
        defaults={"status": status_initial},
    )
    if not created:
        if follow.status == Follow.Status.PENDING:
            raise ValueError("Pedido para seguir já enviado e pendente.")
        raise ValueError("Já está seguindo este usuário.")

    if status_initial == Follow.Status.ACTIVE:
        from core.services.notifications import notify_user_followed

        notify_user_followed(follower=follower, followed=target_user)

    return follow, created


def unfollow_user(*, follower, target_user) -> bool:
    """Deixar de seguir usuário."""
    deleted, _ = Follow.objects.filter(
        follower=follower,
        followed=target_user,
    ).delete()
    return bool(deleted)


@transaction.atomic
def block_user(*, blocker, target_user) -> Tuple[Block, bool]:
    """
    Bloquear usuário. Remove follows mútuos automaticamente.
    Raises ValueError se tentar bloquear a si mesmo ou já estiver bloqueado.
    """
    if blocker == target_user:
        raise ValueError("Não é possível bloquear a si mesmo.")

    # Remove relacionamentos de follow em ambas as direções
    Follow.objects.filter(follower=blocker, followed=target_user).delete()
    Follow.objects.filter(follower=target_user, followed=blocker).delete()

    block, created = Block.objects.get_or_create(
        blocker=blocker,
        blocked=target_user,
    )
    if not created:
        raise ValueError("Já bloqueou este usuário.")
    return block, created


def unblock_user(*, blocker, target_user) -> bool:
    """Desbloquear usuário."""
    deleted, _ = Block.objects.filter(
        blocker=blocker,
        blocked=target_user,
    ).delete()
    return bool(deleted)


def mute_user(*, muter, target_user) -> Tuple[Mute, bool]:
    """Silenciar usuário."""
    if muter == target_user:
        raise ValueError("Não é possível silenciar a si mesmo.")
    mute, created = Mute.objects.get_or_create(
        muter=muter,
        muted=target_user,
    )
    if not created:
        raise ValueError("Já silenciou este usuário.")
    return mute, created


def unmute_user(*, muter, target_user) -> bool:
    """Remover silenciamento."""
    deleted, _ = Mute.objects.filter(
        muter=muter,
        muted=target_user,
    ).delete()
    return bool(deleted)


def add_to_close_friends(*, user, target_user) -> bool:
    """
    Adiciona target_user ao círculo de amigos de user.
    Requires: target_user segue user com status=active (seguidor ativo do dono, estilo Lumem).
    Raises Http404 se não for seguidor ativo ou se houver bloqueio.
    Returns True se adicionado, False se já estava no círculo.
    """
    if is_user_blocked(user, target_user):
        raise Http404("Usuário inacessível ou bloqueado.")

    follow = Follow.objects.filter(
        follower=target_user,
        followed=user,
        status=Follow.Status.ACTIVE,
    ).first()

    # Compatibilidade: se user segue target_user de forma ativa
    if not follow:
        follow = Follow.objects.filter(
            follower=user,
            followed=target_user,
            status=Follow.Status.ACTIVE,
        ).first()

    if not follow:
        raise Http404("Apenas seguidores ativos podem ser adicionados ao círculo.")

    if follow.is_close_friend:
        return False
    follow.is_close_friend = True
    follow.save(update_fields=["is_close_friend"])
    return True


def remove_from_close_friends(*, user, target_user) -> bool:
    """
    Remove target_user do círculo de amigos de user.
    Returns True se removido, False se não estava no círculo.
    """
    updated = Follow.objects.filter(
        (Q(follower=target_user, followed=user) | Q(follower=user, followed=target_user)),
        is_close_friend=True,
    ).update(is_close_friend=False)
    return bool(updated)


@transaction.atomic
def update_user_privacy(*, user, is_private: bool) -> UserProfile:
    """
    Atualiza a privacidade da conta do usuário (Onda 3c).
    - Privada para pública: todos os pedidos pending do alvo viram active
      numa única transação atômica, de forma idempotente, sem notificações em massa.
    - Pública para privada: seguidores ativos continuam ativos; novos seguidores viram pending.
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.is_private == is_private:
        return profile

    if not is_private:
        Follow.objects.filter(
            followed=user,
            status=Follow.Status.PENDING,
        ).update(status=Follow.Status.ACTIVE)

    profile.is_private = is_private
    profile.save(update_fields=["is_private"])

    if hasattr(user, "__dict__") and "profile" in user.__dict__:
        del user.__dict__["profile"]

    return profile


def list_follow_requests(*, user, cursor: Optional[int] = None, limit: int = 20) -> QuerySet:
    """
    Lista pedidos de seguir pendentes direcionados ao usuário.
    Exclui usuários bloqueados em qualquer direção.
    Keyset pagination por id decrescente.
    """
    blocked_subquery = Block.objects.filter(
        Q(blocker=user, blocked=OuterRef("follower"))
        | Q(blocker=OuterRef("follower"), blocked=user)
    )
    qs = (
        Follow.objects.filter(
            followed=user,
            status=Follow.Status.PENDING,
            follower__is_active=True,
        )
        .exclude(Exists(blocked_subquery))
        .select_related("follower", "follower__profile")
        .order_by("-id")
    )
    if cursor is not None:
        try:
            cursor_id = int(cursor)
        except (ValueError, TypeError):
            raise ValueError("Cursor inválido.")
        qs = qs.filter(id__lt=cursor_id)

    return qs[:limit]


@transaction.atomic
def accept_follow_request(*, user, follower_username: str) -> Follow:
    """
    Aceita pedido de seguir pendente direcionado a user.
    - 404 se não houver pedido pendente ou se houver bloqueio.
    - Idempotente.
    - Notifica o solicitante (follower) pelo motor de notificações.
    """
    follow = (
        Follow.objects.select_for_update()
        .filter(
            followed=user,
            follower__username=follower_username,
            status=Follow.Status.PENDING,
        )
        .first()
    )
    if not follow:
        raise Http404("Solicitação de seguir pendente não encontrada.")

    if is_user_blocked(user, follow.follower):
        raise Http404("Solicitação de seguir pendente não encontrada.")

    follow.status = Follow.Status.ACTIVE
    follow.save(update_fields=["status"])

    from core.services.notifications import notify_follow_request_accepted

    notify_follow_request_accepted(follower=follow.follower, followed=user)
    return follow


@transaction.atomic
def reject_follow_request(*, user, follower_username: str) -> bool:
    """
    Recusa pedido de seguir pendente direcionado a user.
    - 404 se não houver pedido pendente.
    - Idempotente.
    - Remove em silêncio (sem notificação).
    """
    follow = Follow.objects.filter(
        followed=user,
        follower__username=follower_username,
        status=Follow.Status.PENDING,
    ).first()
    if not follow:
        raise Http404("Solicitação de seguir pendente não encontrada.")

    deleted, _ = follow.delete()
    return bool(deleted)
