"""
Views sociais (ADR-N2: finas, delegando para services e selectors).
"""

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from core.models import Block, Follow, Mute
from core.serializers.posts import PostSerializer
from core.serializers.social import FollowRequestSerializer
from core.services.social import (
    accept_follow_request,
    add_to_close_friends,
    block_user,
    follow_user,
    list_blocked_users,
    list_follow_requests,
    list_muted_users,
    mute_user,
    reject_follow_request,
    remove_from_close_friends,
    unblock_user,
    unfollow_user,
    unmute_user,
)
from core.throttles import BlockRateThrottle
from core.utils.visibility import (
    can_view_profile,
    get_profile_counters,
    get_relationship_status,
    is_user_blocked,
    visible_posts_for,
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
        if is_user_blocked(request.user, target):
            raise Http404()
        try:
            follow, created = follow_user(follower=request.user, target_user=target)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        msg = "Pedido de seguir enviado." if follow.status == Follow.Status.PENDING else "Seguindo."
        return Response({"detail": msg, "status": follow.status}, status=status.HTTP_201_CREATED)

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
    POST /api/social/block/<username>/   → bloquear usuário (idempotente)
    DELETE /api/social/block/<username>/ → desbloquear (idempotente)
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [BlockRateThrottle]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)
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
        target = get_object_or_404(User, username=username)
        unblock_user(blocker=request.user, target_user=target)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        target = User.objects.filter(username=username).select_related("profile").first()
        if not target or is_user_blocked(request.user, target) or not getattr(target, "is_valid_for_auth", True):
            raise Http404()

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
        if is_user_blocked(request.user, target):
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        try:
            added = add_to_close_friends(user=request.user, target_user=target)
        except Http404:
            return Response(
                {"detail": "Apenas seguidores ativos podem ser adicionados ao círculo."},
                status=status.HTTP_404_NOT_FOUND,
            )
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
                (Q(follower=request.user) | Q(followed=request.user)),
                is_close_friend=True,
                status=Follow.Status.ACTIVE,
            )
            .select_related("follower", "followed", "follower__profile", "followed__profile")
            .order_by("-id")
        )
        results = []
        for f in follows:
            member = f.follower if f.followed_id == request.user.id else f.followed
            avatar = (
                member.profile.avatar.url
                if hasattr(member, "profile") and member.profile.avatar
                else None
            )
            results.append(
                {
                    "username": member.username,
                    "avatar": avatar,
                    "follow_since": f.created_at,
                }
            )
        return Response({"results": results})


class CloseFriendsCandidatesView(APIView):
    """
    GET /api/social/close-friends/candidates/?q=&cursor=&limit=
    Retorna apenas seguidores ativos do usuário autenticado (Lumem),
    com filtro de busca opcional por q, excluindo usuários bloqueados.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        cursor = request.query_params.get("cursor", None)
        try:
            limit = min(int(request.query_params.get("limit", 20)), 50)
        except ValueError:
            limit = 20

        blocked_subquery_1 = Block.objects.filter(
            blocker=request.user, blocked=OuterRef("follower")
        )
        blocked_subquery_2 = Block.objects.filter(
            blocker=OuterRef("follower"), blocked=request.user
        )

        qs = (
            Follow.objects.filter(
                followed=request.user,
                status=Follow.Status.ACTIVE,
            )
            .exclude(Exists(blocked_subquery_1))
            .exclude(Exists(blocked_subquery_2))
            .select_related("follower", "follower__profile")
            .order_by("-id")
        )

        if q:
            qs = qs.filter(follower__username__icontains=q)

        if cursor:
            try:
                cursor_id = int(cursor)
                qs = qs.filter(id__lt=cursor_id)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "Cursor inválido. Deve ser um ID inteiro."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        items = list(qs[: limit + 1])
        has_next = len(items) > limit
        if has_next:
            items = items[:limit]

        next_cursor = str(items[-1].id) if (has_next and items) else None

        results = [
            {
                "username": f.follower.username,
                "avatar": (
                    f.follower.profile.avatar.url
                    if hasattr(f.follower, "profile") and f.follower.profile.avatar
                    else None
                ),
                "is_close_friend": bool(f.is_close_friend),
            }
            for f in items
        ]

        return Response({"results": results, "next_cursor": next_cursor})


class MuteView(APIView):
    """
    POST   /api/social/mute/<username>/  → silenciar usuário (idempotente)
    DELETE /api/social/mute/<username>/  → remover silenciamento (idempotente)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_object_or_404(User, username=username)
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
        target = get_object_or_404(User, username=username)
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
