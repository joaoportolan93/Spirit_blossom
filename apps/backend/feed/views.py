"""
View do feed cronológico seguindo (keyset pagination).
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .selectors import get_following_feed
from posts.serializers import PostSerializer


class FollowingFeedView(APIView):
    """
    GET /api/feed/following/
    Feed cronológico dos usuários que o user atual segue.
    Parâmetro opcional: ?cursor=<uuid> para paginação.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cursor = request.query_params.get("cursor")
        try:
            posts = get_following_feed(user=request.user, cursor=cursor, limit=20)
        except ValueError:
            from rest_framework import status
            return Response(
                {"detail": "Cursor de paginação inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PostSerializer(posts, many=True, context={"request": request})
        return Response(serializer.data)
