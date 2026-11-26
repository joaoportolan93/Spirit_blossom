from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.social import (
    block_user,
    list_blocked_users,
    list_muted_users,
    mute_user,
    unblock_user,
    unmute_user,
)
from core.throttles import BlockRateThrottle
from core.views.social.follows import get_user_by_username_or_404


class BlockView(APIView):
    """
    POST /api/social/block/<username>/   → bloquear usuário (idempotente)
    DELETE /api/social/block/<username>/ → desbloquear (idempotente)
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [BlockRateThrottle]

    def post(self, request, username):
        target = get_user_by_username_or_404(username)
        if target == request.user:
            return Response(
                {"detail": _("Não é possível bloquear a si mesmo.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        block, created = block_user(blocker=request.user, target_user=target)
        msg = _("Usuário bloqueado.") if created else _("Usuário já está bloqueado.")
        return Response(
            {"detail": msg},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, username):
        target = get_user_by_username_or_404(username)
        unblock_user(blocker=request.user, target_user=target)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MuteView(APIView):
    """
    POST   /api/social/mute/<username>/  → silenciar usuário (idempotente)
    DELETE /api/social/mute/<username>/  → remover silenciamento (idempotente)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_user_by_username_or_404(username)
        if target == request.user:
            return Response(
                {"detail": _("Não é possível silenciar a si mesmo.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mute, created = mute_user(muter=request.user, target_user=target)
        msg = _("Usuário silenciado.") if created else _("Usuário já está silenciado.")
        return Response(
            {"detail": msg},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, username):
        target = get_user_by_username_or_404(username)
        unmute_user(muter=request.user, target_user=target)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BlockedUsersListView(APIView):
    """
    GET /api/social/blocked-users/
    Lista contas bloqueadas pelo usuário autenticado (ADR-N24).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = list_blocked_users(user=request.user)
        items = []
        for b in qs:
            target = b.blocked
            avatar_url = None
            if hasattr(target, "profile") and target.profile and target.profile.avatar:
                avatar_url = target.profile.avatar.url
            items.append(
                {
                    "id": str(target.id),
                    "username": target.username,
                    "avatar": avatar_url,
                    "blocked_at": b.created_at.isoformat(),
                }
            )
        return Response({"items": items})


class MutedUsersListView(APIView):
    """
    GET /api/social/muted-users/
    Lista contas silenciadas pelo usuário autenticado (ADR-N24).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = list_muted_users(user=request.user)
        items = []
        for m in qs:
            target = m.muted
            avatar_url = None
            if hasattr(target, "profile") and target.profile and target.profile.avatar:
                avatar_url = target.profile.avatar.url
            items.append(
                {
                    "id": str(target.id),
                    "username": target.username,
                    "avatar": avatar_url,
                    "muted_at": m.created_at.isoformat(),
                }
            )
        return Response({"items": items})
