"""
Serializers para o app posts.
"""
from django.conf import settings
from rest_framework import serializers

from .models import Post


class AuthorSerializer(serializers.Serializer):
    """Representação mínima do autor em posts."""
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj):
        profile = getattr(obj, "profile", None)
        if profile and profile.avatar:
            request = self.context.get("request")
            return request.build_absolute_uri(profile.avatar.url) if request else profile.avatar.url
        return None


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    content_length = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "content_text",
            "content_length",
            "visibility",
            "created_at",
        )
        read_only_fields = ("id", "author", "created_at")

    def get_content_length(self, obj):
        return len(obj.content_text)

    def validate_content_text(self, value):
        max_chars = getattr(settings, "POST_MAX_CHARS", 3000)
        if len(value) > max_chars:
            raise serializers.ValidationError(
                f"Conteúdo excede o limite de {max_chars} caracteres."
            )
        return value

    def create(self, validated_data):
        from .services import create_post
        return create_post(
            author=self.context["request"].user,
            **validated_data,
        )
