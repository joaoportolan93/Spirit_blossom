from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from comments.models import Comment
from core.models import ModerationLog, Report
from core.services.moderation import execute_report_action
from core.services.posts import get_posts_map_for_moderation
from core.views.admin.permissions import IsAdminPermission

User = get_user_model()


class AdminReportsView(APIView):
    """GET /api/admin/reports/ — Lista denúncias com filtro por status e tipo."""

    permission_classes = [IsAdminPermission]

    def get(self, request):
        status_filter = request.query_params.get("status", Report.Status.PENDING)
        target_type_filter = request.query_params.get("target_type", "all")

        qs = Report.objects.select_related("reporter", "moderator").order_by("-created_at")
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        if target_type_filter and target_type_filter != "all":
            qs = qs.filter(target_type=target_type_filter)

        reports = list(qs[:100])

        post_ids = [r.target_id for r in reports if r.target_type == Report.TargetType.POST]
        comment_ids = [r.target_id for r in reports if r.target_type == Report.TargetType.COMMENT]
        user_ids = [r.target_id for r in reports if r.target_type == Report.TargetType.USER]

        posts_map = get_posts_map_for_moderation(post_ids)
        comments_map = (
            {
                str(c.id): c
                for c in Comment.objects.filter(id__in=comment_ids).select_related("author")
            }
            if comment_ids
            else {}
        )
        users_map = (
            {str(u.id): u for u in User.objects.filter(id__in=user_ids).select_related("profile")}
            if user_ids
            else {}
        )

        data = []
        for r in reports:
            item = {
                "id": str(r.id),
                "target_type": r.target_type,
                "target_type_display": r.get_target_type_display(),
                "target_id": r.target_id,
                "reason": r.reason,
                "reason_display": r.get_reason_display(),
                "description": r.description,
                "status": r.status,
                "status_display": r.get_status_display(),
                "action_taken": r.action_taken,
                "action_taken_display": (r.get_action_taken_display() if r.action_taken else None),
                "moderator_notes": r.moderator_notes,
                "created_at": r.created_at.isoformat(),
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                "reporter": {
                    "id": str(r.reporter.id),
                    "username": r.reporter.username,
                },
                "moderator": (
                    {"id": str(r.moderator.id), "username": r.moderator.username}
                    if r.moderator
                    else None
                ),
                "content": None,
            }

            if r.target_type == Report.TargetType.POST:
                post = posts_map.get(r.target_id)
                if post:
                    item["content"] = {
                        "type": "post",
                        "id": str(post.id),
                        "content_text": post.content_text,
                        "is_hidden": post.is_hidden,
                        "author": {
                            "id": str(post.author.id),
                            "username": post.author.username,
                            "status": post.author.status,
                        },
                    }
            elif r.target_type == Report.TargetType.COMMENT:
                comment = comments_map.get(r.target_id)
                if comment:
                    item["content"] = {
                        "type": "comment",
                        "id": str(comment.id),
                        "post_id": str(comment.post_id),
                        "content_text": comment.content_text,
                        "is_hidden": comment.is_hidden,
                        "is_deleted": comment.is_deleted,
                        "author": (
                            {
                                "id": str(comment.author.id),
                                "username": comment.author.username,
                                "status": comment.author.status,
                            }
                            if comment.author
                            else None
                        ),
                    }
            elif r.target_type == Report.TargetType.USER:
                target_user = users_map.get(r.target_id)
                if target_user:
                    profile = getattr(target_user, "profile", None)
                    item["content"] = {
                        "type": "user",
                        "id": str(target_user.id),
                        "username": target_user.username,
                        "display_name": getattr(profile, "display_name", "") if profile else "",
                        "bio": getattr(profile, "bio", "") if profile else "",
                        "status": target_user.status,
                    }

            data.append(item)

        return Response(data)


class AdminReportActionView(APIView):
    """POST /api/admin/reports/<uuid:pk>/action/ — Executa ação sobre denúncia."""

    permission_classes = [IsAdminPermission]

    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        action = request.data.get("action")
        reason = request.data.get("reason", "")
        duration_days = request.data.get("duration_days")
        moderator_notes = request.data.get("moderator_notes", "")
        preserve = bool(request.data.get("preserve_for_authorities", False))

        try:
            updated = execute_report_action(
                report=report,
                moderator=request.user,
                action=action,
                reason=reason,
                duration_days=duration_days,
                moderator_notes=moderator_notes,
                preserve_for_authorities=preserve,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "id": str(updated.id),
                "status": updated.status,
                "action_taken": updated.action_taken,
                "detail": _("Ação de moderação aplicada com sucesso."),
            }
        )


class AdminModerationLogsView(APIView):
    """GET /api/admin/moderation-logs/ — Histórico de auditoria de moderação."""

    permission_classes = [IsAdminPermission]

    def get(self, request):
        logs = ModerationLog.objects.select_related("affected_user", "moderator").order_by(
            "-created_at"
        )[:100]
        return Response(
            [
                {
                    "id": str(log.id),
                    "target_type": log.target_type,
                    "target_id": log.target_id,
                    "affected_username": log.affected_user.username if log.affected_user else None,
                    "moderator_username": log.moderator.username if log.moderator else None,
                    "action": log.action,
                    "action_display": log.get_action_display(),
                    "reason": log.reason,
                    "content_snapshot": log.content_snapshot,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ]
        )
