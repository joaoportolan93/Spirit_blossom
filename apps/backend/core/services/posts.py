"""
Operações de leitura e escrita para posts e rascunhos (ADR-N2 / Onda 3b).
"""

import unicodedata
import uuid
from typing import Optional

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q, QuerySet
from django.utils import timezone

from core.models import Draft, Hashtag, Mute, Notification, Post, PostBookmark, PostLike
from core.utils.text_entities import extract_hashtags
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


def list_posts_keyset(
    *,
    user,
    cursor: Optional[str] = None,
    limit: int = 20,
    hashtag: Optional[str] = None,
) -> QuerySet:
    """
    Lista posts visíveis para o usuário com keyset pagination (cursor por UUIDv7).
    Suporta filtro opcional por hashtag (?hashtag=tag), sempre via visible_posts_for (ADR-N21).
    """
    qs = visible_posts_for(user).order_by("-id")
    if hashtag is not None and hashtag.strip():
        clean_tag = unicodedata.normalize("NFC", hashtag).lstrip("#").strip().lower()
        if not clean_tag:
            return qs.none()
        qs = qs.filter(hashtags__name=clean_tag)
    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor inválido.")
        qs = qs.filter(id__lt=cursor_uuid)
    return qs[:limit]


def get_trending_hashtags(*, user, limit: int = 10) -> list[dict]:
    """
    Retorna hashtags populares baseadas estritamente em posts públicos visíveis
    ao viewer via visible_posts_for (ADR-N21 / ADR-N24).
    Posts privados, de círculo, silenciados ou de usuários bloqueados nunca inflam contagens.
    """
    clamped_limit = max(1, min(limit, 30))
    visible_qs = (
        visible_posts_for(user)
        .filter(visibility=Post.Visibility.PUBLIC)
        .exclude(author__profile__is_private=True)
    )
    if user is not None and getattr(user, "is_authenticated", False):
        muted_by_user = Mute.objects.filter(muter=user, muted=OuterRef("author"))
        visible_qs = visible_qs.exclude(Exists(muted_by_user))
    visible_public_ids = visible_qs.values("id")
    tags = (
        Hashtag.objects.filter(posts__id__in=visible_public_ids)
        .annotate(posts_count=Count("posts", distinct=True))
        .filter(posts_count__gt=0)
        .order_by("-posts_count", "name")[:clamped_limit]
    )
    return [{"name": tag.name, "posts_count": tag.posts_count} for tag in tags]


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


def list_posts_for_export(*, author) -> QuerySet:
    """Retorna todos os posts do autor para exportação LGPD (sem filtro de visibilidade)."""
    return Post.objects.filter(author=author).order_by("-created_at")


def increment_post_comments_count(post_id, amount: int = 1) -> None:
    """Incrementa atômica e seguramente o contador de comentários do post."""
    if amount <= 0:
        return
    Post.objects.filter(pk=post_id).update(comments_count=F("comments_count") + amount)


def decrement_post_comments_count(post_id, amount: int = 1) -> None:
    """Decrementa atômica e seguramente o contador de comentários do post."""
    if amount <= 0:
        return
    Post.objects.filter(pk=post_id, comments_count__gte=amount).update(
        comments_count=F("comments_count") - amount
    )


def increment_post_hidden_comments_count(post_id) -> None:
    """Incrementa contador de respostas ocultas no post."""
    Post.objects.filter(pk=post_id).update(hidden_comments_count=F("hidden_comments_count") + 1)


def decrement_post_hidden_comments_count(post_id) -> None:
    """Decrementa contador de respostas ocultas no post."""
    Post.objects.filter(pk=post_id, hidden_comments_count__gt=0).update(
        hidden_comments_count=F("hidden_comments_count") - 1
    )


def resync_all_post_counters() -> None:
    """Ressincroniza contadores desnormalizados de curtidas e comentários nos posts."""
    from comments.models import Comment

    candidate_posts = Post.objects.filter(
        Q(likes_count__gt=0)
        | Q(comments_count__gt=0)
        | Q(likes__isnull=False)
        | Q(comments__isnull=False)
    ).distinct()
    for post in candidate_posts:
        real_likes = PostLike.objects.filter(post=post).count()
        real_comments = Comment.objects.filter(post=post, is_deleted=False).count()
        if post.likes_count != real_likes or post.comments_count != real_comments:
            Post.objects.filter(pk=post.pk).update(
                likes_count=real_likes,
                comments_count=real_comments,
            )


# -----------------------------------------------------------------------------
# Operações de Escrita (Mutações)
# -----------------------------------------------------------------------------


def sync_post_hashtags(post: Post) -> None:
    """Sincroniza entidades #hashtag de um post de forma transacional."""
    tag_names = extract_hashtags(post.content_text)
    if not tag_names:
        post.hashtags.clear()
        return

    existing = {h.name: h for h in Hashtag.objects.filter(name__in=tag_names)}
    hashtag_objs = []
    for name in tag_names:
        obj = existing.get(name)
        if obj is None:
            obj, _ = Hashtag.objects.get_or_create(name=name)
            existing[name] = obj
        hashtag_objs.append(obj)
    post.hashtags.set(hashtag_objs)


@transaction.atomic
def create_post(
    *,
    author,
    content_text: str = "",
    visibility: str = Post.Visibility.PUBLIC,
    image=None,
    video=None,
) -> Post:
    """
    Cria um post validando texto/mídia, sanitizando arquivos, extraindo hashtags
    e notificando menções.
    """
    from core.utils.media_security import sanitize_media_image, sanitize_media_video

    text = content_text or ""
    max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
    if len(text) > max_chars:
        raise ValueError(f"Conteúdo excede o limite de {max_chars} caracteres.")

    if image and video:
        raise ValueError("Envie apenas uma imagem/GIF ou um vídeo por publicação.")

    if not text.strip() and not image and not video:
        raise ValueError("A publicação precisa de texto ou mídia.")

    clean_image = sanitize_media_image(image) if image else None
    clean_video = sanitize_media_video(video) if video else None

    post = Post.objects.create(
        author=author,
        content_text=text,
        visibility=visibility,
        image=clean_image,
        video=clean_video,
    )
    sync_post_hashtags(post)

    from core.services.notifications import notify_mentions_for_content

    if text.strip():
        notify_mentions_for_content(
            sender=author,
            content_text=text,
            post=post,
            ref_id=str(post.id),
        )
    return post


@transaction.atomic
def update_post(*, post: Post, user, content_text: str) -> Post:
    """Atualiza o conteúdo de texto da publicação mantendo sua visibilidade."""
    if post.author != user:
        raise PermissionError("Sem permissão para editar esta publicação.")
    max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
    cleaned_text = (content_text or "").strip()
    if not cleaned_text and not post.image and not post.video:
        raise ValueError("Conteúdo não pode ser vazio.")
    if len(cleaned_text) > max_chars:
        raise ValueError(f"Conteúdo excede o limite de {max_chars} caracteres.")
    post.content_text = cleaned_text
    post.is_edited = True
    post.edited_at = timezone.now()
    post.save(update_fields=["content_text", "is_edited", "edited_at"])
    sync_post_hashtags(post)

    from core.services.notifications import notify_mentions_for_content

    if cleaned_text:
        notify_mentions_for_content(
            sender=user,
            content_text=cleaned_text,
            post=post,
            ref_id=str(post.id),
        )
    return post


def delete_post(*, post: Post, user) -> bool:
    """
    Apaga um post se o usuário for o autor.
    Remove comentários, curtidas, favoritos, notificações e arquivos de mídia.
    """
    if post.author != user:
        raise PermissionError("Sem permissão para excluir esta publicação.")

    from core.utils.media_security import delete_media_file

    media_to_delete = []
    if post.image and post.image.name:
        media_to_delete.append((post.image.storage, post.image.name))
    if post.video and post.video.name:
        media_to_delete.append((post.video.storage, post.video.name))

    for c in post.comments.all():
        if c.image and c.image.name:
            media_to_delete.append((c.image.storage, c.image.name))
        if c.video and c.video.name:
            media_to_delete.append((c.video.storage, c.video.name))

    with transaction.atomic():
        comment_ids = list(post.comments.values_list("id", flat=True))
        notif_q = Q(ref_id=post.id)
        if comment_ids:
            notif_q |= Q(ref_id__in=comment_ids)
        Notification.objects.filter(notif_q).delete()
        post.likes.all().delete()
        post.bookmarks.all().delete()
        post.comments.all().delete()
        post.delete()

    for storage, name in media_to_delete:
        try:
            storage.delete(name)
        except Exception:
            pass

    # Garante referência utilizada mesmo em mocks simples
    _ = delete_media_file
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
