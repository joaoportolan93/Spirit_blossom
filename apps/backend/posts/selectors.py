"""
Queries de leitura para posts (ADR-N2).
Separadas das views para evitar lógica de domínio em serializers/views.
"""

import uuid
from typing import Optional

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import QuerySet

from social.selectors import visible_posts_for

from .models import Post


def search_posts(*, query: str, user) -> QuerySet:
    """
    Full-text search em posts usando tsvector STORED (Plano A — ADR-N6).
    Respeita regras de visibilidade via visible_posts_for (ADR-N21).
    Ordena por relevância (SearchRank) decrescente.
    `user` é obrigatório para garantir isolamento e respeito a bloqueios/privacidade.
    """
    sq = SearchQuery(query, config="simple", search_type="websearch")
    qs = (
        visible_posts_for(user)
        .filter(search_vector=sq)
        .annotate(rank=SearchRank("search_vector", sq))
        .order_by("-rank", "-id")
    )
    return qs


def list_posts_keyset(*, user, cursor: Optional[str] = None, limit: int = 20) -> QuerySet:
    """
    Lista posts visíveis para o usuário com keyset pagination (cursor por UUIDv7).
    """
    qs = visible_posts_for(user).order_by("-id")
    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor inválido.")
        qs = qs.filter(id__lt=cursor_uuid)
    return qs[:limit]


def get_post_detail_for_user(*, post_id, user) -> Optional[Post]:
    """Retorna o post pelo ID se visível para o usuário, senão None."""
    qs = visible_posts_for(user)
    try:
        return qs.select_related("author", "author__profile").get(pk=post_id)
    except Post.DoesNotExist:
        return None


def list_bookmarked_posts(*, user, cursor: Optional[str] = None, limit: int = 20) -> QuerySet:
    """
    Lista publicações salvas pelo usuário que ainda são visíveis para ele (ADR-N21 / Onda 3b).
    Se o post tornou-se inacessível (ex: autor bloqueou ou privou conta), é omitido.
    """
    from .models import PostBookmark

    bookmarked_ids = PostBookmark.objects.filter(user=user).values("post_id")
    qs = visible_posts_for(user).filter(id__in=bookmarked_ids).order_by("-id")

    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor inválido.")
        qs = qs.filter(id__lt=cursor_uuid)

    return qs[:limit]


def list_drafts(*, author) -> QuerySet:
    """Lista rascunhos de publicações isolados estritamente pelo autor."""
    from .models import Draft

    return Draft.objects.filter(author=author).order_by("-updated_at")
