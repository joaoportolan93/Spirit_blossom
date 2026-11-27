import uuid6
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import GeneratedField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# ---------------------------------------------------------------------------
# Constantes de Onda 9 — posts efêmeros e mídia
# ---------------------------------------------------------------------------
EPHEMERAL_DURATION_CHOICES = [
    (24, _("24 horas")),
    (48, _("48 horas")),
    (168, _("7 dias")),
]
MAX_POST_IMAGES = 4
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_DIMENSIONS = 4096  # px por lado — anti decompression bomb


class Post(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = "public", _("Público")
        CIRCLE = "circle", _("Círculo de Amigos")

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    content_text = models.TextField(max_length=3000, blank=True, default="")
    image = models.ImageField(upload_to="post_images/", null=True, blank=True)
    video = models.FileField(upload_to="post_videos/", null=True, blank=True)
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
    )
    likes_count = models.PositiveIntegerField(default=0)
    bookmarks_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    hidden_comments_count = models.PositiveIntegerField(default=0)
    is_hidden = models.BooleanField(default=False, db_index=True)
    hidden_reason = models.TextField(blank=True, default="")
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_hidden_posts",
    )
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Onda 9: Posts Efêmeros ---
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("expira em"),
        help_text=_("Definido no momento da publicação. Null = permanente."),
    )
    ephemeral_duration_hours = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=EPHEMERAL_DURATION_CHOICES,
        verbose_name=_("duração efêmera (h)"),
        help_text=_("24, 48 ou 168 horas. Null = permanente."),
    )

    search_vector = GeneratedField(
        expression=SearchVector("content_text", config="simple"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        db_table = "posts_post"
        verbose_name = _("publicação")
        verbose_name_plural = _("publicações")
        indexes = [
            models.Index(fields=["author", "-id"], name="posts_post_author_id_idx"),
            models.Index(
                fields=["expires_at"],
                name="posts_post_expires_at_idx",
                condition=models.Q(expires_at__isnull=False),
            ),
            GinIndex(fields=["search_vector"], name="posts_post_search_gin"),
        ]
        ordering = ["-id"]

    def __str__(self):
        return f"{self.author_id} @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_ephemeral(self) -> bool:
        """True se o post tem duração efêmera configurada (expires_at definido)."""
        return self.expires_at is not None

    @property
    def is_expired(self) -> bool:
        """True se o post efêmero já expirou."""
        return self.expires_at is not None and self.expires_at <= timezone.now()


class PostMedia(models.Model):
    """
    Mídia (imagem) associada a um post — até 4 por post (Onda 9).
    Arquivos físicos ficam em post_media/; entregues via endpoint autenticado.
    """

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="media",
    )
    file = models.ImageField(upload_to="post_media/")
    alt_text = models.CharField(
        max_length=300,
        blank=True,
        default="",
        verbose_name=_("texto alternativo"),
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("ordem"),
    )
    width = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("largura (px)"))
    height = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("altura (px)"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "posts_postmedia"
        verbose_name = _("mídia do post")
        verbose_name_plural = _("mídias do post")
        ordering = ["order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(order__gte=0) & models.Q(order__lte=3),
                name="postmedia_order_0_to_3",
            )
        ]

    def __str__(self):
        return f"PostMedia({self.post_id}, order={self.order})"


class PostLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "posts_postlike"
        verbose_name = _("curtida de publicação")
        verbose_name_plural = _("curtidas de publicação")
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_post_like"),
        ]

    def __str__(self):
        return f"{self.user_id} ♥ {self.post_id}"


class PostBookmark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "posts_postbookmark"
        verbose_name = _("favorito de publicação")
        verbose_name_plural = _("favoritos de publicação")
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_post_bookmark"),
        ]

    def __str__(self):
        return f"{self.user_id} 🔖 {self.post_id}"


class Draft(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="drafts",
    )
    content_text = models.TextField(max_length=3000, blank=True, default="")
    visibility = models.CharField(
        max_length=10,
        choices=Post.Visibility.choices,
        default=Post.Visibility.PUBLIC,
    )
    ephemeral_duration_hours = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=EPHEMERAL_DURATION_CHOICES,
        verbose_name=_("duração efêmera (h)"),
        help_text=_("24, 48 ou 168 horas ao publicar. Null = permanente."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "posts_draft"
        verbose_name = _("rascunho")
        verbose_name_plural = _("rascunhos")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Draft({self.author_id}, {self.id})"


class DraftMedia(models.Model):
    """
    Mídia (imagem) associada a um rascunho — até 4 por rascunho (Onda 9).
    Ao publicar o rascunho, os arquivos são movidos para PostMedia.
    """

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    draft = models.ForeignKey(
        Draft,
        on_delete=models.CASCADE,
        related_name="media",
    )
    file = models.ImageField(upload_to="draft_media/")
    alt_text = models.CharField(
        max_length=300,
        blank=True,
        default="",
        verbose_name=_("texto alternativo"),
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("ordem"),
    )
    width = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("largura (px)"))
    height = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("altura (px)"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "posts_draftmedia"
        verbose_name = _("mídia do rascunho")
        verbose_name_plural = _("mídias do rascunho")
        ordering = ["order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(order__gte=0) & models.Q(order__lte=3),
                name="draftmedia_order_0_to_3",
            )
        ]

    def __str__(self):
        return f"DraftMedia({self.draft_id}, order={self.order})"


class Hashtag(models.Model):
    """
    Hashtag normalizada associada a publicações (Onda 7b).
    Sempre armazenada em lowercase, sem o prefixo '#'.
    """

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    name = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name=_("nome"),
    )
    posts = models.ManyToManyField(
        Post,
        related_name="hashtags",
        blank=True,
        verbose_name=_("publicações"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("criado em"))

    class Meta:
        db_table = "posts_hashtag"
        verbose_name = _("hashtag")
        verbose_name_plural = _("hashtags")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"#{self.name}"
