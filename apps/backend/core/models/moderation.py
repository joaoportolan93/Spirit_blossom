import uuid6
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PermanentBanRecord(models.Model):
    """
    Registro mínimo retido após a exclusão definitiva de uma conta banida.
    Garante o bloqueio perpétuo de recadastro com o mesmo @username ou e-mail,
    sem reter dados pessoais desnecessários (LGPD / Princípio da Minimização).
    """

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    username = models.CharField(max_length=50, unique=True, db_index=True)
    email_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text=_("HMAC-SHA256 do e-mail normalizado (minúsculas, sem +tags)."),
    )
    ban_reason = models.TextField(blank=True, default="")
    banned_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(default=timezone.now)
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="permanent_bans_executed",
    )
    preserve_for_authorities = models.BooleanField(
        default=False,
        help_text=_("Indica preservação probatória (CSAM ou ordem judicial)."),
    )

    class Meta:
        db_table = "moderation_permanent_ban_record"
        verbose_name = _("registro de banimento definitivo")
        verbose_name_plural = _("registros de banimento definitivo")
        ordering = ["-deleted_at"]

    def __str__(self):
        return f"PermanentBan @{self.username} ({self.deleted_at:%Y-%m-%d})"


class Report(models.Model):
    """Denúncia de usuário contra publicação, comentário ou perfil."""

    class TargetType(models.TextChoices):
        POST = "post", _("Publicação")
        COMMENT = "comment", _("Comentário")
        USER = "user", _("Usuário")

    class Reason(models.TextChoices):
        INAPPROPRIATE = "inappropriate", _("Conteúdo inadequado")
        HARASSMENT = "harassment", _("Assédio")
        SPAM = "spam", _("Spam")
        HATE_SPEECH = "hate_speech", _("Discurso de ódio")
        ILLEGAL = "illegal", _("Conteúdo ilegal")
        OTHER = "other", _("Outro")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pendente")
        REVIEWED = "reviewed", _("Em análise")
        RESOLVED = "resolved", _("Resolvida")
        DISMISSED = "dismissed", _("Descartada")

    class ActionTaken(models.TextChoices):
        NONE = "none", _("Nenhuma")
        CONTENT_HIDDEN = "content_hidden", _("Conteúdo ocultado")
        CONTENT_REMOVED = "content_removed", _("Conteúdo removido")
        USER_SUSPENDED = "user_suspended", _("Usuário suspenso")
        USER_BANNED = "user_banned", _("Usuário banido")

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_filed",
    )
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.CharField(max_length=36, db_index=True)
    reason = models.CharField(max_length=30, choices=Reason.choices)
    description = models.TextField(max_length=1000, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    action_taken = models.CharField(
        max_length=30,
        choices=ActionTaken.choices,
        null=True,
        blank=True,
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_moderated",
    )
    moderator_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "moderation_report"
        verbose_name = _("denúncia")
        verbose_name_plural = _("denúncias")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="mod_report_status_created_idx"),
            models.Index(fields=["target_type", "target_id"], name="mod_report_target_idx"),
        ]

    def __str__(self):
        return f"Report({self.target_type}:{self.target_id}, {self.status})"


class ModerationLog(models.Model):
    """
    Histórico imutável de decisões de moderação sobre conteúdos e usuários.
    """

    class Action(models.TextChoices):
        HIDE_CONTENT = "hide_content", _("Conteúdo ocultado")
        REMOVE_CONTENT = "remove_content", _("Conteúdo removido")
        RESTORE_CONTENT = "restore_content", _("Conteúdo restaurado")
        SUSPEND = "suspend", _("Usuário suspenso")
        BAN = "ban", _("Usuário banido")
        UNBAN = "unban", _("Usuário desbanido")
        PERMANENT_DELETE = "permanent_delete", _("Exclusão definitiva")
        DISMISS_REPORT = "dismiss_report", _("Denúncia descartada")

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    target_type = models.CharField(max_length=20)
    target_id = models.CharField(max_length=36, db_index=True)
    affected_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_logs_received",
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_logs_performed",
    )
    report = models.ForeignKey(
        Report,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    reason = models.TextField(blank=True, default="")
    content_snapshot = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "moderation_log"
        verbose_name = _("registro de moderação")
        verbose_name_plural = _("registros de moderação")
        ordering = ["-created_at"]

    def __str__(self):
        return f"ModLog({self.action}, {self.target_type}:{self.target_id})"
