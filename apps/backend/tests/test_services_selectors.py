"""
Testes unitários para services.py e selectors.py (ADR-N2).
"""

import pytest
from rest_framework.response import Response

from accounts.selectors import (
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
)
from accounts.services import (
    authenticate_user,
    clear_auth_cookies,
    logout_user,
    refresh_user_tokens,
    register_user,
    set_access_cookie,
    set_refresh_cookie,
)
from notifications.selectors import (
    get_unread_notifications_count,
    get_user_notifications,
)
from notifications.services import (
    create_notification,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)
from posts.models import Post
from posts.selectors import (
    get_post_detail_for_user,
    list_posts_keyset,
)
from posts.services import create_post, delete_post
from social.selectors import get_profile_counters, get_relationship_status
from social.services import (
    block_user,
    follow_user,
    mute_user,
    unblock_user,
    unfollow_user,
    unmute_user,
)
from tests.factories import UserFactory


@pytest.mark.django_db
class TestAccountsServicesSelectors:
    def test_selectors_find_user(self):
        user = UserFactory(username="testuser", email="test@example.com")
        assert get_user_by_id(user.id) == user
        assert get_user_by_username("testuser") == user
        assert get_user_by_email("test@example.com") == user
        assert get_user_by_id("00000000-0000-0000-0000-000000000000") is None
        assert get_user_by_username("nonexistent") is None
        assert get_user_by_email("none@example.com") is None

    def test_register_and_authenticate_user(self):
        user, refresh = register_user(
            email="novo@example.com",
            username="novo_user",
            password="SenhaForte123!@",
            birth_date="1990-01-01",
        )
        assert user.username == "novo_user"
        assert refresh is not None

        # Autentica com sucesso
        auth_user, auth_refresh = authenticate_user(
            email="novo@example.com",
            password="SenhaForte123!@",
        )
        assert auth_user == user
        assert auth_refresh is not None

        # Autentica senha errada
        fail_user, fail_refresh = authenticate_user(
            email="novo@example.com",
            password="SenhaErrada!",
        )
        assert fail_user is None
        assert fail_refresh is None

    def test_cookies_helpers(self):
        response = Response()
        set_access_cookie(response, "fake_access")
        set_refresh_cookie(response, "fake_refresh")
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

        clear_auth_cookies(response)
        assert response.cookies["access_token"]["max-age"] == 0
        assert response.cookies["refresh_token"]["max-age"] == 0

    def test_refresh_and_logout_services(self):
        user = UserFactory()
        from rest_framework_simplejwt.tokens import RefreshToken

        raw_refresh = str(RefreshToken.for_user(user))
        new_acc, new_ref = refresh_user_tokens(raw_refresh_token=raw_refresh)
        assert new_acc and new_ref

        # Inativa usuário
        user.is_active = False
        user.save()
        with pytest.raises(ValueError, match="Conta inativa"):
            refresh_user_tokens(raw_refresh_token=new_ref)

        # Logout blacklist
        logout_user(raw_refresh_token=new_ref)
        logout_user(raw_refresh_token=None)


@pytest.mark.django_db
class TestPostsServicesSelectors:
    def test_create_and_delete_post_service(self):
        author = UserFactory()
        other = UserFactory()
        post = create_post(author=author, content_text="Olá mundo!")
        assert post.content_text == "Olá mundo!"

        # Tentar deletar com outro usuário dá erro
        with pytest.raises(PermissionError):
            delete_post(post=post, user=other)

        # Deletar com autor funciona
        assert delete_post(post=post, user=author) is True
        assert not Post.objects.filter(pk=post.pk).exists()

    def test_create_post_exceed_max_chars(self):
        author = UserFactory()
        with pytest.raises(ValueError, match="excede o limite"):
            create_post(author=author, content_text="A" * 3001)

    def test_list_posts_keyset_and_detail(self):
        author = UserFactory()
        p1 = create_post(author=author, content_text="Post 1")
        p2 = create_post(author=author, content_text="Post 2")

        posts = list_posts_keyset(user=author, limit=10)
        assert len(posts) == 2

        detail = get_post_detail_for_user(post_id=p1.id, user=author)
        assert detail == p1

        with pytest.raises(ValueError, match="Cursor inválido"):
            list_posts_keyset(user=author, cursor="invalid-uuid")


@pytest.mark.django_db
class TestSocialServicesSelectors:
    def test_follow_unfollow_services(self):
        u1 = UserFactory()
        u2 = UserFactory()

        # Seguir a si mesmo
        with pytest.raises(ValueError, match="seguir a si mesmo"):
            follow_user(follower=u1, target_user=u1)

        # Seguir com sucesso
        _follow, created = follow_user(follower=u1, target_user=u2)
        assert created is True

        # Já segue
        with pytest.raises(ValueError, match="Já está seguindo"):
            follow_user(follower=u1, target_user=u2)

        # Status e contadores
        status = get_relationship_status(source_user=u1, target_user=u2)
        assert status["is_following"] is True

        counters = get_profile_counters(target_user=u2)
        assert counters["followers_count"] == 1

        # Deixar de seguir
        assert unfollow_user(follower=u1, target_user=u2) is True
        assert unfollow_user(follower=u1, target_user=u2) is False

    def test_block_unblock_mute_services(self):
        u1 = UserFactory()
        u2 = UserFactory()

        # Follow mútuo
        follow_user(follower=u1, target_user=u2)
        follow_user(follower=u2, target_user=u1)

        # Bloqueia u2: deve remover follows mútuos
        _block, created = block_user(blocker=u1, target_user=u2)
        assert created is True
        assert not get_relationship_status(source_user=u1, target_user=u2)["is_following"]
        assert not get_relationship_status(source_user=u2, target_user=u1)["is_following"]

        with pytest.raises(ValueError, match="bloquear a si mesmo"):
            block_user(blocker=u1, target_user=u1)

        with pytest.raises(ValueError, match="Já bloqueou"):
            block_user(blocker=u1, target_user=u2)

        assert unblock_user(blocker=u1, target_user=u2) is True
        assert unblock_user(blocker=u1, target_user=u2) is False

        # Mute
        _mute, m_created = mute_user(muter=u1, target_user=u2)
        assert m_created is True
        with pytest.raises(ValueError, match="silenciar a si mesmo"):
            mute_user(muter=u1, target_user=u1)
        with pytest.raises(ValueError, match="Já silenciou"):
            mute_user(muter=u1, target_user=u2)

        assert unmute_user(muter=u1, target_user=u2) is True
        assert unmute_user(muter=u1, target_user=u2) is False


@pytest.mark.django_db
class TestNotificationsServicesSelectors:
    def test_notification_lifecycle(self):
        u1 = UserFactory()
        u2 = UserFactory()

        n = create_notification(
            recipient=u1,
            sender=u2,
            notification_type="follow",
        )
        assert n.read is False

        assert get_unread_notifications_count(user=u1) == 1
        notifs = get_user_notifications(user=u1)
        assert len(notifs) == 1

        # Marca como lida
        assert mark_notification_as_read(notification_id=n.id, user=u1) is True
        assert get_unread_notifications_count(user=u1) == 0

        # Cria mais duas e marca todas
        create_notification(recipient=u1, sender=u2, notification_type="follow")
        create_notification(recipient=u1, sender=u2, notification_type="follow")
        assert get_unread_notifications_count(user=u1) == 2
        count = mark_all_notifications_as_read(user=u1)
        assert count == 2
        assert get_unread_notifications_count(user=u1) == 0
