"""
Queries de leitura para posts (ADR-N2).
Separadas das views para evitar lógica de domínio em serializers/views.
"""

import uuid
from typing import Optional

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import QuerySet

from social.selectors import get_visible_posts_queryset

from .models import Post


def search_posts(*, query: str, user=None) -> QuerySet:
    """
    Full-text search em posts usando tsvector STORED (Plano A — ADR-N6).
    Ordena por relevância (SearchRank) decrescente.
    """
    sq = SearchQuery(query, config="simple", search_type="websearch")
    qs = (
        Post.objects.filter(search_vector=sq)
        .annotate(rank=SearchRank("search_vector", sq))
        .order_by("-rank", "-id")
    )
    return qs.select_related("author", "author__profile")


def list_posts_keyset(*, user, cursor: Optional[str] = None, limit: int = 20) -> QuerySet:
    """
    Lista posts visíveis para o usuário com keyset pagination (cursor por UUIDv7).
    """
    qs = get_visible_posts_queryset(user).order_by("-id")
    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor inválido.")
        qs = qs.filter(id__lt=cursor_uuid)
    return qs[:limit]


def get_post_detail_for_user(*, post_id, user) -> Optional[Post]:
    """Retorna o post pelo ID se visível para o usuário, senão None."""
    qs = get_visible_posts_queryset(user)
    try:
        return qs.select_related("author", "author__profile").get(pk=post_id)
    except Post.DoesNotExist:
        return None
