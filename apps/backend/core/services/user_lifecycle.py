"""
user_lifecycle.py — Serviço centralizado de Ciclo de Vida do Usuário (Onda 8 / padrão Lumem).

Implementa:
- Banimento em dois estágios (Estágio 1: Suspensão/Banimento com prazo de recurso ou
  duração temporária; Estágio 2: Exclusão Definitiva em cascata).
  Estágio 2: Exclusão Definitiva em cascata).
- Expiração automática de suspensões temporárias.
- Invalidação de tokens JWT (blacklist) e desativação de PushDevice.
- Normalização de e-mail e HMAC-SHA256 para prevenção de recadastro após banimento definitivo.
- Tombstones de comentários com respostas de terceiros, preservação de AccessLog (Marco Civil)
  e auditoria permanente em ModerationLog.
"""

import hashlib
import hmac
import logging
import re
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


# ==============================================================================
# Normalização e HMAC de e-mail
# ==============================================================================


def normalize_email_address(email: str) -> str:
    """
    Normaliza o e-mail:
    - Minúsculas e remoção de espaços em branco.
    - Remoção de tags/aliases com '+' na parte local (ex: joao+teste@gmail.com -> joao@gmail.com).
    """
    if not email:
        return ""
    cleaned = email.strip().lower()
    if "@" not in cleaned:
        return cleaned
    local_part, domain = cleaned.split("@", 1)
    local_part = re.sub(r"\+.*$", "", local_part)
    return f"{local_part}@{domain}"


def get_email_hmac(email: str) -> str:
    """
    Gera hash HMAC-SHA256 do e-mail normalizado usando BAN_HMAC_SECRET_KEY
    (ou SECRET_KEY como fallback).
    """
    normalized = normalize_email_address(email)
    secret_str = getattr(settings, "BAN_HMAC_SECRET_KEY", settings.SECRET_KEY)
    secret = secret_str.encode("utf-8")
    return hmac.new(secret, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def is_email_or_username_blocked(
    email: Optional[str] = None, username: Optional[str] = None
) -> tuple[bool, str]:
    """
    Verifica se um e-mail ou @username pertence a uma conta definitivamente banida.
    Retorna (is_blocked, reason).
    """
    from core.models import PermanentBanRecord

    if email:
        email_hash = get_email_hmac(email)
        if PermanentBanRecord.objects.filter(email_hash=email_hash).exists():
            return True, _("Este endereço de e-mail está impedido de cadastrar novas contas.")

    if username:
        clean_username = username.strip().lstrip("@")
        if PermanentBanRecord.objects.filter(username__iexact=clean_username).exists():
            return True, _("Este nome de usuário não está disponível.")

    return False, ""


# ==============================================================================
# Estágio 1: Suspensão temporária ou banimento recorrível
# ==============================================================================


def ban_user(
    user,
    reason: str,
    admin_user=None,
    duration_days: Optional[int] = None,
    preserve_for_authorities: bool = False,
):
    """
    Estágio 1 do banimento / suspensão:
    - Valida motivo obrigatório.
    - Define status=SUSPENDED e is_active=False (bloqueio imediato no CookieJWTAuthentication).
    - Se `duration_days` for informado (> 0), configura `ban_expires_at` para expiração automática.
    - Caso contrário, define prazo de recurso (`appeal_deadline`, padrão 30 dias).
    - Coloca todos os OutstandingTokens na blacklist e desativa PushDevices.
    - Registra auditoria em ModerationLog.
    """
    from core.models import ModerationLog, PushDevice

    if not reason or not str(reason).strip():
        raise ValueError(_("O motivo do banimento é obrigatório."))

    if duration_days is not None:
        try:
            duration_days = int(duration_days)
        except (ValueError, TypeError) as exc:
            raise ValueError(_("Duração do banimento inválida.")) from exc
        if duration_days <= 0:
            raise ValueError(_("A duração da suspensão deve ser maior que zero dias."))

    cleaned_reason = str(reason).strip()
    appeal_days = getattr(settings, "BAN_APPEAL_DAYS", 30)
    now = timezone.now()
    expires_at = now + timedelta(days=duration_days) if duration_days else None
    appeal_deadline = None if duration_days else now + timedelta(days=appeal_days)

    with transaction.atomic():
        user.status = user.Status.SUSPENDED
        user.is_active = False
        user.banned_at = now
        user.ban_reason = cleaned_reason
        user.banned_by = admin_user
        user.appeal_deadline = appeal_deadline
        user.ban_expires_at = expires_at
        user.preserve_for_authorities = bool(preserve_for_authorities)
        user.save(
            update_fields=[
                "status",
                "is_active",
                "banned_at",
                "ban_reason",
                "banned_by",
                "appeal_deadline",
                "ban_expires_at",
                "preserve_for_authorities",
            ]
        )

        # Blacklist de todos os OutstandingTokens do SimpleJWT
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken,
                OutstandingToken,
            )

            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
        except Exception as exc:
            logger.debug("Aviso ao colocar tokens na blacklist: %s", exc)

        # Desativa dispositivos push para interromper notificações imediatamente
        PushDevice.objects.filter(user=user).update(is_active=False)

        action = ModerationLog.Action.SUSPEND if duration_days else ModerationLog.Action.BAN
        snapshot = f"@{user.username} - {user.email} " + (
            f"(Suspensão até {expires_at:%d/%m/%Y %H:%M})"
            if expires_at
            else f"(Prazo recurso: {appeal_deadline:%d/%m/%Y})"
        )
        ModerationLog.objects.create(
            target_type="user",
            target_id=str(user.id),
            affected_user=user,
            moderator=admin_user,
            action=action,
            reason=cleaned_reason,
            content_snapshot=snapshot,
        )

    logger.info("Usuário @%s banido/suspenso por %s.", user.username, admin_user)
    return user


def unban_user(user, admin_user=None, reason: str = "Desbanido pelo administrador"):
    """
    Restaura acesso e visibilidade da conta banida/suspensa:
    - status = ACTIVE e is_active = True.
    - Limpa campos de banimento e expiração.
    - Registra ação em ModerationLog.
    """
    from core.models import ModerationLog

    with transaction.atomic():
        user.status = user.Status.ACTIVE
        user.is_active = True
        user.banned_at = None
        user.ban_reason = ""
        user.banned_by = None
        user.appeal_deadline = None
        user.ban_expires_at = None
        user.preserve_for_authorities = False
        user.save(
            update_fields=[
                "status",
                "is_active",
                "banned_at",
                "ban_reason",
                "banned_by",
                "appeal_deadline",
                "ban_expires_at",
                "preserve_for_authorities",
            ]
        )

        ModerationLog.objects.create(
            target_type="user",
            target_id=str(user.id),
            affected_user=user,
            moderator=admin_user,
            action=ModerationLog.Action.UNBAN,
            reason=reason,
            content_snapshot=f"@{user.username} restaurado.",
        )

    logger.info("Usuário @%s desbanido por %s.", user.username, admin_user)
    return user


def expire_temporary_bans() -> int:
    """
    Verifica e restaura todas as contas cuja suspensão temporária (`ban_expires_at`) já expirou.
    Retorna a quantidade de contas restauradas.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    now = timezone.now()
    expired_users = list(
        User.objects.filter(
            status=User.Status.SUSPENDED,
            ban_expires_at__isnull=False,
            ban_expires_at__lte=now,
        )
    )
    for u in expired_users:
        unban_user(u, admin_user=None, reason="Suspensão temporária expirada automaticamente.")
    return len(expired_users)


# ==============================================================================
# Estágio 2: Exclusão definitiva em cascata
# ==============================================================================


def _handle_comments_cleanup(user) -> None:
    """
    Limpeza de comentários do usuário na exclusão definitiva:
    - Com respostas de terceiros: vira tombstone (is_deleted=True, content_text='', author=None).
    - Sem respostas de terceiros: remoção física com mídia.
    """
    from comments.models import Comment
    from core.utils.media_security import delete_media_file

    user_comments = Comment.objects.filter(author=user)
    for comment in user_comments:
        has_replies_from_others = comment.replies.exclude(author=user).exists()
        delete_media_file(comment.image)
        delete_media_file(comment.video)
        if has_replies_from_others:
            comment.is_deleted = True
            comment.content_text = ""
            comment.image = None
            comment.video = None
            comment.author = None
            comment.is_edited = False
            comment.edited_at = None
            comment.save(
                update_fields=[
                    "is_deleted",
                    "content_text",
                    "image",
                    "video",
                    "author",
                    "is_edited",
                    "edited_at",
                    "updated_at",
                ]
            )
        else:
            comment.delete()


def permanently_delete_user(
    user,
    reason: str = "",
    admin_user=None,
    is_ban: bool = True,
) -> bool:
    """
    Exclusão definitiva em cascata:
    - Grava PermanentBanRecord (HMAC do e-mail normalizado + username) quando `is_ban=True`.
    - Preserva AccessLog (via ON DELETE SET NULL, Marco Civil Art. 15).
    - Preserva threads de comentários com tombstone.
    - Remove posts, mídias físicas, rascunhos, reações, relações sociais e dispositivos push.
    - Blacklista tokens SimpleJWT e registra ModerationLog permanente.
    """
    from comments.models import CommentBookmark, CommentLike
    from core.models import (
        Block,
        Draft,
        Follow,
        ModerationLog,
        Mute,
        Notification,
        PasswordResetToken,
        PermanentBanRecord,
        PostBookmark,
        PostLike,
        PushDevice,
    )
    from core.services.posts import delete_posts_for_user
    from core.utils.image_security import delete_old_avatar

    username_snapshot = user.username
    email_snapshot = user.email
    user_id_str = str(user.id)
    final_reason = reason or user.ban_reason or "Exclusão definitiva de conta"
    banned_at = user.banned_at or timezone.now()
    now = timezone.now()

    with transaction.atomic():
        if is_ban:
            email_hash = get_email_hmac(email_snapshot)
            PermanentBanRecord.objects.get_or_create(
                username=username_snapshot,
                defaults={
                    "email_hash": email_hash,
                    "ban_reason": final_reason,
                    "banned_at": banned_at,
                    "deleted_at": now,
                    "executed_by": admin_user,
                    "preserve_for_authorities": getattr(user, "preserve_for_authorities", False),
                },
            )

        _handle_comments_cleanup(user)

        delete_posts_for_user(user)

        profile = getattr(user, "profile", None)
        if profile:
            try:
                delete_old_avatar(profile)
            except Exception:
                logger.warning("Falha ao remover avatar na exclusão definitiva.", exc_info=True)

        PostLike.objects.filter(user=user).delete()
        PostBookmark.objects.filter(user=user).delete()
        CommentLike.objects.filter(user=user).delete()
        CommentBookmark.objects.filter(user=user).delete()
        Draft.objects.filter(author=user).delete()

        Follow.objects.filter(Q(follower=user) | Q(followed=user)).delete()
        Block.objects.filter(Q(blocker=user) | Q(blocked=user)).delete()
        Mute.objects.filter(Q(muter=user) | Q(muted=user)).delete()
        Notification.objects.filter(Q(recipient=user) | Q(sender=user)).delete()

        PushDevice.objects.filter(user=user).delete()
        PasswordResetToken.objects.filter(user=user).delete()

        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken,
                OutstandingToken,
            )

            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
        except Exception as exc:
            logger.debug("Aviso blacklist na exclusão: %s", exc)

        ModerationLog.objects.create(
            target_type="user",
            target_id=user_id_str,
            affected_user=None,
            moderator=admin_user,
            action=ModerationLog.Action.PERMANENT_DELETE,
            reason=final_reason,
            content_snapshot=f"@{username_snapshot} ({email_snapshot}) excluído definitivamente.",
        )

        user.delete()

    logger.info("Usuário @%s (%s) excluído definitivamente.", username_snapshot, user_id_str)
    return True


def purge_expired_banned_accounts(dry_run: Optional[bool] = None) -> list[dict]:
    """
    Busca contas banidas cujo prazo de recurso (`appeal_deadline`) expirou e executa
    a exclusão definitiva (respeitando `preserve_for_authorities=True` e `dry_run=True` padrão).
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if dry_run is None:
        dry_run = getattr(settings, "BAN_PURGE_DRY_RUN", True)

    now = timezone.now()
    expired_users = list(
        User.objects.filter(
            status=User.Status.SUSPENDED,
            appeal_deadline__isnull=False,
            appeal_deadline__lte=now,
            ban_expires_at__isnull=True,
            preserve_for_authorities=False,
        )
    )

    results = []
    for u in expired_users:
        results.append(
            {
                "id": str(u.id),
                "username": u.username,
                "email": u.email,
                "banned_at": u.banned_at.isoformat() if u.banned_at else None,
                "appeal_deadline": u.appeal_deadline.isoformat() if u.appeal_deadline else None,
                "preserve_for_authorities": u.preserve_for_authorities,
                "dry_run": dry_run,
            }
        )
        if not dry_run:
            permanently_delete_user(
                user=u,
                reason=u.ban_reason or "Exclusão definitiva por decurso do prazo de recurso",
                admin_user=None,
                is_ban=True,
            )

    return results
