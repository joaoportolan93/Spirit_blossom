"""
Operações de escrita para posts (ADR-N2 / Onda 3b).
"""

from django.conf import settings
from django.db import transaction
from django.db.models import F

from social.selectors import can_view_post

from .models import Draft, Post, PostBookmark, PostLike


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
        from notifications.services import notify_post_liked
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
