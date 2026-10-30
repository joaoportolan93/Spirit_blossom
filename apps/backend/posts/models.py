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
        FOLLOWERS = "followers", _("Seguidores")

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    content_text = models.TextField(max_length=3000)  # validado também em settings.POST_MAX_CHARS
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Plano A confirmado pelo spike do E3:
    # GeneratedField com db_persist=True gera GENERATED ALWAYS AS ... STORED no Postgres 16.
    # Django 5.x exclui o campo do INSERT/UPDATE automaticamente (field.generated = True).
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
