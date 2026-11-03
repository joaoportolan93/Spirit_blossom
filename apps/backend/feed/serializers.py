"""
Serializer do feed — usa PostSerializer do app posts.
"""

from posts.serializers import PostSerializer


class FeedItemSerializer(PostSerializer):
    """Feed item é um Post com os mesmos campos."""
