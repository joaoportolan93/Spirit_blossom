"""
Queries puras de leitura para accounts (ADR-N2).
"""

from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, QuerySet

User = get_user_model()


def get_user_by_id(user_id) -> Optional[User]:
    """Retorna o usuário pelo ID ou None se não encontrado."""
    try:
        return User.objects.select_related("profile").get(pk=user_id)
    except User.DoesNotExist:
        return None


def get_user_by_username(username: str) -> Optional[User]:
    """Retorna o usuário pelo username ou None."""
    try:
        return User.objects.select_related("profile").get(username=username)
    except User.DoesNotExist:
        return None


def get_user_by_email(email: str) -> Optional[User]:
    """Retorna o usuário pelo e-mail ou None."""
    try:
        return User.objects.select_related("profile").get(email=email)
    except User.DoesNotExist:
        return None


def search_users(*, query: str, viewer, limit: int = 20) -> QuerySet:
    """
    Busca usuários por prefixo de username (ADR-N21 / ADR-N22).

    Regras:
    - Mínimo 2 caracteres no query
    - Busca apenas por username (nunca por e-mail)
    - Exclui contas inativas
    - Exclui o próprio viewer
    - Exclui bloqueados em ambas as direções
    - Limite configurável, padrão 20
    """
    if len(query) < 2:
        return User.objects.none()

    from social.models import Block

    blocked_by_viewer = Block.objects.filter(
        blocker=viewer,
        blocked=OuterRef("pk"),
    )
    viewer_blocked_by = Block.objects.filter(
        blocker=OuterRef("pk"),
        blocked=viewer,
    )

    return (
        User.objects.filter(
            username__istartswith=query,
            is_active=True,
            status=User.Status.ACTIVE,
        )
        .exclude(pk=viewer.pk)
        .exclude(Exists(blocked_by_viewer))
        .exclude(Exists(viewer_blocked_by))
        .select_related("profile")
        .order_by("username")[:limit]
    )
