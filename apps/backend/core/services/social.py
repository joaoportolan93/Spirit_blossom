"""
Operações de escrita e consultas para interações sociais (ADR-N2).
"""

from typing import Tuple

from django.db import transaction

from core.models import Block, Follow, Mute
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
]


def follow_user(*, follower, target_user) -> Tuple[Follow, bool]:
    """
    Seguir usuário.
    Raises ValueError se tentar seguir a si mesmo ou já estiver seguindo.
    """
    if follower == target_user:
        raise ValueError("Não é possível seguir a si mesmo.")

    follow, created = Follow.objects.get_or_create(
        follower=follower,
        followed=target_user,
    )
    if not created:
        raise ValueError("Já está seguindo este usuário.")

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
    Requires: user segue target_user com status=active.
    Returns True se adicionado, False se já estava.
    Raises ValueError se não houver follow ativo.
    """
    follow = Follow.objects.filter(
        follower=user,
        followed=target_user,
        status=Follow.Status.ACTIVE,
    ).first()
    if not follow:
        raise ValueError("Você precisa seguir este usuário para adicioná-lo ao círculo.")
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
        follower=user,
        followed=target_user,
        is_close_friend=True,
    ).update(is_close_friend=False)
    return bool(updated)

