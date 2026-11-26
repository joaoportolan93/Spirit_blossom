from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Block, Follow
from core.services.social import add_to_close_friends, remove_from_close_friends
from core.utils.visibility import is_user_blocked
from core.views.social.follows import get_user_by_username_or_404

User = get_user_model()


class CloseFriendsView(APIView):
    """
    POST   /api/social/close-friends/<username>/  → adiciona ao círculo
    DELETE /api/social/close-friends/<username>/  → remove do círculo
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target = get_user_by_username_or_404(username)
        if is_user_blocked(request.user, target) or not getattr(target, "is_valid_for_auth", True):
            raise Http404()
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
        target = get_user_by_username_or_404(username)
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
                follower__is_active=True,
                follower__status=User.Status.ACTIVE,
                followed__is_active=True,
                followed__status=User.Status.ACTIVE,
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
                follower__is_active=True,
                follower__status=User.Status.ACTIVE,
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
