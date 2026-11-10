"""
Endpoints RESTful para o motor de comentários (Onda 4 / ADR-N24).
Proteção contra BOLA/IDOR, throttle, CSRF e conformidade com can_view_post.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from comments.models import Comment, CommentBookmark
from comments.selectors import (
    get_comment_thread_context,
    list_comment_replies,
    list_post_comments_with_preview,
    list_post_hidden_comments,
)
from comments.serializers import (
    CommentCreateSerializer,
    CommentItemSerializer,
    CommentUpdateSerializer,
    PostSummarySerializer,
)
from comments.services import (
    create_comment,
    delete_comment,
    edit_comment,
    hide_comment,
    toggle_comment_bookmark,
    toggle_comment_like,
    unhide_comment,
)
from core.services.posts import get_post_detail_for_user
from core.utils.visibility import can_view_post, is_user_blocked


class PostCommentsView(APIView):
    """
    GET /api/posts/<post_id>/comments/?sort=recent|likes|relevance&cursor=
    Lista comentários raiz com prévia de respostas até depth 2.

    POST /api/posts/<post_id>/comments/
    Cria comentário ou resposta em uma publicação.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_post_or_404(self, pk, user):
        post = get_post_detail_for_user(post_id=pk, user=user)
        if not post or not can_view_post(user, post):
            raise Http404
        return post

    def get(self, request, pk):
        post = self._get_post_or_404(pk, request.user)
        sort = request.query_params.get("sort", "recent")
        cursor = request.query_params.get("cursor")

        data = list_post_comments_with_preview(
            post=post,
            viewer=request.user,
            sort=sort,
            cursor=cursor,
        )
        serializer = CommentItemSerializer(data["items"], many=True, context={"request": request})
        return Response(
            {"items": serializer.data, "next_cursor": data["next_cursor"]},
            status=status.HTTP_200_OK,
        )

    def post(self, request, pk):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": _("Authentication credentials were not provided.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        post = self._get_post_or_404(pk, request.user)
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parent_id = serializer.validated_data.get("parent_id")
        parent = None
        if parent_id:
            parent = get_object_or_404(
                Comment.objects.select_related("post", "author"), pk=parent_id
            )
            if parent.post_id != post.id:
                return Response(
                    {"parent": _("Parent comment does not belong to this post.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if is_user_blocked(request.user, parent.author):
                raise Http404

        try:
            comment = create_comment(
                author=request.user,
                post=post,
                content_text=serializer.validated_data["content_text"],
                parent=parent,
            )
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response(
                e.message_dict if hasattr(e, "message_dict") else {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        output = CommentItemSerializer(comment, context={"request": request}).data
        return Response(output, status=status.HTTP_201_CREATED)


class CommentRepliesView(APIView):
    """
    GET /api/comments/<pk>/replies/?sort=recent&cursor=
    Lista respostas diretas paginadas a um comentário específico.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        comment = get_object_or_404(
            Comment.objects.select_related("post", "post__author", "author"), pk=pk
        )
        if not can_view_post(request.user, comment.post):
            raise Http404

        sort = request.query_params.get("sort", "recent")
        cursor = request.query_params.get("cursor")

        data = list_comment_replies(
            comment=comment,
            viewer=request.user,
            sort=sort,
            cursor=cursor,
        )
        serializer = CommentItemSerializer(data["items"], many=True, context={"request": request})
        return Response(
            {"items": serializer.data, "next_cursor": data["next_cursor"]},
            status=status.HTTP_200_OK,
        )


class CommentThreadView(APIView):
    """
    GET /api/comments/<pk>/thread/
    Retorna o contexto completo do Focar em uma única requisição.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        context = get_comment_thread_context(comment_id=pk, viewer=request.user)
        if context is None:
            raise Http404

        post_data = PostSummarySerializer(context["post"], context={"request": request}).data
        ancestors_data = CommentItemSerializer(
            context["ancestors"], many=True, context={"request": request}
        ).data
        comment_data = CommentItemSerializer(context["comment"], context={"request": request}).data
        replies_data = CommentItemSerializer(
            context["replies"], many=True, context={"request": request}
        ).data

        return Response(
            {
                "post": post_data,
                "ancestors": ancestors_data,
                "comment": comment_data,
                "replies": replies_data,
                "next_cursor": context["next_cursor"],
            },
            status=status.HTTP_200_OK,
        )


class CommentDetailView(APIView):
    """
    GET /api/comments/<pk>/
    PATCH /api/comments/<pk>/
    DELETE /api/comments/<pk>/
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_comment_or_404(self, pk, user):
        comment = get_object_or_404(
            Comment.objects.select_related("post", "post__author", "author"), pk=pk
        )
        if not can_view_post(user, comment.post) or is_user_blocked(user, comment.author):
            raise Http404
        return comment

    def get(self, request, pk):
        comment = self._get_comment_or_404(pk, request.user)
        serializer = CommentItemSerializer(comment, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": _("Authentication credentials were not provided.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        comment = self._get_comment_or_404(pk, request.user)
        serializer = CommentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = edit_comment(
                comment=comment,
                user=request.user,
                content_text=serializer.validated_data["content_text"],
            )
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response(
                e.message_dict if hasattr(e, "message_dict") else {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            CommentItemSerializer(updated, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": _("Authentication credentials were not provided.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        comment = self._get_comment_or_404(pk, request.user)
        try:
            delete_comment(comment=comment, user=request.user)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CommentLikeView(APIView):
    """POST /api/comments/<pk>/like/ (toggle curtida)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        comment = get_object_or_404(Comment.objects.select_related("post", "author"), pk=pk)
        if not can_view_post(request.user, comment.post) or is_user_blocked(request.user, comment.author):
            raise Http404

        try:
            is_liked, likes_count = toggle_comment_like(user=request.user, comment=comment)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {"is_liked": is_liked, "likes_count": likes_count},
            status=status.HTTP_200_OK,
        )


class CommentBookmarkView(APIView):
    """POST /api/comments/<pk>/bookmark/ (toggle favorito)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        comment = get_object_or_404(Comment.objects.select_related("post", "author"), pk=pk)
        if not can_view_post(request.user, comment.post) or is_user_blocked(request.user, comment.author):
            raise Http404

        try:
            is_bookmarked = toggle_comment_bookmark(user=request.user, comment=comment)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {"is_bookmarked": is_bookmarked},
            status=status.HTTP_200_OK,
        )


class CommentBookmarksListView(APIView):
    """GET /api/comments/bookmarks/ (lista comentários salvos pelo usuário logado)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        bookmarks = (
            CommentBookmark.objects.filter(user=request.user)
            .select_related("comment", "comment__author", "comment__post", "comment__post__author")
            .order_by("-created_at")[:50]
        )
        items = []
        for b in bookmarks:
            if can_view_post(request.user, b.comment.post) and not is_user_blocked(
                request.user, b.comment.author
            ):
                # Comentários ocultos saem dos favoritos de terceiros
                if b.comment.is_hidden and b.comment.author_id != request.user.id:
                    continue
                b.comment.is_bookmarked = True
                items.append(b.comment)

        serializer = CommentItemSerializer(items, many=True, context={"request": request})
        return Response({"items": serializer.data}, status=status.HTTP_200_OK)


class CommentHideView(APIView):
    """
    POST   /api/comments/<pk>/hide/  → Oculta resposta (apenas dono do post)
    DELETE /api/comments/<pk>/hide/  → Reexibe resposta (apenas dono do post)
    Qualquer outro usuário recebe 404 (indistinguível de inexistente).
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_comment_or_404(self, pk, user):
        comment = get_object_or_404(
            Comment.objects.select_related("post", "post__author", "author"), pk=pk
        )
        # Só o dono do post tem acesso a esta rota; qualquer outro recebe 404
        if comment.post.author_id != user.id:
            raise Http404
        return comment

    def post(self, request, pk):
        comment = self._get_comment_or_404(pk, request.user)
        try:
            hide_comment(comment=comment, user=request.user)
        except ValidationError as e:
            return Response(
                e.message_dict if hasattr(e, "message_dict") else {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionDenied:
            raise Http404

        return Response({"status": "hidden", "id": str(comment.id)}, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        comment = self._get_comment_or_404(pk, request.user)
        try:
            unhide_comment(comment=comment, user=request.user)
        except PermissionDenied:
            raise Http404

        return Response({"status": "unhidden", "id": str(comment.id)}, status=status.HTTP_200_OK)


class PostHiddenCommentsView(APIView):
    """
    GET /api/posts/<pk>/hidden-comments/?cursor=
    Lista comentários ocultos de uma publicação paginados (apenas dono do post).
    Qualquer outro usuário recebe 404.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        post = get_post_detail_for_user(post_id=pk, user=request.user)
        if not post or post.author_id != request.user.id:
            raise Http404

        cursor = request.query_params.get("cursor")
        data = list_post_hidden_comments(post=post, user=request.user, cursor=cursor, page_size=20)
        serializer = CommentItemSerializer(data["items"], many=True, context={"request": request})
        return Response({"items": serializer.data, "next_cursor": data["next_cursor"]}, status=status.HTTP_200_OK)
