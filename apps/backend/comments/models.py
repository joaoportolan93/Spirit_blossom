import uuid6
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import Post


class Comment(models.Model):
    """
    Representa um comentário ou resposta a uma publicação (Árvore N-níveis).
    Em conformidade com a Onda 4 / ADR-N24:
    - Identificador UUIDv7 para ordenação temporal intrínseca.
    - Suporte a profundidade recursiva com campo depth desnormalizado.
    - Padrão Tombstone: ao excluir nó com respostas, is_deleted=True,
      conteúdo substituído por placeholder LGPD e autor desvinculado.
    """

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("publicação"),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comments",
        verbose_name=_("autor"),
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name=_("comentário pai"),
    )
    depth = models.PositiveIntegerField(default=0, verbose_name=_("profundidade"))
    content_text = models.TextField(
        max_length=1000, blank=True, default="", verbose_name=_("conteúdo")
    )
    image = models.ImageField(
        upload_to="comment_images/", null=True, blank=True, verbose_name=_("imagem")
    )
    video = models.FileField(
        upload_to="comment_videos/", null=True, blank=True, verbose_name=_("vídeo")
    )
    is_deleted = models.BooleanField(default=False, verbose_name=_("excluído"))
    is_edited = models.BooleanField(default=False, verbose_name=_("editado"))
    edited_at = models.DateTimeField(null=True, blank=True, verbose_name=_("data de edição"))
    is_hidden = models.BooleanField(default=False, verbose_name=_("oculto"))
    hidden_at = models.DateTimeField(null=True, blank=True, verbose_name=_("data de ocultação"))
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hidden_comments",
        verbose_name=_("ocultado por"),
    )
    hidden_reason = models.CharField(
        max_length=20,
        default="owner",
        choices=[
            ("owner", _("Proprietário")),
            ("block", _("Bloqueio")),
            ("moderation", _("Moderação")),
        ],
        verbose_name=_("motivo de ocultação"),
    )
    likes_count = models.PositiveIntegerField(default=0, verbose_name=_("contagem de curtidas"))
    replies_count = models.PositiveIntegerField(default=0, verbose_name=_("contagem de respostas"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("criado em"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("atualizado em"))

    class Meta:
        db_table = "comments_comment"
        verbose_name = _("comentário")
        verbose_name_plural = _("comentários")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["post", "parent", "-created_at"], name="com_post_parent_created_idx"
            ),
            models.Index(fields=["parent", "-created_at"], name="com_parent_created_idx"),
            models.Index(
                fields=["post", "-likes_count", "-created_at"], name="com_post_likes_created_idx"
            ),
            models.Index(
                fields=["post", "is_hidden", "-created_at"], name="com_post_hidden_created_idx"
            ),
        ]

    def __str__(self):
        status = " [deleted]" if self.is_deleted else ""
        return f"Comment {self.id} by {self.author_id} on {self.post_id}{status}"


class CommentLike(models.Model):
    """Curtida em comentário (chave idempotente única por comentário e usuário)."""

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name=_("comentário"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_likes",
        verbose_name=_("usuário"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("criado em"))

    class Meta:
        db_table = "comments_commentlike"
        verbose_name = _("curtida de comentário")
        verbose_name_plural = _("curtidas de comentários")
        constraints = [
            models.UniqueConstraint(fields=["comment", "user"], name="unique_comment_like"),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="com_like_user_created_idx"),
        ]

    def __str__(self):
        return f"{self.user_id} ♥ comment {self.comment_id}"


class CommentBookmark(models.Model):
    """Comentário salvo / favorito do usuário."""

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        verbose_name=_("comentário"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_bookmarks",
        verbose_name=_("usuário"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("criado em"))

    class Meta:
        db_table = "comments_commentbookmark"
        verbose_name = _("comentário salvo")
        verbose_name_plural = _("comentários salvos")
        constraints = [
            models.UniqueConstraint(fields=["comment", "user"], name="unique_comment_bookmark"),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="com_bkmk_user_created_idx"),
        ]

    def __str__(self):
        return f"{self.user_id} 🔖 comment {self.comment_id}"
