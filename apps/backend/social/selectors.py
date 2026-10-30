"""
Queries de visibilidade e filtros sociais.
"""
from django.db import models
from django.db.models import Exists, OuterRef, QuerySet

from posts.models import Post
from .models import Block


def get_visible_posts_queryset(user) -> QuerySet:
    """
    Retorna posts excluindo:
    - Posts de usuários que o `user` bloqueou (blocker=user → blocked=author)
    - Posts de usuários que bloquearam o `user` (blocker=author → blocked=user)
    Aplica filtro de visibilidade (public ou followers-only).
    """
    if user.is_anonymous:
        return Post.objects.filter(visibility=Post.Visibility.PUBLIC)

    # Bloqueio bidirecional: NOT EXISTS em ambas as direções
    blocked_by_user = Block.objects.filter(
        blocker=user,
        blocked=OuterRef("author"),
    )
    blocker_of_user = Block.objects.filter(
        blocker=OuterRef("author"),
        blocked=user,
    )

    qs = Post.objects.exclude(
        Exists(blocked_by_user)
    ).exclude(
        Exists(blocker_of_user)
    )

    # Visibilidade: posts de seguidores visíveis apenas se o user segue o autor
    from .models import Follow
    following_ids = Follow.objects.filter(follower=user).values("followed_id")
    qs = qs.filter(
        models.Q(visibility=Post.Visibility.PUBLIC)
        | models.Q(author__in=following_ids, visibility=Post.Visibility.FOLLOWERS)
        | models.Q(author=user)  # próprios posts sempre visíveis
    )

    return qs.select_related("author", "author__profile")
