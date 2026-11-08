"""
Testes de busca de publicações (full-text FTS Postgres / tsvector) e usuários (prefixo de username).
(ADR-N2 / ADR-N6 / ADR-N21 / ADR-N22)
"""

import inspect
import os

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.factories import BlockFactory, PostFactory, UserFactory
from core.models import Block, Post, UserProfile
from core.services.posts import search_posts

_is_sqlite = (
    os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings_test") == "config.settings_test"
)
requires_postgres = pytest.mark.skipif(
    _is_sqlite,
    reason="Busca full-text exige Postgres (tsvector/GIN). Rode com DJANGO_SETTINGS_MODULE=config.settings_ci.",
)


def _client_for(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


@pytest.mark.django_db
class TestSearch:
    @requires_postgres
    def test_busca_encontra_post_por_palavra(self):
        """Busca retorna post que contém o termo."""
        user = UserFactory()
        post = PostFactory(author=user, content_text="python é uma linguagem incrível")
        client = _client_for(user)
        response = client.get("/api/posts/search/?q=python")
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()]
        assert str(post.pk) in ids

    @requires_postgres
    def test_busca_nao_retorna_post_de_usuario_bloqueado(self):
        """Busca não retorna posts de usuários bloqueados (bidirecional)."""
        user = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=user, blocked=blocked)
        PostFactory(author=blocked, content_text="conteúdo bloqueado único xpto")
        client = _client_for(user)
        response = client.get("/api/posts/search/?q=xpto")
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()]
        blocked_posts = Post.objects.filter(author=blocked).values_list("id", flat=True)
        for blocked_id in blocked_posts:
            assert str(blocked_id) not in ids

    @requires_postgres
    def test_busca_nao_retorna_post_privado_de_nao_seguido(self):
        """Busca não retorna post de conta privada de usuário não seguido."""
        user = UserFactory()
        stranger = UserFactory()
        UserProfile.objects.filter(user=stranger).update(is_private=True)
        PostFactory(
            author=stranger,
            content_text="conteúdo privado restrito zyxw",
            visibility="public",
        )
        client = _client_for(user)
        response = client.get("/api/posts/search/?q=zyxw")
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()]
        private_posts = Post.objects.filter(author=stranger).values_list("id", flat=True)
        for pid in private_posts:
            assert str(pid) not in ids

    @requires_postgres
    def test_busca_ordena_por_relevancia(self):
        """Post com maior densidade do termo aparece antes do menos relevante."""
        user = UserFactory()
        post_baixo = PostFactory(
            author=user,
            content_text="aprendi algo sobre django hoje pela primeira vez na vida",
        )
        post_alto = PostFactory(
            author=user,
            content_text="django django django django django django django framework python",
        )
        client = _client_for(user)
        response = client.get("/api/posts/search/?q=django")
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()]
        assert str(post_alto.pk) in ids
        assert str(post_baixo.pk) in ids
        assert ids.index(str(post_alto.pk)) < ids.index(str(post_baixo.pk))

    @requires_postgres
    def test_busca_funciona_com_texto_pt_br_e_en(self):
        """Busca encontra posts com termos em pt-BR e em EN usando config='simple'."""
        user = UserFactory()
        post_ptbr = PostFactory(author=user, content_text="programação orientada a objetos")
        post_en = PostFactory(author=user, content_text="object oriented programming")
        client = _client_for(user)

        resp_pt = client.get("/api/posts/search/?q=programação")
        ids_pt = [item["id"] for item in resp_pt.json()]
        assert str(post_ptbr.pk) in ids_pt

        resp_en = client.get("/api/posts/search/?q=programming")
        ids_en = [item["id"] for item in resp_en.json()]
        assert str(post_en.pk) in ids_en

    def test_busca_sem_q_retorna_400(self):
        """Busca sem parâmetro q retorna 400."""
        user = UserFactory()
        client = _client_for(user)
        response = client.get("/api/posts/search/")
        assert response.status_code == 400


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


@pytest.mark.django_db
class TestSearchPostsSecurity:
    def test_search_posts_requires_user_argument(self):
        """search_posts exige user explicitamente (parâmetro não-opcional)."""
        sig = inspect.signature(search_posts)
        assert "user" in sig.parameters
        assert sig.parameters["user"].default == inspect.Parameter.empty
