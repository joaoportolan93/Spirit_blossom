"""
Testes adversariais nomeados e cobertura de casos de borda de visibilidade,
notificações, autenticação e rotas anônimas (ADR-N21 / ADR-N22).
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.urls import get_resolver
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.authentication import CookieJWTAuthentication
from accounts.models import UserProfile
from notifications.models import Notification
from notifications.services import notify_post_liked, notify_user_followed
from posts.models import PostBookmark
from posts.selectors import list_bookmarked_posts, search_posts
from social.models import Block, Follow, Mute
from social.selectors import (
    can_view_post,
    can_view_profile,
    get_profile_counters,
    get_relationship_status,
    visible_posts_for,
)

from .factories import BlockFactory, PostFactory, UserFactory

User = get_user_model()


def _client_for(user):
    """APIClient autenticado via cookie JWT."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


def _make_private(user):
    """Marca conta como privada e invalida cache do descriptor."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.is_private = True
    profile.save(update_fields=["is_private"])
    if hasattr(user, "__dict__") and "profile" in user.__dict__:
        del user.__dict__["profile"]


# ===========================================================================
# 1. Testes Adversariais Nomeados (Tentativas Ativas de Burlar a Privacidade)
# ===========================================================================


@pytest.mark.django_db
class TestNamedAdversarialSecurity:
    """
    Testes adversariais: simulam invasores tentando contornar regras de isolamento
    através de ID direto, cursor keyset, contadores, busca, notificações e favoritos.
    """

    def test_adversarial_direct_id_access_private_and_circle_post(self):
        """
        Adversarial ID: invasor tenta acessar GET /api/posts/<id>/ diretamente
        de post de conta privada e post de círculo.
        Resultado: 404 estrito em todos (nunca 403, para não vazar existência).
        """
        author = UserFactory()
        _make_private(author)
        attacker = UserFactory()

        private_post = PostFactory(author=author, visibility="public")
        circle_post = PostFactory(author=author, visibility="circle")

        client = _client_for(attacker)

        # Post de conta privada para não seguidor
        resp1 = client.get(f"/api/posts/{private_post.pk}/")
        assert resp1.status_code == status.HTTP_404_NOT_FOUND
        assert resp1.json()["detail"] == "Não encontrado."

        # Post de círculo para seguidor comum (fora do círculo)
        Follow.objects.create(
            follower=attacker, followed=author, status="active", is_close_friend=False
        )
        resp2 = client.get(f"/api/posts/{circle_post.pk}/")
        assert resp2.status_code == status.HTTP_404_NOT_FOUND

    def test_adversarial_cursor_pagination_does_not_leak_hidden_posts(self):
        """
        Adversarial Keyset Cursor: invasor usa cursor de paginação apontando para
        o UUID de um post inacessível para tentar forçar sua inclusão no feed.
        Resultado: O cursor filtra sobre visible_posts_for; o post oculto nunca aparece.
        """
        author = UserFactory()
        attacker = UserFactory()
        BlockFactory(blocker=author, blocked=attacker)

        hidden_post = PostFactory(author=author, visibility="public")
        accessible_post = PostFactory(author=attacker, visibility="public")

        client = _client_for(attacker)

        # Passa o UUID do post bloqueado como cursor
        resp = client.get(f"/api/posts/?cursor={hidden_post.pk}")
        assert resp.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in resp.json()]
        assert str(hidden_post.pk) not in ids

    def test_adversarial_counters_cannot_infer_private_activity(self):
        """
        Adversarial Counters: invasor tenta inferir volume de atividade ou rede
        de uma conta privada ou de quem o bloqueou.
        Resultado: Contadores são estritamente zerados (posts=0, followers=0, following=0).
        """
        author = UserFactory()
        _make_private(author)
        PostFactory.create_batch(5, author=author, visibility="public")
        attacker = UserFactory()

        client = _client_for(attacker)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["posts_count"] == 0
        assert data["followers_count"] == 0
        assert data["following_count"] == 0
        assert data["posts"] == []

    def test_adversarial_search_cannot_leak_circle_or_private_posts(self):
        """
        Adversarial Search: invasor usa busca por palavras-chave com termos comuns
        para tentar recuperar posts restritos ou de usuários bloqueados.
        Resultado: search_posts aplica visible_posts_for(user), isolando 100% dos resultados.
        """
        author = UserFactory()
        _make_private(author)
        attacker = UserFactory()

        # Post com termo específico em conta privada
        PostFactory(
            author=author, content_text="segredo confidencial absoluto", visibility="public"
        )

        # Chama seletor central com o usuário atacante
        qs = search_posts(query="confidencial", user=attacker)
        assert qs.count() == 0

    def test_adversarial_notification_cannot_leak_to_inaccessible_user(self):
        """
        Adversarial Notifications: tentativa de disparar notificação de curtida
        ou seguir em relacionamentos bloqueados ou posts inacessíveis.
        Resultado: Notificações são atipicamente suprimidas antes de persistir.
        """
        author = UserFactory()
        target = UserFactory()
        BlockFactory(blocker=target, blocked=author)

        post = PostFactory(author=target, visibility="public")

        # Tentativa de notificar curtida sob bloqueio
        notify_post_liked(sender=author, post=post)
        assert Notification.objects.filter(recipient=target, sender=author).count() == 0

        # Tentativa de notificar follow sob bloqueio
        notify_user_followed(follower=author, followed=target)
        assert Notification.objects.filter(recipient=target, sender=author).count() == 0

    def test_adversarial_bookmarks_cannot_retrieve_hidden_or_blocked_posts(self):
        """
        Adversarial Bookmarks: usuário salva post legítimo. Posteriormente, o autor
        priva a conta ou bloqueia o usuário. O invasor tenta ler os favoritos.
        Resultado: O post salvo desaparece dinamicamente de GET /api/posts/bookmarks/.
        """
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")

        # Salva o post
        PostBookmark.objects.create(user=viewer, post=post)
        client = _client_for(viewer)

        # Vê inicialmente
        resp1 = client.get("/api/posts/bookmarks/")
        assert resp1.status_code == status.HTTP_200_OK
        assert str(post.pk) in [p["id"] for p in resp1.json()]

        # Autor bloqueia o viewer
        BlockFactory(blocker=author, blocked=viewer)

        # Post salvo não pode mais aparecer
        resp2 = client.get("/api/posts/bookmarks/")
        assert resp2.status_code == status.HTTP_200_OK
        assert str(post.pk) not in [p["id"] for p in resp2.json()]


# ===========================================================================
# 2. Teste Exaustivo: Todas as rotas de urlpatterns exigem 401 para Anônimo
# ===========================================================================


@pytest.mark.django_db
class TestAllRoutesRequireAuthenticationForAnonymous:
    """
    Percorre programaticamente todas as rotas da aplicação Django sob /api/
    e garante que qualquer acesso anônimo recebe 401 Unauthorized, exceto a lista pública.
    """

    PUBLIC_ROUTES = {
        "/api/auth/csrf/",
        "/api/auth/login/",
        "/api/auth/register/",
        "/api/auth/refresh/",
        "/api/auth/logout/",
        "/api/auth/password-reset/request/",
        "/api/auth/password-reset/confirm/",
        "/api/auth/google/",
        "/api/auth/google/complete/",
        "/api/health/",
    }

    def _extract_routes(self, patterns, prefix=""):
        routes = []
        for p in patterns:
            if hasattr(p, "url_patterns"):
                routes.extend(self._extract_routes(p.url_patterns, prefix + str(p.pattern)))
            else:
                pattern_str = prefix + str(p.pattern)
                if pattern_str.startswith("api/"):
                    routes.append("/" + pattern_str)
        return routes

    def test_todos_endpoints_protegidos_negam_anonimo_com_401(self):
        resolver = get_resolver()
        all_routes = self._extract_routes(resolver.url_patterns)
        client = APIClient()

        dummy_uuid = "00000000-0000-0000-0000-000000000001"
        dummy_username = "testuser"
        dummy_id = "1"

        tested_count = 0
        for route in all_routes:
            if route in self.PUBLIC_ROUTES:
                continue

            # Substitui parâmetros de rota por valores dummy
            resolved_url = (
                route.replace("<uuid:pk>", dummy_uuid)
                .replace("<int:pk>", dummy_id)
                .replace("<str:username>", dummy_username)
                .replace("<id>", dummy_id)
            )

            # Executa requisição anônima GET e POST
            resp_get = client.get(resolved_url)
            assert resp_get.status_code == status.HTTP_401_UNAUTHORIZED, (
                f"Endpoint {resolved_url} (GET) permitiu anônimo ou retornou {resp_get.status_code}"
            )
            resp_post = client.post(resolved_url, {})
            assert resp_post.status_code == status.HTTP_401_UNAUTHORIZED, (
                f"Endpoint {resolved_url} (POST) permitiu anônimo ou retornou {resp_post.status_code}"
            )
            tested_count += 1

        assert tested_count >= 15, "Deve haver pelo menos 15 endpoints privados testados"


# ===========================================================================
# 3. Testes de Cobertura para Linhas Específicas
# ===========================================================================


@pytest.mark.django_db
class TestCoverageMissingLines:
    """
    Cobre linhas não executadas anteriormente:
    - social/selectors.py: 27, 111, 126-127, 137, 153, 182
    - notifications/services.py: 47, 54, 57, 91, 99
    - accounts/authentication.py: 59-60, 77-78, 81
    """

    def test_visible_posts_for_none_and_anonymous_returns_empty_queryset(self):
        """visible_posts_for(None) e AnonymousUser retornam queryset vazio (login obrigatório)."""
        author_public = UserFactory()
        PostFactory(author=author_public, visibility="public")

        qs_none = visible_posts_for(None)
        assert qs_none.count() == 0
        assert list(qs_none) == []

        qs_anon = visible_posts_for(AnonymousUser())
        assert qs_anon.count() == 0
        assert list(qs_anon) == []

    def test_can_view_post_edge_cases(self):
        """Cobre social/selectors.py:97 — post nulo ou sem pk."""
        viewer = UserFactory()
        assert can_view_post(viewer, None) is False
        assert can_view_post(viewer, object()) is False

    def test_can_view_profile_target_invalid_or_none(self):
        """Cobre social/selectors.py:111, 122 — target inválido ou viewer é o próprio autor."""
        viewer = UserFactory()
        assert can_view_profile(viewer, None) is False
        assert can_view_profile(viewer, viewer) is True

        target = UserFactory()
        target.is_active = False
        target.save()
        assert can_view_profile(viewer, target) is False

    def test_can_view_profile_when_user_has_no_profile(self):
        """Cobre social/selectors.py:131-132 — target sem perfil dispara RelatedObjectDoesNotExist."""
        viewer = UserFactory()
        target = UserFactory()
        UserProfile.objects.filter(user=target).delete()
        target.refresh_from_db()
        # Sem perfil = exceção capturada em lines 131-132, profile=None -> conta pública
        assert can_view_profile(viewer, target) is True

    def test_can_view_profile_anonymous_viewer_on_private_account(self):
        """Cobre social/selectors.py:137 — anônimo tentando ver perfil privado."""
        target = UserFactory()
        _make_private(target)
        assert can_view_profile(None, target) is False
        assert can_view_profile(AnonymousUser(), target) is False

    def test_get_profile_counters_when_cannot_view_profile(self):
        """Cobre social/selectors.py:153 — contadores zerados para viewer sem acesso."""
        author = UserFactory()
        viewer = UserFactory()
        BlockFactory(blocker=author, blocked=viewer)
        counters = get_profile_counters(target_user=author, viewer=viewer)
        assert counters == {"posts_count": 0, "followers_count": 0, "following_count": 0}

    def test_get_relationship_status_anonymous_source(self):
        """Cobre social/selectors.py:182 — source_user None ou anônimo."""
        target = UserFactory()
        status_none = get_relationship_status(source_user=None, target_user=target)
        assert status_none["is_following"] is False
        assert status_none["follow_status"] is None

        status_anon = get_relationship_status(source_user=AnonymousUser(), target_user=target)
        assert status_anon["is_following"] is False

    @pytest.mark.django_db(transaction=True)
    def test_notify_user_followed_suppressions(self):
        """Cobre notifications/services.py:47, 54, 57 — auto-follow, bloqueio e mute."""
        user = UserFactory()
        other = UserFactory()

        # 47: auto-follow
        with transaction.atomic():
            notify_user_followed(follower=user, followed=user)
        assert Notification.objects.count() == 0

        # 54: bloqueio bilateral
        BlockFactory(blocker=user, blocked=other)
        with transaction.atomic():
            notify_user_followed(follower=user, followed=other)
        assert Notification.objects.count() == 0
        Block.objects.all().delete()

        # 57: silenciado
        Mute.objects.create(muter=other, muted=user)
        with transaction.atomic():
            notify_user_followed(follower=user, followed=other)
        assert Notification.objects.count() == 0

    @pytest.mark.django_db(transaction=True)
    def test_notify_post_liked_suppressions(self):
        """Cobre notifications/services.py:91, 99 — like sob bloqueio ou post inacessível."""
        author = UserFactory()
        liker = UserFactory()
        post = PostFactory(author=author, visibility="circle")

        # 91: bloqueio bilateral
        BlockFactory(blocker=author, blocked=liker)
        with transaction.atomic():
            notify_post_liked(sender=liker, post=post)
        assert Notification.objects.count() == 0
        Block.objects.all().delete()

        # 99: liker não pode ver post de círculo
        with transaction.atomic():
            notify_post_liked(sender=liker, post=post)
        assert Notification.objects.count() == 0

    def test_custom_jwt_authentication_edge_cases(self):
        """Cobre accounts/authentication.py: 59-60, 77-78, 81."""
        factory = APIRequestFactory()
        auth = CookieJWTAuthentication()

        # 59-60: Token malformado / inválido
        req_invalid = factory.get("/api/feed/")
        req_invalid.COOKIES["access_token"] = "token.invalido.malformado"
        with pytest.raises(Exception):
            auth.authenticate(req_invalid)

        # 77-78: Token válido para usuário que foi deletado do banco
        user = UserFactory()
        token = AccessToken.for_user(user)
        user.delete()
        req_deleted = factory.get("/api/feed/")
        req_deleted.COOKIES["access_token"] = str(token)
        with pytest.raises(Exception) as exc_info:
            auth.authenticate(req_deleted)
        assert "Usuário não encontrado" in str(exc_info.value)

        # 81: Conta inativa ou suspensa
        user_inactive = UserFactory()
        token_inactive = AccessToken.for_user(user_inactive)
        user_inactive.is_active = False
        user_inactive.save()
        req_inactive = factory.get("/api/feed/")
        req_inactive.COOKIES["access_token"] = str(token_inactive)
        with pytest.raises(Exception) as exc_inactive:
            auth.authenticate(req_inactive)
        assert "Conta inativa ou suspensa" in str(exc_inactive.value)


# ===========================================================================
# 4. Testes de Cursor de Favoritos (Item 10) e Obrigatório em Search (Item 8)
# ===========================================================================


@pytest.mark.django_db
class TestBookmarksCursorAndSearchUser:
    """Testa cursor inválido/válido em favoritos e obrigatoriedade de user em search_posts."""

    def test_bookmarked_posts_invalid_cursor_returns_400(self):
        """Cursor malformado em favoritos retorna 400 Bad Request."""
        user = UserFactory()
        client = _client_for(user)
        resp = client.get("/api/posts/bookmarks/?cursor=cursor-invalido-nao-uuid")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cursor inválido" in resp.json()["detail"]

    def test_bookmarked_posts_valid_cursor_pagination(self):
        """Keyset pagination correta em favoritos usando UUID do post."""
        user = UserFactory()
        p1 = PostFactory(author=user, visibility="public")
        p2 = PostFactory(author=user, visibility="public")
        p3 = PostFactory(author=user, visibility="public")

        PostBookmark.objects.create(user=user, post=p1)
        PostBookmark.objects.create(user=user, post=p2)
        PostBookmark.objects.create(user=user, post=p3)

        client = _client_for(user)

        # Primeira página com limit 2
        qs1 = list_bookmarked_posts(user=user, limit=2)
        assert len(qs1) == 2
        last_id = str(qs1[1].pk)

        # Segunda página passando o cursor do último item
        resp = client.get(f"/api/posts/bookmarks/?cursor={last_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(p1.pk)

    def test_search_posts_requires_user_argument(self):
        """search_posts falha com TypeError se user não for informado."""
        with pytest.raises(TypeError):
            search_posts(query="teste")  # falta user obrigatório
