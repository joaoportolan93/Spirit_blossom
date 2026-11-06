"""
Operações de escrita para interações sociais (ADR-N2).
"""

from typing import Tuple

from django.db import transaction

from .models import Block, Follow, Mute


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
