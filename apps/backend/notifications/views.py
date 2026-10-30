"""
View de notificações (polling 30s — VAPID push em M2+).
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    """
    GET   /api/notifications/         → lista notificações não lidas do usuário
    PATCH /api/notifications/<id>/read/ → marca como lida
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(
            recipient=request.user,
        ).select_related("sender").order_by("-created_at")[:50]
        serializer = NotificationSerializer(qs, many=True)
        return Response(serializer.data)


class NotificationMarkReadView(APIView):
    """PATCH /api/notifications/<id>/read/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        from django.shortcuts import get_object_or_404
        notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notif.read = True
        notif.save(update_fields=["read"])
        return Response({"detail": "Notificação marcada como lida."})
