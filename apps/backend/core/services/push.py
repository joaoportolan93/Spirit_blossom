"""
Serviço de Push Notifications via Firebase Cloud Messaging (FCM) — Onda 7a.

Design:
- Inicialização LAZY do firebase-admin: app não crasha em dev/CI/testes sem credenciais.
- No-op seguro: se credenciais não configuradas, loga aviso e retorna sem erro.
- Limpeza automática de tokens inválidos/expirados ao receber UnregisteredError.
- Payloads genéricos (ADR-N21/N24): nunca expõe conteúdo privado.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_firebase_app = None
_firebase_initialized = False


def _get_firebase_app():
    """Inicializa firebase-admin com lazy loading. Retorna None sem credenciais."""
    global _firebase_app, _firebase_initialized

    if _firebase_initialized:
        return _firebase_app

    _firebase_initialized = True
    try:
        import firebase_admin
        from django.conf import settings

        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", None)
        if not cred_path:
            logger.info(
                "FIREBASE_CREDENTIALS_PATH não configurado — push notifications desabilitado."
            )
            return None

        from firebase_admin import credentials

        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK inicializado com sucesso.")
        return _firebase_app
    except ImportError:
        logger.warning("firebase-admin não instalado — push notifications desabilitado.")
        return None
    except Exception as exc:
        logger.warning("Falha ao inicializar Firebase Admin SDK: %s", exc)
        return None


def send_push_notification(
    *,
    tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> dict:
    """
    Envia push notification para uma lista de tokens FCM.

    Retorna dict com 'sent' (int) e 'removed_tokens' (list[str]).
    Nunca levanta exceção — falhas são logadas e ignoradas graciosamente.
    Payloads de dados nunca devem incluir conteúdo privado de posts/comentários.
    """
    if not tokens:
        return {"sent": 0, "removed_tokens": []}

    app = _get_firebase_app()
    if app is None:
        logger.debug("Firebase não disponível — push não enviado (%d tokens).", len(tokens))
        return {"sent": 0, "removed_tokens": []}

    try:
        from firebase_admin import messaging

        messages = [
            messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                token=token,
            )
            for token in tokens
        ]

        batch_response = messaging.send_each(messages)
        sent = 0
        removed_tokens: list[str] = []

        for idx, response in enumerate(batch_response.responses):
            if response.success:
                sent += 1
            else:
                exc = response.exception
                token = tokens[idx]
                if exc is not None:
                    exc_name = type(exc).__name__
                    if exc_name in ("UnregisteredError", "InvalidArgumentError"):
                        removed_tokens.append(token)
                        logger.info("Token FCM inválido/expirado removido: %s…", token[:20])
                    else:
                        logger.warning("Falha ao enviar push para token: %s", exc_name)

        # Desativa tokens inválidos no banco
        if removed_tokens:
            _deactivate_tokens(removed_tokens)

        return {"sent": sent, "removed_tokens": removed_tokens}

    except Exception as exc:
        logger.error("Erro inesperado no envio de push: %s", exc)
        return {"sent": 0, "removed_tokens": []}


def _deactivate_tokens(tokens: list[str]) -> None:
    """Desativa tokens inválidos no PushDevice sem levantar exceção."""
    try:
        from core.models import PushDevice

        PushDevice.objects.filter(token__in=tokens).update(is_active=False)
    except Exception as exc:
        logger.warning("Falha ao desativar tokens inválidos: %s", exc)


def register_device(
    *, user, token: str, platform: str = "web", device_name: str = ""
) -> "PushDevice":  # noqa: F821
    """
    Registra ou reatribui um token FCM ao usuário.

    Se o token já existir para outro usuário (mesmo navegador, login diferente),
    reatribui ao usuário corrente — evitando vazamento cross-account (ADR-N24).
    """
    from django.utils import timezone

    from core.models import PushDevice

    try:
        device = PushDevice.objects.get(token=token)
        # Token de outro usuário → reatribui
        device.user = user
        device.platform = platform
        device.device_name = device_name
        device.is_active = True
        device.last_used_at = timezone.now()
        device.save(update_fields=["user", "platform", "device_name", "is_active", "last_used_at"])
        return device
    except PushDevice.DoesNotExist:
        return PushDevice.objects.create(
            user=user,
            token=token,
            platform=platform,
            device_name=device_name,
            is_active=True,
        )


def deactivate_user_devices(*, user) -> int:
    """Desativa todos os dispositivos do usuário (usado no logout)."""
    from core.models import PushDevice

    return PushDevice.objects.filter(user=user, is_active=True).update(is_active=False)


def remove_device(*, user, token: str) -> bool:
    """Remove um token específico do usuário. Retorna True se encontrado."""
    from core.models import PushDevice

    deleted, _ = PushDevice.objects.filter(user=user, token=token).delete()
    return bool(deleted)
