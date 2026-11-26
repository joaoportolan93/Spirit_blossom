"""
Serializers para Comentários (Onda 4 / ADR-N24).
Campos em inglês, formato snake_case, suporte a LGPD e placeholders seguros.
"""

from rest_framework import serializers

from comments.models import Comment
from core.models import Post


class AuthorSummarySerializer(serializers.Serializer):
    id = serializers.CharField()
    username = serializers.CharField()
    display_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    def get_display_name(self, user):
        try:
            profile = getattr(user, "profile", None)
            return getattr(profile, "display_name", "") or user.username
        except Exception:
            return getattr(user, "username", "")

    def get_avatar(self, user):
        try:
            profile = getattr(user, "profile", None)
            if profile and profile.avatar:
                return profile.avatar.url
        except Exception:
            pass
        return None


def _build_media_url(file_field, request):
    if not file_field:
        return None
    try:
        url = file_field.url
    except Exception:
        return None
    return request.build_absolute_uri(url) if request else url


class PostSummarySerializer(serializers.ModelSerializer):
    author = AuthorSummarySerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "content_text",
            "image_url",
            "video_url",
            "visibility",
            "comments_count",
            "likes_count",
            "created_at",
        ]

    def get_image_url(self, obj):
        return _build_media_url(getattr(obj, "image", None), self.context.get("request"))

    def get_video_url(self, obj):
        return _build_media_url(getattr(obj, "video", None), self.context.get("request"))


class CommentItemSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    parent_id = serializers.CharField(allow_null=True, required=False)
    preview_replies = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    is_liked = serializers.BooleanField(default=False)
    is_bookmarked = serializers.BooleanField(default=False)
    can_delete = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_hide = serializers.SerializerMethodField()
    is_placeholder = serializers.BooleanField(default=False)
    placeholder_reason = serializers.SerializerMethodField()
    is_muted = serializers.BooleanField(default=False)
    is_hidden = serializers.BooleanField(default=False)

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "parent_id",
            "depth",
            "content_text",
            "image_url",
            "video_url",
            "is_deleted",
            "is_edited",
            "edited_at",
            "is_hidden",
            "likes_count",
            "replies_count",
            "created_at",
            "is_liked",
            "is_bookmarked",
            "can_delete",
            "can_edit",
            "can_hide",
            "is_placeholder",
            "placeholder_reason",
            "is_muted",
            "preview_replies",
        ]

    def get_image_url(self, obj):
        if getattr(obj, "is_placeholder", False) or obj.is_deleted:
            return None
        return _build_media_url(getattr(obj, "image", None), self.context.get("request"))

    def get_video_url(self, obj):
        if getattr(obj, "is_placeholder", False) or obj.is_deleted:
            return None
        return _build_media_url(getattr(obj, "video", None), self.context.get("request"))

    def get_author(self, obj):
        # Se for placeholder ou tombstone excluído, não expõe dados do autor (LGPD)
        if getattr(obj, "is_placeholder", False) or obj.is_deleted or not obj.author:
            return None
        return AuthorSummarySerializer(obj.author).data

    def get_placeholder_reason(self, obj):
        reason = getattr(obj, "placeholder_reason", None)
        if not reason and getattr(obj, "is_deleted", False):
            return "deleted"
        return reason

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Oculta texto e mídia se for nó placeholder ou excluído (texto não vem do banco)
        if getattr(instance, "is_placeholder", False) or instance.is_deleted:
            data["content_text"] = ""
            data["image_url"] = None
            data["video_url"] = None
            data["author"] = None
            data["is_edited"] = False
            data["edited_at"] = None
        return data

    def get_preview_replies(self, obj):
        previews = getattr(obj, "preview_replies", [])
        if not previews:
            return []
        context = self.context
        return CommentItemSerializer(previews, many=True, context=context).data

    def get_can_delete(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        if obj.is_deleted:
            return False
        user_id = request.user.id
        return obj.author_id == user_id

    def get_can_hide(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        if obj.is_deleted:
            return False
        user_id = request.user.id
        return obj.post.author_id == user_id and obj.author_id != user_id

    def get_can_edit(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        if obj.is_deleted:
            return False
        return obj.author_id == request.user.id


class CommentCreateSerializer(serializers.Serializer):
    content_text = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, default="", trim_whitespace=True
    )
    parent_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    image = serializers.FileField(required=False, allow_null=True, default=None)
    video = serializers.FileField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        text = (attrs.get("content_text") or "").strip()
        image = attrs.get("image")
        video = attrs.get("video")
        if image and video:
            raise serializers.ValidationError(
                "Envie apenas uma imagem/GIF ou um vídeo por comentário."
            )
        if not text and not image and not video:
            raise serializers.ValidationError({"content_text": "Comment content cannot be empty."})
        return attrs


class CommentUpdateSerializer(serializers.Serializer):
    content_text = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)
