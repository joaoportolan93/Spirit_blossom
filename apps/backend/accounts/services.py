"""
Operações de escrita / mutação para accounts (ADR-N2).
"""

import logging
from typing import Optional, Tuple

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import AccessLog, UserProfile

logger = logging.getLogger(__name__)
User = get_user_model()


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


def register_user(
    *,
    email: str,
    username: str,
    password: str,
    birth_date=None,
    request=None,
) -> Tuple[User, RefreshToken]:
    """Cria novo usuário, perfil e emite par de tokens JWT."""
    user = User.objects.create_user(
        email=email,
        username=username,
        password=password,
    )
    if birth_date:
        UserProfile.objects.filter(user=user).update(birth_date=birth_date)

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
    user = authenticate(request=request, email=email, password=password)
    if not user or not user.is_valid_for_auth:
        return None, None

    log_user_access(user=user, request=request)
    refresh = RefreshToken.for_user(user)
    return user, refresh


def refresh_user_tokens(*, raw_refresh_token: str) -> Tuple[str, str]:
    """
    Valida token de refresh via serializer com rotação e blacklist.
    Retorna (new_access, new_refresh).
    Raises TokenError ou ValueError se conta inativa.
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
