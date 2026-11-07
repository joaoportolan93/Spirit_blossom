"""
Testes de autenticação da Onda 2:
- Recuperação de senha segura (SHA-256 hash, uso único, fragmento #token=, anti-enumeração, pós-commit)
- Google OAuth (validação, vínculo por google_sub, bloqueio de e-mail preexistente, onboarding 18+)
- Aceite de termos obrigatório
"""

from datetime import date, timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import OAuthAccount, PasswordResetToken, User
from tests.factories import UserFactory


def _make_client(enforce_csrf: bool = False) -> APIClient:
    return APIClient(enforce_csrf_checks=enforce_csrf)


def _get_csrf(client: APIClient) -> str:
    response = client.get("/api/auth/csrf/")
    return response.cookies["csrftoken"].value


@pytest.mark.django_db(transaction=True)
class TestPasswordResetFlow:
    def test_request_reset_existing_email_sends_email_with_hash_fragment(self):
        user = UserFactory(email="recuperar@example.com")
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

        response = client.post(
            "/api/auth/password-reset/request/",
            {"email": "recuperar@example.com"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_200_OK
        assert "instruções foram enviadas" in response.data["detail"]

        # Verifica e-mail enviado pós-commit
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert "recuperar@example.com" in sent_email.to
        assert "#token=" in sent_email.body

        # Verifica que o token foi gravado como hash (SHA-256 de 64 caracteres)
        token_obj = PasswordResetToken.objects.filter(user=user).latest("created_at")
        assert len(token_obj.token_hash) == 64
        assert token_obj.used_at is None
        assert token_obj.expires_at > timezone.now()

    def test_request_reset_nonexistent_email_returns_identical_response_and_no_email(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

        response = client.post(
            "/api/auth/password-reset/request/",
            {"email": "naoexiste@example.com"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_200_OK
        assert "instruções foram enviadas" in response.data["detail"]
        assert len(mail.outbox) == 0

    def test_confirm_reset_valid_token_updates_password(self):
        user = UserFactory(email="trocasenha@example.com")
        user.set_password("SenhaAntiga123!")
        user.save()

        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

        # Solicita reset
        client.post(
            "/api/auth/password-reset/request/",
            {"email": "trocasenha@example.com"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        raw_token = body.split("#token=")[1].split()[0].strip()

        # Confirma nova senha
        confirm_resp = client.post(
            "/api/auth/password-reset/confirm/",
            {
                "token": raw_token,
                "new_password": "NovaSenhaForte123!@",
                "new_password_confirm": "NovaSenhaForte123!@",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert confirm_resp.status_code == status.HTTP_200_OK

        # Verifica que senha antiga não autentica mais e nova senha autentica
        login_old = client.post(
            "/api/auth/login/",
            {"email": "trocasenha@example.com", "password": "SenhaAntiga123!"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert login_old.status_code == status.HTTP_400_BAD_REQUEST

        login_new = client.post(
            "/api/auth/login/",
            {"email": "trocasenha@example.com", "password": "NovaSenhaForte123!@"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert login_new.status_code == status.HTTP_200_OK

    def test_confirm_reset_reused_token_fails(self):
        UserFactory(email="reuso@example.com")
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

        client.post(
            "/api/auth/password-reset/request/",
            {"email": "reuso@example.com"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        raw_token = mail.outbox[0].body.split("#token=")[1].split()[0].strip()

        # Primeiro uso
        resp1 = client.post(
            "/api/auth/password-reset/confirm/",
            {
                "token": raw_token,
                "new_password": "Senha123456!@",
                "new_password_confirm": "Senha123456!@",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert resp1.status_code == status.HTTP_200_OK

        # Segundo uso com o mesmo token deve falhar
        resp2 = client.post(
            "/api/auth/password-reset/confirm/",
            {
                "token": raw_token,
                "new_password": "OutraSenha123!@",
                "new_password_confirm": "OutraSenha123!@",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert resp2.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_reset_expired_token_fails(self):
        user = UserFactory(email="expirado@example.com")
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

        client.post(
            "/api/auth/password-reset/request/",
            {"email": "expirado@example.com"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        raw_token = mail.outbox[0].body.split("#token=")[1].split()[0].strip()

        # Força expiração no banco
        PasswordResetToken.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        resp = client.post(
            "/api/auth/password-reset/confirm/",
            {
                "token": raw_token,
                "new_password": "NovaSenhaForte123!@",
                "new_password_confirm": "NovaSenhaForte123!@",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_reset_passwords_mismatch_returns_400(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

        resp = client.post(
            "/api/auth/password-reset/confirm/",
            {
                "token": "qualquer_token",
                "new_password": "NovaSenhaForte123!@",
                "new_password_confirm": "Diferente123!@",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "não conferem" in str(resp.data)


@pytest.mark.django_db(transaction=True)
class TestGoogleOAuthFlow:
    def test_google_login_email_unverified_returns_400(self):
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

        # mock-google-token:sub:email:verified
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
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

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
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

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
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

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
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

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
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

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
        client2 = _make_client(enforce_csrf=True)
        csrf2 = _get_csrf(client2)

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
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

        token = "mock-google-token:sub_alpha:alpha@example.com:true"
        resp = client.post("/api/auth/google/", {"id_token": token}, format="json", HTTP_X_CSRFTOKEN=csrf)
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
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

        token = "mock-google-token:sub_taken:taken@example.com:true"
        resp = client.post("/api/auth/google/", {"id_token": token}, format="json", HTTP_X_CSRFTOKEN=csrf)
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
        client = _make_client(enforce_csrf=True)
        csrf = _get_csrf(client)

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
