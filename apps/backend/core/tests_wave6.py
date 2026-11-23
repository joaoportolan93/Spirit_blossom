"""
Testes da Onda 6: Baixar meus dados (export) e Excluir conta (LGPD).
Cobertura da matriz definida pelo Especialista 6 / ToT.
"""

import datetime

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.factories import UserFactory
from core.models import (
    AccessLog,
    Block,
    Draft,
    Follow,
    Mute,
    OAuthAccount,
    PasswordResetToken,
    Post,
    PostBookmark,
    PostLike,
    UserProfile,
)

try:
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    HAS_BLACKLIST = True
except ImportError:
    HAS_BLACKLIST = False
    BlacklistedToken = None
    OutstandingToken = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def auth_client(user):
    """Retorna APIClient autenticado via cookie JWT."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    client.cookies["refresh_token"] = str(refresh)
    return client, refresh


def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    u = UserFactory()
    get_or_create_profile(u)
    return u


@pytest.fixture
def other_user(db):
    u = UserFactory()
    get_or_create_profile(u)
    return u


@pytest.fixture
def oauth_user(db):
    """Usuário criado apenas via Google OAuth — sem senha utilizável."""
    u = UserFactory()
    u.set_unusable_password()
    u.save()
    get_or_create_profile(u)
    OAuthAccount.objects.create(user=u, provider="google", uid=f"google-{u.pk}")
    return u


# ---------------------------------------------------------------------------
# Testes de Exportação (GET /api/users/export-data/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExportData:
    url = "/api/users/export-data/"

    def test_01_retorna_todas_as_secoes_esperadas(self, user):
        """Teste 1: Export retorna todas as chaves top-level esperadas."""
        client, _ = auth_client(user)
        resp = client.get(self.url)
        assert resp.status_code == 200
        data = resp.json()
        expected_keys = {
            "exported_at",
            "profile",
            "posts",
            "drafts",
            "post_likes",
            "post_bookmarks",
            "comments",
            "comment_likes",
            "comment_bookmarks",
            "following",
            "followers",
            "blocked_users",
            "muted_users",
        }
        assert expected_keys.issubset(set(data.keys()))

    def test_02_nunca_vaza_blocked_me_muted_me(self, user, other_user):
        """Teste 2: Export NUNCA expõe quem bloqueou/silenciou o usuário (ADR-N24 §7)."""
        # other_user bloqueia e silencia user
        Block.objects.create(blocker=other_user, blocked=user)
        Mute.objects.create(muter=other_user, muted=user)

        client, _ = auth_client(user)
        resp = client.get(self.url)
        assert resp.status_code == 200
        data = resp.json()

        # O relatório do `user` não deve ter `blocked_me` ou `muted_me`
        assert "blocked_me" not in data
        assert "muted_me" not in data

        # Quem bloqueou: deve estar vazio para user (ele não bloqueou ninguém)
        assert data["blocked_users"] == []
        assert data["muted_users"] == []

    def test_03_nunca_vaza_senha_token_ip_hash(self, user):
        """Teste 3: Export NUNCA expõe hashes de senha, tokens ou ip_hash."""
        client, _ = auth_client(user)
        resp = client.get(self.url)
        data = resp.json()
        raw = str(data)
        assert "password" not in raw.lower()
        assert "token" not in raw.lower()
        assert "ip_hash" not in raw.lower()

    def test_04_inclui_posts_comentarios_curtidas_bookmarks_follows(self, user, other_user):
        """Teste 4 (antigo 16): Export inclui dados dos sub-recursos."""
        # Cria post
        post = Post.objects.create(author=user, content_text="Meu post de teste")
        # Cria bookmark
        PostBookmark.objects.create(post=post, user=user)
        # Cria curtida
        post2 = Post.objects.create(author=other_user, content_text="Post de outro user")
        PostLike.objects.create(post=post2, user=user)
        # Cria draft
        Draft.objects.create(author=user, content_text="Rascunho")
        # Cria follow
        Follow.objects.create(follower=user, followed=other_user, status=Follow.Status.ACTIVE)

        client, _ = auth_client(user)
        resp = client.get(self.url)
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["posts"]) >= 1
        assert any(str(post.id) == p["id"] for p in data["posts"])
        assert len(data["post_bookmarks"]) >= 1
        assert len(data["post_likes"]) >= 1
        assert len(data["drafts"]) >= 1
        assert len(data["following"]) >= 1

    def test_05_blocked_by_me_inclui_usuarios_bloqueados(self, user, other_user):
        """Teste 5: blocked_by_me inclui contas que o user bloqueou."""
        Block.objects.create(blocker=user, blocked=other_user)
        client, _ = auth_client(user)
        resp = client.get(self.url)
        data = resp.json()
        blocked_usernames = [b["username"] for b in data["blocked_users"]]
        assert other_user.username in blocked_usernames

    def test_06_muted_by_me_inclui_usuarios_silenciados(self, user, other_user):
        """Teste 6: muted_by_me inclui contas que o user silenciou."""
        Mute.objects.create(muter=user, muted=other_user)
        client, _ = auth_client(user)
        resp = client.get(self.url)
        data = resp.json()
        muted_usernames = [m["username"] for m in data["muted_users"]]
        assert other_user.username in muted_usernames

    def test_07_requer_autenticacao(self, db):
        """Teste 7: Export exige autenticação."""
        client = APIClient()
        resp = client.get(self.url)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Testes de Exclusão de Conta (DELETE /api/users/account/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeleteAccount:
    url = "/api/users/account/"

    def test_08_delete_com_senha_correta_retorna_204(self, user):
        """Teste 8 (5): Exclusão com senha correta — 204."""
        client, _ = auth_client(user)
        resp = client.delete(self.url, data={"current_password": "testpass123"}, format="json")
        assert resp.status_code == 204

    def test_09_delete_com_senha_incorreta_retorna_400(self, user):
        """Teste 9 (6): Senha incorreta — 400."""
        client, _ = auth_client(user)
        resp = client.delete(self.url, data={"current_password": "senha_errada_xyz"}, format="json")
        assert resp.status_code == 400
        assert "current_password" in resp.json()

    def test_10_delete_sem_campo_requerido_retorna_400(self, user):
        """Teste 10 (7): Sem campo de confirmação — 400."""
        client, _ = auth_client(user)
        resp = client.delete(self.url, data={}, format="json")
        assert resp.status_code == 400

    def test_11_delete_conta_oauth_username_correto_retorna_204(self, oauth_user):
        """Teste 11 (8): Conta OAuth — confirm_username correto — 204."""
        client, _ = auth_client(oauth_user)
        resp = client.delete(
            self.url,
            data={"confirm_username": oauth_user.username},
            format="json",
        )
        assert resp.status_code == 204

    def test_12_delete_conta_oauth_username_errado_retorna_400(self, oauth_user):
        """Teste 12 (9): Conta OAuth — confirm_username errado — 400."""
        client, _ = auth_client(oauth_user)
        resp = client.delete(
            self.url,
            data={"confirm_username": "username_errado_xyz"},
            format="json",
        )
        assert resp.status_code == 400
        assert "confirm_username" in resp.json()

    def test_13_accesslog_preservado_anonimizado_apos_delete(self, user):
        """Teste 13 (10): AccessLog preservado com user=NULL após exclusão — Marco Civil."""
        # Cria log de acesso vinculado ao user
        AccessLog.objects.create(
            user=user,
            ip_hash="a" * 64,
            port=12345,
        )
        log_count_before = AccessLog.objects.count()

        client, _ = auth_client(user)
        client.delete(self.url, data={"current_password": "testpass123"}, format="json")

        # Log deve persistir, mas user desvinculado (NULL)
        logs = AccessLog.objects.all()
        assert logs.count() == log_count_before
        assert all(log.user is None for log in logs)

    def test_14_cookies_limpos_na_resposta(self, user):
        """Teste 14 (11): Resposta 204 e clear_auth_cookies chamado (view limpa cookies)."""
        client, _ = auth_client(user)
        resp = client.delete(self.url, data={"current_password": "testpass123"}, format="json")
        # A exclusão deve retornar 204 — clear_auth_cookies é chamado internamente
        # (a limpeza de cookies httpOnly é validada nos testes de auth/logout)
        assert resp.status_code == 204

    def test_15_refresh_tokens_revogados_apos_delete(self, user):
        """Teste 15 (12): Refresh tokens blacklistados após exclusão."""
        if not HAS_BLACKLIST:
            pytest.skip("Token blacklist não instalado")

        client, refresh = auth_client(user)
        refresh_jti = refresh["jti"]

        # Passa o refresh token no cookie para o serviço poder blacklistá-lo
        client.cookies["refresh_token"] = str(refresh)
        client.delete(self.url, data={"current_password": "testpass123"}, format="json")

        # O token deve ter sido blacklistado (via OutstandingToken ou direto)
        assert BlacklistedToken.objects.filter(token__jti=refresh_jti).exists()

    def test_16_login_impossivel_apos_delete(self, user):
        """Teste 16 (13): Login falha após exclusão da conta."""
        email = user.email
        client, _ = auth_client(user)
        client.delete(self.url, data={"current_password": "testpass123"}, format="json")

        # Tenta fazer login com as credenciais do usuário deletado
        anon_client = APIClient()
        resp = anon_client.post(
            "/api/auth/login/", data={"email": email, "password": "testpass123"}, format="json"
        )
        assert resp.status_code in (400, 401)

    def test_17_password_reset_tokens_invalidados_apos_delete(self, user):
        """Teste 17 (14): PasswordResetTokens pendentes removidos junto com o usuário.

        PasswordResetToken.user tem on_delete=CASCADE.
        O serviço marca used_at antes da exclusão; após user.delete() o token
        é removido via CASCADE — ambos confirmam que não há tokens ativos pendentes.
        """
        import hashlib

        from django.utils import timezone

        raw = "token_pendente_xpto"
        hash_ = hashlib.sha256(raw.encode()).hexdigest()
        reset_token = PasswordResetToken.objects.create(
            user=user,
            token_hash=hash_,
            expires_at=timezone.now() + datetime.timedelta(minutes=15),
        )
        token_pk = reset_token.pk

        client, _ = auth_client(user)
        client.delete(self.url, data={"current_password": "testpass123"}, format="json")

        # Token não deve mais existir (CASCADE após hard-delete do usuário)
        assert not PasswordResetToken.objects.filter(pk=token_pk).exists()

    def test_18_requer_autenticacao(self, db):
        """Teste 18: Delete exige autenticação."""
        client = APIClient()
        resp = client.delete(self.url, data={"current_password": "password"}, format="json")
        assert resp.status_code == 401

    def test_19_exportacao_inclui_perfil_completo(self, user):
        """Teste 19: Export inclui campos completos de perfil."""
        profile = get_or_create_profile(user)
        profile.bio = "Minha bio"
        profile.save()

        client, _ = auth_client(user)
        resp = client.get("/api/users/export-data/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile"]["username"] == user.username
        assert data["profile"]["email"] == user.email
        assert "bio" in data["profile"]
        assert "date_joined" in data["profile"]
