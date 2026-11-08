from rest_framework import serializers

from core.models import Follow


class FollowSerializer(serializers.ModelSerializer):
    follower_username = serializers.CharField(source="follower.username", read_only=True)
    followed_username = serializers.CharField(source="followed.username", read_only=True)

    class Meta:
        model = Follow
        fields = ("id", "follower_username", "followed_username", "created_at", "is_close_friend")
        read_only_fields = ("id", "follower_username", "followed_username", "created_at")


class FollowRequestSerializer(serializers.ModelSerializer):
    """Serializer para GET /api/social/follow-requests/ — restrito a campos públicos."""

    username = serializers.CharField(source="follower.username", read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Follow
        fields = ("id", "username", "avatar", "created_at")
        read_only_fields = fields

    def get_avatar(self, obj) -> str | None:
        profile = getattr(obj.follower, "profile", None)
        if profile and profile.avatar:
            return profile.avatar.url
        return None
