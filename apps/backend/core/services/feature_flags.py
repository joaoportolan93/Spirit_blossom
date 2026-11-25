"""
Avaliação determinística de Feature Flags (Onda 7a).

Regras:
- Default seguro: retorna False se a flag não existir.
- is_enabled=False → sempre False, independente de rollout.
- allowed_users: sempre habilitado para usuários na lista.
- rollout_percentage: SHA-256(user_id|key) % 100 < rollout_percentage → True.
- Usuários anônimos (user=None): habilitado apenas se rollout_percentage == 100.
"""

import hashlib
from typing import Optional


def is_feature_enabled(key: str, user=None) -> bool:
    """Retorna True se a flag `key` estiver ativa para o usuário dado.

    Nunca levanta exceção — retorna False em qualquer erro.
    """
    try:
        from core.models import FeatureFlag

        flag: Optional[FeatureFlag] = (
            FeatureFlag.objects.filter(key=key).prefetch_related("allowed_users").first()
        )
    except Exception:
        return False

    if flag is None:
        return False

    if not flag.is_enabled:
        return False

    # Usuário autenticado na allowlist → sempre habilitado
    if user is not None and hasattr(user, "pk") and user.pk is not None:
        try:
            if flag.allowed_users.filter(pk=user.pk).exists():
                return True
        except Exception:
            pass

        # Rollout gradual por SHA-256 determinístico
        if flag.rollout_percentage >= 100:
            return True
        if flag.rollout_percentage <= 0:
            return False

        digest = hashlib.sha256(f"{user.pk}|{key}".encode()).hexdigest()
        bucket = int(digest[:8], 16) % 100
        return bucket < flag.rollout_percentage

    # Usuário anônimo: só habilita se rollout = 100%
    return flag.rollout_percentage >= 100


def get_flags_for_user(user=None) -> dict:
    """Retorna dict de todas as flags ativas com seu estado para o usuário."""
    try:
        from core.models import FeatureFlag

        flags = FeatureFlag.objects.all()
    except Exception:
        return {}

    return {flag.key: is_feature_enabled(flag.key, user) for flag in flags}
