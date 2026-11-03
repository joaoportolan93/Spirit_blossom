"""
Testes de ações sociais: follow, unfollow, block, perfil.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile
from social.models import Block, Follow
from .factories import FollowFactory, UserFactory

User = get_user_model()


def _client_for(user, enforce_csrf=False):
    client = APIClient(enforce_csrf_checks=enforce_csrf)
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


def _csrf_token(client):
    r = client.get("/api/auth/csrf/")
    cookie = client.cookies.get("csrftoken")
    return cookie.value if cookie else ""


@pytest.mark.django_db
class TestFollow:
    def test_follow_usuario_retorna_201(self):
        user = UserFactory()
        target = UserFactory()
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.post(
            f"/api/social/follow/{target.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Follow.objects.filter(follower=user, followed=target).exists()

    def test_unfollow_usuario_retorna_204(self):
        user = UserFactory()
        target = UserFactory()
        FollowFactory(follower=user, followed=target)
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.delete(
            f"/api/social/follow/{target.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Follow.objects.filter(follower=user, followed=target).exists()

    def test_seguir_a_si_mesmo_retorna_400(self):
        user = UserFactory()
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.post(
            f"/api/social/follow/{user.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_follow_duplicado_retorna_400(self):
        user = UserFactory()
        target = UserFactory()
        FollowFactory(follower=user, followed=target)
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.post(
            f"/api/social/follow/{target.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unfollow_nao_seguido_retorna_404(self):
        user = UserFactory()
        target = UserFactory()
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.delete(
            f"/api/social/follow/{target.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestBlock:
    def test_bloquear_usuario_retorna_201(self):
        user = UserFactory()
        target = UserFactory()
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.post(
            f"/api/social/block/{target.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Block.objects.filter(blocker=user, blocked=target).exists()

    def test_desbloquear_usuario_retorna_204(self):
        user = UserFactory()
        target = UserFactory()
        Block.objects.create(blocker=user, blocked=target)
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.delete(
            f"/api/social/block/{target.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Block.objects.filter(blocker=user, blocked=target).exists()

    def test_bloquear_a_si_mesmo_retorna_400(self):
        user = UserFactory()
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.post(
            f"/api/social/block/{user.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bloquear_ja_bloqueado_retorna_400(self):
        user = UserFactory()
        target = UserFactory()
        Block.objects.create(blocker=user, blocked=target)
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.post(
            f"/api/social/block/{target.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_desbloquear_nao_bloqueado_retorna_404(self):
        user = UserFactory()
        target = UserFactory()
        client = _client_for(user, enforce_csrf=True)
        csrf = _csrf_token(client)
        response = client.delete(
            f"/api/social/block/{target.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestUserProfile:
    def test_user_criado_pode_ter_perfil(self):
        """UserProfile pode ser criado para um User."""
        user = UserFactory()
        profile = UserProfile.objects.create(user=user, bio="Olá, sou eu.")
        assert profile.user == user
        assert profile.bio == "Olá, sou eu."

    def test_user_status_ativo_por_padrao(self):
        user = UserFactory()
        assert user.status == User.Status.ACTIVE
        assert user.is_valid_for_auth is True

    def test_user_suspenso_nao_valido_para_auth(self):
        user = UserFactory()
        user.status = User.Status.SUSPENDED
        user.save()
        assert user.is_valid_for_auth is False
