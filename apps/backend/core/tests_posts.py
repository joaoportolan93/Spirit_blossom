"""
Testes de CRUD de posts e validação de conteúdo (ADR-N2 / ADR-N21).
"""

import jsonschema
import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from conftest import set_auth_cookies
from core.factories import PostFactory, UserFactory


def _client_for(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


@pytest.mark.django_db
class TestPostCRUD:
    """CRUD básico de posts."""

    def test_criar_post_autenticado(self, db):
        """Usuário autenticado cria post com conteúdo válido."""
        client = APIClient()
        user = UserFactory()
        set_auth_cookies(client, user)

        response = client.post("/api/posts/", {"content_text": "Olá mundo!"})
        assert response.status_code == 201
        assert response.data["content_text"] == "Olá mundo!"
        assert response.data["author"]["username"] == user.username

    def test_criar_post_nao_autenticado_retorna_401(self, db):
        """Usuário não autenticado não pode criar post."""
        client = APIClient()
        response = client.post("/api/posts/", {"content_text": "Olá mundo!"})
        assert response.status_code == 401

    def test_post_max_chars_validado(self, db):
        """Conteúdo acima de POST_MAX_CHARS retorna 400."""
        client = APIClient()
        user = UserFactory()
        set_auth_cookies(client, user)

        conteudo_longo = "x" * (getattr(settings, "POST_MAX_CHARS", 3000) + 1)
        response = client.post("/api/posts/", {"content_text": conteudo_longo})
        assert response.status_code == 400

    def test_content_length_no_response(self, db):
        """Response de post inclui campo content_length correto."""
        client = APIClient()
        user = UserFactory()
        set_auth_cookies(client, user)

        texto = "Teste de conteúdo."
        response = client.post("/api/posts/", {"content_text": texto})
        assert response.status_code == 201
        assert response.data["content_length"] == len(texto)

    def test_listar_posts_publicos(self, db):
        """Feed lista posts públicos."""
        client = APIClient()
        user = UserFactory()
        set_auth_cookies(client, user)
        PostFactory(author=user, visibility="public")
        PostFactory(author=user, visibility="public")

        response = client.get("/api/posts/")
        assert response.status_code == 200
        results = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        assert len(results) >= 2

    def test_deletar_post_proprio(self, db):
        """Autor pode deletar seu próprio post."""
        client = APIClient()
        user = UserFactory()
        set_auth_cookies(client, user)
        post = PostFactory(author=user)

        response = client.delete(f"/api/posts/{post.id}/")
        assert response.status_code == 204

    def test_deletar_post_alheio_retorna_403_ou_404(self, db):
        """Usuário não pode deletar post de outro."""
        client = APIClient()
        user = UserFactory()
        outro = UserFactory()
        set_auth_cookies(client, user)
        post = PostFactory(author=outro)

        response = client.delete(f"/api/posts/{post.id}/")
        assert response.status_code in (403, 404)

    def test_delete_post_by_third_party_returns_403(self):
        """Terceiro tentando deletar post alheio recebe 403 Forbidden."""
        author = UserFactory()
        other = UserFactory()
        post = PostFactory(author=author)

        client = _client_for(other)
        res = client.delete(f"/api/posts/{post.id}/")
        assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestPostContrato:
    """Valida o contrato JSON do response de post."""

    def test_contrato_post_schema(self, db):
        """Response de criação de post tem todos os campos esperados."""
        POST_SCHEMA = {
            "type": "object",
            "required": [
                "id",
                "author",
                "content_text",
                "content_length",
                "visibility",
                "created_at",
            ],
            "properties": {
                "id": {"type": "string"},
                "author": {
                    "type": "object",
                    "required": ["id", "username"],
                    "properties": {
                        "id": {"type": "string"},
                        "username": {"type": "string"},
                        "avatar": {},
                    },
                },
                "content_text": {"type": "string"},
                "content_length": {"type": "integer"},
                "visibility": {"type": "string", "enum": ["public", "circle"]},
                "created_at": {"type": "string"},
            },
        }

        client = APIClient()
        user = UserFactory()
        set_auth_cookies(client, user)

        response = client.post("/api/posts/", {"content_text": "Teste de contrato."})
        assert response.status_code == 201
        jsonschema.validate(instance=response.data, schema=POST_SCHEMA)
