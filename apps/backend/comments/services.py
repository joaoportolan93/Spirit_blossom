"""
Camada de serviços e regras de negócio para Comentários (Onda 4 / ADR-N24).
Operações de criação, edição, exclusão com tombstone, curtidas e favoritos.
"""

from typing import List, Optional, Tuple

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from comments.models import Comment, CommentBookmark, CommentLike
from core.models import Block, Mute, Notification, Post
from core.services.notifications import create_notification, notify_mentions_for_content
from core.services.posts import (
    decrement_post_comments_count,
    decrement_post_hidden_comments_count,
    increment_post_comments_count,
    increment_post_hidden_comments_count,
)
from core.utils.visibility import can_view_post

MAX_COMMENT_DEPTH = 50
MAX_COMMENT_LENGTH = 1000


def is_in_hidden_thread(comment: Comment) -> bool:
    """Verifica se o comentário ou qualquer ancestral na árvore está oculto."""
    curr = comment
    while curr:
        if getattr(curr, "is_hidden", False):
            return True
        curr = curr.parent
    return False


def _get_comment_descendants(comment: Comment) -> List[Comment]:
    """Coleta todos os descendentes recursivamente via busca em profundidade."""
    descendants = []
    frontier = list(comment.replies.all())
    while frontier:
        child = frontier.pop(0)
        descendants.append(child)
        frontier.extend(list(child.replies.all()))
    return descendants


# -----------------------------------------------------------------------------
# Disparo de Notificações
# -----------------------------------------------------------------------------


def notify_comment_created(*, sender, comment: Comment) -> None:
    """
    Notifica o destinatário relevante sobre um novo comentário ou resposta:
    - Se for resposta (parent existe): notifica o autor do comentário pai.
    - Se for comentário raiz: notifica o autor da publicação.
    Regras de supressão:
    - Não notifica a si mesmo.
    - Não notifica se houver bloqueio bilateral.
    - Não notifica se recipient silenciou sender.
    - Nunca notifica se o post não for visível para ambos.
    - Dispara em transaction.on_commit.
    """
    post = comment.post
    parent = comment.parent

    if parent and parent.author:
        recipient = parent.author
        notif_type = Notification.Type.REPLY
    else:
        recipient = post.author
        notif_type = Notification.Type.REPLY

    if not recipient or sender == recipient:
        return

    profile = getattr(recipient, "profile", None)
    if profile is not None and not profile.notify_comments:
        return

    # Conversa oculta não gera notificações
    if is_in_hidden_thread(comment):
        return

    # Bloqueio bilateral
    if Block.objects.filter(
        Q(blocker=recipient, blocked=sender) | Q(blocker=sender, blocked=recipient)
    ).exists():
        return

    # Silenciamento
    if Mute.objects.filter(muter=recipient, muted=sender).exists():
        return

    # Visibilidade do post
    if not can_view_post(sender, post) or not can_view_post(recipient, post):
        return

    def _dispatch():
        create_notification(
            recipient=recipient,
            sender=sender,
            notification_type=notif_type,
            ref_id=str(comment.id),
        )

    transaction.on_commit(_dispatch)


def notify_comment_liked(*, sender, comment: Comment) -> None:
    """
    Notifica o autor do comentário sobre uma nova curtida.
    Regras de supressão idênticas a curtida de publicação.
    """
    recipient = comment.author
    if not recipient or sender == recipient:
        return

    profile = getattr(recipient, "profile", None)
    if profile is not None and not profile.notify_likes:
        return

    # Conversa oculta não gera notificações
    if is_in_hidden_thread(comment):
        return

    if Block.objects.filter(
        Q(blocker=recipient, blocked=sender) | Q(blocker=sender, blocked=recipient)
    ).exists():
        return

    if Mute.objects.filter(muter=recipient, muted=sender).exists():
        return

    if not can_view_post(sender, comment.post) or not can_view_post(recipient, comment.post):
        return

    def _dispatch():
        create_notification(
            recipient=recipient,
            sender=sender,
            notification_type=Notification.Type.LIKE,
            ref_id=str(comment.id),
        )

    transaction.on_commit(_dispatch)


# -----------------------------------------------------------------------------
# Operações de Escrita (Mutações)
# -----------------------------------------------------------------------------


def create_comment(
    *,
    author,
    post: Post,
    content_text: str = "",
    parent: Optional[Comment] = None,
    image=None,
    video=None,
) -> Comment:
    """
    Cria um comentário ou resposta respeitando:
    - can_view_post como guardião estrito.
    - Bloqueio bidirecional com o dono do post e com o autor do comentário pai.
    - Sanitização segura de imagem/GIF/vídeo quando anexado.
    - Limite de profundidade alto (MAX_COMMENT_DEPTH = 50) contra DoS recursivo.
    - Incremento atômico de comments_count no post e replies_count no pai via F().
    - Disparo transacional de notificação via on_commit.
    """
    from core.utils.media_security import (
        MediaSanitizationError,
        sanitize_media_image,
        sanitize_media_video,
    )

    if not can_view_post(author, post):
        raise PermissionDenied(_("You cannot view or comment on this post."))

    # Bloqueio bidirecional com autor do post
    if Block.objects.filter(
        Q(blocker=author, blocked=post.author) | Q(blocker=post.author, blocked=author)
    ).exists():
        raise PermissionDenied(_("Interaction blocked by privacy settings."))

    cleaned_text = (content_text or "").strip()
    if image and video:
        raise ValidationError({"detail": _("Send either an image/GIF or a video, not both.")})
    if not cleaned_text and not image and not video:
        raise ValidationError({"content_text": _("Comment content cannot be empty.")})
    if len(cleaned_text) > MAX_COMMENT_LENGTH:
        raise ValidationError(
            {"content_text": _("Comment exceeds maximum length of 1000 characters.")}
        )

    clean_image = None
    clean_video = None
    if image:
        try:
            clean_image = sanitize_media_image(image)
        except MediaSanitizationError as exc:
            raise ValidationError({"image": str(exc)}) from exc
    if video:
        try:
            clean_video = sanitize_media_video(video)
        except MediaSanitizationError as exc:
            raise ValidationError({"video": str(exc)}) from exc

    depth = 0
    if parent is not None:
        if parent.post_id != post.id:
            raise ValidationError({"parent": _("Parent comment belongs to a different post.")})

        if (
            parent.author
            and Block.objects.filter(
                Q(blocker=author, blocked=parent.author) | Q(blocker=parent.author, blocked=author)
            ).exists()
        ):
            raise PermissionDenied(_("Interaction blocked by privacy settings."))

        depth = parent.depth + 1
        if depth > MAX_COMMENT_DEPTH:
            raise ValidationError({"parent": _("Maximum reply depth reached (50 levels).")})

    with transaction.atomic():
        comment = Comment.objects.create(
            post=post,
            author=author,
            parent=parent,
            depth=depth,
            content_text=cleaned_text,
            image=clean_image,
            video=clean_video,
            is_deleted=False,
            likes_count=0,
            replies_count=0,
        )

        # Atualiza contadores com F()
        increment_post_comments_count(post.pk)
        if parent is not None:
            Comment.objects.filter(pk=parent.pk).update(replies_count=F("replies_count") + 1)

    notify_comment_created(sender=author, comment=comment)
    if cleaned_text:
        notify_mentions_for_content(
            sender=author,
            content_text=cleaned_text,
            post=post,
            ref_id=str(comment.id),
            is_hidden=is_in_hidden_thread(comment),
        )
    return comment


def edit_comment(*, comment: Comment, user, content_text: str) -> Comment:
    """
    Edita o texto de um comentário. Apenas o autor pode editar seus comentários.
    Marca is_edited=True e registra a data da edição.
    """
    if comment.author_id != user.id:
        raise PermissionDenied(_("You can only edit your own comments."))

    if comment.is_deleted:
        raise ValidationError({"detail": _("Cannot edit a deleted comment.")})

    cleaned_text = (content_text or "").strip()
    if not cleaned_text and not comment.image and not comment.video:
        raise ValidationError({"content_text": _("Comment content cannot be empty.")})
    if len(cleaned_text) > MAX_COMMENT_LENGTH:
        raise ValidationError(
            {"content_text": _("Comment exceeds maximum length of 1000 characters.")}
        )

    with transaction.atomic():
        comment.content_text = cleaned_text
        comment.is_edited = True
        comment.edited_at = timezone.now()
        comment.save(update_fields=["content_text", "is_edited", "edited_at", "updated_at"])
        if cleaned_text:
            notify_mentions_for_content(
                sender=user,
                content_text=cleaned_text,
                post=comment.post,
                ref_id=str(comment.id),
                is_hidden=is_in_hidden_thread(comment),
            )
    return comment


def delete_comment(*, comment: Comment, user) -> bool:
    """
    Exclui um comentário.
    Permissão:
    - Apenas o autor do comentário pode excluir seu próprio comentário.
      (O dono do post não pode excluir comentários de terceiros; ele pode ocultar).
    Regra de Tombstone / Expurgo:
    - Se possui respostas filhas: vira Tombstone (is_deleted=True,
      conteúdo vazio no banco sem texto tombstone, autor desvinculado, is_edited=False).
    - Se não possui respostas: é removido fisicamente do banco, e sobe
      recursivamente apagando tombstones ancestrais que agora ficaram sem descendentes ativos.
    - Contadores atômicos com F(): comentários excluídos deixam de contar em comments_count.
    """
    if comment.author_id != user.id:
        raise PermissionDenied(_("You do not have permission to delete this comment."))

    if comment.is_deleted:
        return True

    post_id = comment.post_id
    parent_id = comment.parent_id
    was_hidden = comment.is_hidden

    with transaction.atomic():
        if not was_hidden:
            decrement_post_comments_count(post_id)
            if parent_id:
                Comment.objects.filter(pk=parent_id, replies_count__gt=0).update(
                    replies_count=F("replies_count") - 1
                )
        else:
            decrement_post_hidden_comments_count(post_id)

        Notification.objects.filter(ref_id=comment.id).delete()

        media_to_delete = []
        if comment.image and comment.image.name:
            media_to_delete.append((comment.image.storage, comment.image.name))
        if comment.video and comment.video.name:
            media_to_delete.append((comment.video.storage, comment.video.name))

        # Verifica se há filhos cadastrados
        has_children = comment.replies.exists()

        if has_children:
            # Padrão Tombstone: anonimiza para LGPD (sem texto/mídia de tombstone no banco)
            comment.is_deleted = True
            comment.content_text = ""
            comment.image = None
            comment.video = None
            comment.author = None
            comment.is_edited = False
            comment.edited_at = None
            comment.save(
                update_fields=[
                    "is_deleted",
                    "content_text",
                    "image",
                    "video",
                    "author",
                    "is_edited",
                    "edited_at",
                    "updated_at",
                ]
            )
        else:
            # Comentário folha: exclusão física e poda de ancestrais tombstones
            parent_ref = comment.parent
            comment.delete()

            # Sobe podando tombstones ancestrais que ficaram órfãos
            curr_parent = parent_ref
            while curr_parent and curr_parent.is_deleted and not curr_parent.replies.exists():
                next_parent = curr_parent.parent
                curr_parent.delete()
                curr_parent = next_parent

    for storage, name in media_to_delete:
        try:
            storage.delete(name)
        except Exception:
            pass

    return True


def hide_comment(*, comment: Comment, user, reason: str = "owner") -> Comment:
    """
    Oculta um comentário e suas respostas abaixo dele.
    Apenas o dono da publicação pode ocultar comentários de terceiros.
    Ocultar esconde a conversa para todos exceto o dono do post.
    O autor continua vendo o seu próprio comentário.
    Sai dos contadores atômicos e das notificações.
    """
    if comment.post.author_id != user.id:
        raise PermissionDenied(_("Only the post author can hide comments."))

    if comment.author_id == user.id:
        raise ValidationError({"detail": _("Cannot hide your own comment.")})

    if comment.is_hidden:
        return comment

    with transaction.atomic():
        comment.is_hidden = True
        comment.hidden_at = timezone.now()
        comment.hidden_by = user
        comment.hidden_reason = reason
        comment.save(
            update_fields=["is_hidden", "hidden_at", "hidden_by", "hidden_reason", "updated_at"]
        )

        descendants = _get_comment_descendants(comment)
        all_tree_comments = [comment, *descendants]
        active_count = sum(1 for c in all_tree_comments if not c.is_deleted)

        if active_count > 0:
            decrement_post_comments_count(comment.post_id, amount=active_count)

        increment_post_hidden_comments_count(comment.post_id)

        if comment.parent_id:
            Comment.objects.filter(pk=comment.parent_id, replies_count__gt=0).update(
                replies_count=F("replies_count") - 1
            )

        tree_ids = [c.id for c in all_tree_comments]
        Notification.objects.filter(ref_id__in=tree_ids).delete()

    return comment


def unhide_comment(*, comment: Comment, user) -> Comment:
    """
    Reexibe um comentário anteriormente ocultado.
    Apenas o dono do post pode reexibir.
    Restaura contadores.
    """
    if comment.post.author_id != user.id:
        raise PermissionDenied(_("Only the post author can unhide comments."))

    if not comment.is_hidden:
        return comment

    with transaction.atomic():
        comment.is_hidden = False
        comment.hidden_at = None
        comment.hidden_by = None
        comment.hidden_reason = "owner"
        comment.save(
            update_fields=["is_hidden", "hidden_at", "hidden_by", "hidden_reason", "updated_at"]
        )

        descendants = _get_comment_descendants(comment)
        all_tree_comments = [comment, *descendants]
        active_count = sum(1 for c in all_tree_comments if not c.is_deleted)

        if active_count > 0:
            increment_post_comments_count(comment.post_id, amount=active_count)

        decrement_post_hidden_comments_count(comment.post_id)

        if comment.parent_id:
            Comment.objects.filter(pk=comment.parent_id).update(
                replies_count=F("replies_count") + 1
            )

    return comment


def toggle_comment_like(*, user, comment: Comment) -> Tuple[bool, int]:
    """
    Alterna curtida no comentário (idempotente).
    Retorna (is_liked, likes_count atualizado).
    """
    if not can_view_post(user, comment.post):
        raise PermissionDenied(_("You cannot view this post."))

    if (
        comment.author
        and Block.objects.filter(
            Q(blocker=user, blocked=comment.author) | Q(blocker=comment.author, blocked=user)
        ).exists()
    ):
        raise PermissionDenied(_("Interaction blocked by privacy settings."))

    with transaction.atomic():
        existing = CommentLike.objects.filter(comment=comment, user=user).first()
        if existing:
            existing.delete()
            Comment.objects.filter(pk=comment.pk, likes_count__gt=0).update(
                likes_count=F("likes_count") - 1
            )
            is_liked = False
        else:
            CommentLike.objects.create(comment=comment, user=user)
            Comment.objects.filter(pk=comment.pk).update(likes_count=F("likes_count") + 1)
            is_liked = True
            notify_comment_liked(sender=user, comment=comment)

        comment.refresh_from_db(fields=["likes_count"])

    return is_liked, comment.likes_count


def toggle_comment_bookmark(*, user, comment: Comment) -> bool:
    """Alterna salvar comentário nos favoritos (idempotente)."""
    if not can_view_post(user, comment.post):
        raise PermissionDenied(_("You cannot view this post."))

    existing = CommentBookmark.objects.filter(comment=comment, user=user).first()
    if existing:
        existing.delete()
        return False

    CommentBookmark.objects.create(comment=comment, user=user)
    return True
