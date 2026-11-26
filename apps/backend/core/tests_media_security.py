"""Testes de sanitização e upload de imagem, GIF animado e vídeo em posts e comentários."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status

from comments.models import Comment
from comments.services import create_comment, delete_comment
from conftest import auth_client
from core.factories import UserFactory
from core.services.auth import delete_account, export_user_data
from core.services.posts import create_post, delete_post
from core.utils.media_security import (
    MAX_MEDIA_IMAGE_BYTES,
    MAX_MEDIA_VIDEO_BYTES,
    MediaSanitizationError,
    sanitize_media_image,
    sanitize_media_video,
)


def _make_static_image(fmt="PNG", ext="png", size=(80, 60), append_bytes=b""):
    buf = io.BytesIO()
    img = Image.new("RGBA" if fmt == "PNG" else "RGB", size, (236, 72, 153))
    img.save(buf, format=fmt)
    raw = buf.getvalue() + append_bytes
    return SimpleUploadedFile(f"foto.{ext}", raw, content_type=f"image/{ext}")


def _make_animated_gif(frames_count=3):
    frames = [Image.new("RGBA", (40, 40), (i * 60, 80, 200, 255)) for i in range(frames_count)]
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=120,
        loop=0,
        comment=b"metadata-secreto-gps",
    )
    return SimpleUploadedFile("anim.gif", buf.getvalue(), content_type="image/gif")


def _make_fake_mp4(name="clip.mp4", brand=b"isom", extra=b"\x00" * 32):
    header = b"\x00\x00\x00\x18ftyp" + brand + b"\x00\x00\x02\x00" + extra
    return SimpleUploadedFile(name, header, content_type="video/mp4")


def _make_fake_webm(name="clip.webm"):
    header = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\x82\x84webm\x00\x00\x00"
    return SimpleUploadedFile(name, header, content_type="video/webm")


class TestMediaSecurityUnit:
    def test_sanitize_static_image_strips_eof_payload_and_renames(self):
        polyglot = _make_static_image(
            fmt="JPEG", ext="jpg", append_bytes=b"<script>alert(1)</script>"
        )
        clean = sanitize_media_image(polyglot)
        assert clean.name.endswith(".jpg")
        assert clean.name != "foto.jpg"
        assert b"<script>" not in clean.read()

    def test_sanitize_animated_gif_preserves_frames_and_strips_comment(self):
        gif = _make_animated_gif(frames_count=3)
        clean = sanitize_media_image(gif)
        assert clean.name.endswith(".gif")
        assert clean.content_type == "image/gif"
        cleaned_img = Image.open(io.BytesIO(clean.read()))
        assert cleaned_img.format == "GIF"
        assert getattr(cleaned_img, "n_frames", 1) == 3
        assert b"metadata-secreto-gps" not in cleaned_img.info.get("comment", b"")

    def test_rejects_svg_fake_gif_and_oversized_image(self):
        svg = SimpleUploadedFile(
            "xss.svg", b"<svg onload='alert(1)'/>", content_type="image/svg+xml"
        )
        with pytest.raises(MediaSanitizationError):
            sanitize_media_image(svg)

        fake_gif = _make_static_image(fmt="PNG", ext="gif")
        with pytest.raises(MediaSanitizationError, match="assinatura GIF"):
            sanitize_media_image(fake_gif)

        huge = SimpleUploadedFile("huge.png", b"\x89PNG" + b"0" * (MAX_MEDIA_IMAGE_BYTES + 10))
        with pytest.raises(MediaSanitizationError, match="5 MB"):
            sanitize_media_image(huge)

    def test_video_validation_accepts_mp4_mov_webm_and_blocks_fake_or_oversized(self):
        clean_mp4 = sanitize_media_video(_make_fake_mp4("meu_video.mp4"))
        assert clean_mp4.name.endswith(".mp4")
        assert clean_mp4.name != "meu_video.mp4"

        clean_mov = sanitize_media_video(_make_fake_mp4("clip.mov", brand=b"qt  "))
        assert clean_mov.name.endswith(".mov")

        clean_webm = sanitize_media_video(_make_fake_webm())
        assert clean_webm.name.endswith(".webm")

        html_disguised = SimpleUploadedFile("evil.mp4", b"<html><script>1</script></html>")
        with pytest.raises(MediaSanitizationError, match="malicioso"):
            sanitize_media_video(html_disguised)

        bad_ext = SimpleUploadedFile("clip.avi", b"RIFF1234AVI ")
        with pytest.raises(MediaSanitizationError, match="permitido"):
            sanitize_media_video(bad_ext)

        bad_sig = SimpleUploadedFile("fake.mp4", b"NOT_AN_MP4_HEADER_12345")
        with pytest.raises(MediaSanitizationError, match="MP4/MOV"):
            sanitize_media_video(bad_sig)

        oversized = SimpleUploadedFile("big.mp4", b"\x00\x00\x00\x18ftypisom")
        oversized.size = MAX_MEDIA_VIDEO_BYTES + 1
        with pytest.raises(MediaSanitizationError, match="50 MB"):
            sanitize_media_video(oversized)


@pytest.mark.django_db
class TestMediaEndpointsAndLifecycle:
    def test_create_post_with_gif_and_video_via_api(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        client = auth_client(user)

        res_gif = client.post(
            "/api/posts/",
            {"content_text": "Olha esse GIF", "image": _make_animated_gif()},
            format="multipart",
        )
        assert res_gif.status_code == status.HTTP_201_CREATED
        assert res_gif.data["image_url"] is not None
        assert res_gif.data["video_url"] is None

        # Post só com vídeo (sem texto)
        res_vid = client.post(
            "/api/posts/",
            {"video": _make_fake_mp4()},
            format="multipart",
        )
        assert res_vid.status_code == status.HTTP_201_CREATED
        assert res_vid.data["video_url"] is not None

        # Rejeita imagem e vídeo juntos
        res_both = client.post(
            "/api/posts/",
            {"image": _make_static_image(), "video": _make_fake_mp4()},
            format="multipart",
        )
        assert res_both.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_comment_with_gif_and_tombstone_removes_media(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        author = UserFactory()
        replier = UserFactory()
        post = create_post(author=author, content_text="Post base")
        client = auth_client(author)

        res_c = client.post(
            f"/api/posts/{post.id}/comments/",
            {"content_text": "", "image": _make_animated_gif()},
            format="multipart",
        )
        assert res_c.status_code == status.HTTP_201_CREATED
        assert res_c.data["image_url"] is not None

        parent = Comment.objects.get(pk=res_c.data["id"])
        img_name = parent.image.name
        assert parent.image.storage.exists(img_name)

        # Cria resposta para forçar Tombstone ao excluir o pai
        create_comment(author=replier, post=post, content_text="Resposta", parent=parent)
        delete_comment(comment=parent, user=author)

        parent.refresh_from_db()
        assert parent.is_deleted is True
        assert not parent.image

        res_list = client.get(f"/api/posts/{post.id}/comments/")
        assert res_list.data["items"][0]["image_url"] is None
        assert res_list.data["items"][0]["video_url"] is None

    def test_lgpd_export_and_delete_account_cleans_post_media(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        post = create_post(author=user, content_text="Com mídia", image=_make_static_image())
        storage = post.image.storage
        img_name = post.image.name
        assert storage.exists(img_name)

        exported = export_user_data(user=user)
        assert exported["posts"][0]["image"] is not None

        delete_account(user=user)
        assert not storage.exists(img_name)

    def test_delete_post_removes_physical_media(self, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        user = UserFactory()
        post = create_post(author=user, content_text="Com vídeo", video=_make_fake_mp4())
        storage = post.video.storage
        vid_name = post.video.name
        assert storage.exists(vid_name)

        delete_post(post=post, user=user)
        assert not storage.exists(vid_name)
