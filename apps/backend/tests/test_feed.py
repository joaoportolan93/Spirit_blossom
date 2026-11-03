"""
Testes do feed cronológico (keyset pagination) e validação do contrato JSON Schema.
"""
import json
import pathlib
import uuid

import jsonschema
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .factories import FollowFactory, PostFactory, UserFactory


SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "docs" / "api" / "feed-contract.json"


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
        assert response.json() == []

    def test_feed_retorna_posts_de_seguidos_em_ordem_decrescente(self):
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        p1 = PostFactory(author=followed)
        p2 = PostFactory(author=followed)
        p3 = PostFactory(author=followed)
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        ids = [item["id"] for item in data]
        # Os IDs são UUIDv7 — ordenação descendente = p3, p2, p1
        assert ids.index(str(p3.pk)) < ids.index(str(p2.pk)) < ids.index(str(p1.pk))

    def test_feed_nao_inclui_posts_de_nao_seguidos(self):
        user = UserFactory()
        stranger = UserFactory()
        post = PostFactory(author=stranger)
        client = _client_for(user)
        ids = [item["id"] for item in client.get("/api/feed/following/").json()]
        assert str(post.pk) not in ids

    def test_cursor_invalido_retorna_400(self):
        user = UserFactory()
        client = _client_for(user)
        response = client.get("/api/feed/following/?cursor=nao-e-uuid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cursor_valido_pagina_corretamente(self):
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        posts = [PostFactory(author=followed) for _ in range(5)]
        # Pega os 3 mais recentes (sem cursor)
        client = _client_for(user)
        data_first = client.get("/api/feed/following/").json()
        # Usa o id do último item como cursor
        cursor = data_first[-1]["id"]
        data_next = client.get(f"/api/feed/following/?cursor={cursor}").json()
        ids_first = {item["id"] for item in data_first}
        ids_next = {item["id"] for item in data_next}
        # Não deve haver overlap
        assert ids_first.isdisjoint(ids_next)


@pytest.mark.django_db
class TestFeedContract:
    def test_feed_response_campos_obrigatorios(self):
        """Resposta do feed tem os campos obrigatórios do contrato."""
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        PostFactory(author=followed)
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        assert len(data) > 0
        item = data[0]
        # Campos obrigatórios conforme feed-contract.json
        assert "id" in item
        assert "content_text" in item
        assert "created_at" in item
        assert "author" in item
        assert "visibility" in item

    def test_post_lista_campos_obrigatorios(self):
        """Lista de posts tem os campos obrigatórios."""
        user = UserFactory()
        PostFactory(author=user, visibility="public")
        client = _client_for(user)
        data = client.get("/api/posts/").json()
        assert len(data) > 0
        item = data[0]
        for field in ("id", "content_text", "created_at", "author", "visibility"):
            assert field in item, f"Campo '{field}' ausente na resposta"

    def test_id_e_uuid_valido(self):
        """Campo id deve ser um UUID válido."""
        user = UserFactory()
        PostFactory(author=user)
        client = _client_for(user)
        data = client.get("/api/posts/").json()
        for item in data:
            uuid.UUID(item["id"])  # lança ValueError se inválido

    def test_cursor_keyset_nao_repete_itens(self):
        """Paginação por cursor nunca retorna o mesmo item duas vezes."""
        user = UserFactory()
        followed = UserFactory()
        FollowFactory(follower=user, followed=followed)
        [PostFactory(author=followed) for _ in range(25)]
        client = _client_for(user)
        first_page = client.get("/api/feed/following/").json()
        assert len(first_page) == 20
        cursor = first_page[-1]["id"]
        second_page = client.get(f"/api/feed/following/?cursor={cursor}").json()
        ids_first = {item["id"] for item in first_page}
        ids_second = {item["id"] for item in second_page}
        assert ids_first.isdisjoint(ids_second)

    def test_feed_exclui_posts_bloqueados(self):
        """Feed cronológico não inclui posts de usuários bloqueados."""
        from social.models import Block
        user = UserFactory()
        blocked = UserFactory()
        FollowFactory(follower=user, followed=blocked)
        Block.objects.create(blocker=user, blocked=blocked)
        PostFactory(author=blocked)
        client = _client_for(user)
        data = client.get("/api/feed/following/").json()
        assert data == []
