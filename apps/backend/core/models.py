import hashlib
import hmac

import uuid6
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import GeneratedField, Q
from django.utils.translation import gettext_lazy as _

# ==============================================================================
# Usuários e Autenticação (Accounts)
# ==============================================================================


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
    is_private = models.BooleanField(
        default=False,
        help_text=_("Indica se a conta é privada."),
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


# ==============================================================================
# Publicações (Posts)
# ==============================================================================


class Post(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = "public", _("Público")
        CIRCLE = "circle", _("Círculo de Amigos")

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    content_text = models.TextField(max_length=3000)
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
    )
    likes_count = models.PositiveIntegerField(default=0)
    bookmarks_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    hidden_comments_count = models.PositiveIntegerField(default=0)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    search_vector = GeneratedField(
        expression=SearchVector("content_text", config="simple"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        db_table = "posts_post"
        verbose_name = _("publicação")
        verbose_name_plural = _("publicações")
        indexes = [
            models.Index(fields=["author", "-id"], name="posts_post_author_id_idx"),
            GinIndex(fields=["search_vector"], name="posts_post_search_gin"),
        ]
        ordering = ["-id"]

    def __str__(self):
        return f"{self.author_id} @ {self.created_at:%Y-%m-%d %H:%M}"


class PostLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "posts_postlike"
        verbose_name = _("curtida de publicação")
        verbose_name_plural = _("curtidas de publicação")
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_post_like"),
        ]

    def __str__(self):
        return f"{self.user_id} ♥ {self.post_id}"


class PostBookmark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "posts_postbookmark"
        verbose_name = _("favorito de publicação")
        verbose_name_plural = _("favoritos de publicação")
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_post_bookmark"),
        ]

    def __str__(self):
        return f"{self.user_id} 🔖 {self.post_id}"


class Draft(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="drafts",
    )
    content_text = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "posts_draft"
        verbose_name = _("rascunho")
        verbose_name_plural = _("rascunhos")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Draft({self.author_id}, {self.id})"


# ==============================================================================
# Relações Sociais (Social)
# ==============================================================================


class Follow(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Ativo")
        PENDING = "pending", _("Pendente")

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
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        db_table = "social_follow"
        verbose_name = _("seguimento")
        verbose_name_plural = _("seguimentos")
        constraints = [
            models.UniqueConstraint(fields=["follower", "followed"], name="unique_follow"),
            models.CheckConstraint(
                condition=~Q(follower=models.F("followed")),
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
                condition=~Q(blocker=models.F("blocked")),
                name="no_self_block",
            ),
        ]
        indexes = [
            models.Index(fields=["blocker", "blocked"], name="block_blocker_blocked_idx"),
            models.Index(fields=["blocked", "blocker"], name="block_blocked_blocker_idx"),
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
                condition=~Q(muter=models.F("muted")),
                name="no_self_mute",
            ),
        ]
        indexes = [
            models.Index(fields=["muter", "muted"], name="mute_muter_muted_idx"),
            models.Index(fields=["muted", "muter"], name="mute_muted_muter_idx"),
        ]

    def __str__(self):
        return f"{self.muter_id} 🔇 {self.muted_id}"


# ==============================================================================
# Notificações (Notifications)
# ==============================================================================


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
