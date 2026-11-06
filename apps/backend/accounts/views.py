"""
Views de autenticação (ADR-N2: finas, delegando para services).
"""

import logging

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import _enforce_csrf
from .serializers import LoginSerializer, RegisterSerializer
from .services import (
    authenticate_user,
    clear_auth_cookies,
    issue_auth_cookies,
    logout_user,
    refresh_user_tokens,
    set_access_cookie,
    set_refresh_cookie,
)
from .throttles import LoginRateThrottle, RegisterRateThrottle

logger = logging.getLogger(__name__)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFView(APIView):
    """
    GET /api/auth/csrf/
    Força o Django a enviar o cookie csrftoken ao frontend.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "Cookie CSRF definido."})


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Valida dados, cria conta via serializer e injeta cookies de auth.
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
        issue_auth_cookies(response, refresh)
        return response


class LoginView(APIView):
    """
    POST /api/auth/login/
    Autentica via LoginSerializer e injeta cookies de auth.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        user, refresh = authenticate_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            request=request,
        )
        if not user or not refresh:
            return Response(
                {"detail": "Credenciais inválidas ou conta inativa."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response({"detail": "Login realizado com sucesso."})
        issue_auth_cookies(response, refresh)
        return response


class TokenRefreshView(APIView):
    """
    POST /api/auth/refresh/
    Rotaciona o refresh token e emite novo access token via service.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        _enforce_csrf(request)

        cfg = getattr(settings, "SIMPLE_JWT", {})
        refresh_cookie = cfg.get("AUTH_COOKIE_REFRESH", "refresh_token")
        raw_token = request.COOKIES.get(refresh_cookie)
        if not raw_token:
            return Response(
                {"detail": "Cookie de refresh ausente."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            new_access, new_refresh = refresh_user_tokens(raw_refresh_token=raw_token)
        except TokenError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception:
            return Response({"detail": "Token inválido."}, status=status.HTTP_401_UNAUTHORIZED)

        response = Response({"detail": "Tokens renovados."})
        set_access_cookie(response, new_access)
        set_refresh_cookie(response, new_refresh)
        return response


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Invalida o refresh token e limpa os cookies via service.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        _enforce_csrf(request)

        cfg = getattr(settings, "SIMPLE_JWT", {})
        refresh_cookie = cfg.get("AUTH_COOKIE_REFRESH", "refresh_token")
        raw_token = request.COOKIES.get(refresh_cookie)

        logout_user(raw_refresh_token=raw_token)

        response = Response({"detail": "Logout realizado com sucesso."})
        clear_auth_cookies(response)
        return response
