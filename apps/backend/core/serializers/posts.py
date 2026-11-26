"""
Serializers para publicações e rascunhos.
"""

from django.conf import settings
from rest_framework import serializers

from core.models import Draft, Post


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
            return request.build_absolute_uri(profile.avatar.url) if request else profile.avatar.url
        return None


def _build_media_url(file_field, request):
    if not file_field:
        return None
    try:
        url = file_field.url
    except Exception:
        return None
    return request.build_absolute_uri(url) if request else url


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
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
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
            "image_url",
            "video_url",
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
        if image and video:
            raise serializers.ValidationError(
                "Envie apenas uma imagem/GIF ou um vídeo por publicação."
            )
        if not text and not image and not video:
            raise serializers.ValidationError("A publicação precisa de texto ou mídia.")
        return attrs

    def create(self, validated_data):
        from core.services.posts import create_post
        from core.utils.media_security import MediaSanitizationError

        try:
            return create_post(
                author=self.context["request"].user,
                **validated_data,
            )
        except MediaSanitizationError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc
        except ValueError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class PostEditSerializer(serializers.ModelSerializer):
    content_text = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = Post
        fields = ("content_text",)

    def validate_content_text(self, value):
        max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
        cleaned = (value or "").strip()
        instance = getattr(self, "instance", None)
        has_media = bool(instance and (instance.image or instance.video))
        if not cleaned and not has_media:
            raise serializers.ValidationError("Conteúdo não pode ser vazio.")
        if len(cleaned) > max_chars:
            raise serializers.ValidationError(
                f"Conteúdo excede o limite de {max_chars} caracteres."
            )
        return cleaned

    def update(self, instance, validated_data):
        from core.services.posts import update_post

        return update_post(
            post=instance,
            user=self.context["request"].user,
            content_text=validated_data.get("content_text", ""),
        )


class DraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Draft
        fields = ("id", "content_text", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_content_text(self, value):
        max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
        if len(value) > max_chars:
            raise serializers.ValidationError(
                f"Conteúdo excede o limite de {max_chars} caracteres."
            )
        return value
