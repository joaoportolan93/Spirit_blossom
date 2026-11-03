"""
Testes de visibilidade de posts e bloqueio bidirecional.

Grupos:
  - Visibilidade público vs followers-only (6)
  - Bloqueio bidirecional no feed (6)
  - Bloqueio bidirecional na busca (2)
  - Bloqueio bidirecional no perfil de posts (2)
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .factories import BlockFactory, FollowFactory, PostFactory, UserFactory


def _client_for(user):
    """Cria APIClient autenticado via cookie para um usuário."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


def _csrf_token(client):
    r = client.get("/api/auth/csrf/")
    cookie = client.cookies.get("csrftoken")
    return cookie.value if cookie else ""


# ---------------------------------------------------------------------------
# Visibilidade público vs followers-only
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVisibility:
    def test_post_publico_visivel_para_qualquer_autenticado(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        response = client.get("/api/posts/")
        assert response.status_code == status.HTTP_200_OK
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) in ids

    def test_post_followers_only_visivel_para_seguidor(self):
        author = UserFactory()
        follower = UserFactory()
        FollowFactory(follower=follower, followed=author)
        post = PostFactory(author=author, visibility="followers")
        client = _client_for(follower)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) in ids

    def test_post_followers_only_invisivel_para_nao_seguidor(self):
        author = UserFactory()
        stranger = UserFactory()
        post = PostFactory(author=author, visibility="followers")
        client = _client_for(stranger)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) not in ids

    def test_post_proprio_sempre_visivel(self):
        """Autor sempre vê seus próprios posts mesmo followers-only."""
        user = UserFactory()
        post = PostFactory(author=user, visibility="followers")
        client = _client_for(user)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) in ids

    def test_post_publico_visivel_para_proprio_autor(self):
        user = UserFactory()
        post = PostFactory(author=user, visibility="public")
        client = _client_for(user)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) in ids

    def test_multiple_posts_visibilidade_mista(self):
        """Retorna públicos e followers-only do seguido, mas não do não-seguido."""
        author = UserFactory()
        follower = UserFactory()
        stranger = UserFactory()
        FollowFactory(follower=follower, followed=author)
        pub = PostFactory(author=author, visibility="public")
        priv = PostFactory(author=author, visibility="followers")
        # Seguidor vê ambos
        c_follower = _client_for(follower)
        ids = [str(p["id"]) for p in c_follower.get("/api/posts/").json()]
        assert str(pub.pk) in ids
        assert str(priv.pk) in ids
        # Estranho vê só o público
        c_stranger = _client_for(stranger)
        ids2 = [str(p["id"]) for p in c_stranger.get("/api/posts/").json()]
        assert str(pub.pk) in ids2
        assert str(priv.pk) not in ids2


# ---------------------------------------------------------------------------
# Bloqueio bidirecional no feed
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBidirectionalBlock:
    def test_bloqueado_nao_aparece_no_feed_do_bloqueador(self):
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        post = PostFactory(author=blocked, visibility="public")
        client = _client_for(blocker)
        ids = [str(p["id"]) for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_bloqueador_nao_aparece_no_feed_do_bloqueado(self):
        """Quem foi bloqueado também não vê os posts de quem bloqueou."""
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        post = PostFactory(author=blocker, visibility="public")
        client = _client_for(blocked)
        ids = [str(p["id"]) for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_sem_bloqueio_posts_aparecem_normalmente(self):
        a = UserFactory()
        b = UserFactory()
        post = PostFactory(author=a, visibility="public")
        client = _client_for(b)
        ids = [str(p["id"]) for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids

    def test_bloquear_remove_follow_bidirecional(self):
        """Ao bloquear, o follow nas duas direções é removido."""
        from social.models import Follow

        blocker = UserFactory()
        target = UserFactory()
        FollowFactory(follower=blocker, followed=target)
        FollowFactory(follower=target, followed=blocker)
        assert Follow.objects.filter(follower=blocker, followed=target).exists()
        # Faz o bloqueio via API
        client = APIClient(enforce_csrf_checks=True)
        refresh = RefreshToken.for_user(blocker)
        client.cookies["access_token"] = str(refresh.access_token)
        csrf = _csrf_token(client)
        client.post(
            f"/api/social/block/{target.username}/",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert not Follow.objects.filter(follower=blocker, followed=target).exists()
        assert not Follow.objects.filter(follower=target, followed=blocker).exists()

    def test_desbloquear_restaura_visibilidade_no_feed(self):
        """Ao desbloquear, os posts do usuário voltam a aparecer no feed."""
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        post = PostFactory(author=blocked, visibility="public")
        client = _client_for(blocker)
        ids_before = [str(p["id"]) for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids_before

        response = client.delete(f"/api/social/block/{blocked.username}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        ids_after = [str(p["id"]) for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids_after

    def test_bloqueio_mutuo_ambos_ocultos_no_feed(self):
        """Bloqueio mútuo: nenhum dos dois usuários vê posts do outro no feed."""
        user_a = UserFactory()
        user_b = UserFactory()
        BlockFactory(blocker=user_a, blocked=user_b)
        BlockFactory(blocker=user_b, blocked=user_a)
        post_a = PostFactory(author=user_a, visibility="public")
        post_b = PostFactory(author=user_b, visibility="public")

        client_a = _client_for(user_a)
        client_b = _client_for(user_b)

        ids_a = [str(p["id"]) for p in client_a.get("/api/posts/").json()]
        ids_b = [str(p["id"]) for p in client_b.get("/api/posts/").json()]

        assert str(post_b.pk) not in ids_a
        assert str(post_a.pk) not in ids_b

    def test_post_detail_bloqueado_retorna_404(self):
        """Acesso direto ao post de usuário bloqueado → 404."""
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        post = PostFactory(author=blocked, visibility="public")
        client = _client_for(blocker)
        response = client.get(f"/api/posts/{post.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_post_detail_bloqueador_retorna_404(self):
        """Bloqueado tenta acessar diretamente post de quem o bloqueou → 404."""
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        post = PostFactory(author=blocker, visibility="public")
        client = _client_for(blocked)
        response = client.get(f"/api/posts/{post.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_busca_exclui_posts_de_bloqueados(self):
        """Busca full-text não retorna posts de usuários bloqueados."""
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        PostFactory(author=blocked, content_text="palavra-unica-xablau", visibility="public")
        client = _client_for(blocker)
        response = client.get("/api/posts/search/?q=palavra-unica-xablau")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

    def test_busca_exclui_posts_de_bloqueador(self):
        """Busca full-text não retorna posts de quem bloqueou o usuário."""
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        PostFactory(
            author=blocker, content_text="palavra-unica-xablau-bloqueador", visibility="public"
        )
        client = _client_for(blocked)
        response = client.get("/api/posts/search/?q=palavra-unica-xablau-bloqueador")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0
