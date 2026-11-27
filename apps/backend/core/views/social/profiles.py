from django.contrib.auth import get_user_model
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import PostLike
from core.serializers.posts import PostSerializer
from core.utils.visibility import (
    can_view_likes_tab,
    can_view_profile,
    get_profile_counters,
    get_relationship_status,
    is_user_blocked,
    visible_posts_for,
)

User = get_user_model()


class ProfileDetailView(APIView):
    """
    GET /api/social/profile/<username>/
    Retorna perfil, contadores públicos, status de relacionamento e posts visíveis.
    Bloqueio bilateral retorna 404 indistinguível (ADR-N21 / ADR-N24).
    Conta privada sem seguimento ativo retorna perfil mínimo (200 OK)
    para permitir solicitação de follow.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        target = User.objects.filter(username__iexact=username).select_related("profile").first()
        if (
            not target
            or is_user_blocked(request.user, target)
            or not getattr(target, "is_valid_for_auth", True)
        ):
            raise Http404()

        profile = getattr(target, "profile", None)
        is_private = getattr(profile, "is_private", False)
        relationship = get_relationship_status(source_user=request.user, target_user=target)

        avatar_url = profile.avatar.url if profile and profile.avatar else None
        show_likes_tab = getattr(profile, "show_likes_tab", True) if profile else True
        display_name = getattr(profile, "display_name", "") if profile else ""

        if not can_view_profile(request.user, target):
            return Response(
                {
                    "id": str(target.id),
                    "username": target.username,
                    "display_name": display_name,
                    "bio": "",
                    "avatar": avatar_url,
                    "is_private": True,
                    "show_likes_tab": show_likes_tab,
                    "posts_count": 0,
                    "followers_count": 0,
                    "following_count": 0,
                    **relationship,
                    "posts": [],
                },
                status=status.HTTP_200_OK,
            )

        counters = get_profile_counters(target_user=target, viewer=request.user)
        posts_qs = (
            visible_posts_for(request.user)
            .filter(author=target)
            .prefetch_related("media")
            .order_by("-id")[:20]
        )
        posts_data = PostSerializer(posts_qs, many=True, context={"request": request}).data

        return Response(
            {
                "id": str(target.id),
                "username": target.username,
                "display_name": display_name,
                "bio": getattr(profile, "bio", "") if profile else "",
                "avatar": avatar_url,
                "is_private": is_private,
                "show_likes_tab": show_likes_tab,
                **counters,
                **relationship,
                "posts": posts_data,
            },
            status=status.HTTP_200_OK,
        )


class ProfileLikesView(APIView):
    """
    GET /api/social/profile/<username>/likes/
    Retorna publicações curtidas pelo usuário (respeitando show_likes_tab e visibilidade).
    Dono da conta vê sempre. Visitante é bloqueado (403) se show_likes_tab=False (Onda 5).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        target = User.objects.filter(username__iexact=username).select_related("profile").first()
        if (
            not target
            or is_user_blocked(request.user, target)
            or not getattr(target, "is_valid_for_auth", True)
        ):
            raise Http404()

        if not can_view_likes_tab(request.user, target):
            return Response(
                {"detail": "Aba de curtidas indisponível."},
                status=status.HTTP_403_FORBIDDEN,
            )

        liked_post_ids = PostLike.objects.filter(user=target).values_list("post_id", flat=True)
        posts_qs = (
            visible_posts_for(request.user)
            .filter(id__in=liked_post_ids)
            .prefetch_related("media")
            .order_by("-id")[:20]
        )
        posts_data = PostSerializer(posts_qs, many=True, context={"request": request}).data
        return Response(posts_data, status=status.HTTP_200_OK)
