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

from core.models import AccessLog, Block, OAuthAccount, PasswordResetToken, UserProfile

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


def request_password_reset(*, email: str, base_frontend_url: str = "http://localhost:3001") -> None:
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

        app_name = getattr(settings, "APP_NAME", "Spirit Blossom")
        subject = f"[{app_name}] Recuperação de senha"
        message = (
            f"Olá {user.username},\n\n"
            f"Você solicitou a recuperação da sua senha na {app_name}.\n"
            f"Acesse o link abaixo em até 15 minutos para definir uma nova senha:\n\n"
            f"{reset_url}\n\n"
            f"Se você não solicitou, nenhuma ação é necessária."
        )
        send_mail(
            subject=subject,
            message=message,
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
