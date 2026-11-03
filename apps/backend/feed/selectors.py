"""
Seletor de feed cronológico com keyset pagination.
Sem model próprio no M1a — usa Post e social.selectors.
"""

import uuid

from django.db.models import QuerySet

from social.models import Follow
from social.selectors import get_visible_posts_queryset


def get_following_feed(*, user, cursor: str | None = None, limit: int = 20) -> QuerySet:
    """
    Feed cronológico dos usuários que `user` segue.
    Keyset pagination: id < cursor ORDER BY id DESC.

    Raises:
        ValueError: cursor inválido (não é UUID válido).
    """
    qs = get_visible_posts_queryset(user)

    # Restringe ao feed de "seguindo"
    following_ids = Follow.objects.filter(follower=user).values("followed_id")
    qs = qs.filter(author__in=following_ids)

    # Keyset pagination por UUID (UUIDv7 é ordenável por tempo)
    if cursor is not None:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor de feed inválido.")
        qs = qs.filter(id__lt=cursor_uuid)

    return qs.order_by("-id")[:limit]
