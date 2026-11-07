"""
Views do feed: Seguindo e Explorar (keyset pagination).
Contrato de resposta: {items: [{post_id, reason, cursor}], next_cursor}
conforme docs/api/feed-contract.json.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.feed import get_explore_feed, get_following_feed


class FollowingFeedView(APIView):
    """
    GET /api/feed/following/
    Feed cronológico dos usuários que o user atual segue.
    Parâmetro opcional: ?cursor=<uuid> para paginação.

    Resposta segue docs/api/feed-contract.json:
      {
        "items": [{"post_id": "...", "reason": "following", "cursor": "..."}],
        "next_cursor": "<uuid>" | null
      }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cursor = request.query_params.get("cursor")
        limit = 20
        try:
            posts = get_following_feed(user=request.user, cursor=cursor, limit=limit)
        except ValueError:
            return Response(
                {"detail": "Cursor de paginação inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        post_list = list(posts)
        items = [
            {
                "post_id": str(p.id),
                "reason": "following",
                "cursor": str(p.id),
            }
            for p in post_list
        ]

        next_cursor = str(post_list[-1].id) if len(post_list) == limit else None
        return Response({"items": items, "next_cursor": next_cursor})


class ExploreFeedView(APIView):
    """
    GET /api/feed/explore/
    Posts públicos de qualquer autor, cronológico, sem bloqueados/silenciados.
    Parâmetro opcional: ?cursor=<uuid> para paginação.

    Resposta segue docs/api/feed-contract.json:
      {
        "items": [{"post_id": "...", "reason": "explore", "cursor": "..."}],
        "next_cursor": "<uuid>" | null
      }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cursor = request.query_params.get("cursor")
        limit = 20
        try:
            posts = get_explore_feed(user=request.user, cursor=cursor, limit=limit)
        except ValueError:
            return Response(
                {"detail": "Cursor de Explorar inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        post_list = list(posts)
        items = [
            {
                "post_id": str(p.id),
                "reason": "explore",
                "cursor": str(p.id),
            }
            for p in post_list
        ]

        next_cursor = str(post_list[-1].id) if len(post_list) == limit else None
        return Response({"items": items, "next_cursor": next_cursor})
