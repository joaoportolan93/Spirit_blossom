from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class FeatureFlag(models.Model):
    """
    Feature flag gerenciável via admin — rollout gradual e listas de usuários
    permitidos. Avaliação determinística por SHA-256 do user_id.
    """

    key = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_("Identificador único da flag, ex: push_notifications"),
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text=_("Descrição interna da funcionalidade controlada."),
    )
    is_enabled = models.BooleanField(
        default=False,
        help_text=_("Liga/desliga globalmente."),
    )
    admin_only = models.BooleanField(
        default=False,
        help_text=_("Se True, apenas administradores têm acesso quando ativa."),
    )
    rollout_percentage = models.PositiveSmallIntegerField(
        default=0,
        help_text=_("Porcentagem 0-100 de usuários que recebem a flag (rollout gradual)."),
    )
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="allowed_feature_flags",
        help_text=_("Usuários sempre habilitados, independente do rollout_percentage."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "feature_flags_featureflag"
        verbose_name = _("feature flag")
        verbose_name_plural = _("feature flags")
        ordering = ["key"]

    def __str__(self) -> str:
        status = "ON" if self.is_enabled else "OFF"
        scope = " [admin only]" if self.admin_only else f" {self.rollout_percentage}%"
        return f"{self.key} [{status}{scope}]"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            from core.services.feature_flags import invalidate_flag_cache

            invalidate_flag_cache(self.key)
        except Exception:
            pass

    def delete(self, *args, **kwargs):
        flag_key = self.key
        result = super().delete(*args, **kwargs)
        try:
            from core.services.feature_flags import invalidate_flag_cache

            invalidate_flag_cache(flag_key)
        except Exception:
            pass
        return result
