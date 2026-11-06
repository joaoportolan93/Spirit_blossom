"""
Queries de visibilidade e filtros sociais (ADR-N2).
"""

from typing import Dict

from django.db import models
from django.db.models import Exists, OuterRef, QuerySet

from posts.models import Post

from .models import Block, Follow, Mute


def get_visible_posts_queryset(user) -> QuerySet:
    """
    Retorna posts excluindo:
    - Posts de usuários que o `user` bloqueou (blocker=user → blocked=author)
    - Posts de usuários que bloquearam o `user` (blocker=author → blocked=user)
    Aplica filtro de visibilidade (public ou followers-only).
    """
    if user.is_anonymous:
        return Post.objects.filter(visibility=Post.Visibility.PUBLIC)

    blocked_by_user = Block.objects.filter(
        blocker=user,
        blocked=OuterRef("author"),
    )
    blocker_of_user = Block.objects.filter(
        blocker=OuterRef("author"),
        blocked=user,
    )

    qs = Post.objects.exclude(Exists(blocked_by_user)).exclude(Exists(blocker_of_user))

    following_ids = Follow.objects.filter(follower=user).values("followed_id")
    qs = qs.filter(
        models.Q(visibility=Post.Visibility.PUBLIC)
        | models.Q(author__in=following_ids, visibility=Post.Visibility.FOLLOWERS)
        | models.Q(author=user)
    )

    return qs.select_related("author", "author__profile")


def get_profile_counters(*, target_user) -> Dict[str, int]:
    """Retorna os contadores públicos de um perfil de usuário."""
    posts_count = Post.objects.filter(
        author=target_user,
        visibility=Post.Visibility.PUBLIC,
    ).count()
    followers_count = Follow.objects.filter(followed=target_user).count()
    following_count = Follow.objects.filter(follower=target_user).count()
    return {
        "posts_count": posts_count,
        "followers_count": followers_count,
        "following_count": following_count,
    }


def get_relationship_status(*, source_user, target_user) -> Dict[str, bool]:
    """Retorna status de relacionamento entre dois usuários."""
    if not source_user.is_authenticated:
        return {"is_following": False, "is_blocked": False, "is_muting": False}

    is_following = Follow.objects.filter(follower=source_user, followed=target_user).exists()
    is_blocked = Block.objects.filter(blocker=source_user, blocked=target_user).exists()
    is_muting = Mute.objects.filter(muter=source_user, muted=target_user).exists()
    return {
        "is_following": is_following,
        "is_blocked": is_blocked,
        "is_muting": is_muting,
    }
