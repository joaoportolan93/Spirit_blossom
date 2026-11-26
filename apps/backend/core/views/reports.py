"""
Views de denúncias para usuários comuns (Onda 8).
"""

from django.utils.translation import gettext as _
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.moderation import create_report


class CreateReportView(APIView):
    """POST /api/reports/ — Cria uma denúncia contra post, comentário ou usuário."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        target_type = request.data.get("target_type")
        target_id = request.data.get("target_id")
        reason = request.data.get("reason")
        description = request.data.get("description", "")

        if not all([target_type, target_id, reason]):
            return Response(
                {"detail": _("Campos obrigatórios: target_type, target_id, reason.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            report = create_report(
                reporter=request.user,
                target_type=target_type,
                target_id=str(target_id),
                reason=reason,
                description=description,
            )
        except LookupError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "id": str(report.id),
                "target_type": report.target_type,
                "target_id": report.target_id,
                "status": report.status,
                "detail": _("Denúncia enviada com sucesso."),
            },
            status=status.HTTP_201_CREATED,
        )
