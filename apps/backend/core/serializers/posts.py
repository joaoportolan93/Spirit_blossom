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


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
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
            "likes_count",
            "bookmarks_count",
            "comments_count",
            "hidden_comments_count",
            "is_edited",
            "edited_at",
            "created_at",
        )

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
        if len(value) > max_chars:
            raise serializers.ValidationError(
                f"Conteúdo excede o limite de {max_chars} caracteres."
            )
        return value

    def create(self, validated_data):
        from core.services.posts import create_post

        return create_post(
            author=self.context["request"].user,
            **validated_data,
        )


class PostEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ("content_text",)

    def validate_content_text(self, value):
        max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
        cleaned = (value or "").strip()
        if not cleaned:
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
            content_text=validated_data["content_text"],
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
