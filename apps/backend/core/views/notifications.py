"""
Views de notificações (ADR-N2: finas, delegando para services e selectors) — Onda 7a.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers.notifications import NotificationSerializer
from core.services.notifications import (
    get_unread_notifications_count,
    get_user_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)
from core.services.push import deactivate_user_devices, register_device, remove_device
from core.throttles import DeviceRegistrationRateThrottle


class NotificationListView(APIView):
    """
    GET   /api/notifications/               → lista notificações com filtros
    POST  /api/notifications/mark-all-read/ → marca todas como lidas
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        category = request.query_params.get("category", "all")
        unread_only = request.query_params.get("unread_only", "").lower() == "true"
        qs = get_user_notifications(
            user=request.user,
            limit=50,
            category=category,
            unread_only=unread_only,
        )
        notifs = list(qs)
        ref_ids = [n.ref_id for n in notifs if n.ref_id]
        comment_post_map = {}
        if ref_ids:
            from comments.models import Comment

            comment_post_map = {
                str(cid): str(pid)
                for cid, pid in Comment.objects.filter(pk__in=ref_ids).values_list("id", "post_id")
            }
        serializer = NotificationSerializer(
            notifs, many=True, context={"comment_post_map": comment_post_map}
        )
        return Response(serializer.data)

    def post(self, request):
        count = mark_all_notifications_as_read(user=request.user)
        return Response({"detail": f"{count} notificações marcadas como lidas."})


class NotificationUnreadCountView(APIView):
    """
    GET /api/notifications/unread-count/ → polling leve para badge.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = get_unread_notifications_count(user=request.user)
        return Response({"unread_count": count})


class NotificationMarkReadView(APIView):
    """
    POST /api/notifications/<id>/read/ → marca uma notificação como lida
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        updated = mark_notification_as_read(notification_id=pk, user=request.user)
        if not updated:
            return Response(
                {"detail": "Notificação não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"detail": "Notificação marcada como lida."})

    # Mantém retrocompatibilidade com PATCH existente
    def patch(self, request, pk):
        return self.post(request, pk)


class PushDeviceView(APIView):
    """
    POST   /api/notifications/devices/ → registra ou reatribui token FCM
    DELETE /api/notifications/devices/ → remove token FCM (logout)
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [DeviceRegistrationRateThrottle]

    def post(self, request):
        token = (request.data.get("token") or "").strip()
        platform = request.data.get("platform", "web")
        device_name = (request.data.get("device_name") or "")[:200]

        if not token:
            return Response(
                {"detail": "token é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if platform not in ("web", "android", "ios"):
            platform = "web"

        device = register_device(
            user=request.user,
            token=token,
            platform=platform,
            device_name=device_name,
        )
        return Response(
            {"id": str(device.id), "platform": device.platform},
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        token = (request.data.get("token") or "").strip()
        if token:
            remove_device(user=request.user, token=token)
        else:
            # Logout: desativa todos
            deactivate_user_devices(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
