"""
Views do app posts.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from social.selectors import get_visible_posts_queryset

from .models import Post
from .serializers import PostSerializer


class PostListCreateView(APIView):
    """
    GET  /api/posts/   → lista posts visíveis (filtro de bloqueio aplicado)
    POST /api/posts/   → cria um post
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = get_visible_posts_queryset(request.user).order_by("-id")
        # Keyset pagination simples (cursor via query param)
        cursor = request.query_params.get("cursor")
        if cursor:
            import uuid

            try:
                cursor_uuid = uuid.UUID(cursor)
            except ValueError:
                return Response(
                    {"detail": "Cursor inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(id__lt=cursor_uuid)
        qs = qs[:20]
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
    GET    /api/posts/<id>/  → detalhe de um post (com filtro de visibilidade)
    DELETE /api/posts/<id>/  → apaga o próprio post
    """

    permission_classes = [IsAuthenticated]

    def _get_post(self, request, pk):
        qs = get_visible_posts_queryset(request.user)
        return get_object_or_404(qs, pk=pk)

    def get(self, request, pk):
        post = self._get_post(request, pk)
        serializer = PostSerializer(post, context={"request": request})
        return Response(serializer.data)

    def delete(self, request, pk):
        post = get_object_or_404(Post, pk=pk, author=request.user)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostSearchView(APIView):
    """
    GET /api/posts/search/?q=termo → busca full-text
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response(
                {"detail": "Parâmetro 'q' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .selectors import search_posts

        qs = search_posts(query=query)
        # Aplica filtro de bloqueio bidirecional sobre o resultado da busca
        visible_ids = get_visible_posts_queryset(request.user).values("id")
        qs = qs.filter(id__in=visible_ids)
        serializer = PostSerializer(qs[:20], many=True, context={"request": request})
        return Response(serializer.data)
