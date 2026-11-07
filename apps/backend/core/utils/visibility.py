"""
Regras centralizadas de visibilidade, bloqueio bilateral e filtros sociais (ADR-N2 / ADR-N21).
Único ponto da aplicação onde Post.objects é consultado diretamente para leitura.
"""

from typing import Any, Dict, Optional

from django.db.models import Exists, OuterRef, Q, QuerySet

from core.models import Block, Follow, Mute, Post, UserProfile


def visible_posts_for(user) -> QuerySet:
    """
    Retorna posts visíveis para o usuário considerando:
    1. Bloqueio bilateral (exclui quem o user bloqueou e quem bloqueou o user)
    2. Status do autor (apenas ativos)
    3. Níveis de visibilidade:
       - PUBLIC: visível a todos se autor público, ou se privado apenas a seguidores ativos
       - FOLLOWERS: visível ao autor e a seguidores ativos
       - CIRCLE: visível ao autor e a amigos próximos ativos (is_close_friend=True)
       - Autor sempre vê suas próprias publicações
    """
    if user is None or getattr(user, "is_anonymous", True):
        # Visitante anônimo / não autenticado: login obrigatório em todo o produto
        return Post.objects.none()

    # Exclusão de bloqueios bilaterais
    blocked_by_user = Block.objects.filter(
        blocker=user,
        blocked=OuterRef("author"),
    )
    blocker_of_user = Block.objects.filter(
        blocker=OuterRef("author"),
        blocked=user,
    )

    qs = Post.objects.exclude(Exists(blocked_by_user)).exclude(Exists(blocker_of_user))
    qs = qs.filter(author__is_active=True, author__status="active")

    # IDs de autores que o usuário segue ativamente
    following_active_ids = Follow.objects.filter(
        follower=user,
        status=Follow.Status.ACTIVE,
    ).values("followed_id")

    # IDs de autores onde o usuário é amigo próximo ativo
    close_friends_active_ids = Follow.objects.filter(
        follower=user,
        status=Follow.Status.ACTIVE,
        is_close_friend=True,
    ).values("followed_id")

    # Condições de visibilidade
    is_self = Q(author=user)
    is_public_open = Q(visibility=Post.Visibility.PUBLIC) & ~Q(author__profile__is_private=True)
    is_public_private_follower = Q(
        visibility=Post.Visibility.PUBLIC,
        author__profile__is_private=True,
        author__in=following_active_ids,
    )
    is_followers = Q(
        visibility=Post.Visibility.FOLLOWERS,
        author__in=following_active_ids,
    )
    is_circle = Q(
        visibility=Post.Visibility.CIRCLE,
        author__in=close_friends_active_ids,
    )

    qs = qs.filter(is_self | is_public_open | is_public_private_follower | is_followers | is_circle)

    return qs.select_related("author", "author__profile")


def can_view_post(viewer, post: Optional[Post]) -> bool:
    """
    Retorna True se o viewer possui permissão para ver a publicação informada.
    Nunca levanta exceção.
    """
    if not post or not getattr(post, "pk", None):
        return False
    return visible_posts_for(viewer).filter(pk=post.pk).exists()


def is_user_blocked(user_a, user_b) -> bool:
    """Retorna True se houver bloqueio bilateral entre user_a e user_b."""
    if not user_a or not user_b:
        return False
    if getattr(user_a, "is_anonymous", False) or getattr(user_b, "is_anonymous", False):
        return False
    return Block.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
    ).exists()


def can_view_profile(viewer, target_user) -> bool:
    """
    Retorna True se o viewer tem permissão para visualizar o perfil COMPLETO do target_user
    (bio, contadores e posts).
    Se False (bloqueio bilateral ou conta privada sem seguimento ativo), retorna False.
    """
    if not target_user or not getattr(target_user, "is_valid_for_auth", True):
        return False

    if viewer and getattr(viewer, "is_authenticated", False) and viewer == target_user:
        return True

    # Checa bloqueio bilateral
    if is_user_blocked(viewer, target_user):
        return False

    # Checa conta privada
    try:
        profile = target_user.profile
    except Exception:
        profile = None
    is_private = False
    if profile is not None:
        # Busca is_private diretamente do DB para evitar cache stale
        is_private = UserProfile.objects.filter(user=target_user, is_private=True).exists()
    if is_private:
        if not viewer or not getattr(viewer, "is_authenticated", False):
            return False
        return Follow.objects.filter(
            follower=viewer,
            followed=target_user,
            status=Follow.Status.ACTIVE,
        ).exists()

    return True


def get_profile_counters(*, target_user, viewer=None) -> Dict[str, int]:
    """
    Retorna os contadores públicos de um perfil de usuário.
    Se o viewer for bloqueado ou não tiver acesso ao perfil privado, zera os contadores.
    """
    if viewer is not None and not can_view_profile(viewer, target_user):
        return {
            "posts_count": 0,
            "followers_count": 0,
            "following_count": 0,
        }

    # Posts públicos acessíveis
    posts_count = Post.objects.filter(
        author=target_user,
        visibility=Post.Visibility.PUBLIC,
    ).count()
    followers_count = Follow.objects.filter(
        followed=target_user,
        status=Follow.Status.ACTIVE,
    ).count()
    following_count = Follow.objects.filter(
        follower=target_user,
        status=Follow.Status.ACTIVE,
    ).count()
    return {
        "posts_count": posts_count,
        "followers_count": followers_count,
        "following_count": following_count,
    }


def get_relationship_status(*, source_user, target_user) -> Dict[str, Any]:
    """Retorna status de relacionamento entre dois usuários."""
    if not source_user or not getattr(source_user, "is_authenticated", False):
        return {
            "is_following": False,
            "is_close_friend": False,
            "follow_status": None,
            "is_blocked": False,
            "is_muting": False,
        }

    follow = Follow.objects.filter(follower=source_user, followed=target_user).first()
    is_blocked = Block.objects.filter(blocker=source_user, blocked=target_user).exists()
    is_muting = Mute.objects.filter(muter=source_user, muted=target_user).exists()
    return {
        "is_following": follow is not None and follow.status == Follow.Status.ACTIVE,
        "is_close_friend": follow.is_close_friend if follow else False,
        "follow_status": follow.status if follow else None,
        "is_blocked": is_blocked,
        "is_muting": is_muting,
    }
