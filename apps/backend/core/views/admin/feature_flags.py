from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import FeatureFlag
from core.views.admin.permissions import IsAdminPermission


def _flag_to_dict(flag: FeatureFlag) -> dict:
    return {
        "key": flag.key,
        "description": flag.description,
        "is_enabled": flag.is_enabled,
        "admin_only": flag.admin_only,
        "rollout_percentage": flag.rollout_percentage,
        "created_at": flag.created_at.isoformat(),
        "updated_at": flag.updated_at.isoformat(),
    }


class AdminFeatureFlagListView(APIView):
    """GET / POST /api/admin/feature-flags/"""

    permission_classes = [IsAdminPermission]

    def get(self, request):
        flags = FeatureFlag.objects.all().order_by("key")
        return Response([_flag_to_dict(f) for f in flags])

    def post(self, request):
        key = (request.data.get("key") or "").strip()
        if not key:
            return Response(
                {"detail": _("O campo key é obrigatório.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if FeatureFlag.objects.filter(key=key).exists():
            return Response(
                {"detail": _("Já existe uma flag com essa chave.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rollout = int(request.data.get("rollout_percentage", 100))
        except (ValueError, TypeError):
            return Response(
                {"detail": _("rollout_percentage inválido.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (0 <= rollout <= 100):
            return Response(
                {"detail": _("rollout_percentage deve estar entre 0 e 100.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        flag = FeatureFlag.objects.create(
            key=key,
            description=request.data.get("description", ""),
            is_enabled=bool(request.data.get("is_enabled", False)),
            admin_only=bool(request.data.get("admin_only", False)),
            rollout_percentage=rollout,
        )
        return Response(_flag_to_dict(flag), status=status.HTTP_201_CREATED)


class AdminFeatureFlagDetailView(APIView):
    """GET / PATCH / DELETE /api/admin/feature-flags/<str:key>/"""

    permission_classes = [IsAdminPermission]

    def get(self, request, key):
        flag = get_object_or_404(FeatureFlag, key=key)
        return Response(_flag_to_dict(flag))

    def patch(self, request, key):
        flag = get_object_or_404(FeatureFlag, key=key)

        if "is_enabled" in request.data:
            flag.is_enabled = bool(request.data["is_enabled"])
        if "admin_only" in request.data:
            flag.admin_only = bool(request.data["admin_only"])
        if "rollout_percentage" in request.data:
            try:
                pct = int(request.data["rollout_percentage"])
            except (ValueError, TypeError):
                return Response(
                    {"detail": _("rollout_percentage inválido.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not (0 <= pct <= 100):
                return Response(
                    {"detail": _("rollout_percentage deve estar entre 0 e 100.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            flag.rollout_percentage = pct
        if "description" in request.data:
            flag.description = request.data["description"]

        flag.save()
        return Response(_flag_to_dict(flag))

    def delete(self, request, key):
        flag = get_object_or_404(FeatureFlag, key=key)
        flag.delete()
        return Response({"detail": _("Flag removida.")}, status=status.HTTP_200_OK)
