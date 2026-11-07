"""
Testes de ações sociais: seguir, deixar de seguir, bloquear, silenciar, amigos próximos e perfil.
(ADR-N2 / ADR-N21 / ADR-N22)
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.factories import BlockFactory, FollowFactory, UserFactory
from core.models import Block, Follow, Mute, UserProfile
from core.serializers.social import FollowSerializer
from core.utils.visibility import can_view_profile, get_profile_counters, get_relationship_status

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
        user = UserFactory(profile=False)
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


@pytest.mark.django_db
class TestProfileDetail:
    def test_retorna_contadores_e_status_de_follow(self):
        user = UserFactory()
        target = UserFactory()
        follower1 = UserFactory()
        FollowFactory(follower=follower1, followed=target)
        FollowFactory(follower=target, followed=follower1)

        client = _client_for(user)
        response = client.get(f"/api/social/profile/{target.username}/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == target.username
        assert data["followers_count"] == 1
        assert data["following_count"] == 1
        assert data["is_following"] is False

        FollowFactory(follower=user, followed=target)
        res2 = client.get(f"/api/social/profile/{target.username}/")
        assert res2.status_code == status.HTTP_200_OK
        assert res2.json()["followers_count"] == 2
        assert res2.json()["is_following"] is True


@pytest.mark.django_db
class TestCloseFriendsEndpoints:
    def test_add_close_friend_success(self):
        user = UserFactory()
        target = UserFactory()
        Follow.objects.create(follower=user, followed=target, status=Follow.Status.ACTIVE)

        client = _client_for(user)
        res = client.post(f"/api/social/close-friends/{target.username}/")
        assert res.status_code == status.HTTP_201_CREATED
        assert res.json()["detail"] == "Adicionado ao círculo."

        follow = Follow.objects.get(follower=user, followed=target)
        assert follow.is_close_friend is True

    def test_add_close_friend_already_in_circle(self):
        user = UserFactory()
        target = UserFactory()
        Follow.objects.create(
            follower=user, followed=target, status=Follow.Status.ACTIVE, is_close_friend=True
        )

        client = _client_for(user)
        res = client.post(f"/api/social/close-friends/{target.username}/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Já está no círculo" in res.json()["detail"]

    def test_add_close_friend_not_following_fails(self):
        user = UserFactory()
        target = UserFactory()

        client = _client_for(user)
        res = client.post(f"/api/social/close-friends/{target.username}/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Você precisa seguir este usuário" in res.json()["detail"]

    def test_add_close_friend_target_not_found(self):
        user = UserFactory()
        client = _client_for(user)
        res = client.post("/api/social/close-friends/usuario_inexistente/")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_remove_close_friend_success(self):
        user = UserFactory()
        target = UserFactory()
        Follow.objects.create(
            follower=user, followed=target, status=Follow.Status.ACTIVE, is_close_friend=True
        )

        client = _client_for(user)
        res = client.delete(f"/api/social/close-friends/{target.username}/")
        assert res.status_code == status.HTTP_204_NO_CONTENT

        follow = Follow.objects.get(follower=user, followed=target)
        assert follow.is_close_friend is False

    def test_remove_close_friend_not_in_circle_fails(self):
        user = UserFactory()
        target = UserFactory()
        Follow.objects.create(
            follower=user, followed=target, status=Follow.Status.ACTIVE, is_close_friend=False
        )

        client = _client_for(user)
        res = client.delete(f"/api/social/close-friends/{target.username}/")
        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert "Não estava no círculo" in res.json()["detail"]

    def test_list_close_friends(self):
        user = UserFactory()
        f1 = UserFactory(username="amigo1")
        f2 = UserFactory(username="amigo2")
        f3 = UserFactory(username="outro")

        Follow.objects.create(
            follower=user, followed=f1, is_close_friend=True, status=Follow.Status.ACTIVE
        )
        Follow.objects.create(
            follower=user, followed=f2, is_close_friend=True, status=Follow.Status.ACTIVE
        )
        Follow.objects.create(
            follower=user, followed=f3, is_close_friend=False, status=Follow.Status.ACTIVE
        )

        client = _client_for(user)
        res = client.get("/api/social/close-friends/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()["results"]
        usernames = [item["username"] for item in data]
        assert "amigo1" in usernames
        assert "amigo2" in usernames
        assert "outro" not in usernames


@pytest.mark.django_db
class TestMuteEndpoints:
    def test_mute_user_success(self):
        user = UserFactory()
        target = UserFactory()

        client = _client_for(user)
        res = client.post(f"/api/social/mute/{target.username}/")
        assert res.status_code == status.HTTP_201_CREATED
        assert res.json()["detail"] == "Usuário silenciado."
        assert Mute.objects.filter(muter=user, muted=target).exists()

    def test_mute_self_fails(self):
        user = UserFactory()
        client = _client_for(user)
        res = client.post(f"/api/social/mute/{user.username}/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_mute_already_muted_fails(self):
        user = UserFactory()
        target = UserFactory()
        Mute.objects.create(muter=user, muted=target)

        client = _client_for(user)
        res = client.post(f"/api/social/mute/{target.username}/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_unmute_user_success(self):
        user = UserFactory()
        target = UserFactory()
        Mute.objects.create(muter=user, muted=target)

        client = _client_for(user)
        res = client.delete(f"/api/social/mute/{target.username}/")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert not Mute.objects.filter(muter=user, muted=target).exists()

    def test_unmute_user_not_muted_returns_404(self):
        user = UserFactory()
        target = UserFactory()

        client = _client_for(user)
        res = client.delete(f"/api/social/mute/{target.username}/")
        assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestSocialCoverageAndSerializers:
    def test_follow_serializer(self):
        f = FollowFactory()
        serializer = FollowSerializer(f)
        assert serializer.data["follower_username"] == f.follower.username
        assert serializer.data["followed_username"] == f.followed.username

    def test_can_view_profile_target_invalid_or_none(self):
        viewer = UserFactory()
        assert can_view_profile(viewer, None) is False
        assert can_view_profile(viewer, viewer) is True

        target = UserFactory()
        target.is_active = False
        target.save()
        assert can_view_profile(viewer, target) is False

    def test_can_view_profile_when_user_has_no_profile(self):
        viewer = UserFactory()
        target = UserFactory()
        UserProfile.objects.filter(user=target).delete()
        target.refresh_from_db()
        assert can_view_profile(viewer, target) is True

    def test_can_view_profile_anonymous_viewer_on_private_account(self):
        target = UserFactory()
        profile, _ = UserProfile.objects.get_or_create(user=target)
        profile.is_private = True
        profile.save()
        assert can_view_profile(None, target) is False
        assert can_view_profile(AnonymousUser(), target) is False

    def test_get_profile_counters_when_cannot_view_profile(self):
        author = UserFactory()
        viewer = UserFactory()
        BlockFactory(blocker=author, blocked=viewer)
        counters = get_profile_counters(target_user=author, viewer=viewer)
        assert counters == {"posts_count": 0, "followers_count": 0, "following_count": 0}

    def test_get_relationship_status_anonymous_source(self):
        target = UserFactory()
        status_none = get_relationship_status(source_user=None, target_user=target)
        assert status_none["is_following"] is False
        assert status_none["follow_status"] is None

        status_anon = get_relationship_status(source_user=AnonymousUser(), target_user=target)
        assert status_anon["is_following"] is False

