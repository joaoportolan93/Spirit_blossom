"""
Autenticação JWT via cookie httpOnly.

Fluxo:
  - CookieJWTAuthentication: extrai access_token do cookie e executa
    checagem de CSRF em métodos não-seguros (espelhando SessionAuthentication).
  - _enforce_csrf(): helper para views sem authentication_classes
    (refresh, logout, login, register).
"""

from django.middleware.csrf import CsrfViewMiddleware
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


class _CSRFCheck(CsrfViewMiddleware):
    """Subclasse mínima do middleware CSRF para uso fora do middleware stack."""

    def _reject(self, request, reason):
        return reason  # devolve motivo em vez de HttpResponseForbidden


def _enforce_csrf(request):
    """
    Checa CSRF explicitamente. Levanta PermissionDenied em falha.
    Usar em views com authentication_classes = [] onde o token JWT não existe
    ainda (refresh, logout) ou nunca existiu (login, register quando há cookie).
    """
    from rest_framework.exceptions import PermissionDenied

    check = _CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied(f"Falha na verificação CSRF: {reason}")


class CookieJWTAuthentication(BaseAuthentication):
    """
    Lê o JWT de acesso do cookie httpOnly `access_token`.
    Em métodos não-seguros (POST, PUT, PATCH, DELETE), exige o header
    X-CSRFToken (mesmo comportamento do SessionAuthentication do DRF).
    """

    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def authenticate(self, request):
        from django.conf import settings as django_settings

        cookie_name = getattr(django_settings, "SIMPLE_JWT", {}).get(
            "AUTH_COOKIE", "access_token"
        )
        raw_token = request.COOKIES.get(cookie_name)
        if not raw_token:
            return None  # anônimo; deixa outras classes tentarem

        try:
            token = AccessToken(raw_token)
        except (InvalidToken, TokenError) as exc:
            raise AuthenticationFailed(str(exc)) from exc

        user = self._get_user(token)

        # CSRF obrigatório em métodos não-seguros
        if request.method not in self.SAFE_METHODS:
            _enforce_csrf(request)

        return (user, token)

    def _get_user(self, token):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user_id = token.get("user_id")
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist as exc:
            raise AuthenticationFailed("Usuário não encontrado.") from exc

        if not user.is_active or user.status != user.Status.ACTIVE:
            raise AuthenticationFailed("Conta inativa ou suspensa.")

        return user

    def authenticate_header(self, request):
        return "Cookie"

