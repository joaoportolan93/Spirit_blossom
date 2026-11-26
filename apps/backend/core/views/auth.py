"""
Views de autenticação (ADR-N2: finas, delegando para services).
"""

import logging

from django.conf import settings
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.authentication import _enforce_csrf
from core.models import Follow, UserProfile
from core.serializers.auth import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    DeleteAccountSerializer,
    GoogleAuthSerializer,
    GoogleCompleteSignupSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSettingsSerializer,
    UserSettingsUpdateSerializer,
)
from core.services.auth import (
    authenticate_user,
    authenticate_with_google,
    build_banned_auth_payload,
    clear_auth_cookies,
    complete_google_signup,
    confirm_password_reset,
    delete_account,
    export_user_data,
    issue_auth_cookies,
    logout_user,
    refresh_user_tokens,
    request_password_reset,
    search_users,
    set_access_cookie,
    set_refresh_cookie,
)
from core.throttles import (
    DeleteAccountRateThrottle,
    ExportDataRateThrottle,
    LoginRateThrottle,
    PasswordResetRateThrottle,
    RegisterRateThrottle,
)

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
            {"detail": _("Account created successfully.")},
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

        user, refresh = authenticate_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            request=request,
        )
        if user and not user.is_valid_for_auth:
            return Response(
                build_banned_auth_payload(
                    user,
                    detail=_("Credenciais inválidas ou conta inativa."),
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user or not refresh:
            return Response(
                {"detail": "Credenciais inválidas ou conta inativa."},
                status=status.HTTP_400_BAD_REQUEST,
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


class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset/request/
    Solicita token de redefinição de senha com resposta genérica uniforme (anti-enumeração).
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3001")
        request_password_reset(
            email=serializer.validated_data["email"],
            base_frontend_url=frontend_url,
            language=getattr(request, "LANGUAGE_CODE", "pt-br"),
        )
        return Response({"detail": _("If the email is registered, instructions have been sent.")})


class PasswordResetConfirmView(APIView):
    """
    POST /api/auth/password-reset/confirm/
    Confirma redefinição de senha e invalida token de uso único.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            confirm_password_reset(
                raw_token=serializer.validated_data["token"],
                new_password=serializer.validated_data["new_password"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": _("Password reset successfully.")})


class GoogleAuthView(APIView):
    """
    POST /api/auth/google/
    Autentica token Google ou inicia onboarding para completar cadastro.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            auth_status, data = authenticate_with_google(
                id_token_str=serializer.validated_data["id_token"],
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if auth_status == "banned":
            return Response(data, status=status.HTTP_403_FORBIDDEN)

        if auth_status == "blocked":
            return Response(data, status=status.HTTP_403_FORBIDDEN)

        if auth_status == "logged_in":
            response = Response({"status": "logged_in", "detail": "Login realizado com sucesso."})
            issue_auth_cookies(response, data["refresh"])
            return response

        # needs_signup
        return Response(
            {
                "status": "needs_signup",
                "onboarding_token": data["onboarding_token"],
                "email": data["email"],
            }
        )


class GoogleCompleteSignupView(APIView):
    """
    POST /api/auth/google/complete/
    Conclui onboarding do Google OAuth exigindo username, 18+ e aceite dos termos.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = GoogleCompleteSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            _user, refresh = complete_google_signup(
                onboarding_token=serializer.validated_data["onboarding_token"],
                username=serializer.validated_data["username"],
                birth_date=serializer.validated_data["birth_date"],
                terms_accepted=serializer.validated_data["terms_accepted"],
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response = Response(
            {"detail": "Cadastro concluído com sucesso."},
            status=status.HTTP_201_CREATED,
        )
        issue_auth_cookies(response, refresh)
        return response


class UserSearchView(APIView):
    """
    GET /api/users/search/?q=<prefix>&limit=<int>
    Busca usuários por prefixo de username (ADR-N21 / ADR-N22).
    Mínimo 2 caracteres. Exclui bloqueados em ambas as direções.
    Nunca busca por e-mail.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response(
                {"detail": "O parâmetro 'q' deve ter pelo menos 2 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            limit = min(int(request.query_params.get("limit", 20)), 50)
        except (ValueError, TypeError):
            limit = 20

        users = search_users(query=query, viewer=request.user, limit=limit)

        results = []
        for u in users:
            profile = getattr(u, "profile", None)
            follow_status = None
            follow = Follow.objects.filter(follower=request.user, followed=u).first()
            if follow:
                follow_status = follow.status

            results.append(
                {
                    "username": u.username,
                    "avatar": (profile.avatar.url if profile and profile.avatar else None),
                    "is_private": getattr(profile, "is_private", False),
                    "follow_status": follow_status,
                }
            )

        return Response({"results": results})


class UserDataExportView(APIView):
    """
    GET /api/users/export-data/
    Exportação LGPD completa dos dados do usuário autenticado (Onda 6 — ADR-N24 §7).
    Inclui perfil, posts, rascunhos, curtidas, bookmarks, comentários, follows,
    contas que o usuário bloqueou/silenciou.
    NUNCA inclui quem bloqueou ou silenciou o usuário.
    NUNCA expõe hash de senha, tokens, ip_hash.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ExportDataRateThrottle]

    def get(self, request):
        data = export_user_data(user=request.user)
        return Response(data, status=status.HTTP_200_OK)


class DeleteAccountView(APIView):
    """
    DELETE /api/users/account/
    Exclusão permanente da conta do usuário autenticado (LGPD Art. 18, VI — Onda 6).

    Estratégia: Hard-delete atômico (vencedor ToT).
    - Conta com senha: exige `current_password`.
    - Conta Google OAuth: exige `confirm_username` (@username do titular).
    - Revoga todos os tokens JWT, invalida PasswordResetTokens.
    - AccessLog preservado anonimizado (Marco Civil Art. 15).
    - Comment.author: SET_NULL via tombstone (Onda 4).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [DeleteAccountRateThrottle]

    def delete(self, request):
        serializer = DeleteAccountSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        cfg = getattr(settings, "SIMPLE_JWT", {})
        refresh_cookie = cfg.get("AUTH_COOKIE_REFRESH", "refresh_token")
        raw_refresh_token = request.COOKIES.get(refresh_cookie)

        try:
            delete_account(user=request.user, raw_refresh_token=raw_refresh_token)
        except Exception as exc:
            logger.error("Falha ao excluir conta: %s", exc, exc_info=True)
            return Response(
                {"detail": _("Erro ao excluir conta. Tente novamente.")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response


class CurrentUserView(APIView):
    """
    GET /api/auth/me/
    Retorna os dados completos do usuário autenticado e preferências (Onda 5).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/
    Altera a senha do usuário autenticado e renova cookies JWT (Onda 5).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        response = Response(
            {"detail": _("Senha alterada com sucesso.")},
            status=status.HTTP_200_OK,
        )
        refresh = RefreshToken.for_user(user)
        issue_auth_cookies(response, refresh)
        return response


class UserSettingsView(APIView):
    """
    GET  /api/users/settings/ → Consulta configurações completas do usuário (Onda 5).
    PATCH /api/users/settings/ → Atualiza configurações de perfil, avatar, privacidade,
    notificações, tema e idioma.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserSettingsSerializer(instance=profile)
        return Response(serializer.data)

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserSettingsUpdateSerializer(
            instance=profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        updated_profile = serializer.save()
        if request.path.rstrip("/").endswith("/profile"):
            return Response(
                {
                    "username": request.user.username,
                    "is_private": updated_profile.is_private,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            UserSettingsSerializer(instance=updated_profile).data,
            status=status.HTTP_200_OK,
        )
