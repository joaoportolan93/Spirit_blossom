"""
Operações de escrita para posts.
"""
from django.conf import settings

from .models import Post


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
