from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("notification_type", "recipient", "sender", "read", "created_at")
    list_filter = ("notification_type", "read")
    raw_id_fields = ("recipient", "sender")
    readonly_fields = ("created_at",)
