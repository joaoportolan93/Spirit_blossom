"""
Testes do feed cronológico e busca full-text.

Contrato do feed: docs/api/feed-contract.json
  { "items": [{"post_id": "...", "reason": "following", "cursor": "..."}],
    "next_cursor": "<uuid>" | null }
"""

import json
import os
import pathlib
import uuid

import jsonschema
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .factories import BlockFactory, FollowFactory, PostFactory, UserFactory

SCHEMA_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent / "docs" / "api" / "feed-contract.json"
)

# Testes de busca full-text exigem Postgres (tsvector/GIN).
# Em SQLite com patch, SearchQuery não encontra resultados reais.
# No CI (DJANGO_SETTINGS_MODULE=config.settings_ci), esses testes DEVEM rodar.
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


# ---------------------------------------------------------------------------
# Feed cronológico
# ---------------------------------------------------------------------------


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
        # UUIDv7 — mais recente primeiro
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


# ---------------------------------------------------------------------------
# Contrato JSON Schema
# ---------------------------------------------------------------------------


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
            uuid.UUID(item["post_id"])  # lança ValueError se inválido


# ---------------------------------------------------------------------------
# Busca full-text
# ---------------------------------------------------------------------------


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
        # Post do bloqueado não deve aparecer
        from posts.models import Post

        blocked_posts = Post.objects.filter(author=blocked).values_list("id", flat=True)
        for blocked_id in blocked_posts:
            assert str(blocked_id) not in ids

    @requires_postgres
    def test_busca_nao_retorna_post_privado_de_nao_seguido(self):
        """Busca não retorna post visibility=followers de usuário não seguido."""
        user = UserFactory()
        stranger = UserFactory()
        PostFactory(
            author=stranger,
            content_text="conteúdo privado restrito zyxw",
            visibility="followers",
        )
        client = _client_for(user)
        response = client.get("/api/posts/search/?q=zyxw")
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()]
        from posts.models import Post

        private_posts = Post.objects.filter(author=stranger, visibility="followers").values_list(
            "id", flat=True
        )
        for pid in private_posts:
            assert str(pid) not in ids

    @requires_postgres
    def test_busca_ordena_por_relevancia(self):
        """Post com maior densidade do termo aparece antes do menos relevante.

        post_baixo e criado primeiro (UUID menor) para que, em caso de empate
        no rank, o tiebreaker -id ainda favoreça post_alto. Com 7x vs 1x
        ocorrencia, o rank de post_alto deve ser estritamente maior.
        """
        user = UserFactory()
        # Criado PRIMEIRO → UUID menor (tiebreaker desfavorável → rank precisa ser maior)
        post_baixo = PostFactory(
            author=user,
            content_text="aprendi algo sobre django hoje pela primeira vez na vida",
        )
        # Criado SEGUNDO → UUID maior (tiebreaker favorável como seguro extra)
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

        # pt-BR
        resp_pt = client.get("/api/posts/search/?q=programação")
        ids_pt = [item["id"] for item in resp_pt.json()]
        assert str(post_ptbr.pk) in ids_pt

        # EN
        resp_en = client.get("/api/posts/search/?q=programming")
        ids_en = [item["id"] for item in resp_en.json()]
        assert str(post_en.pk) in ids_en

    def test_busca_sem_q_retorna_400(self):
        """Busca sem parâmetro q retorna 400."""
        user = UserFactory()
        client = _client_for(user)
        response = client.get("/api/posts/search/")
        assert response.status_code == 400
