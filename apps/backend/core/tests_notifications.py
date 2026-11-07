"""
Testes de notificações (listagem, privacidade, idempotência, leitura e supressões).
"""

import pytest
from django.db import transaction
from rest_framework import status
from rest_framework.test import APIClient

from conftest import set_auth_cookies
from core.factories import BlockFactory, PostFactory, UserFactory
from core.models import Block, Mute, Notification, Post
from core.services.notifications import (
    create_notification,
    notify_post_liked,
    notify_user_followed,
)
from core.services.posts import like_post


def _client_for(user):
    client = APIClient()
    set_auth_cookies(client, user)
    return client


@pytest.mark.django_db
class TestNotifications:
    """Listagem e leitura básica de notificações."""

    def test_listar_notificacoes_autenticado(self, db):
        client = APIClient()
        user = UserFactory()
        set_auth_cookies(client, user)

        response = client.get("/api/notifications/")
        assert response.status_code == status.HTTP_200_OK

    def test_listar_notificacoes_nao_autenticado_retorna_401(self, db):
        client = APIClient()
        response = client.get("/api/notifications/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_contrato_notificacoes_schema(self, db):
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
        assert response.status_code == status.HTTP_200_OK
        if isinstance(response.data, dict):
            jsonschema.validate(instance=response.data, schema=SCHEMA)
        else:
            assert isinstance(response.data, list)


@pytest.mark.django_db(transaction=True)
class TestNotificationEnginePrivacy:
    """Regras de privacidade do motor de notificações."""

    def test_curtir_post_com_bloqueio_mutuo_nao_gera_notificacao(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        Block.objects.create(blocker=author, blocked=viewer)

        success = like_post(user=viewer, post_id=post.id)
        assert success is False
        assert not Notification.objects.filter(recipient=author).exists()

    def test_curtir_post_quando_autor_silenciou_sender_nao_gera_notificacao(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        Mute.objects.create(muter=author, muted=viewer)

        client = _client_for(viewer)
        res = client.post(f"/api/posts/{post.id}/like/")
        assert res.status_code == status.HTTP_201_CREATED
        assert not Notification.objects.filter(recipient=author, sender=viewer).exists()

    def test_seguir_usuario_gera_notificacao(self):
        follower = UserFactory()
        followed = UserFactory()

        client = _client_for(follower)
        res = client.post(f"/api/social/follow/{followed.username}/")
        assert res.status_code == status.HTTP_201_CREATED

        notif = Notification.objects.filter(
            recipient=followed,
            sender=follower,
            notification_type=Notification.Type.FOLLOW,
        ).first()
        assert notif is not None

    def test_notificacao_idempotencia(self):
        user1 = UserFactory()
        user2 = UserFactory()
        post = PostFactory(author=user1)

        n1 = create_notification(
            recipient=user1,
            sender=user2,
            notification_type=Notification.Type.LIKE,
            ref_id=str(post.id),
        )
        n2 = create_notification(
            recipient=user1,
            sender=user2,
            notification_type=Notification.Type.LIKE,
            ref_id=str(post.id),
        )
        assert n1.id == n2.id
        assert Notification.objects.filter(recipient=user1, ref_id=post.id).count() == 1


@pytest.mark.django_db
class TestNotificationViews:
    """Marcação de lido e operações em lote."""

    def test_notification_views_mark_read_and_mark_all(self):
        user = UserFactory()
        other = UserFactory()
        n1 = Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.FOLLOW
        )
        n2 = Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.FOLLOW
        )

        client = _client_for(user)

        res_list = client.get("/api/notifications/")
        assert res_list.status_code == status.HTTP_200_OK
        assert len(res_list.json()) == 2

        res_patch = client.patch(f"/api/notifications/{n1.id}/read/")
        assert res_patch.status_code == status.HTTP_200_OK
        n1.refresh_from_db()
        assert n1.read is True

        res_patch_404 = client.patch("/api/notifications/999999/read/")
        assert res_patch_404.status_code == status.HTTP_404_NOT_FOUND

        res_all = client.post("/api/notifications/mark-all-read/")
        assert res_all.status_code == status.HTTP_200_OK
        n2.refresh_from_db()
        assert n2.read is True


@pytest.mark.django_db
class TestNotificationSuppressions:
    """Supressão de notificações sob bloqueio, mute ou inacessibilidade."""

    @pytest.mark.django_db(transaction=True)
    def test_notify_user_followed_suppressions(self):
        user = UserFactory()
        other = UserFactory()

        with transaction.atomic():
            notify_user_followed(follower=user, followed=user)
        assert Notification.objects.count() == 0

        BlockFactory(blocker=user, blocked=other)
        with transaction.atomic():
            notify_user_followed(follower=user, followed=other)
        assert Notification.objects.count() == 0
        Block.objects.all().delete()

        Mute.objects.create(muter=other, muted=user)
        with transaction.atomic():
            notify_user_followed(follower=user, followed=other)
        assert Notification.objects.count() == 0

    @pytest.mark.django_db(transaction=True)
    def test_notify_post_liked_suppressions(self):
        author = UserFactory()
        liker = UserFactory()
        post = PostFactory(author=author, visibility="circle")

        BlockFactory(blocker=author, blocked=liker)
        with transaction.atomic():
            notify_post_liked(sender=liker, post=post)
        assert Notification.objects.count() == 0
        Block.objects.all().delete()

        with transaction.atomic():
            notify_post_liked(sender=liker, post=post)
        assert Notification.objects.count() == 0
