from django.contrib.auth import get_user_model
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from core.models import FeatureFlag, Follow
from core.serializers.social import FollowRequestSerializer
from core.services.feature_flags import is_feature_enabled
from core.services.social import (
    accept_follow_request,
    follow_user,
    list_follow_requests,
    reject_follow_request,
    suggest_users_to_follow,
    unfollow_user,
)
from core.utils.visibility import is_user_blocked

User = get_user_model()


def get_user_by_username_or_404(username: str) -> User:
    target = User.objects.filter(username__iexact=username).select_related("profile").first()
    if not target:
        raise Http404()
    return target


class FollowView(APIView):
    """
    POST /api/social/follow/<username>/   → seguir usuário
    DELETE /api/social/follow/<username>/ → deixar de seguir
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_user_by_username_or_404(username)
        if is_user_blocked(request.user, target) or not getattr(target, "is_valid_for_auth", True):
            raise Http404()
        try:
            follow, created = follow_user(follower=request.user, target_user=target)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        msg = "Pedido de seguir enviado." if follow.status == Follow.Status.PENDING else "Seguindo."
        return Response({"detail": msg, "status": follow.status}, status=status.HTTP_201_CREATED)

    def delete(self, request, username):
        target = get_user_by_username_or_404(username)
        if is_user_blocked(request.user, target):
            raise Http404()
        deleted = unfollow_user(follower=request.user, target_user=target)
        if not deleted:
            return Response(
                {"detail": "Não estava seguindo este usuário."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowRequestListView(APIView):
    """
    GET /api/social/follow-requests/
    Lista pedidos de seguir pendentes direcionados ao usuário autenticado.
    Suporta keyset pagination via ?cursor=<id>&limit=<int>.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        cursor = request.query_params.get("cursor")
        try:
            limit = min(int(request.query_params.get("limit", 20)), 50)
        except (ValueError, TypeError):
            limit = 20

        try:
            qs = list_follow_requests(user=request.user, cursor=cursor, limit=limit)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        items = FollowRequestSerializer(qs, many=True).data
        next_cursor = str(items[-1]["id"]) if len(items) == limit else None
        return Response({"results": items, "next_cursor": next_cursor}, status=status.HTTP_200_OK)


class FollowRequestAcceptView(APIView):
    """
    POST /api/social/follow-requests/<username>/accept/
    Aceita pedido de seguir pendente. 404 se não houver pedido pendente ou bloqueado.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request, username):
        try:
            accept_follow_request(user=request.user, follower_username=username)
        except Http404:
            return Response(
                {"detail": "Solicitação de seguir pendente não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"detail": "Solicitação de seguir aceita.", "status": "active"},
            status=status.HTTP_200_OK,
        )


class FollowRequestRejectView(APIView):
    """
    POST /api/social/follow-requests/<username>/reject/
    Recusa pedido de seguir pendente em silêncio. 404 se não houver pedido pendente.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request, username):
        try:
            reject_follow_request(user=request.user, follower_username=username)
        except Http404:
            return Response(
                {"detail": "Solicitação de seguir pendente não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"detail": "Solicitação de seguir recusada."},
            status=status.HTTP_200_OK,
        )


class FollowSuggestionsView(APIView):
    """
    GET /api/social/suggestions/?limit=5
    Retorna sugestões transparentes para seguir (Onda 7b / ADR-N24).
    Integrado com FeatureFlag `follow_suggestions` (se cadastrada).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        if FeatureFlag.objects.filter(key="follow_suggestions").exists() and not is_feature_enabled(
            "follow_suggestions", request.user
        ):
            return Response({"results": []}, status=status.HTTP_200_OK)

        try:
            limit = max(1, min(int(request.query_params.get("limit", 5)), 20))
        except (ValueError, TypeError):
            limit = 5

        results = suggest_users_to_follow(request.user, limit=limit)
        return Response({"results": results}, status=status.HTTP_200_OK)
