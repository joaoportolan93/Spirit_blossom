"""
Serializer do feed — usa PostSerializer do app posts.
"""
from posts.serializers import PostSerializer  # noqa: re-export para o feed


class FeedItemSerializer(PostSerializer):
    """Feed item é um Post com os mesmos campos."""
    pass
