"""
Queries puras de leitura para accounts (ADR-N2).
"""

from typing import Optional

from django.contrib.auth import get_user_model

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
