"""
Fixtures compartilhadas entre todos os testes.
"""

from config.sqlite_compat import patch_sqlite

patch_sqlite()

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.factories import PostFactory, UserFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def csrf_client():
    """APIClient com enforce_csrf_checks=True — obrigatório para testes de CSRF."""
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def other_user(db):
    return UserFactory()


@pytest.fixture
def post(db, user):
    return PostFactory(author=user)


@pytest.fixture
def auth_cookies(user):
    """Retorna dict com cookies de access e refresh para um usuário."""
    refresh = RefreshToken.for_user(user)
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
    }


def set_auth_cookies(client, user):
    """Helper: injeta cookies JWT no client sem passar pela view de login."""
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    client.cookies["refresh_token"] = str(refresh)
    return refresh


def get_csrf_token(client):
    """Obtém csrftoken via GET /api/auth/csrf/ e retorna o valor do cookie."""
    response = client.get("/api/auth/csrf/")
    return (
        client.cookies.get("csrftoken", {}).value
        if hasattr(client.cookies.get("csrftoken", {}), "value")
        else response.cookies.get("csrftoken", "")
    )
