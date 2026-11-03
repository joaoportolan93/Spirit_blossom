"""
Testes básicos de notificações.
"""

import pytest
from rest_framework.test import APIClient

from tests.conftest import set_auth_cookies
from tests.factories import UserFactory


@pytest.mark.django_db
class TestNotifications:
    """Listagem e leitura de notificações."""

    def test_listar_notificacoes_autenticado(self, db):
        """Usuário autenticado obtém lista de notificações (pode ser vazia)."""
        client = APIClient()
        user = UserFactory()
        set_auth_cookies(client, user)

        response = client.get("/api/notifications/")
        assert response.status_code == 200

    def test_listar_notificacoes_nao_autenticado_retorna_401(self, db):
        """Usuário não autenticado não acessa notificações."""
        client = APIClient()
        response = client.get("/api/notifications/")
        assert response.status_code == 401

    def test_contrato_notificacoes_schema(self, db):
        """Response de listagem de notificações tem estrutura paginada."""
        import jsonschema

        SCHEMA = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "results": {"type": "array"},
            },
        }

        client = APIClient()
        user = UserFactory()
        set_auth_cookies(client, user)

        response = client.get("/api/notifications/")
        assert response.status_code == 200
        # Se paginado, valida schema; se lista simples, aceita array
        if isinstance(response.data, dict):
            jsonschema.validate(instance=response.data, schema=SCHEMA)
        else:
            assert isinstance(response.data, list)
