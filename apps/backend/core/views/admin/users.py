from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Follow, ModerationLog, Report
from core.services.posts import count_posts_for_author
from core.services.user_lifecycle import ban_user, permanently_delete_user, unban_user
from core.views.admin.permissions import IsAdminPermission

User = get_user_model()


def _serialize_admin_user(u, now=None) -> dict:
    if now is None:
        now = timezone.now()
    profile = getattr(u, "profile", None)
    days_remaining = max(0, (u.appeal_deadline - now).days) if u.appeal_deadline else None
    return {
        "id": str(u.id),
        "username": u.username,
        "email": u.email,
        "display_name": getattr(profile, "display_name", "") if profile else "",
        "avatar": profile.avatar.url if profile and profile.avatar else None,
        "status": u.status,
        "status_display": u.get_status_display(),
        "is_active": u.is_active,
        "is_staff": u.is_staff,
        "is_superuser": u.is_superuser,
        "date_joined": u.date_joined.isoformat(),
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "banned_at": u.banned_at.isoformat() if u.banned_at else None,
        "ban_reason": u.ban_reason,
        "banned_by": u.banned_by.username if u.banned_by else None,
        "appeal_deadline": u.appeal_deadline.isoformat() if u.appeal_deadline else None,
        "ban_expires_at": u.ban_expires_at.isoformat() if u.ban_expires_at else None,
        "appeal_days_remaining": days_remaining,
        "preserve_for_authorities": u.preserve_for_authorities,
    }


class AdminUsersView(APIView):
    """GET /api/admin/users/ — Listagem, busca e filtro por status."""

    permission_classes = [IsAdminPermission]

    def get(self, request):
        search = request.query_params.get("search", "").strip()
        status_filter = request.query_params.get("status", "").strip()
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        page_size = 50

        qs = User.objects.select_related("profile", "banned_by").all()

        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(profile__display_name__icontains=search)
            )

        if status_filter in {
            User.Status.ACTIVE,
            User.Status.SUSPENDED,
            User.Status.DEACTIVATED,
        }:
            qs = qs.filter(status=status_filter)

        total = qs.count()
        offset = (page - 1) * page_size
        users = list(qs.order_by("-date_joined")[offset : offset + page_size])
        now = timezone.now()

        return Response(
            {
                "results": [_serialize_admin_user(u, now=now) for u in users],
                "count": total,
                "page": page,
                "has_next": offset + len(users) < total,
            }
        )


class AdminUserDetailView(APIView):
    """GET / PATCH / DELETE /api/admin/users/<uuid:pk>/ — Inspeção, ban, desban e exclusão."""

    permission_classes = [IsAdminPermission]

    def get(self, request, pk):
        user = get_object_or_404(User.objects.select_related("profile", "banned_by"), pk=pk)
        data = _serialize_admin_user(user)
        profile = getattr(user, "profile", None)
        data.update(
            {
                "bio": getattr(profile, "bio", "") if profile else "",
                "is_private": getattr(profile, "is_private", False) if profile else False,
                "posts_count": count_posts_for_author(user),
                "followers_count": Follow.objects.filter(
                    followed=user, status=Follow.Status.ACTIVE
                ).count(),
                "following_count": Follow.objects.filter(
                    follower=user, status=Follow.Status.ACTIVE
                ).count(),
                "reports_received": Report.objects.filter(
                    target_type=Report.TargetType.USER, target_id=str(user.id)
                ).count(),
                "moderation_logs": [
                    {
                        "id": str(log.id),
                        "action": log.action,
                        "action_display": log.get_action_display(),
                        "reason": log.reason,
                        "moderator": log.moderator.username if log.moderator else None,
                        "created_at": log.created_at.isoformat(),
                    }
                    for log in ModerationLog.objects.filter(affected_user=user)
                    .select_related("moderator")
                    .order_by("-created_at")[:10]
                ],
            }
        )
        return Response(data)

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        new_status = request.data.get("status")

        if user.id == request.user.id and new_status in (
            User.Status.SUSPENDED,
            User.Status.DEACTIVATED,
        ):
            return Response(
                {"detail": _("Você não pode suspender ou desativar a sua própria conta.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == User.Status.SUSPENDED:
            reason = request.data.get("reason") or request.data.get("ban_reason") or ""
            duration_days = request.data.get("duration_days")
            preserve = bool(request.data.get("preserve_for_authorities", False))
            try:
                ban_user(
                    user,
                    reason=reason,
                    admin_user=request.user,
                    duration_days=duration_days,
                    preserve_for_authorities=preserve,
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(
                {
                    "detail": _("Usuário suspenso/banido com sucesso."),
                    "user": _serialize_admin_user(user),
                }
            )

        if new_status == User.Status.ACTIVE:
            reason = request.data.get("reason", "Desbanido pelo administrador")
            unban_user(user, admin_user=request.user, reason=reason)
            return Response(
                {
                    "detail": _("Usuário reativado com sucesso."),
                    "user": _serialize_admin_user(user),
                }
            )

        if new_status == User.Status.DEACTIVATED:
            user.status = User.Status.DEACTIVATED
            user.is_active = False
            user.save(update_fields=["status", "is_active"])
            return Response(
                {
                    "detail": _("Conta desativada."),
                    "user": _serialize_admin_user(user),
                }
            )

        return Response({"detail": _("Status inválido.")}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.id == request.user.id:
            return Response(
                {
                    "detail": _(
                        "Você não pode excluir sua própria conta pelo painel administrativo."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        confirm_username = (request.data.get("confirm_username") or "").strip().lstrip("@")
        if confirm_username.lower() != user.username.lower():
            return Response(
                {
                    "detail": _(
                        "O nome de usuário digitado não coincide com a conta a ser excluída."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permanently_delete_user(
            user=user,
            reason=user.ban_reason or "Exclusão definitiva manual pelo administrador",
            admin_user=request.user,
            is_ban=True,
        )
        return Response(
            {"detail": _("Usuário e seus dados foram excluídos definitivamente.")},
            status=status.HTTP_200_OK,
        )
