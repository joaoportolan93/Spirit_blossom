from rest_framework import serializers

from core.models import Notification


class SenderSerializer(serializers.Serializer):
    """Dados públicos seguros do remetente da notificação."""

    username = serializers.CharField(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        try:
            return obj.profile.display_name or obj.username
        except Exception:
            return obj.username

    def get_avatar(self, obj):
        try:
            avatar = obj.profile.avatar
            if avatar and hasattr(avatar, "url"):
                return avatar.url
        except Exception:
            pass
        return None


class NotificationSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(
        source="sender.username", read_only=True, allow_null=True
    )
    sender = SenderSerializer(read_only=True, allow_null=True)
    is_read = serializers.BooleanField(source="read", read_only=True)
    target_url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "notification_type",
            "sender_username",
            "sender",
            "ref_id",
            "read",
            "is_read",
            "created_at",
            "target_url",
        )
        read_only_fields = fields

    def get_target_url(self, obj) -> str | None:
        """URL de navegação direta para o recurso referenciado."""
        if obj.notification_type == Notification.Type.FOLLOW:
            if obj.sender:
                return f"/profile/{obj.sender.username}"
        elif obj.notification_type in (
            Notification.Type.LIKE,
            Notification.Type.REPLY,
            Notification.Type.MENTION,
        ):
            if obj.ref_id:
                return f"/posts/{obj.ref_id}"
        return None

