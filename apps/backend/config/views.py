"""
Views utilitárias de infra — não fazem parte do domínio.
"""

import os

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.utils._os import safe_join
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.services.posts import can_view_media_path, guess_media_content_type


def health_check(request):
    """GET /api/health/ — verifica que Django e banco respondem."""
    from django.db import connection

    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    status = 200 if db_ok else 503
    return JsonResponse(
        {
            "status": "ok" if db_ok else "degraded",
            "db": "ok" if db_ok else "error",
        },
        status=status,
    )


class ProtectedMediaView(APIView):
    """
    GET /api/media/<path:file_path> — entrega protegida de mídia (ADR-N5 / ADR-N21).
    Exige autenticação e permissão via can_view_media_path (retorna 404 se negado).
    Em produção, emite header X-Accel-Redirect para Nginx (/protected-media/).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, file_path):
        clean_rel = (file_path or "").replace("\\", "/").lstrip("/")
        try:
            full_path = safe_join(str(settings.MEDIA_ROOT), clean_rel)
        except (SuspiciousFileOperation, ValueError):
            raise Http404()

        if not can_view_media_path(user=request.user, relative_path=clean_rel):
            raise Http404()

        content_type = guess_media_content_type(clean_rel)

        # Em produção atrás de Nginx, delega I/O estático via X-Accel-Redirect (ADR-N5)
        if not settings.DEBUG and not getattr(settings, "TESTING", False):
            response = HttpResponse(status=200, content_type=content_type)
            response["X-Accel-Redirect"] = f"/protected-media/{clean_rel}"
            response["X-Content-Type-Options"] = "nosniff"
            return response

        if not os.path.isfile(full_path):
            raise Http404()

        response = FileResponse(open(full_path, "rb"), content_type=content_type)
        response["X-Content-Type-Options"] = "nosniff"
        return response
