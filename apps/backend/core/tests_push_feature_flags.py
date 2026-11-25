"""
Testes de Feature Flags, PushDevice (FCM) e Central de Notificações com filtros.

Cobertura:
- FeatureFlag: rollout, allowlist, anônimo, flag inexistente
- PushDevice: registro, reatribuição cross-account, remoção, deactivate
- Endpoint /api/notifications/: filtros categoria, unread_only
- Endpoint /api/notifications/unread-count/
- Endpoint /api/notifications/<id>/read/ (POST idempotente)
- Endpoint /api/notifications/devices/ (POST/DELETE)
- Endpoint /api/feature-flags/
- Push: mock FCM, remoção de token inválido, respeito a bloqueios/preferências
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from conftest import set_auth_cookies
from core.factories import UserFactory
from core.models import FeatureFlag, Notification, PushDevice
from core.services.feature_flags import get_flags_for_user, is_feature_enabled
from core.services.push import deactivate_user_devices, register_device, remove_device


def _client_for(user):
    client = APIClient()
    set_auth_cookies(client, user)
    return client


# =============================================================================
# Feature Flags — Avaliação
# =============================================================================


@pytest.mark.django_db
class TestFeatureFlagEvaluation:
    """is_feature_enabled — rollout, allowlist, anônimo."""

    def test_flag_inexistente_retorna_false(self):
        assert is_feature_enabled("flag_inexistente") is False

    def test_flag_desabilitada_globalmente_retorna_false(self):
        FeatureFlag.objects.create(key="ff_off", is_enabled=False, rollout_percentage=100)
        user = UserFactory()
        assert is_feature_enabled("ff_off", user) is False

    def test_flag_rollout_100_habilita_todos(self):
        FeatureFlag.objects.create(key="ff_100", is_enabled=True, rollout_percentage=100)
        user = UserFactory()
        assert is_feature_enabled("ff_100", user) is True

    def test_flag_rollout_0_desabilita_todos(self):
        FeatureFlag.objects.create(key="ff_0", is_enabled=True, rollout_percentage=0)
        user = UserFactory()
        assert is_feature_enabled("ff_0", user) is False

    def test_allowlist_habilita_usuario_mesmo_rollout_zero(self):
        flag = FeatureFlag.objects.create(key="ff_allowlist", is_enabled=True, rollout_percentage=0)
        user = UserFactory()
        flag.allowed_users.add(user)
        assert is_feature_enabled("ff_allowlist", user) is True

    def test_rollout_determinismo(self):
        """Mesma flag + mesmo usuário sempre retorna mesmo resultado."""
        FeatureFlag.objects.create(key="ff_det", is_enabled=True, rollout_percentage=50)
        user = UserFactory()
        result1 = is_feature_enabled("ff_det", user)
        result2 = is_feature_enabled("ff_det", user)
        assert result1 == result2

    def test_anonimo_rollout_100_habilita(self):
        FeatureFlag.objects.create(key="ff_anon", is_enabled=True, rollout_percentage=100)
        assert is_feature_enabled("ff_anon", user=None) is True

    def test_anonimo_rollout_50_desabilita(self):
        FeatureFlag.objects.create(key="ff_anon50", is_enabled=True, rollout_percentage=50)
        # Anônimos só habilitados com rollout=100
        assert is_feature_enabled("ff_anon50", user=None) is False

    def test_get_flags_for_user_retorna_dict(self):
        FeatureFlag.objects.create(key="push_notifications", is_enabled=True, rollout_percentage=100)
        FeatureFlag.objects.create(key="notification_center_filters", is_enabled=False, rollout_percentage=0)
        user = UserFactory()
        flags = get_flags_for_user(user)
        assert "push_notifications" in flags
        assert "notification_center_filters" in flags
        assert flags["push_notifications"] is True
        assert flags["notification_center_filters"] is False


# =============================================================================
# Feature Flags — Endpoint
# =============================================================================


@pytest.mark.django_db
class TestFeatureFlagsEndpoint:
    def test_get_flags_autenticado(self):
        FeatureFlag.objects.create(key="push_notifications", is_enabled=True, rollout_percentage=100)
        user = UserFactory()
        client = _client_for(user)
        res = client.get("/api/feature-flags/")
        assert res.status_code == status.HTTP_200_OK
        assert "flags" in res.data
        assert res.data["flags"]["push_notifications"] is True

    def test_get_flags_anonimo_permitido(self):
        FeatureFlag.objects.create(key="push_notifications", is_enabled=True, rollout_percentage=100)
        client = APIClient()
        res = client.get("/api/feature-flags/")
        assert res.status_code == status.HTTP_200_OK
        assert "flags" in res.data


# =============================================================================
# PushDevice — Registro e Reatribuição
# =============================================================================


@pytest.mark.django_db
class TestPushDeviceService:
    def test_registrar_novo_dispositivo(self):
        user = UserFactory()
        device = register_device(user=user, token="token-abc", platform="web")
        assert device.user == user
        assert device.token == "token-abc"
        assert device.is_active is True

    def test_reatribuicao_cross_account(self):
        """Token de outro usuário deve ser reatribuído ao novo usuário."""
        user1 = UserFactory()
        user2 = UserFactory()
        register_device(user=user1, token="shared-token", platform="web")
        # user2 loga no mesmo navegador
        device = register_device(user=user2, token="shared-token", platform="web")
        assert device.user == user2
        # Deve existir apenas 1 PushDevice com esse token
        assert PushDevice.objects.filter(token="shared-token").count() == 1

    def test_remover_dispositivo(self):
        user = UserFactory()
        register_device(user=user, token="token-rem", platform="web")
        result = remove_device(user=user, token="token-rem")
        assert result is True
        assert PushDevice.objects.filter(token="token-rem").exists() is False

    def test_remover_dispositivo_inexistente(self):
        user = UserFactory()
        result = remove_device(user=user, token="token-nao-existe")
        assert result is False

    def test_deactivate_user_devices(self):
        user = UserFactory()
        register_device(user=user, token="tok1", platform="web")
        register_device(user=user, token="tok2", platform="android")
        count = deactivate_user_devices(user=user)
        assert count == 2
        assert PushDevice.objects.filter(user=user, is_active=True).count() == 0


# =============================================================================
# PushDevice — Endpoints API
# =============================================================================


@pytest.mark.django_db
class TestPushDeviceEndpoints:
    def test_registrar_device_autenticado(self):
        user = UserFactory()
        client = _client_for(user)
        res = client.post(
            "/api/notifications/devices/",
            {"token": "fcm-token-123", "platform": "web"},
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED
        assert "id" in res.data
        assert PushDevice.objects.filter(token="fcm-token-123").exists()

    def test_registrar_device_nao_autenticado_retorna_401(self):
        client = APIClient()
        res = client.post(
            "/api/notifications/devices/",
            {"token": "fcm-token-anon"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_registrar_device_sem_token_retorna_400(self):
        user = UserFactory()
        client = _client_for(user)
        res = client.post("/api/notifications/devices/", {}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_device_especifico(self):
        user = UserFactory()
        register_device(user=user, token="tok-del", platform="web")
        client = _client_for(user)
        res = client.delete(
            "/api/notifications/devices/",
            {"token": "tok-del"},
            format="json",
        )
        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert not PushDevice.objects.filter(token="tok-del").exists()

    def test_delete_sem_token_desativa_todos(self):
        user = UserFactory()
        register_device(user=user, token="t1", platform="web")
        register_device(user=user, token="t2", platform="android")
        client = _client_for(user)
        res = client.delete("/api/notifications/devices/", {}, format="json")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert PushDevice.objects.filter(user=user, is_active=True).count() == 0


# =============================================================================
# Central de Notificações — Filtros e Unread Count
# =============================================================================


@pytest.mark.django_db
class TestNotificationCenterFilters:
    def test_unread_count_endpoint(self):
        user = UserFactory()
        other = UserFactory()
        Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.FOLLOW, read=False
        )
        Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.LIKE, read=True
        )
        client = _client_for(user)
        res = client.get("/api/notifications/unread-count/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["unread_count"] == 1

    def test_filtro_category_likes(self):
        user = UserFactory()
        other = UserFactory()
        Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.LIKE
        )
        Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.FOLLOW
        )
        client = _client_for(user)
        res = client.get("/api/notifications/?category=likes")
        assert res.status_code == status.HTTP_200_OK
        data = res.json() if not isinstance(res.data, list) else res.data
        notifications = data if isinstance(data, list) else data.get("results", data)
        types = [n["notification_type"] for n in notifications]
        assert all(t == "like" for t in types)
        assert len(types) >= 1

    def test_filtro_unread_only(self):
        user = UserFactory()
        other = UserFactory()
        Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.FOLLOW, read=False
        )
        Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.LIKE, read=True
        )
        client = _client_for(user)
        res = client.get("/api/notifications/?unread_only=true")
        assert res.status_code == status.HTTP_200_OK
        data = res.json() if not isinstance(res.data, list) else list(res.data)
        notifications = data if isinstance(data, list) else data.get("results", data)
        assert all(not n.get("read", False) for n in notifications)

    def test_mark_read_post_idempotente(self):
        user = UserFactory()
        other = UserFactory()
        notif = Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.FOLLOW
        )
        client = _client_for(user)
        res1 = client.post(f"/api/notifications/{notif.id}/read/")
        res2 = client.post(f"/api/notifications/{notif.id}/read/")
        assert res1.status_code == status.HTTP_200_OK
        assert res2.status_code == status.HTTP_200_OK
        notif.refresh_from_db()
        assert notif.read is True

    def test_mark_read_patch_retrocompativel(self):
        """PATCH ainda deve funcionar (retrocompatibilidade)."""
        user = UserFactory()
        other = UserFactory()
        notif = Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.LIKE
        )
        client = _client_for(user)
        res = client.patch(f"/api/notifications/{notif.id}/read/")
        assert res.status_code == status.HTTP_200_OK

    def test_notification_serializer_enriquecido(self):
        user = UserFactory()
        other = UserFactory()
        from core.models import Post
        post = Post.objects.create(
            author=other, content_text="Teste", visibility=Post.Visibility.PUBLIC
        )
        notif = Notification.objects.create(
            recipient=user,
            sender=other,
            notification_type=Notification.Type.LIKE,
            ref_id=post.id,
        )
        client = _client_for(user)
        res = client.get("/api/notifications/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json() if not isinstance(res.data, list) else list(res.data)
        notifications = data if isinstance(data, list) else data.get("results", data)
        item = next(n for n in notifications if str(n.get("id")) == str(notif.id))
        assert "sender" in item
        assert item["sender"]["username"] == other.username
        assert "target_url" in item


# =============================================================================
# Push — Mock FCM + Respeito a bloqueios/preferências
# =============================================================================


@pytest.mark.django_db
class TestPushWithMockFCM:
    def test_push_sem_credenciais_nao_crasha(self):
        """Sem FIREBASE_CREDENTIALS_PATH configurado, envio é no-op silencioso."""
        from core.services.push import send_push_notification

        result = send_push_notification(
            tokens=["fake-token"],
            title="Teste",
            body="Corpo",
            data={"type": "follow"},
        )
        # Sem credenciais → sent=0, sem exceção
        assert result["sent"] == 0

    def test_push_token_invalido_desativa_no_banco(self, monkeypatch):
        """Token inválido (UnregisteredError) deve ser marcado como is_active=False."""
        from core.services import push as push_module

        user = UserFactory()
        device = register_device(user=user, token="invalid-token-xyz", platform="web")

        # Mock firebase para simular UnregisteredError
        class FakeException(Exception):
            pass

        class FakeResponse:
            success = False
            exception = FakeException("UnregisteredError")

        class FakeBatchResponse:
            responses = [FakeResponse()]

        class FakeMessaging:
            @staticmethod
            def send_each(messages):
                return FakeBatchResponse()

            class Notification:
                def __init__(self, **kwargs):
                    pass

            class Message:
                def __init__(self, **kwargs):
                    pass

        def mock_get_app():
            return object()  # app não-None

        monkeypatch.setattr(push_module, "_get_firebase_app", mock_get_app)
        monkeypatch.setattr(push_module, "_firebase_initialized", True)

        # Patch firebase_admin e firebase_admin.messaging
        import sys
        import types

        fake_admin = types.ModuleType("firebase_admin")
        fake_mod = types.ModuleType("firebase_admin.messaging")
        fake_mod.send_each = FakeMessaging.send_each
        fake_mod.Message = FakeMessaging.Message
        fake_mod.Notification = FakeMessaging.Notification
        fake_admin.messaging = fake_mod
        sys.modules["firebase_admin"] = fake_admin
        sys.modules["firebase_admin.messaging"] = fake_mod

        # Sobrescreve tipo da exceção para combinar nome
        type(FakeResponse().exception).__name__ = "UnregisteredError"

        # Chama send_push_notification que por sua vez chama _deactivate_tokens
        result = push_module.send_push_notification(
            tokens=["invalid-token-xyz"],
            title="Título",
            body="Corpo",
            data={"test": "1"},
        )
        assert "invalid-token-xyz" in result["removed_tokens"]
        device.refresh_from_db()
        assert device.is_active is False

    def test_send_push_notification_task_execucao(self, monkeypatch):
        """Task Celery busca tokens dos devices do recipient e chama send_push_notification."""
        from core.tasks import send_push_notification_task

        user = UserFactory()
        other = UserFactory()
        register_device(user=user, token="celery-token-1", platform="web")
        notif = Notification.objects.create(
            recipient=user,
            sender=other,
            notification_type=Notification.Type.FOLLOW,
        )

        chamado = []

        def mock_send_push(*, tokens, title, body, data=None):
            chamado.append((tokens, title, body))
            return {"sent": 1, "removed_tokens": []}

        import core.services.push as push_mod
        monkeypatch.setattr(push_mod, "send_push_notification", mock_send_push)

        # Executa task síncrona
        send_push_notification_task(notif.id, title="Olá", body="Mundo")
        assert len(chamado) == 1
        assert "celery-token-1" in chamado[0][0]

    def test_export_user_data_inclui_push_devices(self):
        """export_user_data inclui metadados dos dispositivos push (Onda 7a / LGPD)."""
        from core.services.auth import export_user_data

        user = UserFactory()
        register_device(user=user, token="secret-token-123", platform="web", device_name="Chrome/Win")

        data = export_user_data(user=user)
        assert "push_devices" in data
        assert len(data["push_devices"]) == 1
        dev = data["push_devices"][0]
        assert dev["platform"] == "web"
        assert dev["device_name"] == "Chrome/Win"
        assert dev["is_active"] is True
        # Nunca vaza o token secreto no export
        assert "secret-token-123" not in str(dev)

    def test_push_respeitando_preferencia_notify_off(self):
        """Se notify_likes=False, nenhuma notificação criada, logo push não disparado."""
        from core.services.notifications import create_notification

        user = UserFactory()
        other = UserFactory()
        profile = user.profile
        profile.notify_likes = False
        profile.save()

        result = create_notification(
            recipient=user,
            sender=other,
            notification_type=Notification.Type.LIKE,
            ref_id="fake-ref-id",
        )
        assert result is None
        assert Notification.objects.filter(recipient=user).count() == 0
