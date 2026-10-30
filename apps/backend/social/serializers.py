from rest_framework import serializers
from .models import Follow, Block, Mute


class FollowSerializer(serializers.ModelSerializer):
    follower_username = serializers.CharField(source="follower.username", read_only=True)
    followed_username = serializers.CharField(source="followed.username", read_only=True)

    class Meta:
        model = Follow
        fields = ("id", "follower_username", "followed_username", "created_at", "is_close_friend")
        read_only_fields = ("id", "follower_username", "followed_username", "created_at")
