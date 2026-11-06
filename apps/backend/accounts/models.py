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


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="profile",
    )
    bio = models.CharField(max_length=160, blank=True, default="")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    birth_date = models.DateField(
        null=True,
        blank=True,
        help_text=_("Data de nascimento — usada para verificação de idade mínima."),
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
        from django.utils import timezone

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

    # BigAutoField herdado de DEFAULT_AUTO_FIELD
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_logs",
    )
    ip_hash = models.CharField(max_length=64, db_index=True)  # HMAC-SHA256 hex
    port = models.PositiveIntegerField()  # Portas efêmeras chegam a 65535
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "accounts_accesslog"
        verbose_name = _("registro de acesso")
        verbose_name_plural = _("registros de acesso")
        # Marco Civil exige retenção de 1 ano — retenção via Celery ou particionamento futuro.

    @classmethod
    def hash_ip(cls, ip: str) -> str:
        """HMAC-SHA256 do IP usando ACCESS_LOG_HMAC_KEY como chave. Não é reversível.

        Usa chave separada da SECRET_KEY para que a rotação da SECRET_KEY
        não quebre o histórico de hashes (Marco Civil exige retenção por 1 ano).
        """
        from django.conf import settings as django_settings
        from django.core.exceptions import ImproperlyConfigured

        key_str = getattr(django_settings, "ACCESS_LOG_HMAC_KEY", "")
        if not key_str:
            raise ImproperlyConfigured(
                "ACCESS_LOG_HMAC_KEY ausente ou vazia. "
                "Defina uma chave de no mínimo 32 bytes no settings."
            )
        return hmac.new(key_str.encode(), ip.encode(), hashlib.sha256).hexdigest()
