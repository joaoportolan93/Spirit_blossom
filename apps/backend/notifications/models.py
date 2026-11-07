from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    class Type(models.TextChoices):
        FOLLOW = "follow", _("Novo seguidor")
        LIKE = "like", _("Curtida")
        MENTION = "mention", _("Menção")
        REPLY = "reply", _("Resposta")
        REPOST = "repost", _("Repost")
        SYSTEM = "system", _("Sistema")

    # BigAutoField herdado de DEFAULT_AUTO_FIELD
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
    ref_id = models.UUIDField(null=True, blank=True)  # ID do Post, Follow, etc.
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
