"""
Avaliação determinística e cacheada de Feature Flags (Onda 7a + Onda 8).

Regras de avaliação (em ordem de prioridade):
- Default seguro: retorna False se a flag não existir ou em caso de erro.
- is_enabled=False → sempre False, independente de rollout/admin_only.
- admin_only=True → True somente se user for is_staff ou is_superuser.
- allowed_users → sempre habilitado para usuários na allowlist.
- rollout_percentage: SHA-256(user_id|key) % 100 < rollout_percentage → True.
- Usuários anônimos (user=None): habilitado apenas se rollout_percentage == 100
  (com admin_only=False).

Performance:
- Cache em memória via Django cache framework (TTL 60s), invalidado via save/delete/m2m_changed.
"""

import hashlib
import logging
from typing import Optional

from django.core.cache import cache
from django.db.models.signals import m2m_changed

logger = logging.getLogger(__name__)

_CACHE_TTL = 60  # segundos


def _cache_key(flag_key: str) -> str:
    return f"feature_flag:{flag_key}"


def invalidate_flag_cache(flag_key: str) -> None:
    """Invalida o cache de uma flag específica."""
    try:
        cache.delete(_cache_key(flag_key))
    except Exception:
        pass


def _get_flag(flag_key: str):
    """Retorna FeatureFlag (com allowed_users prefetch) ou None, usando cache."""
    key = _cache_key(flag_key)
    cached = cache.get(key)
    if cached is not None:
        return cached if cached is not False else None

    try:
        from core.models import FeatureFlag

        flag: Optional[FeatureFlag] = (
            FeatureFlag.objects.filter(key=flag_key).prefetch_related("allowed_users").first()
        )
        # Força avaliação da allowlist antes de armazenar no cache em memória
        if flag is not None:
            flag._cached_allowed_ids = set(flag.allowed_users.values_list("pk", flat=True))
            cache.set(key, flag, _CACHE_TTL)
        else:
            cache.set(key, False, _CACHE_TTL)
        return flag
    except Exception:
        logger.warning("[FeatureFlag] Erro ao buscar flag '%s' no banco.", flag_key)
        return None


def _connect_m2m_invalidation() -> None:
    try:
        from core.models import FeatureFlag

        def _on_allowed_users_changed(sender, instance, action, **kwargs):
            if action in ("post_add", "post_remove", "post_clear") and hasattr(instance, "key"):
                invalidate_flag_cache(instance.key)

        m2m_changed.connect(
            _on_allowed_users_changed,
            sender=FeatureFlag.allowed_users.through,
            weak=False,
        )
    except Exception:
        pass


_connect_m2m_invalidation()


def is_feature_enabled(key: str, user=None) -> bool:
    """Retorna True se a flag `key` estiver ativa para o usuário dado.

    Nunca levanta exceção — retorna False em qualquer erro.
    """
    flag = _get_flag(key)
    if flag is None:
        return False

    if not flag.is_enabled:
        return False

    if getattr(flag, "admin_only", False):
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))

    # Usuário autenticado na allowlist → sempre habilitado
    if user is not None and hasattr(user, "pk") and user.pk is not None:
        try:
            allowed_ids = getattr(flag, "_cached_allowed_ids", None)
            if allowed_ids is not None:
                if user.pk in allowed_ids:
                    return True
            elif flag.allowed_users.filter(pk=user.pk).exists():
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
    """Retorna dict de todas as flags com seu estado avaliado para o usuário."""
    try:
        from core.models import FeatureFlag

        keys = list(FeatureFlag.objects.values_list("key", flat=True))
    except Exception:
        return {}

    return {k: is_feature_enabled(k, user) for k in keys}
