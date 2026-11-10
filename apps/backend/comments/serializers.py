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
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, user):
        try:
            profile = getattr(user, "profile", None)
            if profile and profile.avatar:
                return profile.avatar.url
        except Exception:
            pass
        return None


class PostSummarySerializer(serializers.ModelSerializer):
    author = AuthorSummarySerializer(read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "content_text",
            "visibility",
            "comments_count",
            "likes_count",
            "created_at",
        ]


class CommentItemSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    parent_id = serializers.CharField(allow_null=True, required=False)
    preview_replies = serializers.SerializerMethodField()
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
        # Oculta texto se for nó placeholder ou excluído (texto não vem do banco)
        if getattr(instance, "is_placeholder", False):
            data["content_text"] = ""
            data["author"] = None
            data["is_edited"] = False
            data["edited_at"] = None
        elif instance.is_deleted:
            data["content_text"] = ""
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
    content_text = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)
    parent_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class CommentUpdateSerializer(serializers.Serializer):
    content_text = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)
