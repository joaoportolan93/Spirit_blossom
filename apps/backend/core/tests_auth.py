"""
Testes de autenticação: login, register, CSRF endpoint, AccessLog,
Throttles, e proteção de rotas privadas contra acesso anônimo (ADR-N2 / ADR-N22).
"""

from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import get_resolver
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from conftest import get_csrf_token, make_client
from core.authentication import CookieJWTAuthentication
from core.factories import UserFactory
from core.models import AccessLog
from core.throttles import LoginRateThrottle, RegisterRateThrottle

User = get_user_model()


@pytest.mark.django_db
class TestCSRFEndpoint:
    def test_csrf_endpoint_retorna_200_e_seta_cookie(self):
        client = make_client()
        response = client.get("/api/auth/csrf/")
        assert response.status_code == status.HTTP_200_OK
        assert "csrftoken" in response.cookies or "csrftoken" in client.cookies

    def test_csrf_endpoint_nao_requer_autenticacao(self):
        """GET /csrf/ deve funcionar sem token."""
        client = make_client()
        response = client.get("/api/auth/csrf/")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestRegister:
    def test_register_cria_usuario_e_retorna_cookies(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
        data = {
            "email": "novo@example.com",
            "username": "novousuario",
            "password": "senhaforte123",
            "password_confirm": "senhaforte123",
            "birth_date": "2000-01-01",
            "terms_accepted": True,
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
        assert user.profile.terms_accepted_at is not None
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    def test_register_sem_terms_accepted_retorna_400(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
        data = {
            "email": "semtermos@example.com",
            "username": "semtermos",
            "password": "senhaforte123",
            "password_confirm": "senhaforte123",
            "birth_date": "2000-01-01",
            "terms_accepted": False,
        }
        response = client.post(
            "/api/auth/register/",
            data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "terms_accepted" in response.data

    def test_register_senha_diferente_retorna_400(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
        today = date.today()
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
        response = client.post(
            "/api/auth/login/",
            {"email": "wrong@example.com", "password": "errada"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_usuario_inexistente_retorna_400(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        assert len(log.ip_hash) == 64

    def test_access_log_porta_registrada(self):
        """Campo port do AccessLog registra porta de conexão de origem."""
        user = UserFactory(email="portatest@example.com")
        user.set_password("senhaforte123")
        user.save()
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)
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
        client = APIClient()
        user = UserFactory()

        refresh = RefreshToken.for_user(user)
        old_refresh_str = str(refresh)

        client.cookies["refresh_token"] = old_refresh_str
        client.cookies["csrftoken"] = "testcsrf"
        response = client.post(
            "/api/auth/refresh/",
            HTTP_X_CSRFTOKEN="testcsrf",
        )
        assert response.status_code == 200, f"Primeiro refresh falhou: {response.data}"

        client2 = APIClient()
        client2.cookies["refresh_token"] = old_refresh_str
        client2.cookies["csrftoken"] = "testcsrf"
        response2 = client2.post(
            "/api/auth/refresh/",
            HTTP_X_CSRFTOKEN="testcsrf",
        )
        assert response2.status_code == 401, f"Token reutilizado deveria dar 401: {response2.data}"

    def test_refresh_apos_logout_retorna_401(self, db):
        client = APIClient()
        user = UserFactory()

        refresh = RefreshToken.for_user(user)
        refresh_str = str(refresh)

        client.cookies["refresh_token"] = refresh_str
        client.cookies["csrftoken"] = "testcsrf"
        response_logout = client.post(
            "/api/auth/logout/",
            HTTP_X_CSRFTOKEN="testcsrf",
        )
        assert response_logout.status_code == 200

        client2 = APIClient()
        client2.cookies["refresh_token"] = refresh_str
        client2.cookies["csrftoken"] = "testcsrf"
        response = client2.post(
            "/api/auth/refresh/",
            HTTP_X_CSRFTOKEN="testcsrf",
        )
        assert response.status_code == 401, f"Token pós-logout deveria dar 401: {response.data}"


@pytest.mark.django_db
class TestThrottles:
    """Valida rate limiting de produção (login 5/min e register 3/min)."""

    def test_login_rate_throttle_bloqueia_na_sexta_tentativa(self):
        cache.clear()
        try:
            with patch.dict(LoginRateThrottle.THROTTLE_RATES, {"login": "5/min"}):
                client = make_client(enforce_csrf=True)
                csrf = get_csrf_token(client)
                login_payload = {"email": "tentativa@example.com", "password": "wrongpassword"}

                for _ in range(5):
                    resp = client.post(
                        "/api/auth/login/",
                        login_payload,
                        format="json",
                        HTTP_X_CSRFTOKEN=csrf,
                    )
                    assert resp.status_code != status.HTTP_429_TOO_MANY_REQUESTS

                blocked_resp = client.post(
                    "/api/auth/login/",
                    login_payload,
                    format="json",
                    HTTP_X_CSRFTOKEN=csrf,
                )
                assert blocked_resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            cache.clear()

    def test_register_rate_throttle_bloqueia_na_quarta_tentativa(self):
        cache.clear()
        try:
            with patch.dict(RegisterRateThrottle.THROTTLE_RATES, {"register": "3/min"}):
                client = make_client(enforce_csrf=True)
                csrf = get_csrf_token(client)
                register_payload = {
                    "email": "invalid_register",
                    "password": "short",
                }

                for _ in range(3):
                    resp = client.post(
                        "/api/auth/register/",
                        register_payload,
                        format="json",
                        HTTP_X_CSRFTOKEN=csrf,
                    )
                    assert resp.status_code != status.HTTP_429_TOO_MANY_REQUESTS

                blocked_resp = client.post(
                    "/api/auth/register/",
                    register_payload,
                    format="json",
                    HTTP_X_CSRFTOKEN=csrf,
                )
                assert blocked_resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        finally:
            cache.clear()


@pytest.mark.django_db
class TestAllRoutesRequireAuthenticationForAnonymous:
    """
    Percorre programaticamente todas as rotas da aplicação Django sob /api/
    e garante que qualquer acesso anônimo recebe 401 Unauthorized, exceto a lista pública.
    """

    PUBLIC_ROUTES = {
        "/api/auth/csrf/",
        "/api/auth/login/",
        "/api/auth/register/",
        "/api/auth/refresh/",
        "/api/auth/logout/",
        "/api/auth/password-reset/request/",
        "/api/auth/password-reset/confirm/",
        "/api/auth/google/",
        "/api/auth/google/complete/",
        "/api/health/",
    }

    def _extract_routes(self, patterns, prefix=""):
        routes = []
        for p in patterns:
            if hasattr(p, "url_patterns"):
                routes.extend(self._extract_routes(p.url_patterns, prefix + str(p.pattern)))
            else:
                pattern_str = prefix + str(p.pattern)
                if pattern_str.startswith("api/"):
                    routes.append("/" + pattern_str)
        return routes

    def test_todos_endpoints_protegidos_negam_anonimo_com_401(self):
        resolver = get_resolver()
        all_routes = self._extract_routes(resolver.url_patterns)
        client = APIClient()

        dummy_uuid = "00000000-0000-0000-0000-000000000001"
        dummy_username = "testuser"
        dummy_id = "1"

        tested_count = 0
        for route in all_routes:
            if route in self.PUBLIC_ROUTES:
                continue

            resolved_url = (
                route.replace("<uuid:pk>", dummy_uuid)
                .replace("<int:pk>", dummy_id)
                .replace("<str:username>", dummy_username)
                .replace("<id>", dummy_id)
            )

            resp_get = client.get(resolved_url)
            assert (
                resp_get.status_code == status.HTTP_401_UNAUTHORIZED
            ), f"Endpoint {resolved_url} (GET) permitiu anônimo ou retornou {resp_get.status_code}"
            resp_post = client.post(resolved_url, {})
            assert (
                resp_post.status_code == status.HTTP_401_UNAUTHORIZED
            ), f"Endpoint {resolved_url} (POST) permitiu anônimo ou retornou {resp_post.status_code}"
            tested_count += 1

        assert tested_count >= 15, "Deve haver pelo menos 15 endpoints privados testados"


@pytest.mark.django_db
class TestAuthenticationEdgeCases:
    """Cobre core/authentication.py: linhas de exceção e validação."""

    def test_custom_jwt_authentication_edge_cases(self):
        factory = APIRequestFactory()
        auth = CookieJWTAuthentication()

        # Token malformado / inválido
        req_invalid = factory.get("/api/feed/")
        req_invalid.COOKIES["access_token"] = "token.invalido.malformado"
        with pytest.raises(Exception):
            auth.authenticate(req_invalid)

        # Token válido para usuário que foi deletado do banco
        user = UserFactory()
        token = AccessToken.for_user(user)
        user.delete()
        req_deleted = factory.get("/api/feed/")
        req_deleted.COOKIES["access_token"] = str(token)
        with pytest.raises(Exception) as exc_info:
            auth.authenticate(req_deleted)
        assert "Usuário não encontrado" in str(exc_info.value)

        # Conta inativa ou suspensa
        user_inactive = UserFactory()
        token_inactive = AccessToken.for_user(user_inactive)
        user_inactive.is_active = False
        user_inactive.save()
        req_inactive = factory.get("/api/feed/")
        req_inactive.COOKIES["access_token"] = str(token_inactive)
        with pytest.raises(Exception) as exc_inactive:
            auth.authenticate(req_inactive)
        assert "Conta inativa ou suspensa" in str(exc_inactive.value)
