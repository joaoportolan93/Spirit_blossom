"""
View de Feature Flags — Onda 7a.

GET /api/feature-flags/ → retorna dict de flags ativas para o usuário autenticado.
Autenticação opcional: anônimos recebem estado com user=None.
"""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.feature_flags import get_flags_for_user


class FeatureFlagsView(APIView):
    """
    GET /api/feature-flags/ → { "flags": { "push_notifications": true, ... } }
    """

    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        flags = get_flags_for_user(user=user)
        return Response({"flags": flags})
