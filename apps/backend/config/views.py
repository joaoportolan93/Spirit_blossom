"""
Views utilitárias de infra — não fazem parte do domínio.
"""

from django.http import JsonResponse


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

