"""
Queries de leitura para posts.
Separadas das views para evitar lógica de domínio em serializers/views.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import QuerySet

from .models import Post


def search_posts(*, query: str, user=None) -> QuerySet:
    """
    Full-text search em posts usando tsvector STORED (Plano A — ADR-N6).
    Ordena por relevância (SearchRank) decrescente.
    O filtro de bloqueio bidirecional é aplicado pelo caller via get_visible_posts_queryset().
    """
    sq = SearchQuery(query, config="simple", search_type="websearch")
    qs = (
        Post.objects.filter(search_vector=sq)
        .annotate(rank=SearchRank("search_vector", sq))
        .order_by("-rank", "-id")
    )
    return qs.select_related("author", "author__profile")
