"""
Serializer do feed — herda de PostSerializer.
"""

from core.serializers.posts import PostSerializer


class FeedItemSerializer(PostSerializer):
    """Feed item é um Post com os mesmos campos."""
