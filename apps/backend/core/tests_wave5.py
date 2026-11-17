"""
Suíte de testes da Onda 5 (Configurações, Privacidade, Mídia Segura, Temas e Notificações).
"""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.factories import PostFactory, UserFactory
from core.models import Follow, Notification, PostLike, UserProfile
from core.services.notifications import (
    create_notification,
    notify_follow_request_accepted,
    notify_post_liked,
    notify_user_followed,
)
from core.utils.image_security import (
    delete_old_avatar,
    sanitize_avatar_image,
)
from core.utils.visibility import can_view_likes_tab

User = get_user_model()


def _client_for(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


def _create_test_image(format="JPEG", size=(200, 200), color="blue"):
    buf = io.BytesIO()
    mode = "RGBA" if format == "PNG" else "RGB"
    img = Image.new(mode, size, color=color)
    img.save(buf, format=format)
    buf.seek(0)
    ext = format.lower()
    return SimpleUploadedFile(f"test.{ext}", buf.getvalue(), content_type=f"image/{ext}")


# ==============================================================================
# 1. Segurança de Mídia e Sanitização (AppSec)
# ==============================================================================


class TestImageSecurity:
    def test_sanitize_valid_jpeg(self):
        f = _create_test_image("JPEG", (100, 100))
        cleaned = sanitize_avatar_image(f)
        assert cleaned.name.endswith(".jpg")
        img = Image.open(cleaned)
        assert img.format == "JPEG"
        assert img.size == (100, 100)

    def test_sanitize_valid_png_with_alpha(self):
        f = _create_test_image("PNG", (120, 120))
        cleaned = sanitize_avatar_image(f)
        assert cleaned.name.endswith(".png")
        img = Image.open(cleaned)
        assert img.format == "PNG"

    def test_sanitize_valid_webp(self):
        f = _create_test_image("WEBP", (150, 150))
        cleaned = sanitize_avatar_image(f)
        img = Image.open(cleaned)
        assert img.format in ("JPEG", "PNG", "WEBP")

    def test_sanitize_resizes_large_dimensions(self):
        f = _create_test_image("JPEG", (1000, 800))
        cleaned = sanitize_avatar_image(f)
        img = Image.open(cleaned)
        assert img.width <= 512
        assert img.height <= 512

    def test_sanitize_rejects_svg(self):
        svg_content = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='10'/></svg>"
        f = SimpleUploadedFile("avatar.svg", svg_content, content_type="image/svg+xml")
        with pytest.raises(ValidationError, match="Extensão de imagem inválida"):
            sanitize_avatar_image(f)

    def test_sanitize_rejects_corrupted_file(self):
        f = SimpleUploadedFile("avatar.jpg", b"not-a-valid-image", content_type="image/jpeg")
        with pytest.raises(ValidationError, match="inválido ou corrompido"):
            sanitize_avatar_image(f)

    def test_sanitize_rejects_oversized_file(self):
        # 6 MB file
        big_content = b"0" * (6 * 1024 * 1024)
        f = SimpleUploadedFile("avatar.jpg", big_content, content_type="image/jpeg")
        with pytest.raises(ValidationError, match="não pode exceder 5 MB"):
            sanitize_avatar_image(f)

    def test_sanitize_rejects_none(self):
        with pytest.raises(ValidationError, match="Nenhum arquivo enviado"):
            sanitize_avatar_image(None)

    def test_delete_old_avatar(self, db):
        user = UserFactory()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        f = _create_test_image("JPEG", (50, 50))
        profile.avatar.save("old_avatar.jpg", f)
        profile.save()

        storage = profile.avatar.storage
        name = profile.avatar.name
        assert storage.exists(name)

        delete_old_avatar(profile)
        assert not storage.exists(name)

    def test_delete_old_avatar_safely_handles_empty(self):
        delete_old_avatar(None)
        user = User()
        delete_old_avatar(user)


# ==============================================================================
# 2. Troca de Senha (/api/auth/change-password/)
# ==============================================================================


@pytest.mark.django_db
class TestChangePassword:
    def test_change_password_success(self):
        user = UserFactory()
        user.set_password("OldSecret123!")
        user.save()

        client = _client_for(user)
        res = client.post(
            "/api/auth/change-password/",
            {
                "current_password": "OldSecret123!",
                "new_password": "NewSecret456!",
                "new_password_confirm": "NewSecret456!",
            },
        )
        assert res.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password("NewSecret456!")
        assert "access_token" in res.cookies

    def test_change_password_wrong_current(self):
        user = UserFactory()
        user.set_password("OldSecret123!")
        user.save()

        client = _client_for(user)
        res = client.post(
            "/api/auth/change-password/",
            {
                "current_password": "WrongPassword!",
                "new_password": "NewSecret456!",
                "new_password_confirm": "NewSecret456!",
            },
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Senha atual incorreta" in str(res.data)

    def test_change_password_mismatch(self):
        user = UserFactory()
        user.set_password("OldSecret123!")
        user.save()

        client = _client_for(user)
        res = client.post(
            "/api/auth/change-password/",
            {
                "current_password": "OldSecret123!",
                "new_password": "NewSecret456!",
                "new_password_confirm": "DifferentPassword789!",
            },
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "não coincidem" in str(res.data)

    def test_change_password_too_short(self):
        user = UserFactory()
        user.set_password("OldSecret123!")
        user.save()

        client = _client_for(user)
        res = client.post(
            "/api/auth/change-password/",
            {
                "current_password": "OldSecret123!",
                "new_password": "short",
                "new_password_confirm": "short",
            },
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# 3. Configurações do Usuário (/api/users/settings/ e /api/auth/me/)
# ==============================================================================


@pytest.mark.django_db
class TestUserSettings:
    def test_get_settings_and_me(self):
        user = UserFactory(username="testuser", email="test@example.com")
        user.profile.display_name = "Nome Teste"
        user.profile.bio = "Bio original"
        user.profile.save()

        client = _client_for(user)
        res_settings = client.get("/api/users/settings/")
        assert res_settings.status_code == status.HTTP_200_OK
        data = res_settings.json()
        assert data["username"] == "testuser"
        assert data["display_name"] == "Nome Teste"
        assert data["email"] == "test@example.com"
        assert data["bio"] == "Bio original"
        assert data["notify_likes"] is True
        assert data["notify_comments"] is True
        assert data["notify_follows"] is True
        assert data["notify_mentions"] is True
        assert data["show_likes_tab"] is True
        assert data["theme"] == "light"
        assert data["language"] == "pt-BR"

        res_me = client.get("/api/auth/me/")
        assert res_me.status_code == status.HTTP_200_OK
        data_me = res_me.json()
        assert data_me["username"] == "testuser"
        assert data_me["display_name"] == "Nome Teste"
        assert data_me["theme"] == "light"
        assert data_me["language"] == "pt-BR"

    def test_patch_settings_scalars(self):
        user = UserFactory()
        client = _client_for(user)

        res = client.patch(
            "/api/users/settings/",
            {
                "display_name": "João Portolan",
                "bio": "Nova bio atualizada",
                "notify_likes": False,
                "notify_comments": False,
                "notify_follows": False,
                "notify_mentions": False,
                "show_likes_tab": False,
                "theme": "oled",
                "language": "en",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["display_name"] == "João Portolan"
        assert data["bio"] == "Nova bio atualizada"
        assert data["notify_likes"] is False
        assert data["notify_comments"] is False
        assert data["notify_follows"] is False
        assert data["notify_mentions"] is False
        assert data["show_likes_tab"] is False
        assert data["theme"] == "oled"
        assert data["language"] == "en"

    def test_patch_settings_username_change_and_conflict(self):
        user1 = UserFactory(username="alice")
        user2 = UserFactory(username="bob")

        client1 = _client_for(user1)

        # Alteração com sucesso
        res = client1.patch("/api/users/settings/", {"username": "alice2"}, format="json")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["username"] == "alice2"

        # Conflito com username existente
        res_conflict = client1.patch("/api/users/settings/", {"username": "bob"}, format="json")
        assert res_conflict.status_code == status.HTTP_400_BAD_REQUEST
        assert "já está em uso" in str(res_conflict.data)

        # Username com caracteres inválidos
        res_invalid = client1.patch("/api/users/settings/", {"username": "alice!@#"}, format="json")
        assert res_invalid.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_settings_avatar_upload_and_removal(self):
        user = UserFactory()
        client = _client_for(user)

        avatar_file = _create_test_image("JPEG", (100, 100))
        res_upload = client.patch(
            "/api/users/settings/",
            {"avatar": avatar_file},
            format="multipart",
        )
        assert res_upload.status_code == status.HTTP_200_OK
        assert res_upload.json()["avatar"] is not None

        # Remoção do avatar
        res_remove = client.patch(
            "/api/users/settings/",
            {"remove_avatar": True},
            format="json",
        )
        assert res_remove.status_code == status.HTTP_200_OK
        assert res_remove.json()["avatar"] is None

        # Remoção via avatar=""
        res_upload2 = client.patch(
            "/api/users/settings/",
            {"avatar": _create_test_image("PNG", (80, 80))},
            format="multipart",
        )
        assert res_upload2.status_code == status.HTTP_200_OK
        assert res_upload2.json()["avatar"] is not None

        res_remove2 = client.patch(
            "/api/users/settings/",
            {"avatar": ""},
            format="json",
        )
        assert res_remove2.status_code == status.HTTP_200_OK
        assert res_remove2.json()["avatar"] is None

    def test_patch_settings_private_to_public_deletes_pending_requests(self):
        author = UserFactory()
        UserProfile.objects.update_or_create(user=author, defaults={"is_private": True})

        requester = UserFactory()
        Follow.objects.create(follower=requester, followed=author, status=Follow.Status.PENDING)
        assert Follow.objects.filter(
            follower=requester, followed=author, status=Follow.Status.PENDING
        ).exists()

        client = _client_for(author)
        res = client.patch(
            "/api/users/settings/",
            {"is_private": False},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["is_private"] is False

        # Regra Onda 5: pedidos pendentes foram DELETADOS, não viraram ativos
        assert not Follow.objects.filter(follower=requester, followed=author).exists()


# ==============================================================================
# 4. Supressão de Notificações com Flags Desativadas (Onda 5)
# ==============================================================================


@pytest.mark.django_db(transaction=True)
class TestNotificationSuppression:
    def test_notify_likes_suppressed_when_false(self):
        author = UserFactory()
        UserProfile.objects.update_or_create(user=author, defaults={"notify_likes": False})
        liker = UserFactory()
        post = PostFactory(author=author)

        notify_post_liked(sender=liker, post=post)
        assert (
            Notification.objects.filter(
                recipient=author, notification_type=Notification.Type.LIKE
            ).count()
            == 0
        )

        # Quando ativado, notificação é criada
        UserProfile.objects.filter(user=author).update(notify_likes=True)
        notify_post_liked(sender=liker, post=post)
        assert (
            Notification.objects.filter(
                recipient=author, notification_type=Notification.Type.LIKE
            ).count()
            == 1
        )

    def test_notify_follows_suppressed_when_false(self):
        followed = UserFactory()
        UserProfile.objects.update_or_create(user=followed, defaults={"notify_follows": False})
        follower = UserFactory()

        notify_user_followed(follower=follower, followed=followed)
        assert (
            Notification.objects.filter(
                recipient=followed, notification_type=Notification.Type.FOLLOW
            ).count()
            == 0
        )

        UserProfile.objects.filter(user=followed).update(notify_follows=True)
        notify_user_followed(follower=follower, followed=followed)
        assert (
            Notification.objects.filter(
                recipient=followed, notification_type=Notification.Type.FOLLOW
            ).count()
            == 1
        )

    def test_notify_follow_request_accepted_suppressed_when_false(self):
        follower = UserFactory()
        UserProfile.objects.update_or_create(user=follower, defaults={"notify_follows": False})
        followed = UserFactory()

        notify_follow_request_accepted(follower=follower, followed=followed)
        assert (
            Notification.objects.filter(
                recipient=follower, notification_type=Notification.Type.FOLLOW
            ).count()
            == 0
        )

    def test_notify_comments_and_mentions_suppressed(self):
        recipient = UserFactory()
        UserProfile.objects.update_or_create(
            user=recipient,
            defaults={"notify_comments": False, "notify_mentions": False},
        )
        sender = UserFactory()

        notif_comment = create_notification(
            recipient=recipient,
            sender=sender,
            notification_type=Notification.Type.REPLY,
        )
        assert notif_comment is None
        assert Notification.objects.filter(recipient=recipient).count() == 0

        notif_mention = create_notification(
            recipient=recipient,
            sender=sender,
            notification_type=Notification.Type.MENTION,
        )
        assert notif_mention is None
        assert Notification.objects.filter(recipient=recipient).count() == 0


# ==============================================================================
# 5. Visibilidade da Aba de Curtidas (/api/social/profile/<username>/likes/)
# ==============================================================================


@pytest.mark.django_db
class TestProfileLikesVisibility:
    def test_can_view_likes_tab_logic(self):
        author = UserFactory()
        author.profile.show_likes_tab = False
        author.profile.save()
        visitor = UserFactory()

        # O dono sempre pode ver sua própria aba de curtidas
        assert can_view_likes_tab(author, author) is True

        # Visitante não pode ver se show_likes_tab=False
        assert can_view_likes_tab(visitor, author) is False

        # Se autor permitir, visitante vê
        author.profile.show_likes_tab = True
        author.profile.save()
        assert can_view_likes_tab(visitor, author) is True

    def test_profile_likes_api_owner_sees_even_when_hidden(self):
        author = UserFactory()
        UserProfile.objects.update_or_create(user=author, defaults={"show_likes_tab": False})

        post = PostFactory(author=author, visibility="public")
        PostLike.objects.create(user=author, post=post)

        client_author = _client_for(author)
        res = client_author.get(f"/api/social/profile/{author.username}/likes/")
        assert res.status_code == status.HTTP_200_OK
        assert len(res.json()) == 1

    def test_profile_likes_api_visitor_blocked_when_hidden(self):
        author = UserFactory()
        UserProfile.objects.update_or_create(user=author, defaults={"show_likes_tab": False})

        post = PostFactory(author=author, visibility="public")
        PostLike.objects.create(user=author, post=post)

        visitor = UserFactory()
        client_visitor = _client_for(visitor)
        res = client_visitor.get(f"/api/social/profile/{author.username}/likes/")
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert "Aba de curtidas indisponível" in str(res.json())

    def test_profile_likes_api_visitor_sees_when_allowed(self):
        author = UserFactory()
        UserProfile.objects.update_or_create(user=author, defaults={"show_likes_tab": True})

        post = PostFactory(author=author, visibility="public")
        PostLike.objects.create(user=author, post=post)

        visitor = UserFactory()
        client_visitor = _client_for(visitor)
        res = client_visitor.get(f"/api/social/profile/{author.username}/likes/")
        assert res.status_code == status.HTTP_200_OK
        assert len(res.json()) == 1
