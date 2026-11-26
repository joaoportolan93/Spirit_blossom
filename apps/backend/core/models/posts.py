import uuid6
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import GeneratedField
from django.utils.translation import gettext_lazy as _


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
            GinIndex(fields=["search_vector"], name="posts_post_search_gin"),
        ]
        ordering = ["-id"]

    def __str__(self):
        return f"{self.author_id} @ {self.created_at:%Y-%m-%d %H:%M}"


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
    content_text = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "posts_draft"
        verbose_name = _("rascunho")
        verbose_name_plural = _("rascunhos")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Draft({self.author_id}, {self.id})"


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
