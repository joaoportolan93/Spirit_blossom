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
    delete_draft,
    delete_post,
    get_draft_for_author,
    get_post_detail_for_user,
    get_trending_hashtags,
    like_post,
    list_bookmarked_posts,
    list_drafts,
    list_posts_keyset,
    publish_draft,
    search_posts,
    unbookmark_post,
    unlike_post,
)


class PostListCreateView(APIView):
    """
    GET  /api/posts/   → lista posts visíveis via selector keyset (com ?hashtag= opcional)
    POST /api/posts/   → cria um post via serializer/service
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cursor = request.query_params.get("cursor")
        hashtag = request.query_params.get("hashtag")
        try:
            qs = list_posts_keyset(user=request.user, cursor=cursor, limit=20, hashtag=hashtag)
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
            return Response(
                {"detail": "Sem permissão para editar esta publicação."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = PostEditSerializer(
            post, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated_post = serializer.save()
        refreshed = (
            get_post_detail_for_user(post_id=updated_post.id, user=request.user) or updated_post
        )
        return Response(PostSerializer(refreshed, context={"request": request}).data)

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
    POST /api/posts/drafts/  → cria novo rascunho (JSON ou multipart)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = list_drafts(author=request.user)
        serializer = DraftSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        serializer = DraftSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        draft = serializer.save()
        return Response(
            DraftSerializer(draft, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DraftDetailView(APIView):
    """
    GET    /api/posts/drafts/<id>/  → detalha rascunho do usuário
    PATCH  /api/posts/drafts/<id>/  → edita rascunho (JSON ou multipart)
    DELETE /api/posts/drafts/<id>/  → exclui rascunho do usuário
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        draft = get_draft_for_author(author=request.user, draft_id=pk)
        if not draft:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DraftSerializer(draft, context={"request": request}).data)

    def patch(self, request, pk):
        draft = get_draft_for_author(author=request.user, draft_id=pk)
        if not draft:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = DraftSerializer(
            draft,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(DraftSerializer(updated, context={"request": request}).data)

    def delete(self, request, pk):
        deleted = delete_draft(author=request.user, draft_id=pk)
        if not deleted:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DraftPublishView(APIView):
    """
    POST /api/posts/drafts/<id>/publish/  → publica rascunho (inicia expires_at aqui)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        draft = get_draft_for_author(author=request.user, draft_id=pk)
        if not draft:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            post = publish_draft(draft=draft, author=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PostSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class TrendingHashtagsView(APIView):
    """
    GET /api/hashtags/trending/?limit=<int>
    Lista hashtags populares a partir de posts públicos visíveis (ADR-N21 / ADR-N24).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            limit = min(int(request.query_params.get("limit", 10)), 30)
        except (ValueError, TypeError):
            limit = 10
        results = get_trending_hashtags(user=request.user, limit=limit)
        return Response({"results": results})
