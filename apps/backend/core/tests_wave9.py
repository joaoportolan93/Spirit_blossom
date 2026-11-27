"""
Testes automatizados da Onda 9: Midia nos Posts + Posts Efemeros.

Cobertura:
- Upload de 1-4 imagens (happy path), bloqueio >4, arquivo invalido/corrompido
- Remocao de EXIF/GPS apos sanitizacao
- Acesso nao autorizado a midia de post privado/circulo -> 404 / proibido
- Criacao e expiracao de post efemero
- Expiracao filtra feeds/hashtags/busca/perfil (visible_posts_for)
- Detalhe de post expirado -> 404
- Task Celery de limpeza de posts expirados
- Exportacao LGPD inclui expires_at e media
- Retrocompatibilidade com application/json (sem imagens)
- Allowlist Post.objects via services/visibility
- Prefetch .media sem queries N+1
"""

import io
import os
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework import status

from conftest import auth_client
from core.factories import FollowFactory, PostFactory, UserFactory
from core.models import Draft, DraftMedia, Follow, Post, PostMedia
from core.services.auth import delete_account, export_user_data
from core.services.posts import (
    create_post,
    get_post_detail_for_user,
    list_posts_keyset,
)
from core.tasks import cleanup_expired_ephemeral_posts
from core.utils.image_security import (
    sanitize_post_media_image,
    sanitize_post_media_images,
)
from core.utils.visibility import visible_posts_for

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_image_file(
    name="test.jpg",
    fmt="JPEG",
    size=(100, 100),
    color=(255, 0, 0),
    with_exif=False,
) -> SimpleUploadedFile:
    """Gera um arquivo de imagem em memoria, opcionalmente com metadados EXIF nativos."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)

    if with_exif and fmt == "JPEG":
        exif = img.getexif()
        exif[0x010E] = "GPS-SECRET-COORDINATES"
        exif[0x013B] = "Camera-Serial-123"
        img.save(buf, format=fmt, exif=exif.tobytes())
    else:
        img.save(buf, format=fmt)

    buf.seek(0)
    mime = "image/jpeg" if fmt == "JPEG" else f"image/{fmt.lower()}"
    return SimpleUploadedFile(name, buf.read(), content_type=mime)


def make_png_file(name="test.png", size=(100, 100)):
    buf = io.BytesIO()
    img = Image.new("RGBA", size, color=(0, 128, 255, 200))
    img.save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


# ---------------------------------------------------------------------------
# TestPostMediaUpload -- Upload de imagens via API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPostMediaUpload:
    def test_upload_single_image(self):
        """POST /api/posts/ com 1 imagem cria PostMedia."""
        user = UserFactory()
        client = auth_client(user)
        img = make_image_file()

        resp = client.post(
            "/api/posts/",
            data={"content_text": "Ola!", "visibility": "public", "images": [img]},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert len(data["media"]) == 1
        assert data["media"][0]["order"] == 0
        assert data["is_ephemeral"] is False

    def test_upload_four_images(self):
        """Maximo de 4 imagens aceito."""
        user = UserFactory()
        client = auth_client(user)
        images = [make_image_file(f"img{i}.jpg") for i in range(4)]

        resp = client.post(
            "/api/posts/",
            data={"content_text": "Grid!", "visibility": "public", "images": images},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert len(resp.json()["media"]) == 4

    def test_upload_five_images_rejected(self):
        """Mais de 4 imagens -> 400."""
        user = UserFactory()
        client = auth_client(user)
        images = [make_image_file(f"img{i}.jpg") for i in range(5)]

        resp = client.post(
            "/api/posts/",
            data={"content_text": "Excesso", "visibility": "public", "images": images},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_invalid_file_rejected(self):
        """Arquivo que nao e imagem real -> 400."""
        user = UserFactory()
        client = auth_client(user)
        fake = SimpleUploadedFile("evil.jpg", b"not-an-image", content_type="image/jpeg")

        resp = client.post(
            "/api/posts/",
            data={"content_text": "Spam", "visibility": "public", "images": [fake]},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_svg_rejected(self):
        """SVG deve ser rejeitado na sanitizacao."""
        user = UserFactory()
        client = auth_client(user)
        svg = SimpleUploadedFile(
            "xss.svg",
            b"<svg><script>alert(1)</script></svg>",
            content_type="image/svg+xml",
        )
        resp = client.post(
            "/api/posts/",
            data={"content_text": "XSS?", "visibility": "public", "images": [svg]},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_alt_texts_stored(self):
        """alt_texts enviados via multipart sao armazenados no PostMedia."""
        user = UserFactory()
        client = auth_client(user)
        img = make_image_file()

        resp = client.post(
            "/api/posts/",
            data={
                "content_text": "Com alt",
                "visibility": "public",
                "images": [img],
                "alt_texts": ["Uma imagem bonita"],
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["media"][0]["alt_text"] == "Uma imagem bonita"

    def test_post_without_images_still_works(self):
        """Retrocompatibilidade: post JSON sem imagens aceito normalmente."""
        user = UserFactory()
        client = auth_client(user)
        resp = client.post(
            "/api/posts/",
            data={"content_text": "So texto", "visibility": "public"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["media"] == []

    def test_image_and_images_mutually_exclusive(self):
        """Nao pode usar image (legado) + images[] juntos."""
        user = UserFactory()
        client = auth_client(user)
        single_img = make_image_file("legacy.jpg")
        multi_img = make_image_file("multi.jpg")

        resp = client.post(
            "/api/posts/",
            data={
                "content_text": "Conflito",
                "visibility": "public",
                "image": single_img,
                "images": [multi_img],
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# TestExifRemoval -- Remocao de metadados EXIF/GPS
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExifRemoval:
    def test_exif_stripped_from_jpeg(self):
        """Imagem JPEG com EXIF: apos sanitizacao, nenhum EXIF permanece no output."""
        img_with_exif = make_image_file("gps.jpg", with_exif=True)
        raw_before = img_with_exif.read()
        img_with_exif.seek(0)
        assert b"GPS-SECRET-COORDINATES" in raw_before

        sanitized = sanitize_post_media_image(img_with_exif)
        sanitized_bytes = sanitized.read()
        result_img = Image.open(io.BytesIO(sanitized_bytes))
        assert len(result_img.getexif()) == 0
        assert b"GPS-SECRET-COORDINATES" not in sanitized_bytes
        assert b"Camera-Serial-123" not in sanitized_bytes

    def test_sanitized_file_has_uuid_name(self):
        """Nome do arquivo sanitizado deve ser UUID hex."""
        img = make_image_file()
        result = sanitize_post_media_image(img)
        name, _ext = os.path.splitext(result.name)
        assert len(name) == 32
        try:
            int(name, 16)
        except ValueError:
            pytest.fail("Nome do arquivo sanitizado nao e UUID hex")

    def test_sanitized_has_dimension_metadata(self):
        """ContentFile sanitizado carrega atributos de dimensao."""
        img = make_image_file(size=(200, 150))
        result = sanitize_post_media_image(img)
        assert hasattr(result, "_post_media_width")
        assert hasattr(result, "_post_media_height")
        assert result._post_media_width > 0
        assert result._post_media_height > 0


# ---------------------------------------------------------------------------
# TestPostMediaVisibility -- Acesso a midia de posts privados/circulo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPostMediaVisibility:
    def test_private_post_media_not_in_feed_for_non_follower(self):
        """Post de conta privada nao aparece para usuario sem follow."""
        viewer = UserFactory()
        owner = UserFactory()
        owner.profile.is_private = True
        owner.profile.save()

        post = PostFactory(author=owner, visibility=Post.Visibility.PUBLIC)

        qs = list(visible_posts_for(viewer).filter(id=post.id))
        assert len(qs) == 0

    def test_circle_post_visible_to_close_friend(self):
        """Post de circulo visivel para close friend."""
        viewer = UserFactory()
        owner = UserFactory()
        Follow.objects.create(follower=viewer, followed=owner, is_close_friend=True)

        post = PostFactory(author=owner, visibility=Post.Visibility.CIRCLE)

        qs = list(visible_posts_for(viewer).filter(id=post.id))
        assert len(qs) == 1

    def test_circle_post_not_visible_to_regular_follower(self):
        """Post de circulo invisivel para seguidor que nao e close friend."""
        viewer = UserFactory()
        owner = UserFactory()
        Follow.objects.create(follower=viewer, followed=owner, is_close_friend=False)

        post = PostFactory(author=owner, visibility=Post.Visibility.CIRCLE)

        qs = list(visible_posts_for(viewer).filter(id=post.id))
        assert len(qs) == 0

    def test_post_detail_of_inaccessible_post_returns_404(self):
        """GET /api/posts/<id>/ de post inacessivel -> 404."""
        viewer = UserFactory()
        client = auth_client(viewer)
        owner = UserFactory()
        owner.profile.is_private = True
        owner.profile.save()

        post = PostFactory(author=owner, visibility=Post.Visibility.PUBLIC)

        resp = client.get(f"/api/posts/{post.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# TestEphemeralPost -- Criacao, expiracao e visibilidade
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEphemeralPost:
    def test_create_ephemeral_24h(self):
        """Post efemero com 24h -> expires_at definido no momento da publicacao."""
        user = UserFactory()
        client = auth_client(user)
        before = timezone.now()

        resp = client.post(
            "/api/posts/",
            data={
                "content_text": "Efemero!",
                "visibility": "public",
                "ephemeral_duration_hours": 24,
            },
            format="json",
        )
        after = timezone.now()
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["is_ephemeral"] is True
        assert data["expires_at"] is not None

        from dateutil.parser import parse

        expires = parse(data["expires_at"])
        assert before + timedelta(hours=24) - timedelta(seconds=10) <= expires
        assert expires <= after + timedelta(hours=24) + timedelta(seconds=10)

    def test_ephemeral_durations_48h_7d(self):
        """Duracoes 48h e 168h (7d) aceitas."""
        user = UserFactory()
        client = auth_client(user)
        for hours in (48, 168):
            resp = client.post(
                "/api/posts/",
                data={
                    "content_text": f"Efemero {hours}h",
                    "visibility": "public",
                    "ephemeral_duration_hours": hours,
                },
                format="json",
            )
            assert resp.status_code == status.HTTP_201_CREATED
            assert resp.json()["is_ephemeral"] is True

    def test_invalid_ephemeral_duration_rejected(self):
        """Duracao invalida (ex: 10h) -> 400."""
        user = UserFactory()
        client = auth_client(user)
        resp = client.post(
            "/api/posts/",
            data={
                "content_text": "Invalido",
                "visibility": "public",
                "ephemeral_duration_hours": 10,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_expired_post_invisible_in_visible_posts_for(self):
        """Post com expires_at no passado nao retorna em visible_posts_for."""
        owner = UserFactory()
        post = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        viewer = UserFactory()
        qs = list(visible_posts_for(viewer).filter(id=post.id))
        assert len(qs) == 0

    def test_non_expired_post_visible(self):
        """Post efemero com expires_at no futuro ainda aparece."""
        owner = UserFactory()
        post = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        viewer = UserFactory()
        qs = list(visible_posts_for(viewer).filter(id=post.id))
        assert len(qs) == 1

    def test_expired_post_detail_returns_404(self):
        """GET /api/posts/<id>/ de post expirado -> 404."""
        viewer = UserFactory()
        client = auth_client(viewer)
        owner = UserFactory()
        post = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        resp = client.get(f"/api/posts/{post.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_expired_post_not_in_feed(self):
        """Post expirado ausente do feed (GET /api/posts/)."""
        viewer = UserFactory()
        client = auth_client(viewer)
        owner = UserFactory()
        Follow.objects.create(follower=viewer, followed=owner)

        expired_post = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        active_post = PostFactory(author=owner, visibility=Post.Visibility.PUBLIC)

        resp = client.get("/api/posts/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in resp.json()]
        assert str(expired_post.id) not in ids
        assert str(active_post.id) in ids

    def test_expired_post_not_in_hashtag_search(self):
        """Post expirado nao aparece em busca por hashtag."""
        viewer = UserFactory()
        client = auth_client(viewer)
        owner = UserFactory()

        expired = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            content_text="#onda9test expirado",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        from core.services.posts import sync_post_hashtags

        sync_post_hashtags(expired)

        resp = client.get("/api/posts/?hashtag=onda9test")
        assert resp.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in resp.json()]
        assert str(expired.id) not in ids

    def test_expires_at_set_at_publish_not_before(self):
        """expires_at definido ao chamar create_post (nunca antes)."""
        before = timezone.now()
        user = UserFactory()
        post = create_post(
            author=user,
            content_text="Efemero",
            ephemeral_duration_hours=24,
        )
        after = timezone.now()

        assert post.expires_at >= before + timedelta(hours=23, minutes=59)
        assert post.expires_at <= after + timedelta(hours=24, seconds=1)


# ---------------------------------------------------------------------------
# TestEphemeralCleanupTask -- Task Celery
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEphemeralCleanupTask:
    def test_cleanup_deletes_expired_posts(self):
        """cleanup_expired_ephemeral_posts remove posts expirados do banco."""
        owner = UserFactory()

        expired1 = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() - timedelta(hours=2),
        )
        expired2 = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() - timedelta(minutes=5),
        )
        active = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() + timedelta(hours=10),
        )
        permanent = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=None,
        )

        cleanup_expired_ephemeral_posts()

        assert not Post.objects.filter(id=expired1.id).exists()
        assert not Post.objects.filter(id=expired2.id).exists()
        assert Post.objects.filter(id=active.id).exists()
        assert Post.objects.filter(id=permanent.id).exists()

    def test_cleanup_does_not_error_without_media(self):
        """cleanup_expired_ephemeral_posts funciona mesmo com posts sem PostMedia."""
        owner = UserFactory()
        post = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        # Sem PostMedia criado
        cleanup_expired_ephemeral_posts()
        assert not Post.objects.filter(id=post.id).exists()


# ---------------------------------------------------------------------------
# TestLGPDExport -- Exportacao LGPD inclui Onda 9
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLGPDExport:
    def test_export_includes_expires_at(self):
        """export_user_data inclui expires_at nos posts."""
        user = UserFactory()
        PostFactory(
            author=user,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        data = export_user_data(user=user)
        post_data = data["posts"][0]
        assert "expires_at" in post_data

    def test_export_includes_media_list(self):
        """export_user_data inclui lista de media nos posts que tem PostMedia."""
        user = UserFactory()
        post = PostFactory(author=user, visibility=Post.Visibility.PUBLIC)
        PostMedia.objects.create(
            post=post,
            order=0,
            alt_text="Teste ALT",
            width=100,
            height=100,
        )

        data = export_user_data(user=user)
        post_data = next((p for p in data["posts"] if str(p["id"]) == str(post.id)), None)
        assert post_data is not None
        assert "media" in post_data
        assert len(post_data["media"]) == 1
        assert post_data["media"][0]["alt_text"] == "Teste ALT"


# ---------------------------------------------------------------------------
# TestImageSanitization -- Funcoes de sanitizacao de imagem
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestImageSanitization:
    def test_oversized_file_rejected(self):
        """Arquivo > 5 MB lanca ValidationError."""
        from django.core.exceptions import ValidationError

        big_data = b"X" * (6 * 1024 * 1024)
        fake = SimpleUploadedFile("big.jpg", big_data, content_type="image/jpeg")
        fake.size = len(big_data)

        with pytest.raises(ValidationError):
            sanitize_post_media_image(fake)

    def test_more_than_4_images_rejected(self):
        """Lista de 5 imagens levanta ValidationError."""
        from django.core.exceptions import ValidationError

        imgs = [make_image_file(f"img{i}.jpg") for i in range(5)]
        with pytest.raises(ValidationError):
            sanitize_post_media_images(imgs)

    def test_png_with_alpha_accepted(self):
        """PNG com canal alpha e aceito e processado."""
        png = make_png_file()
        result = sanitize_post_media_image(png)
        assert result.name.endswith(".png")

    def test_wrong_extension_rejected(self):
        """Extensao .bmp rejeitada mesmo que conteudo seja valido."""
        from django.core.exceptions import ValidationError

        buf = io.BytesIO()
        Image.new("RGB", (100, 100)).save(buf, format="JPEG")
        buf.seek(0)
        fake = SimpleUploadedFile("evil.bmp", buf.read(), content_type="image/bmp")
        with pytest.raises(ValidationError):
            sanitize_post_media_image(fake)


# ---------------------------------------------------------------------------
# TestAllowlist -- Post.objects so via services/visibility (ADR-N21)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAllowlist:
    def test_visible_posts_for_respects_expiry(self):
        """visible_posts_for exclui posts expirados -- confirma ADR-N21."""
        owner = UserFactory()
        viewer = UserFactory()

        expired = PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        active = PostFactory(author=owner, visibility=Post.Visibility.PUBLIC)

        result_ids = set(visible_posts_for(viewer).values_list("id", flat=True))
        assert expired.id not in result_ids
        assert active.id in result_ids

    def test_list_posts_keyset_prefetches_media(self):
        """list_posts_keyset retorna queryset com prefetch_related('media')."""
        owner = UserFactory()
        viewer = UserFactory()
        PostFactory(author=owner, visibility=Post.Visibility.PUBLIC)

        qs = list_posts_keyset(user=viewer)
        assert "media" in qs._prefetch_related_lookups

    def test_get_post_detail_prefetches_media(self):
        """get_post_detail_for_user prefetch 'media' (zero N+1)."""
        owner = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=owner, visibility=Post.Visibility.PUBLIC)

        result = get_post_detail_for_user(post_id=post.id, user=viewer)
        assert result is not None
        _ = list(result.media.all())


# ---------------------------------------------------------------------------
# TestMultiImagePost -- Post com multiplas imagens via service
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMultiImagePost:
    def test_create_post_with_3_images(self):
        """create_post cria PostMedia em ordem correta (order 0,1,2)."""
        user = UserFactory()
        images = [make_image_file(f"img{i}.jpg") for i in range(3)]
        alt_texts = ["Alt 0", "Alt 1", "Alt 2"]

        post = create_post(
            author=user,
            content_text="Grid",
            images=images,
            alt_texts=alt_texts,
        )

        media = list(post.media.order_by("order"))
        assert len(media) == 3
        for i, pm in enumerate(media):
            assert pm.order == i
            assert pm.alt_text == alt_texts[i]
            assert pm.width is not None
            assert pm.height is not None

    def test_create_post_no_text_no_media_fails(self):
        """Post sem texto e sem midia levanta ValueError."""
        user = UserFactory()
        with pytest.raises(ValueError):
            create_post(author=user, content_text="")


# ---------------------------------------------------------------------------
# TestProtectedMediaDelivery -- Entrega protegida de midia (ADR-N5 / ADR-N21)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProtectedMediaDelivery:
    def test_anonymous_cannot_access_protected_media(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        owner = UserFactory()
        post = create_post(author=owner, content_text="Privado", images=[make_image_file()])
        media_name = post.media.first().file.name

        anon = auth_client()
        resp = anon.get(f"/api/media/{media_name}")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_direct_protected_media_path_returns_404(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        owner = UserFactory()
        post = create_post(author=owner, content_text="Publico", images=[make_image_file()])
        media_name = post.media.first().file.name

        client = auth_client(owner)
        resp = client.get(f"/protected-media/{media_name}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_circle_post_media_blocked_for_non_member_allowed_for_member(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        owner = UserFactory()
        stranger = UserFactory()
        friend = UserFactory()
        Follow.objects.create(
            follower=friend, followed=owner, status=Follow.Status.ACTIVE, is_close_friend=True
        )

        post = create_post(
            author=owner,
            content_text="So circulo",
            visibility=Post.Visibility.CIRCLE,
            images=[make_image_file()],
        )
        media_url = f"/api/media/{post.media.first().file.name}"

        # Nao membro -> 404 indistinguivel
        assert auth_client(stranger).get(media_url).status_code == status.HTTP_404_NOT_FOUND
        # Close friend -> 200 OK com nosniff
        ok_resp = auth_client(friend).get(media_url)
        assert ok_resp.status_code == status.HTTP_200_OK
        assert ok_resp["X-Content-Type-Options"] == "nosniff"

    def test_private_account_media_blocked_for_non_follower(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        owner = UserFactory()
        owner.profile.is_private = True
        owner.profile.save()
        stranger = UserFactory()
        follower = UserFactory()
        FollowFactory(follower=follower, followed=owner, status=Follow.Status.ACTIVE)

        post = create_post(author=owner, content_text="Conta privada", images=[make_image_file()])
        media_url = f"/api/media/{post.media.first().file.name}"

        assert auth_client(stranger).get(media_url).status_code == status.HTTP_404_NOT_FOUND
        ok_resp = auth_client(follower).get(media_url)
        assert ok_resp.status_code == status.HTTP_200_OK

    def test_expired_ephemeral_media_returns_404(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        owner = UserFactory()
        post = create_post(
            author=owner,
            content_text="Expira",
            images=[make_image_file()],
            ephemeral_duration_hours=24,
        )
        post.expires_at = timezone.now() - timedelta(minutes=1)
        post.save(update_fields=["expires_at"])

        media_url = f"/api/media/{post.media.first().file.name}"
        assert auth_client(owner).get(media_url).status_code == status.HTTP_404_NOT_FOUND

    def test_path_traversal_and_unknown_prefix_rejected(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        client = auth_client(user)
        assert client.get("/api/media/../settings.py").status_code == status.HTTP_404_NOT_FOUND
        assert client.get("/api/media/unknown/secret.txt").status_code == status.HTTP_404_NOT_FOUND

    def test_x_accel_redirect_in_production_mode(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        settings.DEBUG = False
        settings.TESTING = False
        owner = UserFactory()
        post = create_post(author=owner, content_text="Prod media", images=[make_image_file()])
        rel_name = post.media.first().file.name

        resp = auth_client(owner).get(f"/api/media/{rel_name}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp["X-Accel-Redirect"] == f"/protected-media/{rel_name}"

    def test_delete_post_and_account_remove_physical_post_media(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        client = auth_client(user)

        post1 = create_post(author=user, content_text="P1", images=[make_image_file("p1.jpg")])
        pm1 = post1.media.first()
        storage = pm1.file.storage
        name1 = pm1.file.name
        assert storage.exists(name1)

        assert client.delete(f"/api/posts/{post1.id}/").status_code == status.HTTP_204_NO_CONTENT
        assert not storage.exists(name1)

        # Segundo post removido ao excluir a conta (LGPD)
        post2 = create_post(author=user, content_text="P2", images=[make_image_file("p2.jpg")])
        name2 = post2.media.first().file.name
        assert storage.exists(name2)

        delete_account(user=user)
        assert not storage.exists(name2)


# ---------------------------------------------------------------------------
# TestEphemeralDraftsAndPublish -- Rascunhos com midia, PATCH e publicacao
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEphemeralDraftsAndPublish:
    def test_create_draft_multipart_with_images_and_ephemeral_duration(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        other = UserFactory()
        client = auth_client(user)

        resp = client.post(
            "/api/posts/drafts/",
            data={
                "content_text": "Rascunho com fotos",
                "ephemeral_duration": "48",
                "images": [make_image_file("d1.jpg"), make_image_file("d2.jpg")],
                "alt_texts": ["Foto um", "Foto dois"],
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["ephemeral_duration_hours"] == 48
        assert len(data["media"]) == 2
        assert data["media"][0]["alt_text"] == "Foto um"
        assert data["media"][1]["alt_text"] == "Foto dois"

        draft = Draft.objects.get(pk=data["id"])
        assert not hasattr(draft, "expires_at")  # expires_at nunca inicia no rascunho

        # Somente o autor acessa a midia do rascunho
        dm_url = f"/api/media/{draft.media.first().file.name}"
        ok_resp = client.get(dm_url)
        assert ok_resp.status_code == status.HTTP_200_OK
        assert auth_client(other).get(dm_url).status_code == status.HTTP_404_NOT_FOUND

    def test_patch_draft_updates_duration_and_replaces_images(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        client = auth_client(user)

        create_resp = client.post(
            "/api/posts/drafts/",
            data={
                "content_text": "Original",
                "ephemeral_duration": "24",
                "images": [make_image_file("old.jpg")],
            },
            format="multipart",
        )
        draft_id = create_resp.json()["id"]
        old_name = DraftMedia.objects.get(draft_id=draft_id).file.name

        patch_resp = client.patch(
            f"/api/posts/drafts/{draft_id}/",
            data={
                "content_text": "Atualizado",
                "ephemeral_duration": "168",
                "images": [make_image_file("new1.jpg"), make_image_file("new2.jpg")],
                "alt_texts": '["Alt JSON 1", "Alt JSON 2"]',
            },
            format="multipart",
        )
        assert patch_resp.status_code == status.HTTP_200_OK
        pdata = patch_resp.json()
        assert pdata["content_text"] == "Atualizado"
        assert pdata["ephemeral_duration_hours"] == 168
        assert len(pdata["media"]) == 2
        assert pdata["media"][0]["alt_text"] == "Alt JSON 1"
        assert not DraftMedia.objects.filter(file=old_name).exists()

    def test_publish_draft_starts_expires_at_at_publish_time(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        client = auth_client(user)

        draft_resp = client.post(
            "/api/posts/drafts/",
            data={
                "content_text": "Vai publicar #onda9",
                "visibility": "circle",
                "ephemeral_duration": "24",
                "images": [make_image_file("pub.jpg")],
                "alt_texts": ["Capa"],
            },
            format="multipart",
        )
        assert draft_resp.status_code == status.HTTP_201_CREATED
        draft_id = draft_resp.json()["id"]

        before_publish = timezone.now()
        pub_resp = client.post(f"/api/posts/drafts/{draft_id}/publish/")
        after_publish = timezone.now()

        assert pub_resp.status_code == status.HTTP_201_CREATED
        post_data = pub_resp.json()
        assert post_data["is_ephemeral"] is True
        assert post_data["visibility"] == "circle"
        assert len(post_data["media"]) == 1
        assert post_data["media"][0]["alt_text"] == "Capa"
        assert not Draft.objects.filter(id=draft_id).exists()

        from dateutil.parser import parse

        expires = parse(post_data["expires_at"])
        assert before_publish + timedelta(hours=24) - timedelta(seconds=10) <= expires
        assert expires <= after_publish + timedelta(hours=24) + timedelta(seconds=10)

    def test_profile_excludes_expired_posts_and_counters(self):
        owner = UserFactory()
        viewer = UserFactory()
        PostFactory(author=owner, visibility=Post.Visibility.PUBLIC)
        PostFactory(
            author=owner,
            visibility=Post.Visibility.PUBLIC,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        resp = auth_client(viewer).get(f"/api/social/profile/{owner.username}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["posts_count"] == 1
        assert len(resp.json()["posts"]) == 1

    def test_large_dimension_image_rejected_anti_bomb(self):
        from django.core.exceptions import ValidationError

        big = make_image_file("wide.jpg", size=(4097, 10))
        with pytest.raises(ValidationError):
            sanitize_post_media_image(big)

    def test_multipart_ephemeral_string_coercion_and_invalid_strings(self):
        user = UserFactory()
        client = auth_client(user)

        ok = client.post(
            "/api/posts/",
            data={
                "content_text": "Com foto e prazo string",
                "images": [make_image_file("e.jpg")],
                "ephemeral_duration": "24",
            },
            format="multipart",
        )
        assert ok.status_code == status.HTTP_201_CREATED
        assert ok.json()["is_ephemeral"] is True

        bad = client.post(
            "/api/posts/",
            data={"content_text": "Prazo invalido", "ephemeral_duration": "abc"},
            format="json",
        )
        assert bad.status_code == status.HTTP_400_BAD_REQUEST

        bad_bool = client.post(
            "/api/posts/",
            data={"content_text": "Bool", "ephemeral_duration": True},
            format="json",
        )
        assert bad_bool.status_code == status.HTTP_400_BAD_REQUEST

    def test_edit_post_with_postmedia_allows_empty_text(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        client = auth_client(user)
        post = create_post(author=user, content_text="Texto inicial", images=[make_image_file()])
        resp = client.patch(f"/api/posts/{post.id}/", {"content_text": ""}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["content_text"] == ""

    def test_edit_post_remove_update_alt_and_add_media(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        client = auth_client(user)
        post = create_post(
            author=user,
            content_text="Post com duas fotos",
            images=[make_image_file("f1.jpg"), make_image_file("f2.jpg")],
            alt_texts=["Alt 1", "Alt 2"],
        )
        pm1, pm2 = list(post.media.order_by("order"))
        storage, pm1_name = pm1.file.storage, pm1.file.name
        assert storage.exists(pm1_name)

        # Remove pm1, atualiza alt de pm2 e adiciona nova imagem
        resp = client.patch(
            f"/api/posts/{post.id}/",
            {
                "content_text": "Editado com nova foto",
                "remove_media_ids": f'["{pm1.id}"]',
                "media_alt_updates": f'{{"{pm2.id}": "Alt 2 atualizado"}}',
                "images": [make_image_file("f3.jpg")],
                "alt_texts": ["Alt 3"],
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["is_edited"] is True
        assert len(data["media"]) == 2
        assert data["media"][0]["id"] == str(pm2.id)
        assert data["media"][0]["alt_text"] == "Alt 2 atualizado"
        assert data["media"][0]["order"] == 0
        assert data["media"][1]["alt_text"] == "Alt 3"
        assert data["media"][1]["order"] == 1
        assert not storage.exists(pm1_name)

        # Remove todas as imagens restantes mantendo texto
        rem_ids = [item["id"] for item in data["media"]]
        resp2 = client.patch(
            f"/api/posts/{post.id}/",
            {"remove_media_ids": rem_ids},
            format="json",
        )
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.json()["media"] == []

        # Se tentar zerar texto e sem midia -> 400
        bad = client.patch(f"/api/posts/{post.id}/", {"content_text": ""}, format="json")
        assert bad.status_code == status.HTTP_400_BAD_REQUEST

    def test_protected_media_for_legacy_post_comments_and_avatars(self, settings, tmp_path):
        from comments.models import Comment
        from core.models import Block

        settings.MEDIA_ROOT = tmp_path
        owner = UserFactory()
        viewer = UserFactory()
        blocked = UserFactory()
        Block.objects.create(blocker=owner, blocked=blocked)

        # Avatar protegido
        avatar_file = make_image_file("av.jpg")
        resp_av = auth_client(owner).patch(
            "/api/users/settings/", {"avatar": avatar_file}, format="multipart"
        )
        assert resp_av.status_code == status.HTTP_200_OK
        owner.refresh_from_db()
        av_path = f"/api/media/{owner.profile.avatar.name}"
        ok_av = auth_client(viewer).get(av_path)
        assert ok_av.status_code == status.HTTP_200_OK
        assert auth_client(blocked).get(av_path).status_code == status.HTTP_404_NOT_FOUND

        # Post legado com imagem/video e comentario com imagem
        legacy_post = create_post(
            author=owner, content_text="Legado", image=make_image_file("leg.jpg")
        )
        leg_url = f"/api/media/{legacy_post.image.name}"
        ok_leg = auth_client(viewer).get(leg_url)
        assert ok_leg.status_code == status.HTTP_200_OK
        assert auth_client(blocked).get(leg_url).status_code == status.HTTP_404_NOT_FOUND

        comment = Comment.objects.create(
            post=legacy_post, author=owner, content_text="c", image=make_image_file("cm.jpg")
        )
        cm_url = f"/api/media/{comment.image.name}"
        ok_cm = auth_client(viewer).get(cm_url)
        assert ok_cm.status_code == status.HTTP_200_OK
        assert auth_client(blocked).get(cm_url).status_code == status.HTTP_404_NOT_FOUND

    def test_draft_detail_get_clear_images_empty_validation_and_404s(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        owner = UserFactory()
        other = UserFactory()
        c_owner = auth_client(owner)
        c_other = auth_client(other)

        # Rascunho totalmente vazio -> 400
        empty_resp = c_owner.post("/api/posts/drafts/", {"content_text": "  "}, format="json")
        assert empty_resp.status_code == status.HTTP_400_BAD_REQUEST

        # Cria rascunho com texto e imagem
        res = c_owner.post(
            "/api/posts/drafts/",
            {
                "content_text": "Texto",
                "images": [make_image_file("dm.jpg")],
                "ephemeral_duration": "",
            },
            format="multipart",
        )
        assert res.status_code == status.HTTP_201_CREATED
        draft_id = res.json()["id"]

        # GET rascunho proprio -> 200; terceiro -> 404
        assert c_owner.get(f"/api/posts/drafts/{draft_id}/").status_code == status.HTTP_200_OK
        assert (
            c_other.get(f"/api/posts/drafts/{draft_id}/").status_code == status.HTTP_404_NOT_FOUND
        )
        assert (
            c_other.patch(
                f"/api/posts/drafts/{draft_id}/", {"content_text": "X"}, format="json"
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )
        assert (
            c_other.post(f"/api/posts/drafts/{draft_id}/publish/").status_code
            == status.HTTP_404_NOT_FOUND
        )

        # PATCH alt_texts sem substituir imagens + visibility
        p_alt = c_owner.patch(
            f"/api/posts/drafts/{draft_id}/",
            {"visibility": "circle", "alt_texts": ["Novo alt"]},
            format="json",
        )
        assert p_alt.status_code == status.HTTP_200_OK
        assert p_alt.json()["visibility"] == "circle"
        assert p_alt.json()["media"][0]["alt_text"] == "Novo alt"

        # PATCH clear_images=True com texto -> remove midias
        p_clear = c_owner.patch(
            f"/api/posts/drafts/{draft_id}/",
            {"clear_images": True, "ephemeral_duration_hours": "null"},
            format="json",
        )
        assert p_clear.status_code == status.HTTP_200_OK
        assert p_clear.json()["media"] == []
        assert p_clear.json()["ephemeral_duration_hours"] is None

        # Excluir conta limpa rascunhos com DraftMedia
        c_owner.post(
            "/api/posts/drafts/",
            {"content_text": "Outro", "images": [make_image_file("dm2.jpg")]},
            format="multipart",
        )
        dm = DraftMedia.objects.filter(draft__author=owner).first()
        dm_name = dm.file.name
        dm_storage = dm.file.storage
        assert dm_storage.exists(dm_name)
        delete_account(user=owner)
        assert not dm_storage.exists(dm_name)

    def test_cleanup_expired_removes_media_and_legacy_files(self, settings, tmp_path):
        from comments.models import Comment

        settings.MEDIA_ROOT = tmp_path
        owner = UserFactory()
        post = create_post(
            author=owner,
            content_text="Expira com tudo",
            images=[make_image_file("exp.jpg")],
            ephemeral_duration_hours=24,
        )
        c = Comment.objects.create(
            post=post, author=owner, content_text="Com anexo", image=make_image_file("cexp.jpg")
        )
        pm = post.media.first()
        pm_storage, pm_name = pm.file.storage, pm.file.name
        c_storage, c_name = c.image.storage, c.image.name

        post.expires_at = timezone.now() - timedelta(minutes=5)
        post.save(update_fields=["expires_at"])

        assert post.is_expired is True
        assert str(pm).startswith("PostMedia(")
        assert cleanup_expired_ephemeral_posts() == 1
        assert not pm_storage.exists(pm_name)
        assert not c_storage.exists(c_name)
        assert cleanup_expired_ephemeral_posts() == 0

    def test_sanitize_errors_and_serializer_conflict_edges(self):
        from django.core.exceptions import ValidationError

        user = UserFactory()
        client = auth_client(user)

        # sanitize_post_media_image(None)
        with pytest.raises(ValidationError):
            sanitize_post_media_image(None)

        # Conflito ephemeral_duration_hours != ephemeral_duration
        resp = client.post(
            "/api/posts/",
            data={
                "content_text": "Conflito",
                "ephemeral_duration_hours": 24,
                "ephemeral_duration": 48,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        # WEBP valido
        webp = make_image_file("test.webp", fmt="WEBP", size=(64, 64))
        clean_webp = sanitize_post_media_image(webp)
        assert clean_webp.name.endswith(".jpg")  # RGB WEBP reencoded cleanly without EXIF

        # DraftMedia __str__
        dm = DraftMedia(alt_text="x", order=0)
        assert str(dm).startswith("DraftMedia(")
