"""
Operações de escrita e consultas para interações sociais (ADR-N2).
"""

from typing import Optional, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, F, OrderBy, OuterRef, Q, QuerySet
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext as _

from core.models import Block, Follow, Mute, UserProfile
from core.utils.visibility import (
    can_view_profile,
    get_profile_counters,
    get_relationship_status,
    is_user_blocked,
)

__all__ = [
    "follow_user",
    "unfollow_user",
    "block_user",
    "unblock_user",
    "mute_user",
    "unmute_user",
    "list_blocked_users",
    "list_muted_users",
    "add_to_close_friends",
    "remove_from_close_friends",
    "can_view_profile",
    "get_profile_counters",
    "get_relationship_status",
    "is_user_blocked",
    "update_user_privacy",
    "list_follow_requests",
    "accept_follow_request",
    "reject_follow_request",
    "suggest_users_to_follow",
]


def follow_user(*, follower, target_user) -> Tuple[Follow, bool]:
    """
    Seguir usuário.
    Se a conta do usuário for privada, status inicia como 'pending'.
    Raises ValueError se tentar seguir a si mesmo ou já estiver seguindo / pedido pendente.
    """
    if follower == target_user:
        raise ValueError("Não é possível seguir a si mesmo.")

    profile = getattr(target_user, "profile", None)
    is_private = getattr(profile, "is_private", False)
    status_initial = Follow.Status.PENDING if is_private else Follow.Status.ACTIVE

    follow, created = Follow.objects.get_or_create(
        follower=follower,
        followed=target_user,
        defaults={"status": status_initial},
    )
    if not created:
        if follow.status == Follow.Status.PENDING:
            raise ValueError("Pedido para seguir já enviado e pendente.")
        raise ValueError("Já está seguindo este usuário.")

    if status_initial == Follow.Status.ACTIVE:
        from core.services.notifications import notify_user_followed

        notify_user_followed(follower=follower, followed=target_user)

    return follow, created


def unfollow_user(*, follower, target_user) -> bool:
    """Deixar de seguir usuário."""
    deleted, _ = Follow.objects.filter(
        follower=follower,
        followed=target_user,
    ).delete()
    return bool(deleted)


@transaction.atomic
def block_user(*, blocker, target_user) -> Tuple[Block, bool]:
    """
    Bloquear usuário (ADR-N24 / Onda 4c).
    Numa transação atômica:
    1. Cria o bloqueio (idempotente).
    2. Remove seguimentos nos dois sentidos (ativos e pendentes).
    3. Remove marcas de círculo de amigos dos dois lados.
    4. Oculta retroativamente comentários antigos do bloqueado nos posts do bloqueador
       (mecanismo 'ocultar', motivo 'block').
    5. Preserva curtidas, favoritos e notificações históricas (filtrados apenas na leitura).
    Raises ValueError se tentar bloquear a si mesmo.
    """
    if blocker == target_user:
        raise ValueError(_("Não é possível bloquear a si mesmo."))

    block, created = Block.objects.get_or_create(
        blocker=blocker,
        blocked=target_user,
    )

    # Remove relacionamentos de follow e pedidos em ambas as direções
    Follow.objects.filter(
        Q(follower=blocker, followed=target_user) | Q(follower=target_user, followed=blocker)
    ).delete()

    if created:
        # Oculta comentários do bloqueado nas publicações de quem bloqueou
        from comments.models import Comment
        from core.services.posts import (
            decrement_post_comments_count,
            increment_post_hidden_comments_count,
        )

        comments_to_hide = list(
            Comment.objects.filter(
                post__author=blocker,
                author=target_user,
                is_hidden=False,
            ).select_related("post")
        )

        now = timezone.now()
        for c in comments_to_hide:
            c.is_hidden = True
            c.hidden_reason = "block"
            c.hidden_at = now
            c.hidden_by = blocker
            c.save(update_fields=["is_hidden", "hidden_reason", "hidden_at", "hidden_by"])
            decrement_post_comments_count(c.post_id)
            increment_post_hidden_comments_count(c.post_id)

    return block, created


@transaction.atomic
def unblock_user(*, blocker, target_user) -> bool:
    """
    Desbloquear usuário (ADR-N24 / Onda 4c).
    Reversível: restaura visibilidade e reexibe comentários ocultados por bloqueio.
    Não restaura seguidores nem círculo de amigos.
    Idempotente.
    """
    deleted_count, _ = Block.objects.filter(
        blocker=blocker,
        blocked=target_user,
    ).delete()

    if deleted_count > 0:
        from comments.models import Comment
        from core.services.posts import (
            decrement_post_hidden_comments_count,
            increment_post_comments_count,
        )

        comments_to_unhide = list(
            Comment.objects.filter(
                post__author=blocker,
                author=target_user,
                is_hidden=True,
                hidden_reason="block",
            ).select_related("post")
        )

        for c in comments_to_unhide:
            c.is_hidden = False
            c.hidden_reason = "owner"
            c.hidden_at = None
            c.hidden_by = None
            c.save(update_fields=["is_hidden", "hidden_reason", "hidden_at", "hidden_by"])
            increment_post_comments_count(c.post_id)
            decrement_post_hidden_comments_count(c.post_id)

    return bool(deleted_count)


def mute_user(*, muter, target_user) -> Tuple[Mute, bool]:
    """Silenciar usuário (ADR-N24). Idempotente."""
    if muter == target_user:
        raise ValueError(_("Não é possível silenciar a si mesmo."))
    mute, created = Mute.objects.get_or_create(
        muter=muter,
        muted=target_user,
    )
    return mute, created


def unmute_user(*, muter, target_user) -> bool:
    """Remover silenciamento (ADR-N24). Idempotente."""
    deleted, _ = Mute.objects.filter(
        muter=muter,
        muted=target_user,
    ).delete()
    return bool(deleted)


def list_blocked_users(*, user) -> QuerySet:
    """Lista contas bloqueadas pelo usuário solicitante (ADR-N24)."""
    return (
        Block.objects.filter(blocker=user)
        .select_related("blocked", "blocked__profile")
        .order_by("-created_at")
    )


def list_muted_users(*, user) -> QuerySet:
    """Lista contas silenciadas pelo usuário solicitante (ADR-N24)."""
    return (
        Mute.objects.filter(muter=user)
        .select_related("muted", "muted__profile")
        .order_by("-created_at")
    )


def add_to_close_friends(*, user, target_user) -> bool:
    """
    Adiciona target_user ao círculo de amigos de user.
    Requires: target_user segue user com status=active (seguidor ativo do dono, estilo Lumem).
    Raises Http404 se não for seguidor ativo ou se houver bloqueio.
    Returns True se adicionado, False se já estava no círculo.
    """
    if is_user_blocked(user, target_user):
        raise Http404("Usuário inacessível ou bloqueado.")

    follow = Follow.objects.filter(
        follower=target_user,
        followed=user,
        status=Follow.Status.ACTIVE,
    ).first()

    # Compatibilidade: se user segue target_user de forma ativa
    if not follow:
        follow = Follow.objects.filter(
            follower=user,
            followed=target_user,
            status=Follow.Status.ACTIVE,
        ).first()

    if not follow:
        raise Http404("Apenas seguidores ativos podem ser adicionados ao círculo.")

    if follow.is_close_friend:
        return False
    follow.is_close_friend = True
    follow.save(update_fields=["is_close_friend"])
    return True


def remove_from_close_friends(*, user, target_user) -> bool:
    """
    Remove target_user do círculo de amigos de user.
    Returns True se removido, False se não estava no círculo.
    """
    updated = Follow.objects.filter(
        (Q(follower=target_user, followed=user) | Q(follower=user, followed=target_user)),
        is_close_friend=True,
    ).update(is_close_friend=False)
    return bool(updated)


@transaction.atomic
def update_user_privacy(*, user, is_private: bool) -> UserProfile:
    """
    Atualiza a privacidade da conta do usuário (Onda 5).
    - Privada para pública: solicitações status='pending' NÃO são aprovadas automaticamente.
      Elas devem ser deletadas (Follow.objects.filter(followed=user, status=PENDING).delete()),
      obrigando quem tinha pedido pendente a clicar em 'Seguir' novamente.
    - Pública para privada: seguidores ativos continuam ativos; novos solicitantes viram pending.
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.is_private == is_private:
        return profile

    if not is_private:
        Follow.objects.filter(
            followed=user,
            status=Follow.Status.PENDING,
        ).delete()

    profile.is_private = is_private
    profile.save(update_fields=["is_private"])

    if hasattr(user, "__dict__") and "profile" in user.__dict__:
        del user.__dict__["profile"]

    return profile


def list_follow_requests(*, user, cursor: Optional[int] = None, limit: int = 20) -> QuerySet:
    """
    Lista pedidos de seguir pendentes direcionados ao usuário.
    Exclui usuários bloqueados em qualquer direção.
    Keyset pagination por id decrescente.
    """
    blocked_subquery = Block.objects.filter(
        Q(blocker=user, blocked=OuterRef("follower"))
        | Q(blocker=OuterRef("follower"), blocked=user)
    )
    qs = (
        Follow.objects.filter(
            followed=user,
            status=Follow.Status.PENDING,
            follower__is_active=True,
        )
        .exclude(Exists(blocked_subquery))
        .select_related("follower", "follower__profile")
        .order_by("-id")
    )
    if cursor is not None:
        try:
            cursor_id = int(cursor)
        except (ValueError, TypeError):
            raise ValueError("Cursor inválido.")
        qs = qs.filter(id__lt=cursor_id)

    return qs[:limit]


@transaction.atomic
def accept_follow_request(*, user, follower_username: str) -> Follow:
    """
    Aceita pedido de seguir pendente direcionado a user.
    - 404 se não houver pedido pendente ou se houver bloqueio.
    - Idempotente.
    - Notifica o solicitante (follower) pelo motor de notificações.
    """
    follow = (
        Follow.objects.select_for_update()
        .filter(
            followed=user,
            follower__username__iexact=follower_username,
            status=Follow.Status.PENDING,
        )
        .first()
    )
    if not follow:
        raise Http404("Solicitação de seguir pendente não encontrada.")

    if is_user_blocked(user, follow.follower):
        raise Http404("Solicitação de seguir pendente não encontrada.")

    follow.status = Follow.Status.ACTIVE
    follow.save(update_fields=["status"])

    from core.services.notifications import notify_follow_request_accepted

    notify_follow_request_accepted(follower=follow.follower, followed=user)
    return follow


@transaction.atomic
def reject_follow_request(*, user, follower_username: str) -> bool:
    """
    Recusa pedido de seguir pendente direcionado a user.
    - 404 se não houver pedido pendente.
    - Idempotente.
    - Remove em silêncio (sem notificação).
    """
    follow = Follow.objects.filter(
        followed=user,
        follower__username__iexact=follower_username,
        status=Follow.Status.PENDING,
    ).first()
    if not follow:
        raise Http404("Solicitação de seguir pendente não encontrada.")

    deleted, _ = follow.delete()
    return bool(deleted)


def suggest_users_to_follow(viewer, limit: int = 5) -> list[dict]:
    """
    Sugere contas para o viewer seguir de forma transparente e não-predatória (Onda 7b).

    Prioridade:
    1. Conexões reais de 2º grau (pessoas seguidas por quem o viewer segue ativamente).
    2. Contas públicas ativas recentes da comunidade.

    Exclusões obrigatórias (ADR-N21 / ADR-N24):
    - O próprio viewer;
    - Contas já seguidas ou com pedido PENDING;
    - Bloqueios e silenciamentos em ambas as direções;
    - Contas inativas/suspensas.
    """
    if viewer is None or getattr(viewer, "is_anonymous", True):
        return []

    clamped_limit = max(1, min(limit, 20))
    User = get_user_model()

    already_following_ids = Follow.objects.filter(follower=viewer).values("followed_id")
    blocked_out_ids = Block.objects.filter(blocker=viewer).values("blocked_id")
    blocked_in_ids = Block.objects.filter(blocked=viewer).values("blocker_id")
    muted_out_ids = Mute.objects.filter(muter=viewer).values("muted_id")
    muted_in_ids = Mute.objects.filter(muted=viewer).values("muter_id")

    candidates_base = (
        User.objects.filter(is_active=True, status=User.Status.ACTIVE)
        .exclude(pk=viewer.pk)
        .exclude(pk__in=already_following_ids)
        .exclude(pk__in=blocked_out_ids)
        .exclude(pk__in=blocked_in_ids)
        .exclude(pk__in=muted_out_ids)
        .exclude(pk__in=muted_in_ids)
        .select_related("profile")
    )

    results: list[dict] = []
    selected_ids = []

    # 1. Rede de 2º grau (seguidores em comum via conexões ativas)
    active_connector_ids = list(
        Follow.objects.filter(
            follower=viewer,
            status=Follow.Status.ACTIVE,
            followed__is_active=True,
            followed__status=User.Status.ACTIVE,
        )
        .exclude(followed_id__in=blocked_out_ids)
        .exclude(followed_id__in=blocked_in_ids)
        .exclude(followed_id__in=muted_out_ids)
        .exclude(followed_id__in=muted_in_ids)
        .values_list("followed_id", flat=True)
    )

    if active_connector_ids:
        mutual_users = list(
            candidates_base.filter(
                followers__follower_id__in=active_connector_ids,
                followers__status=Follow.Status.ACTIVE,
            )
            .annotate(mutual_count=Count("followers__follower_id", distinct=True))
            .order_by("-mutual_count", "-date_joined")[:clamped_limit]
        )

        if mutual_users:
            mutual_user_ids = [u.id for u in mutual_users]
            sample_follows = (
                Follow.objects.filter(
                    follower_id__in=active_connector_ids,
                    followed_id__in=mutual_user_ids,
                    status=Follow.Status.ACTIVE,
                )
                .select_related("follower")
                .order_by("follower__username")
            )
            sample_map = {}
            for f in sample_follows:
                sample_map.setdefault(f.followed_id, f.follower.username)

            for u in mutual_users:
                profile = getattr(u, "profile", None)
                is_private = getattr(profile, "is_private", False) if profile else False
                bio = "" if is_private else (getattr(profile, "bio", "") if profile else "")
                results.append(
                    {
                        "id": str(u.id),
                        "username": u.username,
                        "display_name": (getattr(profile, "display_name", "") if profile else ""),
                        "bio": bio,
                        "avatar": (profile.avatar.url if profile and profile.avatar else None),
                        "is_private": is_private,
                        "mutual_count": int(getattr(u, "mutual_count", 0) or 0),
                        "mutual_sample_username": sample_map.get(u.id),
                        "reason": "mutual",
                    }
                )
                selected_ids.append(u.id)

    # 2. Complementa até `limit` com contas públicas ativas recentes
    remaining = clamped_limit - len(results)
    if remaining > 0:
        public_qs = (
            candidates_base.exclude(pk__in=selected_ids)
            .exclude(profile__is_private=True)
            .order_by(OrderBy(F("last_login"), descending=True, nulls_last=True), "-date_joined")[
                :remaining
            ]
        )
        for u in public_qs:
            profile = getattr(u, "profile", None)
            results.append(
                {
                    "id": str(u.id),
                    "username": u.username,
                    "display_name": (getattr(profile, "display_name", "") if profile else ""),
                    "bio": (getattr(profile, "bio", "") if profile else ""),
                    "avatar": (profile.avatar.url if profile and profile.avatar else None),
                    "is_private": False,
                    "mutual_count": 0,
                    "mutual_sample_username": None,
                    "reason": "active_community",
                }
            )

    return results
