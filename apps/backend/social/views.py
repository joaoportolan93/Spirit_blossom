"""
Views sociais (ADR-N2: finas, delegando para services e selectors).
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from posts.serializers import PostSerializer

from .models import Follow
from .selectors import (
    can_view_profile,
    get_profile_counters,
    get_relationship_status,
    is_user_blocked,
    visible_posts_for,
)
from .services import (
    add_to_close_friends,
    block_user,
    follow_user,
    mute_user,
    remove_from_close_friends,
    unblock_user,
    unfollow_user,
    unmute_user,
)

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
    Retorna perfil, contadores públicos, status de relacionamento e posts visíveis.
    Bloqueio bilateral retorna 404 (ADR-N21).
    Conta privada sem seguimento ativo retorna perfil mínimo (200 OK)
    para permitir solicitação de follow.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        target = get_object_or_404(User.objects.select_related("profile"), username=username)

        # 1. Se houver bloqueio bilateral ou conta desativada para auth -> 404 (inacessível)
        if is_user_blocked(request.user, target) or not getattr(target, "is_valid_for_auth", True):
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        profile = getattr(target, "profile", None)
        is_private = getattr(profile, "is_private", False)
        relationship = get_relationship_status(source_user=request.user, target_user=target)

        avatar_url = profile.avatar.url if profile and profile.avatar else None

        # 2. Se for conta privada e viewer não puder ver perfil completo -> perfil mínimo (200 OK)
        if not can_view_profile(request.user, target):
            return Response(
                {
                    "username": target.username,
                    "bio": "",
                    "avatar": avatar_url,
                    "is_private": True,
                    "posts_count": 0,
                    "followers_count": 0,
                    "following_count": 0,
                    **relationship,
                    "posts": [],
                },
                status=status.HTTP_200_OK,
            )

        # 3. Perfil completo
        counters = get_profile_counters(target_user=target, viewer=request.user)
        posts_qs = visible_posts_for(request.user).filter(author=target).order_by("-id")[:20]
        posts_data = PostSerializer(posts_qs, many=True, context={"request": request}).data

        return Response(
            {
                "username": target.username,
                "bio": getattr(profile, "bio", "") if profile else "",
                "avatar": avatar_url,
                "is_private": is_private,
                **counters,
                **relationship,
                "posts": posts_data,
            },
            status=status.HTTP_200_OK,
        )


class CloseFriendsView(APIView):
    """
    POST   /api/social/close-friends/<username>/  → adiciona ao círculo
    DELETE /api/social/close-friends/<username>/  → remove do círculo
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)
        try:
            added = add_to_close_friends(user=request.user, target_user=target)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not added:
            return Response(
                {"detail": "Já está no círculo de amigos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Adicionado ao círculo."}, status=status.HTTP_201_CREATED)

    def delete(self, request, username):
        target = get_object_or_404(User, username=username)
        removed = remove_from_close_friends(user=request.user, target_user=target)
        if not removed:
            return Response(
                {"detail": "Não estava no círculo de amigos."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CloseFriendsListView(APIView):
    """
    GET /api/social/close-friends/  → lista membros do círculo do usuário autenticado
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        follows = (
            Follow.objects.filter(
                follower=request.user,
                is_close_friend=True,
                status=Follow.Status.ACTIVE,
            )
            .select_related("followed", "followed__profile")
            .order_by("followed__username")
        )
        results = [
            {
                "username": f.followed.username,
                "avatar": (
                    f.followed.profile.avatar.url
                    if hasattr(f.followed, "profile") and f.followed.profile.avatar
                    else None
                ),
                "follow_since": f.created_at,
            }
            for f in follows
        ]
        return Response({"results": results})


class MuteView(APIView):
    """
    POST   /api/social/mute/<username>/  → silenciar usuário
    DELETE /api/social/mute/<username>/  → remover silenciamento
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)
        try:
            mute_user(muter=request.user, target_user=target)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Usuário silenciado."}, status=status.HTTP_201_CREATED)

    def delete(self, request, username):
        target = get_object_or_404(User, username=username)
        removed = unmute_user(muter=request.user, target_user=target)
        if not removed:
            return Response(
                {"detail": "Este usuário não estava silenciado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
