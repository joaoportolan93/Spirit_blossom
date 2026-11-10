"""
Throttles específicos para endpoints de autenticação.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """5 tentativas de login por minuto por IP."""

    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    """3 registros por minuto por IP."""

    scope = "register"


class PasswordResetRateThrottle(AnonRateThrottle):
    """5 tentativas de recuperação de senha por minuto por IP."""

    scope = "password_reset"


class BlockRateThrottle(UserRateThrottle):
    """10 operações de bloqueio/desbloqueio por minuto por usuário (ADR-N24)."""

    scope = "block"

