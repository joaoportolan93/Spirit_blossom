"""
Testes de recuperação de senha segura (ADR-N2 / Onda 2):
- Hash SHA-256 no banco, token cru apenas na URL/e-mail
- Fragmento #token= (não chega ao servidor no HTTP Referer)
- Resposta uniforme contra enumeração de e-mail
- Disparo de e-mail em pós-commit (transaction.on_commit)
- Invalidação após uso e expiração em 15 minutos
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.factories import UserFactory
from core.models import PasswordResetToken


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
