"""
Views de publicações e rascunhos (ADR-N2: finas, delegando para services).
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers.posts import DraftSerializer, PostEditSerializer, PostSerializer
from core.services.posts import (
    bookmark_post,
    create_draft,
    delete_draft,
    delete_post,
    get_post_detail_for_user,
    like_post,
    list_bookmarked_posts,
    list_drafts,
    list_posts_keyset,
    search_posts,
    unbookmark_post,
    unlike_post,
)


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
    PATCH  /api/posts/<id>/  → edita texto do post (apenas autor)
    DELETE /api/posts/<id>/  → apaga o post via service
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        post = get_post_detail_for_user(post_id=pk, user=request.user)
        if not post:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PostSerializer(post, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, pk):
        post = get_post_detail_for_user(post_id=pk, user=request.user)
        if not post:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if post.author != request.user:
            return Response({"detail": "Sem permissão para editar esta publicação."}, status=status.HTTP_403_FORBIDDEN)
        serializer = PostEditSerializer(post, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PostSerializer(post, context={"request": request}).data)

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


class PostLikeView(APIView):
    """
    POST   /api/posts/<id>/like/  → curtir publicação
    DELETE /api/posts/<id>/like/  → descurtir publicação
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        success = like_post(user=request.user, post_id=pk)
        if not success:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": "Publicação curtida."}, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        success = unlike_post(user=request.user, post_id=pk)
        if not success:
            return Response(
                {"detail": "Não estava curtido."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostBookmarkView(APIView):
    """
    POST   /api/posts/<id>/bookmark/  → salvar publicação
    DELETE /api/posts/<id>/bookmark/  → remover publicação dos salvos
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        success = bookmark_post(user=request.user, post_id=pk)
        if not success:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": "Publicação salva."}, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        success = unbookmark_post(user=request.user, post_id=pk)
        if not success:
            return Response(
                {"detail": "Não estava salva."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookmarkedPostListView(APIView):
    """
    GET /api/posts/bookmarks/  → lista publicações salvas visíveis
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cursor = request.query_params.get("cursor")
        try:
            qs = list_bookmarked_posts(user=request.user, cursor=cursor, limit=20)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PostSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


class DraftListCreateView(APIView):
    """
    GET  /api/posts/drafts/  → lista rascunhos do usuário
    POST /api/posts/drafts/  → cria novo rascunho
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = list_drafts(author=request.user)
        serializer = DraftSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = DraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        draft = create_draft(
            author=request.user,
            content_text=serializer.validated_data["content_text"],
        )
        return Response(DraftSerializer(draft).data, status=status.HTTP_201_CREATED)


class DraftDetailView(APIView):
    """
    DELETE /api/posts/drafts/<id>/  → exclui rascunho do usuário
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        deleted = delete_draft(author=request.user, draft_id=pk)
        if not deleted:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
