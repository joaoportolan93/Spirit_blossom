"""
Testes de autenticação: login, register, CSRF endpoint, AccessLog.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AccessLog

from .factories import UserFactory

User = get_user_model()


def _make_client(enforce_csrf=False):
    return APIClient(enforce_csrf_checks=enforce_csrf)


def _get_csrf(client):
    r = client.get("/api/auth/csrf/")
    assert r.status_code == 200
    cookie = client.cookies.get("csrftoken")
    return cookie.value if cookie else ""


@pytest.mark.django_db
class TestCSRFEndpoint:
    def test_csrf_endpoint_retorna_200_e_seta_cookie(self):
        client = _make_client()
        response = client.get("/api/auth/csrf/")
        assert response.status_code == status.HTTP_200_OK
        assert "csrftoken" in response.cookies or "csrftoken" in client.cookies

    def test_csrf_endpoint_nao_requer_autenticacao(self):
        """GET /csrf/ deve funcionar sem token."""
        client = _make_client()
        response = client.get("/api/auth/csrf/")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestRegister:
    def test_register_cria_usuario_e_retorna_cookies(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        data = {
            "email": "novo@example.com",
            "username": "novousuario",
            "password": "senhaforte123",
            "password_confirm": "senhaforte123",
            "birth_date": "2000-01-01",
        }
        response = client.post(
            "/api/auth/register/",
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.filter(email="novo@example.com").first()
        assert user is not None
        assert user.profile.birth_date.isoformat() == "2000-01-01"
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    def test_register_senha_diferente_retorna_400(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        data = {
            "email": "x@example.com",
            "username": "xuser",
            "password": "senha123",
            "password_confirm": "diferente456",
            "birth_date": "2000-01-01",
        }
        response = client.post(
            "/api/auth/register/",
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_username_duplicado_retorna_400(self):
        UserFactory(username="existente")
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        data = {
            "email": "outro@example.com",
            "username": "existente",
            "password": "senha123",
            "password_confirm": "senha123",
            "birth_date": "2000-01-01",
        }
        response = client.post(
            "/api/auth/register/",
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_email_duplicado_retorna_400(self):
        UserFactory(email="duplicado@example.com")
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        data = {
            "email": "duplicado@example.com",
            "username": "novouser1",
            "password": "senhaforte123",
            "password_confirm": "senhaforte123",
            "birth_date": "2000-01-01",
        }
        response = client.post(
            "/api/auth/register/",
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_senha_curta_retorna_400(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        data = {
            "email": "curta@example.com",
            "username": "novouser2",
            "password": "123",
            "password_confirm": "123",
            "birth_date": "2000-01-01",
        }
        response = client.post(
            "/api/auth/register/",
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_username_invalido_retorna_400(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        data = {
            "email": "invalido@example.com",
            "username": "user com espaco",
            "password": "senhaforte123",
            "password_confirm": "senhaforte123",
            "birth_date": "2000-01-01",
        }
        response = client.post(
            "/api/auth/register/",
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_menor_de_18_anos_retorna_400(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        from datetime import date

        today = date.today()
        # 17 anos atrás
        underage = date(today.year - 17, today.month, today.day).isoformat()
        data = {
            "email": "menor@example.com",
            "username": "menoridade",
            "password": "senhaforte123",
            "password_confirm": "senhaforte123",
            "birth_date": underage,
        }
        response = client.post(
            "/api/auth/register/",
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "18 anos" in str(response.data)

    def test_register_sem_birth_date_retorna_400(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        data = {
            "email": "sembirth@example.com",
            "username": "sembirth",
            "password": "senhaforte123",
            "password_confirm": "senhaforte123",
        }
        response = client.post(
            "/api/auth/register/",
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "birth_date" in response.data


@pytest.mark.django_db
class TestLogin:
    def test_login_correto_retorna_200_e_cookies(self):
        user = UserFactory(email="auth@example.com")
        user.set_password("senhaforte123")
        user.save()
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        response = client.post(
            "/api/auth/login/",
            {"email": "auth@example.com", "password": "senhaforte123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    def test_login_senha_errada_retorna_400(self):
        user = UserFactory(email="wrong@example.com")
        user.set_password("senhaforte123")
        user.save()
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        response = client.post(
            "/api/auth/login/",
            {"email": "wrong@example.com", "password": "errada"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_usuario_inexistente_retorna_400(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        response = client.post(
            "/api/auth/login/",
            {"email": "inexistente@example.com", "password": "qualquersenha"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_usuario_inativo_retorna_400(self):
        user = UserFactory(email="inativo@example.com", is_active=False)
        user.set_password("senhaforte123")
        user.save()
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        response = client.post(
            "/api/auth/login/",
            {"email": "inativo@example.com", "password": "senhaforte123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_usuario_suspenso_retorna_400(self):
        user = UserFactory(email="suspenso@example.com", status=User.Status.SUSPENDED)
        user.set_password("senhaforte123")
        user.save()
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        response = client.post(
            "/api/auth/login/",
            {"email": "suspenso@example.com", "password": "senhaforte123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_cria_access_log(self):
        """Login bem-sucedido deve criar um AccessLog."""
        user = UserFactory(email="log@example.com")
        user.set_password("senhaforte123")
        user.save()
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        initial_count = AccessLog.objects.filter(user=user).count()
        client.post(
            "/api/auth/login/",
            {"email": "log@example.com", "password": "senhaforte123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert AccessLog.objects.filter(user=user).count() == initial_count + 1

    def test_access_log_ip_esta_hasheado(self):
        """Campo ip_hash do AccessLog não contém o IP em texto puro."""
        user = UserFactory(email="hashtest@example.com")
        user.set_password("senhaforte123")
        user.save()
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        client.post(
            "/api/auth/login/",
            {"email": "hashtest@example.com", "password": "senhaforte123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
            REMOTE_ADDR="192.168.1.100",
        )
        log = AccessLog.objects.filter(user=user).last()
        assert log is not None
        assert log.ip_hash != "192.168.1.100"
        assert len(log.ip_hash) == 64  # HMAC-SHA256 hex = 64 chars

    def test_access_log_porta_registrada(self):
        """Campo port do AccessLog registra porta de conexão de origem."""
        user = UserFactory(email="portatest@example.com")
        user.set_password("senhaforte123")
        user.save()
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)
        client.post(
            "/api/auth/login/",
            {"email": "portatest@example.com", "password": "senhaforte123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
            REMOTE_ADDR="127.0.0.1",
            REMOTE_PORT="54321",
        )
        log = AccessLog.objects.filter(user=user).last()
        assert log is not None
        assert log.port == 54321


@pytest.mark.django_db
class TestRefreshTokenRotation:
    """Testa que refresh token é rotacionado corretamente e não pode ser reutilizado."""

    def test_refresh_reutilizado_retorna_401(self, db):
        """Usar um refresh token já rotacionado deve retornar 401."""
        client = APIClient()
        user = UserFactory()

        # Obtém refresh token original
        refresh = RefreshToken.for_user(user)
        old_refresh_str = str(refresh)

        # Primeiro uso — deve funcionar
        client.cookies["refresh_token"] = old_refresh_str
        client.cookies["csrftoken"] = "testcsrf"
        response = client.post(
            "/api/auth/refresh/",
            HTTP_X_CSRFTOKEN="testcsrf",
        )
        assert response.status_code == 200, f"Primeiro refresh falhou: {response.data}"

        # Segundo uso do mesmo token — deve falhar (blacklistado)
        client2 = APIClient()
        client2.cookies["refresh_token"] = old_refresh_str
        client2.cookies["csrftoken"] = "testcsrf"
        response2 = client2.post(
            "/api/auth/refresh/",
            HTTP_X_CSRFTOKEN="testcsrf",
        )
        assert response2.status_code == 401, f"Token reutilizado deveria dar 401: {response2.data}"

    def test_refresh_apos_logout_retorna_401(self, db):
        """Após logout, o refresh token deve ser blacklistado e não funcionar."""
        client = APIClient()
        user = UserFactory()

        refresh = RefreshToken.for_user(user)
        refresh_str = str(refresh)

        # Logout
        client.cookies["refresh_token"] = refresh_str
        client.cookies["csrftoken"] = "testcsrf"
        response_logout = client.post(
            "/api/auth/logout/",
            HTTP_X_CSRFTOKEN="testcsrf",
        )
        assert response_logout.status_code == 200

        # Tentar usar o token após logout — deve falhar
        client2 = APIClient()
        client2.cookies["refresh_token"] = refresh_str
        client2.cookies["csrftoken"] = "testcsrf"
        response = client2.post(
            "/api/auth/refresh/",
            HTTP_X_CSRFTOKEN="testcsrf",
        )
        assert response.status_code == 401, f"Token pós-logout deveria dar 401: {response.data}"
