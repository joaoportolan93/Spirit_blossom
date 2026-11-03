"""
Views de autenticação.

Fluxo de CSRF:
  GET  /api/auth/csrf/     → seta cookie csrftoken (ensure_csrf_cookie)
  POST /api/auth/login/    → lê csrftoken do cookie, retorna access+refresh cookies
  POST /api/auth/register/ → igual ao login
  POST /api/auth/refresh/  → authentication_classes=[], _enforce_csrf() manual na view
  POST /api/auth/logout/   → authentication_classes=[], _enforce_csrf() manual na view
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import _enforce_csrf
from .models import AccessLog
from .serializers import LoginSerializer, RegisterSerializer
from .throttles import LoginRateThrottle, RegisterRateThrottle

logger = logging.getLogger(__name__)
User = get_user_model()


def _jwt_settings():
    """Retorna as configurações SimpleJWT do settings."""
    return getattr(settings, "SIMPLE_JWT", {})


def _set_access_cookie(response, access_token: str):
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


def _set_refresh_cookie(response, refresh_token: str):
    """Define o cookie httpOnly de refresh token, restrito ao path /api/auth/."""
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


def _clear_auth_cookies(response):
    """Zera os cookies de access e refresh (max_age=0)."""
    cfg = _jwt_settings()
    response.delete_cookie(cfg.get("AUTH_COOKIE", "access_token"))
    response.delete_cookie(
        cfg.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        path="/api/auth/",
    )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFView(APIView):
    """
    GET /api/auth/csrf/
    Força o Django a enviar o cookie csrftoken ao frontend.
    Sem autenticação — o frontend chama isso antes de qualquer POST.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "Cookie CSRF definido."})


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Cria conta e retorna cookies JWT.
    authentication_classes=[] para evitar que cookie de acesso antigo cause 401.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        response = Response(
            {"detail": "Conta criada com sucesso."},
            status=status.HTTP_201_CREATED,
        )
        _set_access_cookie(response, str(refresh.access_token))
        _set_refresh_cookie(response, str(refresh))
        return response


class LoginView(APIView):
    """
    POST /api/auth/login/
    Autentica e retorna cookies JWT.
    authentication_classes=[] para evitar que cookie de acesso antigo cause 401.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Registra acesso (Marco Civil — validar com jurista)
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

        refresh = RefreshToken.for_user(user)
        response = Response({"detail": "Login realizado com sucesso."})
        _set_access_cookie(response, str(refresh.access_token))
        _set_refresh_cookie(response, str(refresh))
        return response


class TokenRefreshView(APIView):
    """
    POST /api/auth/refresh/
    Rotaciona o refresh token e emite novo access token.

    authentication_classes=[] porque o access token já expirou quando o
    refresh é chamado. O CSRF é verificado manualmente com _enforce_csrf().
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. CSRF obrigatório (SameSite=Lax não protege sozinho em todos os cenários)
        _enforce_csrf(request)

        cfg = _jwt_settings()
        refresh_cookie = cfg.get("AUTH_COOKIE_REFRESH", "refresh_token")
        raw_token = request.COOKIES.get(refresh_cookie)
        if not raw_token:
            return Response(
                {"detail": "Cookie de refresh ausente."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # 2. Usa o serializer oficial (cuida de rotação e blacklist)
        serializer = TokenRefreshSerializer(data={"refresh": raw_token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        # 3. Valida que o usuário ainda está ativo
        new_refresh = serializer.validated_data.get("refresh", raw_token)
        new_access = serializer.validated_data["access"]

        # Extrai user_id do access token para checar status
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            decoded = AccessToken(new_access)
            user = User.objects.get(pk=decoded["user_id"])
            if not user.is_active or user.status != user.Status.ACTIVE:
                return Response(
                    {"detail": "Conta inativa ou suspensa."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        except User.DoesNotExist:
            return Response(
                {"detail": "Token inválido."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            return Response(
                {"detail": "Token inválido."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response({"detail": "Tokens renovados."})
        _set_access_cookie(response, str(new_access))
        _set_refresh_cookie(response, str(new_refresh))
        return response


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Invalida o refresh token e limpa os cookies.

    authentication_classes=[] para não falhar com access token expirado.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. CSRF obrigatório
        _enforce_csrf(request)

        cfg = _jwt_settings()
        refresh_cookie = cfg.get("AUTH_COOKIE_REFRESH", "refresh_token")
        raw_token = request.COOKIES.get(refresh_cookie)

        if raw_token:
            try:
                token = RefreshToken(raw_token)
                token.blacklist()
            except TokenError:
                pass  # token já inválido — logout mesmo assim

        response = Response({"detail": "Logout realizado com sucesso."})
        _clear_auth_cookies(response)
        return response
