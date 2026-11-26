import hashlib
import hmac

import uuid6
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError(_("O e-mail é obrigatório."))
        if not username:
            raise ValueError(_("O nome de usuário é obrigatório."))
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Ativo")
        SUSPENDED = "suspended", _("Suspenso")
        DEACTIVATED = "deactivated", _("Desativado")

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    email = models.EmailField(_("endereço de e-mail"), unique=True, max_length=255)
    username = models.CharField(_("nome de usuário"), unique=True, max_length=30, db_index=True)
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # --- Ciclo de vida de banimento / suspensão (Onda 8) ---
    banned_at = models.DateTimeField(null=True, blank=True)
    ban_reason = models.TextField(blank=True, default="")
    banned_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="banned_users",
    )
    appeal_deadline = models.DateTimeField(null=True, blank=True)
    ban_expires_at = models.DateTimeField(null=True, blank=True)
    preserve_for_authorities = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")

    def __str__(self):
        return self.username

    @property
    def is_valid_for_auth(self):
        """Returns True if the account is active and not suspended/deactivated."""
        return self.is_active and self.status == self.Status.ACTIVE

    @property
    def appeal_days_remaining(self):
        """Returns remaining days for appeal when banned, or None."""
        if not self.appeal_deadline:
            return None
        return max(0, (self.appeal_deadline - timezone.now()).days)

    def check_and_expire_ban(self) -> bool:
        """
        If the user has a temporary suspension (`ban_expires_at`) that has expired,
        restores the account to active status and records a moderation log.
        Returns True if an expired suspension was lifted.
        """
        if (
            self.status == self.Status.SUSPENDED
            and self.ban_expires_at is not None
            and self.ban_expires_at <= timezone.now()
        ):
            from core.services.user_lifecycle import unban_user

            unban_user(self, admin_user=None, reason="Temporary suspension expired.")
            return True
        return False


class UserProfile(models.Model):
    class Theme(models.TextChoices):
        LIGHT = "light", _("Branco")
        DARK = "dark", _("Preto")
        OLED = "oled", _("Preto OLED")

    class Language(models.TextChoices):
        PT_BR = "pt-BR", _("Português")
        EN = "en", _("Inglês")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="profile",
    )
    display_name = models.CharField(
        max_length=60,
        blank=True,
        default="",
        help_text=_("Nome completo ou apelido de exibição."),
    )
    bio = models.CharField(max_length=160, blank=True, default="")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    birth_date = models.DateField(
        null=True,
        blank=True,
        help_text=_("Data de nascimento — usada para verificação de idade mínima."),
    )
    is_private = models.BooleanField(
        default=False,
        help_text=_("Indica se a conta é privada."),
    )
    show_likes_tab = models.BooleanField(
        default=True,
        help_text=_("Controla se visitantes podem ver a aba de curtidas no perfil."),
    )
    notify_likes = models.BooleanField(
        default=True,
        help_text=_("Receber notificações de curtidas."),
    )
    notify_comments = models.BooleanField(
        default=True,
        help_text=_("Receber notificações de comentários e respostas."),
    )
    notify_follows = models.BooleanField(
        default=True,
        help_text=_("Receber notificações de novos seguidores."),
    )
    notify_mentions = models.BooleanField(
        default=True,
        help_text=_("Receber notificações de menções."),
    )
    theme = models.CharField(
        max_length=10,
        choices=Theme.choices,
        default=Theme.LIGHT,
        help_text=_("Tema visual da aplicação."),
    )
    language = models.CharField(
        max_length=10,
        choices=Language.choices,
        default=Language.PT_BR,
        help_text=_("Idioma preferencial do usuário."),
    )
    terms_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Momento em que o usuário aceitou os Termos de Uso e Política de Privacidade."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_userprofile"
        verbose_name = _("perfil de usuário")
        verbose_name_plural = _("perfis de usuário")

    def __str__(self):
        return f"Perfil de {self.user.username}"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_resets",
    )
    token_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_password_reset_token"
        verbose_name = _("token de recuperação de senha")
        verbose_name_plural = _("tokens de recuperação de senha")

    def __str__(self):
        return f"ResetToken({self.user_id}, used={self.used_at is not None})"

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class OAuthAccount(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oauth_accounts",
    )
    provider = models.CharField(max_length=30, default="google")
    uid = models.CharField(max_length=255, db_index=True)  # google_sub
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_oauth_account"
        verbose_name = _("conta oauth")
        verbose_name_plural = _("contas oauth")
        unique_together = ("provider", "uid")

    def __str__(self):
        return f"{self.provider}:{self.uid} -> {self.user.username}"


class AccessLog(models.Model):
    """
    Registro de acesso por IP hasheado (HMAC-SHA256).
    Finalidade: cumprimento do Marco Civil da Internet, Art. 13/15.
    VALIDAR COM JURISTA antes de ativar em produção.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_logs",
    )
    ip_hash = models.CharField(max_length=64, db_index=True)  # HMAC-SHA256 hex
    port = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "accounts_accesslog"
        verbose_name = _("registro de acesso")
        verbose_name_plural = _("registros de acesso")

    @classmethod
    def hash_ip(cls, ip: str) -> str:
        """HMAC-SHA256 do IP usando ACCESS_LOG_HMAC_KEY como chave. Não é reversível."""
        from django.conf import settings as django_settings
        from django.core.exceptions import ImproperlyConfigured

        key_str = getattr(django_settings, "ACCESS_LOG_HMAC_KEY", "")
        if not key_str:
            raise ImproperlyConfigured(
                "ACCESS_LOG_HMAC_KEY ausente ou vazia. "
                "Defina uma chave de no mínimo 32 bytes no settings."
            )
        return hmac.new(key_str.encode(), ip.encode(), hashlib.sha256).hexdigest()
