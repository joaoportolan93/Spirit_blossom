"""
Views de notificações (ADR-N2: finas, delegando para services e selectors).
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers.notifications import NotificationSerializer
from core.services.notifications import (
    get_user_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)


class NotificationListView(APIView):
    """
    GET   /api/notifications/               → lista notificações do usuário via selector
    POST  /api/notifications/mark-all-read/ → marca todas como lidas via service
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = get_user_notifications(user=request.user, limit=50)
        serializer = NotificationSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        count = mark_all_notifications_as_read(user=request.user)
        return Response({"detail": f"{count} notificações marcadas como lidas."})


class NotificationMarkReadView(APIView):
    """
    PATCH /api/notifications/<id>/read/ → marca uma notificação como lida via service
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        updated = mark_notification_as_read(notification_id=pk, user=request.user)
        if not updated:
            return Response(
                {"detail": "Notificação não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"detail": "Notificação marcada como lida."})
