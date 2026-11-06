"""
Views do app posts (ADR-N2: finas, delegando para services e selectors).
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .selectors import get_post_detail_for_user, list_posts_keyset, search_posts
from .serializers import PostSerializer
from .services import delete_post


class PostListCreateView(APIView):
    """
    GET  /api/posts/   → lista posts visíveis via selector keyset
    POST /api/posts/   → cria um post via serializer/service
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cursor = request.query_params.get("cursor")
        try:
            qs = list_posts_keyset(user=request.user, cursor=cursor, limit=20)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PostSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        serializer = PostSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        post = serializer.save()
        return Response(
            PostSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PostDetailView(APIView):
    """
    GET    /api/posts/<id>/  → detalhe de um post via selector
    DELETE /api/posts/<id>/  → apaga o post via service
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        post = get_post_detail_for_user(post_id=pk, user=request.user)
        if not post:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PostSerializer(post, context={"request": request})
        return Response(serializer.data)

    def delete(self, request, pk):
        post = get_post_detail_for_user(post_id=pk, user=request.user)
        if not post:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            delete_post(post=post, user=request.user)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostSearchView(APIView):
    """
    GET /api/posts/search/?q=<termo>
    Busca full-text com SearchRank via selector.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response(
                {"detail": "Parâmetro 'q' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = search_posts(query=query, user=request.user)
        serializer = PostSerializer(qs[:20], many=True, context={"request": request})
        return Response(serializer.data)
