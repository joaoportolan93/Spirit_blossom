"""
Views sociais (ADR-N2: finas, delegando para services e selectors).
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from posts.models import Post
from posts.serializers import PostSerializer

from .selectors import get_profile_counters, get_relationship_status
from .services import block_user, follow_user, unblock_user, unfollow_user

User = get_user_model()


class FollowView(APIView):
    """
    POST /api/social/follow/<username>/   → seguir usuário
    DELETE /api/social/follow/<username>/ → deixar de seguir
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)
        try:
            follow_user(follower=request.user, target_user=target)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Seguindo."}, status=status.HTTP_201_CREATED)

    def delete(self, request, username):
        target = get_object_or_404(User, username=username)
        deleted = unfollow_user(follower=request.user, target_user=target)
        if not deleted:
            return Response(
                {"detail": "Não estava seguindo este usuário."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlockView(APIView):
    """
    POST /api/social/block/<username>/   → bloquear usuário
    DELETE /api/social/block/<username>/ → desbloquear
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)
        try:
            block_user(blocker=request.user, target_user=target)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Usuário bloqueado."}, status=status.HTTP_201_CREATED)

    def delete(self, request, username):
        target = get_object_or_404(User, username=username)
        deleted = unblock_user(blocker=request.user, target_user=target)
        if not deleted:
            return Response(
                {"detail": "Este usuário não estava bloqueado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileDetailView(APIView):
    """
    GET /api/social/profile/<username>/
    Retorna perfil, contadores públicos, status de relacionamento e posts públicos.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        target = get_object_or_404(User.objects.select_related("profile"), username=username)

        counters = get_profile_counters(target_user=target)
        relationship = get_relationship_status(source_user=request.user, target_user=target)

        posts = (
            Post.objects.filter(author=target, visibility=Post.Visibility.PUBLIC)
            .select_related("author", "author__profile")
            .order_by("-id")[:20]
        )
        posts_data = PostSerializer(posts, many=True, context={"request": request}).data

        return Response(
            {
                "username": target.username,
                "bio": getattr(target.profile, "bio", "") if hasattr(target, "profile") else "",
                "avatar": (
                    target.profile.avatar.url
                    if hasattr(target, "profile") and target.profile.avatar
                    else None
                ),
                **counters,
                **relationship,
                "posts": posts_data,
            }
        )
