"""
Serializers para publicações e rascunhos.
"""

import json

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.models import Draft, DraftMedia, Post, PostMedia

_ALLOWED_EPHEMERAL_CHOICES = {24, 48, 168}


class EphemeralDurationField(serializers.Field):
    """Aceita 24, 48, 168, None ou equivalentes em string vindos de multipart/form-data."""

    default_error_messages = {
        "invalid": "Duração efêmera inválida. Use 24, 48, 168 ou null.",
    }

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_null", True)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if data is None or data == "":
            return None
        if isinstance(data, str):
            lowered = data.strip().lower()
            if lowered in ("", "null", "none"):
                return None
            if not lowered.isdigit():
                self.fail("invalid")
            value = int(lowered)
        elif isinstance(data, bool):
            self.fail("invalid")
        elif isinstance(data, int):
            value = data
        else:
            self.fail("invalid")

        if value not in _ALLOWED_EPHEMERAL_CHOICES:
            self.fail("invalid")
        return value

    def to_representation(self, value):
        return value


class AltTextsListField(serializers.ListField):
    """Suporta múltiplos campos `alt_texts` em FormData ou JSON array serializado."""

    def get_value(self, dictionary):
        raw = super().get_value(dictionary)
        if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], str):
            stripped = raw[0].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(x) if x is not None else "" for x in parsed]
                except ValueError:
                    pass
        return raw


def _build_protected_media_url(file_field, request):
    if not file_field or not getattr(file_field, "name", None):
        return None
    rel_url = f"/api/media/{file_field.name.lstrip('/')}"
    return request.build_absolute_uri(rel_url) if request else rel_url


def _resolve_ephemeral_duration(attrs, default=None):
    """Unifica ephemeral_duration_hours e alias ephemeral_duration."""
    has_hours = "ephemeral_duration_hours" in attrs
    has_alias = "ephemeral_duration" in attrs
    dur_hours = attrs.get("ephemeral_duration_hours")
    dur_alias = attrs.get("ephemeral_duration")
    if (
        has_hours
        and has_alias
        and dur_hours != dur_alias
        and dur_hours is not None
        and dur_alias is not None
    ):
        raise serializers.ValidationError(
            "Conflito entre ephemeral_duration_hours e ephemeral_duration."
        )
    if has_hours and dur_hours is not None:
        return dur_hours
    if has_alias and dur_alias is not None:
        return dur_alias
    if has_hours or has_alias:
        return None
    return default


# ---------------------------------------------------------------------------
# Onda 9 — Serializers de mídia de post e rascunho (leitura)
# ---------------------------------------------------------------------------


class BaseMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return _build_protected_media_url(getattr(obj, "file", None), self.context.get("request"))


class PostMediaSerializer(BaseMediaSerializer):
    class Meta:
        model = PostMedia
        fields = ("id", "url", "alt_text", "order", "width", "height")


class DraftMediaSerializer(BaseMediaSerializer):
    class Meta:
        model = DraftMedia
        fields = ("id", "url", "alt_text", "order", "width", "height")


class AuthorSerializer(serializers.Serializer):
    """Representação mínima do autor em posts."""

    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        profile = getattr(obj, "profile", None)
        return getattr(profile, "display_name", "") or obj.username

    def get_avatar(self, obj):
        profile = getattr(obj, "profile", None)
        if profile and profile.avatar:
            request = self.context.get("request")
            if getattr(settings, "MEDIA_URL", "").startswith("/protected-media"):
                return _build_protected_media_url(profile.avatar, request)
            return request.build_absolute_uri(profile.avatar.url) if request else profile.avatar.url
        return None


def _build_media_url(file_field, request):
    return _build_protected_media_url(file_field, request)


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    content_text = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=False,
    )
    image = serializers.FileField(write_only=True, required=False, allow_null=True)
    video = serializers.FileField(write_only=True, required=False, allow_null=True)
    # Onda 9: múltiplas imagens (write_only)
    images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False),
        write_only=True,
        required=False,
        allow_empty=True,
        max_length=4,
    )
    alt_texts = AltTextsListField(
        child=serializers.CharField(max_length=300, allow_blank=True),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    ephemeral_duration_hours = EphemeralDurationField(write_only=True, default=None)
    ephemeral_duration = EphemeralDurationField(write_only=True, default=None)
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    # Onda 9: leitura de mídia múltipla
    media = PostMediaSerializer(many=True, read_only=True)
    # Onda 9: leitura de expiração
    expires_at = serializers.DateTimeField(read_only=True)
    is_ephemeral = serializers.SerializerMethodField()
    content_length = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    hidden_comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "content_text",
            "content_length",
            "image",
            "video",
            "images",
            "alt_texts",
            "ephemeral_duration_hours",
            "ephemeral_duration",
            "image_url",
            "video_url",
            "media",
            "expires_at",
            "is_ephemeral",
            "visibility",
            "likes_count",
            "bookmarks_count",
            "comments_count",
            "hidden_comments_count",
            "is_edited",
            "edited_at",
            "is_liked",
            "is_bookmarked",
            "created_at",
        )
        read_only_fields = (
            "id",
            "author",
            "image_url",
            "video_url",
            "media",
            "expires_at",
            "is_ephemeral",
            "likes_count",
            "bookmarks_count",
            "comments_count",
            "hidden_comments_count",
            "is_edited",
            "edited_at",
            "created_at",
        )

    def get_image_url(self, obj):
        return _build_media_url(getattr(obj, "image", None), self.context.get("request"))

    def get_video_url(self, obj):
        return _build_media_url(getattr(obj, "video", None), self.context.get("request"))

    def get_is_ephemeral(self, obj):
        return getattr(obj, "is_ephemeral", False)

    def get_hidden_comments_count(self, obj):
        request = self.context.get("request")
        if (
            request
            and getattr(request.user, "is_authenticated", False)
            and obj.author_id == request.user.id
        ):
            return getattr(obj, "hidden_comments_count", 0)
        return 0

    def get_content_length(self, obj):
        return len(obj.content_text)

    def get_is_liked(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        return obj.likes.filter(user=request.user).exists()

    def get_is_bookmarked(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        return obj.bookmarks.filter(user=request.user).exists()

    def validate_content_text(self, value):
        max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
        if len(value or "") > max_chars:
            raise serializers.ValidationError(
                f"Conteúdo excede o limite de {max_chars} caracteres."
            )
        return value or ""

    def validate(self, attrs):
        text = (attrs.get("content_text") or "").strip()
        image = attrs.get("image")
        video = attrs.get("video")
        images = attrs.get("images") or []
        if image and video:
            raise serializers.ValidationError(
                "Envie apenas uma imagem/GIF ou um vídeo por publicação."
            )
        if (image or video) and images:
            raise serializers.ValidationError("Use images[] OU image/video, não ambos.")
        if len(images) > 4:
            raise serializers.ValidationError("Máximo de 4 imagens por publicação.")
        if not text and not image and not video and not images:
            raise serializers.ValidationError("A publicação precisa de texto ou mídia.")
        _resolve_ephemeral_duration(attrs)
        return attrs

    def create(self, validated_data):
        from core.services.posts import create_post
        from core.utils.media_security import MediaSanitizationError

        images = validated_data.pop("images", None) or []
        alt_texts = validated_data.pop("alt_texts", None) or []
        ephemeral_duration_hours = _resolve_ephemeral_duration(validated_data)
        validated_data.pop("ephemeral_duration_hours", None)
        validated_data.pop("ephemeral_duration", None)

        try:
            return create_post(
                author=self.context["request"].user,
                images=images if images else None,
                alt_texts=alt_texts,
                ephemeral_duration_hours=ephemeral_duration_hours,
                **validated_data,
            )
        except (MediaSanitizationError, DjangoValidationError, ValueError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class PostEditSerializer(serializers.ModelSerializer):
    content_text = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False),
        write_only=True,
        required=False,
        allow_empty=True,
        max_length=4,
    )
    alt_texts = AltTextsListField(
        child=serializers.CharField(max_length=300, allow_blank=True),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    remove_media_ids = AltTextsListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    media_alt_updates = serializers.JSONField(write_only=True, required=False)
    image = serializers.FileField(write_only=True, required=False, allow_null=True)
    video = serializers.FileField(write_only=True, required=False, allow_null=True)
    remove_image = serializers.BooleanField(write_only=True, required=False, default=False)
    remove_video = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Post
        fields = (
            "content_text",
            "images",
            "alt_texts",
            "remove_media_ids",
            "media_alt_updates",
            "image",
            "video",
            "remove_image",
            "remove_video",
        )

    def validate_content_text(self, value):
        max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
        cleaned = (value or "").strip()
        if len(cleaned) > max_chars:
            raise serializers.ValidationError(
                f"Conteúdo excede o limite de {max_chars} caracteres."
            )
        return cleaned

    def validate_media_alt_updates(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("media_alt_updates deve ser um objeto JSON.")
        return value

    def update(self, instance, validated_data):
        from core.services.posts import _UNSET, update_post
        from core.utils.media_security import MediaSanitizationError

        content_text = (
            validated_data["content_text"] if "content_text" in validated_data else _UNSET
        )
        try:
            return update_post(
                post=instance,
                user=self.context["request"].user,
                content_text=content_text,
                images=validated_data.get("images"),
                alt_texts=validated_data.get("alt_texts"),
                remove_media_ids=validated_data.get("remove_media_ids"),
                media_alt_updates=validated_data.get("media_alt_updates"),
                image=validated_data.get("image"),
                video=validated_data.get("video"),
                remove_image=validated_data.get("remove_image", False),
                remove_video=validated_data.get("remove_video", False),
            )
        except (MediaSanitizationError, DjangoValidationError, ValueError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class DraftSerializer(serializers.ModelSerializer):
    content_text = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=False,
    )
    visibility = serializers.ChoiceField(
        choices=Post.Visibility.choices,
        required=False,
        default=Post.Visibility.PUBLIC,
    )
    ephemeral_duration_hours = EphemeralDurationField()
    ephemeral_duration = EphemeralDurationField(write_only=True)
    images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False),
        write_only=True,
        required=False,
        allow_empty=True,
        max_length=4,
    )
    alt_texts = AltTextsListField(
        child=serializers.CharField(max_length=300, allow_blank=True),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    clear_images = serializers.BooleanField(write_only=True, required=False, default=False)
    media = DraftMediaSerializer(many=True, read_only=True)

    class Meta:
        model = Draft
        fields = (
            "id",
            "content_text",
            "visibility",
            "ephemeral_duration_hours",
            "ephemeral_duration",
            "images",
            "alt_texts",
            "clear_images",
            "media",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "media", "created_at", "updated_at")

    def validate_content_text(self, value):
        max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
        if len(value or "") > max_chars:
            raise serializers.ValidationError(
                f"Conteúdo excede o limite de {max_chars} caracteres."
            )
        return value or ""

    def validate(self, attrs):
        _resolve_ephemeral_duration(attrs)
        if self.instance is None:
            text = (attrs.get("content_text") or "").strip()
            images = attrs.get("images") or []
            if not text and not images:
                raise serializers.ValidationError("O rascunho precisa de texto ou mídia.")
        return attrs

    def create(self, validated_data):
        from core.services.posts import create_draft

        images = validated_data.pop("images", None) or []
        alt_texts = validated_data.pop("alt_texts", None) or []
        validated_data.pop("clear_images", None)
        ephemeral_duration_hours = _resolve_ephemeral_duration(validated_data)
        validated_data.pop("ephemeral_duration_hours", None)
        validated_data.pop("ephemeral_duration", None)

        try:
            return create_draft(
                author=self.context["request"].user,
                content_text=validated_data.get("content_text", ""),
                visibility=validated_data.get("visibility", Post.Visibility.PUBLIC),
                images=images if images else None,
                alt_texts=alt_texts,
                ephemeral_duration_hours=ephemeral_duration_hours,
            )
        except (DjangoValidationError, ValueError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc

    def update(self, instance, validated_data):
        from core.services.posts import _UNSET, update_draft

        kwargs = {}
        if "content_text" in validated_data:
            kwargs["content_text"] = validated_data["content_text"]
        if "visibility" in validated_data:
            kwargs["visibility"] = validated_data["visibility"]
        if "images" in validated_data:
            kwargs["images"] = validated_data["images"]
        if "alt_texts" in validated_data:
            kwargs["alt_texts"] = validated_data["alt_texts"]
        if "clear_images" in validated_data:
            kwargs["clear_images"] = validated_data["clear_images"]
        if "ephemeral_duration_hours" in validated_data or "ephemeral_duration" in validated_data:
            kwargs["ephemeral_duration_hours"] = _resolve_ephemeral_duration(validated_data)
        else:
            kwargs["ephemeral_duration_hours"] = _UNSET

        try:
            return update_draft(
                draft=instance,
                author=self.context["request"].user,
                **kwargs,
            )
        except (DjangoValidationError, ValueError) as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
