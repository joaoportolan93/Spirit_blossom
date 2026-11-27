"""
Operações de leitura e escrita para posts e rascunhos (ADR-N2 / Onda 3b).
"""

import mimetypes
import unicodedata
import uuid
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q, QuerySet
from django.utils import timezone

from core.models import (
    Draft,
    DraftMedia,
    Hashtag,
    Mute,
    Notification,
    Post,
    PostBookmark,
    PostLike,
    PostMedia,
    UserProfile,
)
from core.utils.text_entities import extract_hashtags
from core.utils.visibility import can_view_post, is_user_blocked, visible_posts_for

_UNSET = object()
_ALLOWED_EPHEMERAL_DURATIONS = {24, 48, 168, None}

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
        .prefetch_related("media")
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
    qs = visible_posts_for(user).order_by("-id").prefetch_related("media")
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
        return (
            qs.select_related("author", "author__profile").prefetch_related("media").get(pk=post_id)
        )
    except Post.DoesNotExist:
        return None


def list_bookmarked_posts(*, user, cursor: Optional[str] = None, limit: int = 20) -> QuerySet:
    """
    Lista publicações salvas pelo usuário que ainda são visíveis para ele (ADR-N21 / Onda 3b).
    Se o post tornou-se inacessível (ex: autor bloqueou ou privou conta), é omitido.
    """
    bookmarked_ids = PostBookmark.objects.filter(user=user).values("post_id")
    qs = (
        visible_posts_for(user)
        .filter(id__in=bookmarked_ids)
        .order_by("-id")
        .prefetch_related("media")
    )

    if cursor:
        try:
            cursor_uuid = uuid.UUID(cursor)
        except (ValueError, AttributeError):
            raise ValueError("Cursor inválido.")
        qs = qs.filter(id__lt=cursor_uuid)

    return qs[:limit]


def list_drafts(*, author) -> QuerySet:
    """Lista rascunhos de publicações isolados estritamente pelo autor."""
    return Draft.objects.filter(author=author).prefetch_related("media").order_by("-updated_at")


def get_draft_for_author(*, author, draft_id) -> Optional[Draft]:
    """Busca rascunho pertencente ao autor com prefetch de mídia."""
    return Draft.objects.filter(pk=draft_id, author=author).prefetch_related("media").first()


def list_posts_for_export(*, author) -> QuerySet:
    """Retorna todos os posts do autor para exportação LGPD (sem filtro de visibilidade)."""
    return Post.objects.filter(author=author).prefetch_related("media").order_by("-created_at")


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


def _delete_storage_paths(paths: list[tuple]) -> None:
    """Remove fisicamente arquivos de storage ignorando ausência prévia."""
    for storage, name in paths:
        if name:
            try:
                storage.delete(name)
            except Exception:
                pass


def _save_sanitized_media_list(
    model_cls,
    parent_kwargs: dict,
    sanitized_images: list,
    alt_texts: Optional[list] = None,
) -> None:
    """Persiste lista ordenada de PostMedia ou DraftMedia."""
    alt_list = alt_texts or []
    for idx, clean_file in enumerate(sanitized_images):
        alt = (alt_list[idx] if idx < len(alt_list) else "") or ""
        width = getattr(clean_file, "_post_media_width", None)
        height = getattr(clean_file, "_post_media_height", None)
        media_obj = model_cls(
            **parent_kwargs,
            order=idx,
            alt_text=alt[:300],
            width=width,
            height=height,
        )
        media_obj.file.save(clean_file.name, clean_file, save=False)
        media_obj.save()


@transaction.atomic
def create_post(
    *,
    author,
    content_text: str = "",
    visibility: str = Post.Visibility.PUBLIC,
    image=None,
    video=None,
    images: Optional[list] = None,
    alt_texts: Optional[list] = None,
    ephemeral_duration_hours: Optional[int] = None,
) -> Post:
    """
    Cria um post validando texto/mídia, sanitizando arquivos, extraindo hashtags
    e notificando menções.

    Onda 9: suporta múltiplas imagens (images + alt_texts) e posts efêmeros.
    Mantém retrocompatibilidade com image/video (single media).
    expires_at é definido AQUI (no momento da publicação), nunca antes.
    """
    from core.utils.image_security import sanitize_post_media_images
    from core.utils.media_security import sanitize_media_image, sanitize_media_video

    text = content_text or ""
    max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
    if len(text) > max_chars:
        raise ValueError(f"Conteúdo excede o limite de {max_chars} caracteres.")

    if ephemeral_duration_hours not in _ALLOWED_EPHEMERAL_DURATIONS:
        raise ValueError("Duração efêmera inválida. Use 24, 48, 168 ou null.")

    has_legacy_image = bool(image)
    has_legacy_video = bool(video)
    has_multi_images = bool(images)

    if has_legacy_image and has_legacy_video:
        raise ValueError("Envie apenas uma imagem/GIF ou um vídeo por publicação.")
    if (has_legacy_image or has_legacy_video) and has_multi_images:
        raise ValueError("Use imagens[] OU image/video, não ambos.")

    if not text.strip() and not has_legacy_image and not has_legacy_video and not has_multi_images:
        raise ValueError("A publicação precisa de texto ou mídia.")

    clean_image = sanitize_media_image(image) if image else None
    clean_video = sanitize_media_video(video) if video else None

    sanitized_images = sanitize_post_media_images(images) if has_multi_images else []

    # expires_at definido no momento da publicação (nunca antes)
    expires_at = (
        timezone.now() + timedelta(hours=ephemeral_duration_hours)
        if ephemeral_duration_hours
        else None
    )

    post = Post.objects.create(
        author=author,
        content_text=text,
        visibility=visibility,
        image=clean_image,
        video=clean_video,
        expires_at=expires_at,
        ephemeral_duration_hours=ephemeral_duration_hours if ephemeral_duration_hours else None,
    )

    if sanitized_images:
        _save_sanitized_media_list(PostMedia, {"post": post}, sanitized_images, alt_texts)

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


def update_post(
    *,
    post: Post,
    user,
    content_text=_UNSET,
    images: Optional[list] = None,
    alt_texts: Optional[list] = None,
    remove_media_ids: Optional[list] = None,
    media_alt_updates: Optional[dict] = None,
    image=None,
    video=None,
    remove_image: bool = False,
    remove_video: bool = False,
) -> Post:
    """
    Atualiza texto e/ou mídias de uma publicação mantendo sua visibilidade.
    Permite remover, substituir ou adicionar até 4 imagens sanitizadas.
    """
    from core.utils.image_security import MAX_POST_MEDIA_COUNT, sanitize_post_media_images
    from core.utils.media_security import sanitize_media_image, sanitize_media_video

    if post.author != user:
        raise PermissionError("Sem permissão para editar esta publicação.")

    max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
    update_fields = ["is_edited", "edited_at"]

    if content_text is not _UNSET:
        cleaned_text = (content_text or "").strip()
        if len(cleaned_text) > max_chars:
            raise ValueError(f"Conteúdo excede o limite de {max_chars} caracteres.")
        post.content_text = cleaned_text
        update_fields.append("content_text")
    else:
        cleaned_text = (post.content_text or "").strip()

    old_files = []

    with transaction.atomic():
        # 1. Remoção/substituição de mídia legada (image/video)
        if remove_image and post.image and post.image.name:
            old_files.append((post.image.storage, post.image.name))
            post.image = None
            update_fields.append("image")
        if remove_video and post.video and post.video.name:
            old_files.append((post.video.storage, post.video.name))
            post.video = None
            update_fields.append("video")

        if image is not None:
            if post.image and post.image.name:
                old_files.append((post.image.storage, post.image.name))
            post.image = sanitize_media_image(image)
            update_fields.append("image")

        if video is not None:
            if post.video and post.video.name:
                old_files.append((post.video.storage, post.video.name))
            post.video = sanitize_media_video(video)
            update_fields.append("video")

        # 2. Remoção seletiva de PostMedia existentes
        if remove_media_ids:
            to_remove = list(post.media.filter(id__in=remove_media_ids))
            for pm in to_remove:
                if pm.file and pm.file.name:
                    old_files.append((pm.file.storage, pm.file.name))
            if to_remove:
                post.media.filter(id__in=[pm.id for pm in to_remove]).delete()

        # 3. Atualização de ALT de PostMedia existentes e reordenação sequencial (0..3)
        remaining_media = list(post.media.order_by("order"))
        alt_map = media_alt_updates if isinstance(media_alt_updates, dict) else {}
        for idx, pm in enumerate(remaining_media):
            changed_pm_fields = []
            if pm.order != idx:
                pm.order = idx
                changed_pm_fields.append("order")
            pm_id_str = str(pm.id)
            if pm_id_str in alt_map:
                new_alt = (str(alt_map[pm_id_str]) if alt_map[pm_id_str] is not None else "")[:300]
                if pm.alt_text != new_alt:
                    pm.alt_text = new_alt
                    changed_pm_fields.append("alt_text")
            if changed_pm_fields:
                pm.save(update_fields=changed_pm_fields)

        # 4. Adição de novas imagens (multi-imagem)
        if images:
            if post.image or post.video:
                raise ValueError("Use imagens[] OU image/video, não ambos.")
            if len(remaining_media) + len(images) > MAX_POST_MEDIA_COUNT:
                raise ValueError(f"Máximo de {MAX_POST_MEDIA_COUNT} imagens por publicação.")
            sanitized_new = sanitize_post_media_images(images)
            alt_list = alt_texts or []
            start_order = len(remaining_media)
            for offset, clean_file in enumerate(sanitized_new):
                alt = (alt_list[offset] if offset < len(alt_list) else "") or ""
                width = getattr(clean_file, "_post_media_width", None)
                height = getattr(clean_file, "_post_media_height", None)
                pm = PostMedia(
                    post=post,
                    order=start_order + offset,
                    alt_text=alt[:300],
                    width=width,
                    height=height,
                )
                pm.file.save(clean_file.name, clean_file, save=False)
                pm.save()

        if post.image and post.video:
            raise ValueError("Envie apenas uma imagem/GIF ou um vídeo por publicação.")
        has_any_multi = post.media.exists()
        if (post.image or post.video) and has_any_multi:
            raise ValueError("Use imagens[] OU image/video, não ambos.")
        if not cleaned_text and not post.image and not post.video and not has_any_multi:
            raise ValueError("Conteúdo não pode ser vazio.")

        post.is_edited = True
        post.edited_at = timezone.now()
        post.save(update_fields=list(dict.fromkeys(update_fields)))
        if hasattr(post, "_prefetched_objects_cache"):
            post._prefetched_objects_cache.pop("media", None)

        sync_post_hashtags(post)

        from core.services.notifications import notify_mentions_for_content

        if content_text is not _UNSET and cleaned_text:
            notify_mentions_for_content(
                sender=user,
                content_text=cleaned_text,
                post=post,
                ref_id=str(post.id),
            )

    _delete_storage_paths(old_files)
    return post


def delete_post(*, post: Post, user) -> bool:
    """
    Apaga um post se o usuário for o autor.
    Remove comentários, curtidas, favoritos, notificações e arquivos de mídia.
    Onda 9: também remove PostMedia físicos (post_media/).
    """
    if post.author != user:
        raise PermissionError("Sem permissão para excluir esta publicação.")

    from core.utils.media_security import delete_media_file

    media_to_delete = []
    if post.image and post.image.name:
        media_to_delete.append((post.image.storage, post.image.name))
    if post.video and post.video.name:
        media_to_delete.append((post.video.storage, post.video.name))

    # Onda 9: coleta PostMedia físicos
    post_media_files = []
    for pm in post.media.all():
        if pm.file and pm.file.name:
            post_media_files.append((pm.file.storage, pm.file.name))

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
        post.media.all().delete()  # Onda 9: PostMedia (FK CASCADE já cobre, mas explicitamos)
        post.comments.all().delete()
        post.delete()

    for storage, name in media_to_delete + post_media_files:
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


@transaction.atomic
def create_draft(
    *,
    author,
    content_text: str = "",
    visibility: str = Post.Visibility.PUBLIC,
    images: Optional[list] = None,
    alt_texts: Optional[list] = None,
    ephemeral_duration_hours: Optional[int] = None,
) -> Draft:
    """
    Cria um rascunho de publicação isolado por autor.
    Onda 9: aceita múltiplas imagens e ephemeral_duration_hours (expires_at NÃO inicia aqui).
    """
    from core.utils.image_security import sanitize_post_media_images

    text = content_text or ""
    max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
    if len(text) > max_chars:
        raise ValueError(f"Conteúdo excede o limite de {max_chars} caracteres.")
    if ephemeral_duration_hours not in _ALLOWED_EPHEMERAL_DURATIONS:
        raise ValueError("Duração efêmera inválida. Use 24, 48, 168 ou null.")
    if not text.strip() and not images:
        raise ValueError("O rascunho precisa de texto ou mídia.")

    sanitized_images = sanitize_post_media_images(images) if images else []
    draft = Draft.objects.create(
        author=author,
        content_text=text,
        visibility=visibility,
        ephemeral_duration_hours=ephemeral_duration_hours if ephemeral_duration_hours else None,
    )
    if sanitized_images:
        _save_sanitized_media_list(DraftMedia, {"draft": draft}, sanitized_images, alt_texts)
    return draft


@transaction.atomic
def update_draft(
    *,
    draft: Draft,
    author,
    content_text=_UNSET,
    visibility=_UNSET,
    images=_UNSET,
    alt_texts=_UNSET,
    ephemeral_duration_hours=_UNSET,
    clear_images: bool = False,
) -> Draft:
    """Atualiza rascunho existente (PATCH) sem iniciar expires_at."""
    from core.utils.image_security import sanitize_post_media_images

    if draft.author != author:
        raise PermissionError("Sem permissão para editar este rascunho.")

    max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
    update_fields = ["updated_at"]

    if content_text is not _UNSET:
        text = content_text or ""
        if len(text) > max_chars:
            raise ValueError(f"Conteúdo excede o limite de {max_chars} caracteres.")
        draft.content_text = text
        update_fields.append("content_text")

    if visibility is not _UNSET and visibility is not None:
        draft.visibility = visibility
        update_fields.append("visibility")

    if ephemeral_duration_hours is not _UNSET:
        if ephemeral_duration_hours not in _ALLOWED_EPHEMERAL_DURATIONS:
            raise ValueError("Duração efêmera inválida. Use 24, 48, 168 ou null.")
        draft.ephemeral_duration_hours = ephemeral_duration_hours or None
        update_fields.append("ephemeral_duration_hours")

    old_files = []
    if clear_images or (images is not _UNSET and images is not None):
        old_files = [
            (dm.file.storage, dm.file.name) for dm in draft.media.all() if dm.file and dm.file.name
        ]
        if images is not _UNSET and images:
            sanitized_images = sanitize_post_media_images(images)
            draft.media.all().delete()
            alt_list = [] if alt_texts is _UNSET else alt_texts
            _save_sanitized_media_list(DraftMedia, {"draft": draft}, sanitized_images, alt_list)
        else:
            draft.media.all().delete()
    elif alt_texts is not _UNSET and isinstance(alt_texts, list):
        for idx, dm in enumerate(draft.media.order_by("order")):
            if idx < len(alt_texts):
                dm.alt_text = (alt_texts[idx] or "")[:300]
                dm.save(update_fields=["alt_text"])

    if not (draft.content_text or "").strip() and not draft.media.exists():
        raise ValueError("O rascunho precisa de texto ou mídia.")

    draft.save(update_fields=list(dict.fromkeys(update_fields)))
    if hasattr(draft, "_prefetched_objects_cache"):
        draft._prefetched_objects_cache.pop("media", None)
    transaction.on_commit(lambda: _delete_storage_paths(old_files))
    return draft


@transaction.atomic
def publish_draft(*, draft: Draft, author) -> Post:
    """
    Publica um rascunho transformando-o em Post.
    expires_at só é calculado AQUI no momento da publicação.
    """
    from django.core.files.base import ContentFile

    if draft.author != author:
        raise PermissionError("Sem permissão para publicar este rascunho.")

    dur = draft.ephemeral_duration_hours
    expires_at = timezone.now() + timedelta(hours=dur) if dur else None

    draft_media_items = list(draft.media.order_by("order"))
    if not (draft.content_text or "").strip() and not draft_media_items:
        raise ValueError("A publicação precisa de texto ou mídia.")

    post = Post.objects.create(
        author=author,
        content_text=draft.content_text,
        visibility=draft.visibility,
        expires_at=expires_at,
        ephemeral_duration_hours=dur,
    )

    old_draft_files = []
    for idx, dm in enumerate(draft_media_items):
        if dm.file and dm.file.name:
            old_draft_files.append((dm.file.storage, dm.file.name))
            dm.file.open("rb")
            try:
                raw_bytes = dm.file.read()
            finally:
                dm.file.close()
            ext = dm.file.name.rsplit(".", 1)[-1] if "." in dm.file.name else "jpg"
            new_name = f"{uuid.uuid4().hex}.{ext}"
            pm = PostMedia(
                post=post,
                order=idx,
                alt_text=dm.alt_text,
                width=dm.width,
                height=dm.height,
            )
            pm.file.save(new_name, ContentFile(raw_bytes), save=False)
            pm.save()

    sync_post_hashtags(post)
    text = post.content_text or ""
    if text.strip():
        from core.services.notifications import notify_mentions_for_content

        notify_mentions_for_content(
            sender=author,
            content_text=text,
            post=post,
            ref_id=str(post.id),
        )

    draft.delete()
    transaction.on_commit(lambda: _delete_storage_paths(old_draft_files))
    return post


def delete_draft(*, author, draft_id) -> bool:
    """Exclui rascunho do autor e remove mídias físicas associadas."""
    draft = Draft.objects.filter(pk=draft_id, author=author).prefetch_related("media").first()
    if not draft:
        return False
    files = [
        (dm.file.storage, dm.file.name) for dm in draft.media.all() if dm.file and dm.file.name
    ]
    draft.delete()
    _delete_storage_paths(files)
    return True


def purge_expired_ephemeral_posts() -> int:
    """
    Remove em lote posts efêmeros expirados (expires_at <= now) e seus arquivos físicos.
    Centraliza queries em Post.objects neste módulo (ADR-N21).
    """
    now = timezone.now()
    expired_posts = list(
        Post.objects.filter(
            expires_at__isnull=False,
            expires_at__lte=now,
        ).prefetch_related("media", "comments")
    )
    if not expired_posts:
        return 0

    files_to_delete = []
    for post in expired_posts:
        for pm in post.media.all():
            if pm.file and pm.file.name:
                files_to_delete.append((pm.file.storage, pm.file.name))
        if post.image and post.image.name:
            files_to_delete.append((post.image.storage, post.image.name))
        if post.video and post.video.name:
            files_to_delete.append((post.video.storage, post.video.name))
        for c in post.comments.all():
            if c.image and c.image.name:
                files_to_delete.append((c.image.storage, c.image.name))
            if c.video and c.video.name:
                files_to_delete.append((c.video.storage, c.video.name))

    ids = [p.id for p in expired_posts]
    _, deleted_by_model = Post.objects.filter(id__in=ids).delete()
    _delete_storage_paths(files_to_delete)
    return deleted_by_model.get(Post._meta.label, 0)


def can_view_media_path(*, user, relative_path: str) -> bool:
    """
    Autoriza entrega de arquivo de mídia respeitando ADR-N21 e ADR-N24.
    Fail-closed: qualquer caminho não mapeado retorna False (view responde 404).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if not relative_path or ".." in relative_path.split("/"):
        return False

    clean_rel = relative_path.lstrip("/")

    if clean_rel.startswith("post_media/"):
        pm = PostMedia.objects.select_related("post").filter(file=clean_rel).first()
        return bool(pm and can_view_post(user, pm.post))

    if clean_rel.startswith(("post_images/", "post_videos/")):
        post = Post.objects.filter(Q(image=clean_rel) | Q(video=clean_rel)).first()
        return bool(post and can_view_post(user, post))

    if clean_rel.startswith(("comment_images/", "comment_videos/")):
        from comments.models import Comment

        comment = (
            Comment.objects.select_related("post", "author")
            .filter(Q(image=clean_rel) | Q(video=clean_rel), is_deleted=False, is_hidden=False)
            .first()
        )
        if not comment or not can_view_post(user, comment.post):
            return False
        if comment.author and is_user_blocked(user, comment.author):
            return False
        return True

    if clean_rel.startswith("draft_media/"):
        dm = DraftMedia.objects.select_related("draft").filter(file=clean_rel).first()
        return bool(dm and dm.draft.author_id == user.id)

    if clean_rel.startswith("avatars/"):
        prof = UserProfile.objects.select_related("user").filter(avatar=clean_rel).first()
        if not prof or not getattr(prof.user, "is_valid_for_auth", True):
            return False
        return not is_user_blocked(user, prof.user)

    return False


def guess_media_content_type(file_path: str) -> str:
    """Inferência segura de Content-Type para mídia servida pelo backend."""
    mime, _ = mimetypes.guess_type(file_path)
    return mime or "application/octet-stream"


# -----------------------------------------------------------------------------
# Helpers administrativos e de moderação sobre Post (centraliza Post.objects)
# -----------------------------------------------------------------------------


def get_post_by_id_for_moderation(post_id) -> Optional[Post]:
    """Busca publicação sem filtro de visibilidade para moderação/denúncia."""
    return Post.objects.filter(pk=post_id).select_related("author").first()


def get_posts_map_for_moderation(post_ids: list) -> dict[str, Post]:
    """Carrega lote de publicações para a fila de moderação sem N+1."""
    if not post_ids:
        return {}
    return {str(p.id): p for p in Post.objects.filter(id__in=post_ids).select_related("author")}


def count_posts_for_author(user) -> int:
    """Conta todas as publicações de um autor para inspeção administrativa."""
    return Post.objects.filter(author=user).count()


def delete_posts_for_user(user) -> None:
    """Remove fisicamente todas as publicações e mídias de um usuário na exclusão definitiva."""
    from core.utils.media_security import delete_media_file

    user_posts = list(Post.objects.filter(author=user).prefetch_related("media"))
    for p in user_posts:
        delete_media_file(p.image)
        delete_media_file(p.video)
        # Onda 9: remove PostMedia físicos
        for pm in p.media.all():
            if pm.file and pm.file.name:
                try:
                    pm.file.storage.delete(pm.file.name)
                except Exception:
                    pass
    Post.objects.filter(author=user).delete()


def delete_drafts_for_user(user) -> None:
    """Remove fisicamente rascunhos e mídias de rascunho de um usuário na exclusão de conta."""
    user_drafts = list(Draft.objects.filter(author=user).prefetch_related("media"))
    files = []
    for d in user_drafts:
        for dm in d.media.all():
            if dm.file and dm.file.name:
                files.append((dm.file.storage, dm.file.name))
    Draft.objects.filter(author=user).delete()
    _delete_storage_paths(files)


def get_admin_post_stats(today, seven_days_ago) -> dict:
    """Retorna contagens e série diária de posts para o dashboard administrativo."""
    from django.db.models.functions import TruncDate

    total_posts = Post.objects.count()
    hidden_posts = Post.objects.filter(is_hidden=True).count()
    new_posts_today = Post.objects.filter(created_at__date=today).count()
    posts_by_day = dict(
        Post.objects.filter(created_at__date__gte=seven_days_ago)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .values_list("day", "total")
    )
    return {
        "total_posts": total_posts,
        "hidden_posts": hidden_posts,
        "new_posts_today": new_posts_today,
        "posts_by_day": posts_by_day,
    }
