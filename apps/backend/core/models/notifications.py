import uuid6
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class PushDevice(models.Model):
    """
    Dispositivo registrado para receber notificações push via FCM.
    Token é único globalmente — ao fazer login em dispositivo de outra conta,
    o token é reatribuído ao usuário corrente (ADR-N21/N24 — zero vazamento).
    """

    class Platform(models.TextChoices):
        WEB = "web", _("Web")
        ANDROID = "android", _("Android")
        IOS = "ios", _("iOS")

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_devices",
    )
    token = models.TextField(
        unique=True,
        db_index=True,
        help_text=_("FCM registration token — único globalmente."),
    )
    platform = models.CharField(
        max_length=10,
        choices=Platform.choices,
        default=Platform.WEB,
    )
    device_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text=_("User-agent ou nome amigável do dispositivo."),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "push_device"
        verbose_name = _("dispositivo push")
        verbose_name_plural = _("dispositivos push")
        indexes = [
            models.Index(fields=["user", "is_active"], name="push_device_user_active_idx"),
        ]

    def __str__(self) -> str:
        return f"PushDevice({self.user_id}, {self.platform}, active={self.is_active})"


class Notification(models.Model):
    class Type(models.TextChoices):
        FOLLOW = "follow", _("Novo seguidor")
        LIKE = "like", _("Curtida")
        MENTION = "mention", _("Menção")
        REPLY = "reply", _("Resposta")
        REPOST = "repost", _("Repost")
        SYSTEM = "system", _("Sistema")

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    notification_type = models.CharField(
        max_length=20,
        choices=Type.choices,
    )
    ref_id = models.UUIDField(null=True, blank=True)
    read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_notification"
        verbose_name = _("notificação")
        verbose_name_plural = _("notificações")
        indexes = [
            models.Index(
                fields=["recipient", "-created_at"],
                name="notif_recipient_created_idx",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} → {self.recipient_id}"
