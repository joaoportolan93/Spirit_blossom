"""
Testes de Google OAuth (ADR-N2 / Onda 2):
- Validação de ID token (email_verified obrigatório)
- Bloqueio de e-mail preexistente com senha local (sem auto-linking arbitrário)
- Novo usuário retorna status=needs_signup e onboarding_token assinado
- Conclusão de cadastro com validação de idade mínima 18+, username alfanumérico e aceite de termos
- Login subsequente transparente direto para conta já cadastrada
"""

from datetime import date

import pytest
from rest_framework import status

from conftest import get_csrf_token, make_client
from core.factories import UserFactory
from core.models import OAuthAccount, User


@pytest.mark.django_db(transaction=True)
class TestGoogleOAuthFlow:
    def test_google_login_email_unverified_returns_400(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)

        token = "mock-google-token:sub123:unverified@example.com:false"
        resp = client.post(
            "/api/auth/google/",
            {"id_token": token},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "não foi verificado" in str(resp.data)

    def test_google_login_email_already_exists_with_password_refuses_auto_link(self):
        UserFactory(email="existente_com_senha@example.com")
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)

        token = "mock-google-token:sub456:existente_com_senha@example.com:true"
        resp = client.post(
            "/api/auth/google/",
            {"id_token": token},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "já está cadastrado" in str(resp.data)
        assert "vincule sua conta Google" in str(resp.data)

    def test_google_login_new_user_returns_needs_signup_and_onboarding_token(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)

        token = "mock-google-token:sub_novo_789:novo_google@example.com:true"
        resp = client.post(
            "/api/auth/google/",
            {"id_token": token},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["status"] == "needs_signup"
        assert "onboarding_token" in resp.data
        assert resp.data["email"] == "novo_google@example.com"

    def test_google_complete_signup_underage_rejected(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)

        token = "mock-google-token:sub_menor:menor_google@example.com:true"
        resp = client.post(
            "/api/auth/google/",
            {"id_token": token},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        onboarding_token = resp.data["onboarding_token"]

        # Tenta completar cadastro com 16 anos
        today = date.today()
        underage_date = date(today.year - 16, today.month, today.day).isoformat()
        complete_resp = client.post(
            "/api/auth/google/complete/",
            {
                "onboarding_token": onboarding_token,
                "username": "googletestuser",
                "birth_date": underage_date,
                "terms_accepted": True,
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert complete_resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "18 anos" in str(complete_resp.data)

    def test_google_complete_signup_without_terms_rejected(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)

        token = "mock-google-token:sub_sem_termos:semtermos_google@example.com:true"
        resp = client.post(
            "/api/auth/google/",
            {"id_token": token},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        onboarding_token = resp.data["onboarding_token"]

        complete_resp = client.post(
            "/api/auth/google/complete/",
            {
                "onboarding_token": onboarding_token,
                "username": "usersemtermos",
                "birth_date": "2000-01-01",
                "terms_accepted": False,
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert complete_resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "terms_accepted" in complete_resp.data

    def test_google_full_signup_and_subsequent_login_flow(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)

        google_token = "mock-google-token:google_sub_unique_999:sucesso_google@example.com:true"

        # 1. Primeiro acesso -> needs_signup
        step1 = client.post(
            "/api/auth/google/",
            {"id_token": google_token},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert step1.data["status"] == "needs_signup"
        onboarding_token = step1.data["onboarding_token"]

        # 2. Completa cadastro 18+ com username e termos
        step2 = client.post(
            "/api/auth/google/complete/",
            {
                "onboarding_token": onboarding_token,
                "username": "usuariogoogleok",
                "birth_date": "1995-05-15",
                "terms_accepted": True,
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert step2.status_code == status.HTTP_201_CREATED
        assert "access_token" in step2.cookies
        assert "refresh_token" in step2.cookies

        # Confirma criação no banco
        user = User.objects.get(email="sucesso_google@example.com")
        assert user.username == "usuariogoogleok"
        assert user.profile.birth_date.isoformat() == "1995-05-15"
        assert user.profile.terms_accepted_at is not None

        oauth = OAuthAccount.objects.get(user=user, provider="google")
        assert oauth.uid == "google_sub_unique_999"

        # 3. Próximo acesso com o mesmo token Google -> logged_in direto!
        client2 = make_client(enforce_csrf=True)
        csrf2 = get_csrf_token(client2)

        step3 = client2.post(
            "/api/auth/google/",
            {"id_token": google_token},
            format="json",
            HTTP_X_CSRFTOKEN=csrf2,
        )
        assert step3.status_code == status.HTTP_200_OK
        assert step3.data["status"] == "logged_in"
        assert "access_token" in step3.cookies
        assert "refresh_token" in step3.cookies

    def test_google_complete_signup_non_alphanumeric_username_rejected(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)

        token = "mock-google-token:sub_alpha:alpha@example.com:true"
        resp = client.post(
            "/api/auth/google/", {"id_token": token}, format="json", HTTP_X_CSRFTOKEN=csrf
        )
        onboarding_token = resp.data["onboarding_token"]

        step = client.post(
            "/api/auth/google/complete/",
            {
                "onboarding_token": onboarding_token,
                "username": "user_with_underscore",
                "birth_date": "1995-05-15",
                "terms_accepted": True,
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert step.status_code == status.HTTP_400_BAD_REQUEST
        assert "apenas letras e números" in str(step.data)

    def test_google_complete_signup_username_taken_rejected(self):
        UserFactory(username="existente")
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)

        token = "mock-google-token:sub_taken:taken@example.com:true"
        resp = client.post(
            "/api/auth/google/", {"id_token": token}, format="json", HTTP_X_CSRFTOKEN=csrf
        )
        onboarding_token = resp.data["onboarding_token"]

        step = client.post(
            "/api/auth/google/complete/",
            {
                "onboarding_token": onboarding_token,
                "username": "existente",
                "birth_date": "1995-05-15",
                "terms_accepted": True,
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert step.status_code == status.HTTP_400_BAD_REQUEST
        assert "já está em uso" in str(step.data)

    def test_google_complete_signup_tampered_token_rejected(self):
        client = make_client(enforce_csrf=True)
        csrf = get_csrf_token(client)

        step = client.post(
            "/api/auth/google/complete/",
            {
                "onboarding_token": "token-falso-adulterado",
                "username": "novousuario123",
                "birth_date": "1995-05-15",
                "terms_accepted": True,
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert step.status_code == status.HTTP_400_BAD_REQUEST
        assert "inválido ou expirado" in str(step.data)
