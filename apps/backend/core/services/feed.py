"""
Serviços e seletores de feed cronológico e Explorar com keyset pagination (ADR-N2).
"""

import unicodedata
import uuid

from django.db.models import Exists, OuterRef, Q, QuerySet

from core.models import Follow, Mute, Post
from core.utils.visibility import visible_posts_for


def get_following_feed(*, user, cursor: str | None = None, limit: int = 20) -> QuerySet:
    """
    Feed cronológico dos usuários que `user` segue + suas próprias publicações.
    Keyset pagination: id < cursor ORDER BY id DESC.

    Raises:
        ValueError: cursor inválido (não é UUID válido).
    """
    qs = visible_posts_for(user)

    # Restringe ao feed de "seguindo" incluindo os próprios posts do usuário
    following_ids = Follow.objects.filter(
        follower=user,
        status=Follow.Status.ACTIVE,
    ).values("followed_id")
    qs = qs.filter(Q(author=user) | Q(author__in=following_ids))

    # Exclui autores silenciados pelo usuário (ADR-N24)
    muted_by_user = Mute.objects.filter(muter=user, muted=OuterRef("author"))
    qs = qs.exclude(Exists(muted_by_user))

    # Keyset pagination por UUID (UUIDv7 é ordenável por tempo)
    if cursor is not None:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor de feed inválido.")
        qs = qs.filter(id__lt=cursor_uuid)

    return qs.order_by("-id")[:limit]


def get_explore_feed(
    *,
    user,
    cursor: str | None = None,
    limit: int = 20,
    hashtag: str | None = None,
) -> QuerySet:
    """
    Feed Explorar: posts públicos de qualquer autor, cronológico por keyset.
    Exclui autores bloqueados em ambas as direções e silenciados (ADR-N22).
    Suporta filtro opcional por hashtag (?hashtag=tag).
    Centralizado via visible_posts_for (ADR-N21).

    Raises:
        ValueError: cursor inválido.
    """
    muted_by_user = Mute.objects.filter(muter=user, muted=OuterRef("author"))

    qs = (
        visible_posts_for(user)
        .filter(visibility=Post.Visibility.PUBLIC)
        .exclude(author__profile__is_private=True)
        .exclude(Exists(muted_by_user))
    )

    if hashtag is not None and hashtag.strip():
        clean_tag = unicodedata.normalize("NFC", hashtag).lstrip("#").strip().lower()
        if not clean_tag:
            return qs.none()
        qs = qs.filter(hashtags__name=clean_tag)

    if cursor is not None:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor de Explorar inválido.")
        qs = qs.filter(id__lt=cursor_uuid)

    return qs.order_by("-id")[:limit]
