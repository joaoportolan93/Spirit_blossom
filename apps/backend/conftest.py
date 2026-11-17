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


def auth_client(user=None, *, enforce_csrf=False):
    """Retorna APIClient com cookies JWT setados se o usuário for fornecido."""
    client = APIClient(enforce_csrf_checks=enforce_csrf)
    if user:
        set_auth_cookies(client, user)
    return client


def make_client(enforce_csrf=False):
    """Cria e retorna um APIClient (com ou sem enforce_csrf)."""
    return APIClient(enforce_csrf_checks=enforce_csrf)


def make_csrf_client():
    """Cria e retorna um APIClient com enforce_csrf_checks=True."""
    return APIClient(enforce_csrf_checks=True)


def inject_access(client, user):
    """Injeta access_token no cookie do client."""
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return refresh


def inject_refresh(client, user):
    """Injeta apenas refresh_token no cookie (simula access expirado)."""
    refresh = RefreshToken.for_user(user)
    client.cookies["refresh_token"] = str(refresh)
    return refresh


def get_csrf_token(client):
    """Obtém csrftoken via GET /api/auth/csrf/ e retorna o valor string do cookie."""
    response = client.get("/api/auth/csrf/")
    cookie = client.cookies.get("csrftoken")
    if cookie:
        return cookie.value if hasattr(cookie, "value") else str(cookie)
    resp_cookie = response.cookies.get("csrftoken")
    if resp_cookie:
        return resp_cookie.value if hasattr(resp_cookie, "value") else str(resp_cookie)
    return ""
