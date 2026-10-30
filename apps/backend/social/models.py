from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following",
    )
    followed = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_close_friend = models.BooleanField(default=False)

    class Meta:
        db_table = "social_follow"
        verbose_name = _("seguimento")
        verbose_name_plural = _("seguimentos")
        constraints = [
            models.UniqueConstraint(fields=["follower", "followed"], name="unique_follow"),
            models.CheckConstraint(
                check=~Q(follower=models.F("followed")),
                name="no_self_follow",
            ),
        ]

    def __str__(self):
        return f"{self.follower_id} → {self.followed_id}"


class Block(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocking",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_block"
        verbose_name = _("bloqueio")
        verbose_name_plural = _("bloqueios")
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block"),
            models.CheckConstraint(
                check=~Q(blocker=models.F("blocked")),
                name="no_self_block",
            ),
        ]

    def __str__(self):
        return f"{self.blocker_id} ✕ {self.blocked_id}"


class Mute(models.Model):
    muter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="muting",
    )
    muted = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="muted_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_mute"
        verbose_name = _("silenciamento")
        verbose_name_plural = _("silenciamentos")
        constraints = [
            models.UniqueConstraint(fields=["muter", "muted"], name="unique_mute"),
            models.CheckConstraint(
                check=~Q(muter=models.F("muted")),
                name="no_self_mute",
            ),
        ]

    def __str__(self):
        return f"{self.muter_id} 🔇 {self.muted_id}"
