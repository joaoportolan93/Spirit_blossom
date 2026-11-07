"""
Operações de leitura e escrita para posts e rascunhos (ADR-N2 / Onda 3b).
"""

import uuid
from typing import Optional

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import transaction
from django.db.models import F, QuerySet

from core.models import Draft, Post, PostBookmark, PostLike
from core.utils.visibility import can_view_post, visible_posts_for

# -----------------------------------------------------------------------------
# Consultas e Seletores de Posts
# -----------------------------------------------------------------------------


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
    return Draft.objects.filter(author=author).order_by("-updated_at")


# -----------------------------------------------------------------------------
# Operações de Escrita (Mutações)
# -----------------------------------------------------------------------------


def create_post(*, author, content_text: str, visibility: str = Post.Visibility.PUBLIC) -> Post:
    """Cria um post validando o limite de caracteres."""
    max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
    if len(content_text) > max_chars:
        raise ValueError(f"Conteúdo excede o limite de {max_chars} caracteres.")
    return Post.objects.create(
        author=author,
        content_text=content_text,
        visibility=visibility,
    )


def delete_post(*, post: Post, user) -> bool:
    """Apaga um post se o usuário for o autor."""
    if post.author != user:
        raise PermissionError("Sem permissão para excluir esta publicação.")
    post.delete()
    return True


@transaction.atomic
def like_post(*, user, post_id) -> bool:
    """
    Curte uma publicação visível para o usuário.
    Atualiza contador atômico com F().
    Dispara notificação se aplicável.
    """
    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        return False

    if not can_view_post(user, post):
        return False

    _, created = PostLike.objects.get_or_create(post=post, user=user)
    if created:
        Post.objects.filter(pk=post.pk).update(likes_count=F("likes_count") + 1)
        from core.services.notifications import notify_post_liked

        notify_post_liked(sender=user, post=post)
    return True


@transaction.atomic
def unlike_post(*, user, post_id) -> bool:
    """Remove curtida de uma publicação."""
    deleted, _ = PostLike.objects.filter(post_id=post_id, user=user).delete()
    if deleted:
        Post.objects.filter(pk=post_id, likes_count__gt=0).update(likes_count=F("likes_count") - 1)
        return True
    return False


@transaction.atomic
def bookmark_post(*, user, post_id) -> bool:
    """Salva publicação nos favoritos do usuário."""
    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        return False

    if not can_view_post(user, post):
        return False

    _, created = PostBookmark.objects.get_or_create(post=post, user=user)
    if created:
        Post.objects.filter(pk=post.pk).update(bookmarks_count=F("bookmarks_count") + 1)
    return True


@transaction.atomic
def unbookmark_post(*, user, post_id) -> bool:
    """Remove publicação dos favoritos."""
    deleted, _ = PostBookmark.objects.filter(post_id=post_id, user=user).delete()
    if deleted:
        Post.objects.filter(pk=post_id, bookmarks_count__gt=0).update(
            bookmarks_count=F("bookmarks_count") - 1
        )
        return True
    return False


def create_draft(*, author, content_text: str) -> Draft:
    """Cria um rascunho de publicação isolado por autor."""
    max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
    if len(content_text) > max_chars:
        raise ValueError(f"Conteúdo excede o limite de {max_chars} caracteres.")
    return Draft.objects.create(author=author, content_text=content_text)


def delete_draft(*, author, draft_id) -> bool:
    """Exclui rascunho do autor."""
    deleted, _ = Draft.objects.filter(pk=draft_id, author=author).delete()
    return bool(deleted)
