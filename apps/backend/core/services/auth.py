"""
Serviços e consultas de usuários e autenticação (ADR-N2).
"""

import hashlib
import logging
import secrets
from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from core.models import (
    AccessLog,
    Block,
    Draft,
    Follow,
    Mute,
    OAuthAccount,
    PasswordResetToken,
    PostBookmark,
    PostLike,
    UserProfile,
)
from core.services.posts import list_posts_for_export

logger = logging.getLogger(__name__)
User = get_user_model()


# -----------------------------------------------------------------------------
# Consultas de Usuários (ex-selectors)
# -----------------------------------------------------------------------------


def get_user_by_id(user_id) -> Optional[User]:
    """Retorna o usuário pelo ID ou None se não encontrado."""
    try:
        return User.objects.select_related("profile").get(pk=user_id)
    except User.DoesNotExist:
        return None


def get_user_by_username(username: str) -> Optional[User]:
    """Retorna o usuário pelo username ou None."""
    try:
        return User.objects.select_related("profile").get(username=username)
    except User.DoesNotExist:
        return None


def get_user_by_email(email: str) -> Optional[User]:
    """Retorna o usuário pelo e-mail ou None."""
    try:
        return User.objects.select_related("profile").get(email=email)
    except User.DoesNotExist:
        return None


def search_users(*, query: str, viewer, limit: int = 20) -> QuerySet:
    """
    Busca usuários por prefixo de username (ADR-N21 / ADR-N22).

    Regras:
    - Mínimo 2 caracteres no query
    - Busca apenas por username (nunca por e-mail)
    - Exclui contas inativas
    - Exclui o próprio viewer
    - Exclui bloqueados em ambas as direções
    - Limite configurável, padrão 20
    """
    if len(query) < 2:
        return User.objects.none()

    blocked_by_viewer = Block.objects.filter(
        blocker=viewer,
        blocked=OuterRef("pk"),
    )
    viewer_blocked_by = Block.objects.filter(
        blocker=OuterRef("pk"),
        blocked=viewer,
    )

    return (
        User.objects.filter(
            username__istartswith=query,
            is_active=True,
            status=User.Status.ACTIVE,
        )
        .exclude(pk=viewer.pk)
        .exclude(Exists(blocked_by_viewer))
        .exclude(Exists(viewer_blocked_by))
        .select_related("profile")
        .order_by("username")[:limit]
    )


# -----------------------------------------------------------------------------
# Cookies e Sessão JWT
# -----------------------------------------------------------------------------


def _jwt_settings() -> dict:
    return getattr(settings, "SIMPLE_JWT", {})


def set_access_cookie(response, access_token: str) -> None:
    """Define o cookie httpOnly de access token."""
    cfg = _jwt_settings()
    lifetime = cfg.get("ACCESS_TOKEN_LIFETIME")
    max_age = int(lifetime.total_seconds()) if lifetime else 900
    response.set_cookie(
        key=cfg.get("AUTH_COOKIE", "access_token"),
        value=access_token,
        max_age=max_age,
        httponly=True,
        secure=cfg.get("AUTH_COOKIE_SECURE", not settings.DEBUG),
        samesite=cfg.get("AUTH_COOKIE_SAMESITE", "Lax"),
    )


def set_refresh_cookie(response, refresh_token: str) -> None:
    """Define o cookie httpOnly de refresh token, restrito a /api/auth/."""
    cfg = _jwt_settings()
    lifetime = cfg.get("REFRESH_TOKEN_LIFETIME")
    max_age = int(lifetime.total_seconds()) if lifetime else 604800
    response.set_cookie(
        key=cfg.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=cfg.get("AUTH_COOKIE_SECURE", not settings.DEBUG),
        samesite=cfg.get("AUTH_COOKIE_SAMESITE", "Lax"),
        path="/api/auth/",
    )


def clear_auth_cookies(response) -> None:
    """Zera os cookies de autenticação (max_age=0)."""
    cfg = _jwt_settings()
    response.delete_cookie(cfg.get("AUTH_COOKIE", "access_token"))
    response.delete_cookie(
        cfg.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        path="/api/auth/",
    )


def issue_auth_cookies(response, refresh_token: RefreshToken) -> None:
    """Aplica ambos os cookies httpOnly (access e refresh) na resposta."""
    set_access_cookie(response, str(refresh_token.access_token))
    set_refresh_cookie(response, str(refresh_token))


# -----------------------------------------------------------------------------
# Fluxos de Registro, Login e Logout
# -----------------------------------------------------------------------------


def register_user(
    *,
    email: str,
    username: str,
    password: str,
    birth_date=None,
    terms_accepted: bool = True,
    request=None,
) -> Tuple[User, RefreshToken]:
    """Cria novo usuário, perfil e emite par de tokens JWT."""
    if not terms_accepted:
        raise ValueError("Você deve aceitar os Termos de Uso e Política de Privacidade.")

    user = User.objects.create_user(
        email=email,
        username=username,
        password=password,
    )
    defaults = {"terms_accepted_at": timezone.now()}
    if birth_date:
        defaults["birth_date"] = birth_date

    UserProfile.objects.update_or_create(user=user, defaults=defaults)

    refresh = RefreshToken.for_user(user)
    return user, refresh


def log_user_access(*, user: User, request) -> None:
    """Registra log de acesso do usuário (Marco Civil da Internet)."""
    if not request:
        return
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
    ip = ip.split(",")[0].strip()
    port = request.META.get("REMOTE_PORT", 0)
    try:
        AccessLog.objects.create(
            user=user,
            ip_hash=AccessLog.hash_ip(ip),
            port=int(port) if port else 0,
        )
    except Exception:
        logger.warning("Falha ao registrar AccessLog.", exc_info=True)


def authenticate_user(
    *,
    email: str,
    password: str,
    request=None,
) -> Tuple[Optional[User], Optional[RefreshToken]]:
    """Autentica usuário e retorna user e tokens ou None."""
    user = authenticate(request=request, username=email, password=password)
    if not user or not user.is_valid_for_auth:
        return None, None

    log_user_access(user=user, request=request)
    refresh = RefreshToken.for_user(user)
    return user, refresh


def refresh_user_tokens(*, raw_refresh_token: str) -> Tuple[str, str]:
    """
    Valida token de refresh via serializer com rotação e blacklist.
    Retorna (new_access, new_refresh).
    """
    serializer = TokenRefreshSerializer(data={"refresh": raw_refresh_token})
    serializer.is_valid(raise_exception=True)

    new_refresh = serializer.validated_data.get("refresh", raw_refresh_token)
    new_access = serializer.validated_data["access"]

    decoded = AccessToken(new_access)
    user = User.objects.get(pk=decoded["user_id"])
    if not user.is_valid_for_auth:
        raise ValueError("Conta inativa ou suspensa.")

    return str(new_access), str(new_refresh)


def logout_user(*, raw_refresh_token: Optional[str]) -> None:
    """Blacklista o refresh token se fornecido."""
    if raw_refresh_token:
        try:
            token = RefreshToken(raw_refresh_token)
            token.blacklist()
        except TokenError:
            pass


# -----------------------------------------------------------------------------
# Recuperação de Senha
# -----------------------------------------------------------------------------


def request_password_reset(
    *,
    email: str,
    base_frontend_url: str = "http://localhost:3001",
    language: Optional[str] = None,
) -> None:
    """
    Solicita redefinição de senha com token de uso único (15 min).
    Sempre responde sem vazar se o usuário existe (anti-enumeração).
    Envia e-mail em transaction.on_commit com token no fragmento (#token=...).
    """
    user = User.objects.filter(email=email).first()
    if not user or not user.is_valid_for_auth:
        return

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = timezone.now() + timedelta(minutes=15)

    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    PasswordResetToken.objects.create(
        user=user,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    reset_url = f"{base_frontend_url}/reset-password#token={raw_token}"

    def _send():
        from django.core.mail import send_mail
        from django.utils import translation
        from django.utils.translation import gettext as _

        user_lang = (
            language or getattr(getattr(user, "profile", None), "language", "pt-br") or "pt-br"
        )
        with translation.override(user_lang):
            app_name = getattr(settings, "APP_NAME", "Spirit Blossom")
            subject = _("[%(app_name)s] Password reset") % {"app_name": app_name}
            message = _(
                "Hello %(username)s,\n\n"
                "You requested a password reset on %(app_name)s.\n"
                "Access the link below within 15 minutes to set a new password:\n\n"
                "%(reset_url)s\n\n"
                "If you did not request this, no action is needed."
            ) % {"username": user.username, "app_name": app_name, "reset_url": reset_url}
            send_mail(
                subject=str(subject),
                message=str(message),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@spiritblossom.local"),
                recipient_list=[user.email],
                fail_silently=False,
            )

    transaction.on_commit(_send)


@transaction.atomic
def confirm_password_reset(*, raw_token: str, new_password: str) -> User:
    """
    Confirma nova senha usando token do fragmento.
    Invalida o token e atualiza a senha do usuário.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    reset_token = (
        PasswordResetToken.objects.select_related("user")
        .filter(token_hash=token_hash, used_at__isnull=True, expires_at__gt=timezone.now())
        .first()
    )
    if not reset_token or not reset_token.user.is_valid_for_auth:
        raise ValueError("Token de recuperação inválido ou expirado.")

    user = reset_token.user
    user.set_password(new_password)
    user.save(update_fields=["password"])

    reset_token.used_at = timezone.now()
    reset_token.save(update_fields=["used_at"])
    return user


# -----------------------------------------------------------------------------
# Google OAuth
# -----------------------------------------------------------------------------


def verify_google_id_token(id_token_str: str) -> dict:
    """
    Valida ID token do Google.
    Em testes e dev suporta tokens simulados `mock-google-token:sub:email:verified`.
    """
    if getattr(settings, "TESTING", False) or settings.DEBUG:
        if id_token_str.startswith("mock-google-token:"):
            parts = id_token_str.split(":")
            if len(parts) >= 4:
                return {
                    "sub": parts[1],
                    "email": parts[2],
                    "email_verified": parts[3].lower() == "true",
                    "aud": getattr(settings, "GOOGLE_CLIENT_ID", "test-client-id"),
                    "iss": "https://accounts.google.com",
                }

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    google_client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
    req = google_requests.Request()
    id_info = id_token.verify_oauth2_token(id_token_str, req, google_client_id)
    if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
        raise ValueError("Emissor do token Google inválido.")
    return id_info


def generate_google_onboarding_token(*, google_sub: str, email: str) -> str:
    from django.core import signing

    return signing.dumps({"sub": google_sub, "email": email}, salt="google-onboarding")


def verify_google_onboarding_token(token_str: str) -> dict:
    from django.core import signing

    try:
        return signing.loads(token_str, salt="google-onboarding", max_age=600)
    except Exception:
        raise ValueError("Token de cadastro do Google inválido ou expirado.")


def authenticate_with_google(*, id_token_str: str, request=None) -> Tuple[str, dict]:
    """
    Autentica com token Google.
    Retorna ('logged_in', {'user': user, 'refresh': refresh}) ou
            ('needs_signup', {'onboarding_token': token, 'email': email})
    """
    id_info = verify_google_id_token(id_token_str)
    google_sub = id_info.get("sub")
    email = id_info.get("email")
    email_verified = id_info.get("email_verified", False)

    if not google_sub or not email:
        raise ValueError("Token do Google inválido: sub ou email ausente.")
    if not email_verified:
        raise ValueError("O e-mail da conta Google não foi verificado.")

    oauth_acc = (
        OAuthAccount.objects.select_related("user")
        .filter(provider="google", uid=google_sub)
        .first()
    )
    if oauth_acc:
        user = oauth_acc.user
        if not user.is_valid_for_auth:
            raise ValueError("Conta inativa ou suspensa.")
        log_user_access(user=user, request=request)
        refresh = RefreshToken.for_user(user)
        return "logged_in", {"user": user, "refresh": refresh}

    if User.objects.filter(email=email).exists():
        raise ValueError(
            "Este e-mail já está cadastrado. Faça login com sua senha e vincule sua conta Google "
            "nas configurações de segurança."
        )

    onboarding_token = generate_google_onboarding_token(google_sub=google_sub, email=email)
    return "needs_signup", {"onboarding_token": onboarding_token, "email": email}


# -----------------------------------------------------------------------------
# Exportação LGPD (ADR-N24 §7) e Exclusão de Conta (LGPD Art. 18, VI)
# -----------------------------------------------------------------------------


def export_user_data(*, user) -> dict:
    """
    Exporta todos os dados do titular conforme LGPD Art. 18, V.

    NUNCA expõe:
    - Quem bloqueou/silenciou o usuário (ADR-N24 §7)
    - Hashes de senha, tokens, ip_hash ou chaves internas
    """
    from comments.models import Comment, CommentBookmark, CommentLike

    profile = getattr(user, "profile", None)

    # Perfil
    profile_data = {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "display_name": getattr(profile, "display_name", "") or "",
        "bio": getattr(profile, "bio", "") or "",
        "is_private": getattr(profile, "is_private", False),
        "birth_date": str(profile.birth_date) if profile and profile.birth_date else None,
        "theme": getattr(profile, "theme", UserProfile.Theme.LIGHT),
        "language": getattr(profile, "language", UserProfile.Language.PT_BR),
        "terms_accepted_at": (
            profile.terms_accepted_at.isoformat() if profile and profile.terms_accepted_at else None
        ),
        "date_joined": user.date_joined.isoformat(),
    }

    # Posts
    posts_data = [
        {
            "id": str(p.id),
            "content_text": p.content_text,
            "visibility": p.visibility,
            "likes_count": p.likes_count,
            "comments_count": p.comments_count,
            "created_at": p.created_at.isoformat(),
        }
        for p in list_posts_for_export(author=user)
    ]

    # Rascunhos
    drafts_data = [
        {
            "id": str(d.id),
            "content_text": d.content_text,
            "updated_at": d.updated_at.isoformat(),
        }
        for d in Draft.objects.filter(author=user).order_by("-updated_at")
    ]

    # Curtidas de post
    post_likes_data = [
        {
            "post_id": str(pl.post_id),
            "created_at": pl.created_at.isoformat(),
        }
        for pl in PostLike.objects.filter(user=user).order_by("-created_at")
    ]

    # Bookmarks de post
    post_bookmarks_data = [
        {
            "post_id": str(pb.post_id),
            "created_at": pb.created_at.isoformat(),
        }
        for pb in PostBookmark.objects.filter(user=user).order_by("-created_at")
    ]

    # Comentários do usuário
    comments_data = [
        {
            "id": str(c.id),
            "post_id": str(c.post_id),
            "parent_id": str(c.parent_id) if c.parent_id else None,
            "content_text": c.content_text,
            "created_at": c.created_at.isoformat(),
        }
        for c in Comment.objects.filter(author=user, is_deleted=False).order_by("-created_at")
    ]

    # Curtidas de comentário
    comment_likes_data = [
        {
            "comment_id": str(cl.comment_id),
            "created_at": cl.created_at.isoformat(),
        }
        for cl in CommentLike.objects.filter(user=user).order_by("-created_at")
    ]

    # Bookmarks de comentário
    comment_bookmarks_data = [
        {
            "comment_id": str(cb.comment_id),
            "created_at": cb.created_at.isoformat(),
        }
        for cb in CommentBookmark.objects.filter(user=user).order_by("-created_at")
    ]

    # Seguindo
    following_data = [
        {
            "username": f.followed.username,
            "is_close_friend": f.is_close_friend,
            "since": f.created_at.isoformat(),
        }
        for f in Follow.objects.filter(follower=user, status=Follow.Status.ACTIVE).select_related(
            "followed"
        )
    ]

    # Seguidores
    followers_data = [
        {
            "username": f.follower.username,
            "since": f.created_at.isoformat(),
        }
        for f in Follow.objects.filter(followed=user, status=Follow.Status.ACTIVE).select_related(
            "follower"
        )
    ]

    # Contas que o usuário bloqueou (NUNCA o contrário — ADR-N24 §7)
    blocked_by_me = [
        {
            "id": str(b.blocked.id),
            "username": b.blocked.username,
            "blocked_at": b.created_at.isoformat(),
        }
        for b in Block.objects.filter(blocker=user).select_related("blocked")
    ]

    # Contas que o usuário silenciou (NUNCA o contrário — ADR-N24 §7)
    muted_by_me = [
        {
            "id": str(m.muted.id),
            "username": m.muted.username,
            "muted_at": m.created_at.isoformat(),
        }
        for m in Mute.objects.filter(muter=user).select_related("muted")
    ]

    return {
        "exported_at": timezone.now().isoformat(),
        "profile": profile_data,
        "posts": posts_data,
        "drafts": drafts_data,
        "post_likes": post_likes_data,
        "post_bookmarks": post_bookmarks_data,
        "comments": comments_data,
        "comment_likes": comment_likes_data,
        "comment_bookmarks": comment_bookmarks_data,
        "following": following_data,
        "followers": followers_data,
        "blocked_users": blocked_by_me,
        "muted_users": muted_by_me,
    }


@transaction.atomic
def delete_account(*, user, raw_refresh_token: Optional[str] = None) -> None:
    """
    Exclui permanentemente a conta do usuário (LGPD Art. 18, VI).

    Estratégia: Caminho A — Hard-delete atômico (vencedor ToT).
    - AccessLog: preservado anonimizado via ON DELETE SET NULL (Marco Civil Art. 15).
    - Comment.author: SET_NULL já garante tombstone (Onda 4).
    - Revoga todos os outstanding tokens antes da exclusão.
    - Invalida PasswordResetTokens pendentes.
    - Exclui avatar físico do storage.
    """
    # 1. Blacklista o refresh token atual
    if raw_refresh_token:
        try:
            token = RefreshToken(raw_refresh_token)
            token.blacklist()
        except TokenError:
            pass

    # 2. Revoga todos os outstanding tokens do usuário via blacklist
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )

        for ot in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=ot)
    except Exception:
        logger.warning("Falha ao revogar outstanding tokens.", exc_info=True)

    # 3. Invalida PasswordResetTokens pendentes
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    # 4. Remove avatar físico do storage
    profile = getattr(user, "profile", None)
    if profile:
        try:
            from core.utils.image_security import delete_old_avatar

            delete_old_avatar(profile)
        except Exception:
            logger.warning("Falha ao excluir avatar do storage.", exc_info=True)

    # 5. Hard-delete do usuário (AccessLog e Comments ficam via SET_NULL)
    user.delete()


@transaction.atomic
def complete_google_signup(
    *,
    onboarding_token: str,
    username: str,
    birth_date,
    terms_accepted: bool,
    request=None,
) -> Tuple[User, RefreshToken]:
    """Completa cadastro via Google OAuth com verificação 18+, username e termos."""
    if not terms_accepted:
        raise ValueError("Você deve aceitar os Termos de Uso e Política de Privacidade.")

    data = verify_google_onboarding_token(onboarding_token)
    google_sub = data["sub"]
    email = data["email"]

    user = User.objects.create_user(email=email, username=username)
    UserProfile.objects.update_or_create(
        user=user,
        defaults={
            "birth_date": birth_date,
            "terms_accepted_at": timezone.now(),
        },
    )
    OAuthAccount.objects.create(user=user, provider="google", uid=google_sub)

    log_user_access(user=user, request=request)
    refresh = RefreshToken.for_user(user)
    return user, refresh
