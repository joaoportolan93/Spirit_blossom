"""
Testes dedicados aos novos endpoints e seletores da Onda 3a:
- Close friends (POST /api/social/close-friends/<username>/, DELETE, GET)
- Mute (POST /api/social/mute/<username>/, DELETE)
- User Search (GET /api/users/search/?q=)
- Explore Feed (GET /api/feed/explore/)
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile
from posts.models import Post
from social.models import Block, Follow, Mute
from tests.factories import PostFactory, UserFactory

User = get_user_model()


def _client_for(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


# ---------------------------------------------------------------------------
# Close Friends Endpoints
# ---------------------------------------------------------------------------

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

        Follow.objects.create(follower=user, followed=f1, is_close_friend=True, status=Follow.Status.ACTIVE)
        Follow.objects.create(follower=user, followed=f2, is_close_friend=True, status=Follow.Status.ACTIVE)
        Follow.objects.create(follower=user, followed=f3, is_close_friend=False, status=Follow.Status.ACTIVE)

        client = _client_for(user)
        res = client.get("/api/social/close-friends/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()["results"]
        usernames = [item["username"] for item in data]
        assert "amigo1" in usernames
        assert "amigo2" in usernames
        assert "outro" not in usernames


# ---------------------------------------------------------------------------
# Mute Endpoints
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# User Search Endpoint
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUserSearchEndpoint:
    def test_search_requires_at_least_two_chars(self):
        user = UserFactory()
        client = _client_for(user)
        res = client.get("/api/users/search/?q=a")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "pelo menos 2 caracteres" in res.json()["detail"]

    def test_search_prefix_success(self):
        viewer = UserFactory()
        target1 = UserFactory(username="alessandra")
        target2 = UserFactory(username="alexandre")
        target3 = UserFactory(username="bernardo")

        client = _client_for(viewer)
        res = client.get("/api/users/search/?q=ale")
        assert res.status_code == status.HTTP_200_OK
        results = res.json()["results"]
        usernames = [r["username"] for r in results]
        assert "alessandra" in usernames
        assert "alexandre" in usernames
        assert "bernardo" not in usernames

    def test_search_excludes_self_and_blocked(self):
        viewer = UserFactory(username="alexviewer")
        target_blocked_by_me = UserFactory(username="alexblocked")
        target_who_blocked_me = UserFactory(username="alexblocker")
        normal_target = UserFactory(username="alexnormal")

        Block.objects.create(blocker=viewer, blocked=target_blocked_by_me)
        Block.objects.create(blocker=target_who_blocked_me, blocked=viewer)

        client = _client_for(viewer)
        res = client.get("/api/users/search/?q=alex")
        assert res.status_code == status.HTTP_200_OK
        usernames = [r["username"] for r in res.json()["results"]]
        assert "alexnormal" in usernames
        assert "alexviewer" not in usernames
        assert "alexblocked" not in usernames
        assert "alexblocker" not in usernames


# ---------------------------------------------------------------------------
# Explore Feed Endpoint
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExploreFeedEndpoint:
    def test_explore_returns_public_posts_with_reason(self):
        viewer = UserFactory()
        author = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        client = _client_for(viewer)
        res = client.get("/api/feed/explore/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert "items" in data
        assert any(item["post_id"] == str(post.id) and item["reason"] == "explore" for item in data["items"])

    def test_explore_excludes_private_accounts_and_non_public_posts(self):
        viewer = UserFactory()
        private_author = UserFactory()
        prof, _ = UserProfile.objects.get_or_create(user=private_author)
        prof.is_private = True
        prof.save()

        post_private_author = PostFactory(author=private_author, visibility=Post.Visibility.PUBLIC)
        normal_author = UserFactory()
        post_circle = PostFactory(author=normal_author, visibility=Post.Visibility.CIRCLE)
        post_followers = PostFactory(author=normal_author, visibility=Post.Visibility.FOLLOWERS)

        client = _client_for(viewer)
        res = client.get("/api/feed/explore/")
        assert res.status_code == status.HTTP_200_OK
        post_ids = [item["post_id"] for item in res.json()["items"]]
        assert str(post_private_author.id) not in post_ids
        assert str(post_circle.id) not in post_ids
        assert str(post_followers.id) not in post_ids

    def test_explore_excludes_blocked_and_muted_users(self):
        viewer = UserFactory()
        author_blocked = UserFactory()
        author_blocker = UserFactory()
        author_muted = UserFactory()
        normal_author = UserFactory()

        Block.objects.create(blocker=viewer, blocked=author_blocked)
        Block.objects.create(blocker=author_blocker, blocked=viewer)
        Mute.objects.create(muter=viewer, muted=author_muted)

        p_blocked = PostFactory(author=author_blocked, visibility=Post.Visibility.PUBLIC)
        p_blocker = PostFactory(author=author_blocker, visibility=Post.Visibility.PUBLIC)
        p_muted = PostFactory(author=author_muted, visibility=Post.Visibility.PUBLIC)
        p_normal = PostFactory(author=normal_author, visibility=Post.Visibility.PUBLIC)

        client = _client_for(viewer)
        res = client.get("/api/feed/explore/")
        assert res.status_code == status.HTTP_200_OK
        post_ids = [item["post_id"] for item in res.json()["items"]]
        assert str(p_normal.id) in post_ids
        assert str(p_blocked.id) not in post_ids
        assert str(p_blocker.id) not in post_ids
        assert str(p_muted.id) not in post_ids

    def test_explore_invalid_cursor_returns_400(self):
        viewer = UserFactory()
        client = _client_for(viewer)
        res = client.get("/api/feed/explore/?cursor=invalid-uuid")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
