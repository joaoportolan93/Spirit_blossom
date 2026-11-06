"""
Operações de escrita para posts (ADR-N2).
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


def delete_post(*, post: Post, user) -> bool:
    """Apaga um post se o usuário for o autor."""
    if post.author != user:
        raise PermissionError("Sem permissão para excluir esta publicação.")
    post.delete()
    return True
