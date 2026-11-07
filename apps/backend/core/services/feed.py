"""
Serviços e seletores de feed cronológico e Explorar com keyset pagination (ADR-N2).
"""

import uuid

from django.db.models import Exists, OuterRef, QuerySet

from core.models import Follow, Mute, Post
from core.utils.visibility import visible_posts_for


def get_following_feed(*, user, cursor: str | None = None, limit: int = 20) -> QuerySet:
    """
    Feed cronológico dos usuários que `user` segue.
    Keyset pagination: id < cursor ORDER BY id DESC.

    Raises:
        ValueError: cursor inválido (não é UUID válido).
    """
    qs = visible_posts_for(user)

    # Restringe ao feed de "seguindo"
    following_ids = Follow.objects.filter(
        follower=user,
        status=Follow.Status.ACTIVE,
    ).values("followed_id")
    qs = qs.filter(author__in=following_ids)

    # Keyset pagination por UUID (UUIDv7 é ordenável por tempo)
    if cursor is not None:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor de feed inválido.")
        qs = qs.filter(id__lt=cursor_uuid)

    return qs.order_by("-id")[:limit]


def get_explore_feed(*, user, cursor: str | None = None, limit: int = 20) -> QuerySet:
    """
    Feed Explorar: posts públicos de qualquer autor, cronológico por keyset.
    Exclui autores bloqueados em ambas as direções e silenciados (ADR-N22).
    Centralizado via visible_posts_for (ADR-N21).

    Raises:
        ValueError: cursor inválido.
    """
    muted_by_user = Mute.objects.filter(muter=user, muted=OuterRef("author"))

    qs = (
        visible_posts_for(user)
        .filter(
            visibility=Post.Visibility.PUBLIC,
            author__profile__is_private=False,
        )
        .exclude(Exists(muted_by_user))
    )

    if cursor is not None:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor de Explorar inválido.")
        qs = qs.filter(id__lt=cursor_uuid)

    return qs.order_by("-id")[:limit]

