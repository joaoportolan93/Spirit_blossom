"""
Testes de feed cronológico (Seguindo e Explorar) e contrato JSON Schema.
(ADR-N2 / ADR-N21 / ADR-N22)
"""

import json
import pathlib
import uuid

import jsonschema
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.factories import BlockFactory, FollowFactory, PostFactory, UserFactory
from core.models import Block, Mute, Post, UserProfile

SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent
    / "docs"
    / "api"
    / "feed-contract.json"
)


def _client_for(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


@pytest.mark.django_db
class TestFollowingFeed:
    def test_feed_vazio_para_usuario_sem_seguidos(self):
        user = UserFactory()
        client = _client_for(user)
        response = client.get("/api/feed/following/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["next_cursor"] is None

    def test_feed_retorna_posts_de_seguidos_em_ordem_decrescente(self):
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        p1 = PostFactory(author=followed)
        p2 = PostFactory(author=followed)
        p3 = PostFactory(author=followed)
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        ids = [item["post_id"] for item in data["items"]]
        assert ids.index(str(p3.pk)) < ids.index(str(p2.pk)) < ids.index(str(p1.pk))

    def test_feed_nao_inclui_posts_de_nao_seguidos(self):
        user = UserFactory()
        stranger = UserFactory()
        post = PostFactory(author=stranger)
        client = _client_for(user)
        ids = [item["post_id"] for item in client.get("/api/feed/following/").json()["items"]]
        assert str(post.pk) not in ids

    def test_cursor_invalido_retorna_400(self):
        user = UserFactory()
        client = _client_for(user)
        response = client.get("/api/feed/following/?cursor=nao-e-uuid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cursor_valido_pagina_sem_sobreposicao(self):
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        [PostFactory(author=followed) for _ in range(5)]
        client = _client_for(user)
        data_first = client.get("/api/feed/following/").json()
        cursor = data_first["items"][-1]["cursor"]
        data_next = client.get(f"/api/feed/following/?cursor={cursor}").json()
        ids_first = {item["post_id"] for item in data_first["items"]}
        ids_next = {item["post_id"] for item in data_next["items"]}
        assert ids_first.isdisjoint(ids_next)

    def test_feed_exclui_posts_bloqueados(self):
        user = UserFactory()
        blocked = UserFactory()
        FollowFactory(follower=user, followed=blocked)
        BlockFactory(blocker=user, blocked=blocked)
        PostFactory(author=blocked)
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        assert data["items"] == []


@pytest.mark.django_db
class TestFeedContract:
    def test_feed_valida_contra_json_schema(self):
        """Response do feed valida contra docs/api/feed-contract.json."""
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        PostFactory(author=followed)
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        jsonschema.validate(instance=data, schema=schema)

    def test_reason_e_following_nos_items(self):
        """Cada item do feed tem reason='following'."""
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        PostFactory(author=followed)
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        for item in data["items"]:
            assert item["reason"] == "following"

    def test_next_cursor_presente_quando_pagina_cheia(self):
        """next_cursor é string quando há exatamente 20 posts."""
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        [PostFactory(author=followed) for _ in range(20)]
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        assert len(data["items"]) == 20
        assert data["next_cursor"] is not None

    def test_next_cursor_nulo_quando_pagina_incompleta(self):
        """next_cursor é null quando há menos de 20 posts."""
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        [PostFactory(author=followed) for _ in range(5)]
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        assert len(data["items"]) == 5
        assert data["next_cursor"] is None

    def test_post_id_e_uuid_valido(self):
        """post_id em cada item deve ser UUID válido."""
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        PostFactory(author=followed)
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        for item in data["items"]:
            uuid.UUID(item["post_id"])


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
        assert any(
            item["post_id"] == str(post.id) and item["reason"] == "explore"
            for item in data["items"]
        )

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
