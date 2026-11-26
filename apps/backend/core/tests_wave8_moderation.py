"""
Testes completos da Onda 8:
- Ciclo de vida de banimentos (Estágio 1, expiração temporária, Estágio 2, purga, HMAC)
- Denúncias (criação, validação, fila admin, ocultar/remover/banir/descartar)
- Controle de acesso (/api/admin/* restrito a staff/superuser, tokens invalidados)
- Feature flags administrativas (admin_only, cache invalidation, CRUD admin)
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status

from comments.models import Comment
from conftest import auth_client, get_csrf_token, make_csrf_client
from core.factories import PostFactory, UserFactory
from core.models import (
    AccessLog,
    FeatureFlag,
    Follow,
    ModerationLog,
    PermanentBanRecord,
    Post,
    PushDevice,
    Report,
)
from core.services.feature_flags import is_feature_enabled
from core.services.user_lifecycle import (
    ban_user,
    expire_temporary_bans,
    get_email_hmac,
    is_email_or_username_blocked,
    normalize_email_address,
    permanently_delete_user,
    purge_expired_banned_accounts,
    unban_user,
)
from core.tasks import expire_temporary_bans_task, purge_expired_banned_accounts_task


def _csrf_post(client, url, data=None):
    csrf = get_csrf_token(client)
    return client.post(url, data or {}, format="json", HTTP_X_CSRFTOKEN=csrf)


def _csrf_patch(client, url, data=None):
    csrf = get_csrf_token(client)
    return client.patch(url, data or {}, format="json", HTTP_X_CSRFTOKEN=csrf)


def _csrf_delete(client, url, data=None):
    csrf = get_csrf_token(client)
    return client.delete(url, data or {}, format="json", HTTP_X_CSRFTOKEN=csrf)


# ==============================================================================
# Ciclo de vida de banimento (padrão Lumem tests_ban_lifecycle.py)
# ==============================================================================


@pytest.mark.django_db
class TestBanLifecycle:
    def test_normalize_email_address_e_hmac(self):
        assert normalize_email_address("User.Name+spam@gmail.com") == "user.name@gmail.com"
        assert normalize_email_address("  JoAo+teste123@Spirit.Social  ") == "joao@spirit.social"
        assert normalize_email_address("invalido") == "invalido"
        assert normalize_email_address("") == ""

        h1 = get_email_hmac("Alvo+alias@example.com")
        h2 = get_email_hmac("ALVO@example.com")
        assert h1 == h2
        assert len(h1) == 64

    def test_ban_e_rejeicao_imediata_de_token_antigo(self):
        admin = UserFactory(is_staff=True)
        target = UserFactory(username="infrator")
        PushDevice.objects.create(user=target, token="push-tok-1", platform="web")

        client = auth_client(target)
        res_before = client.get("/api/auth/me/")
        assert res_before.status_code == status.HTTP_200_OK

        ban_user(target, reason="Violação grave dos termos", admin_user=admin)
        target.refresh_from_db()

        assert target.status == target.Status.SUSPENDED
        assert target.is_active is False
        assert target.appeal_deadline is not None
        assert target.appeal_days_remaining in (29, 30)
        assert PushDevice.objects.get(token="push-tok-1").is_active is False
        assert ModerationLog.objects.filter(
            target_id=str(target.id), action=ModerationLog.Action.BAN
        ).exists()

        res_after = client.get("/api/auth/me/")
        assert res_after.status_code == status.HTTP_401_UNAUTHORIZED

    def test_suspensao_temporaria_expira_automaticamente(self):
        admin = UserFactory(is_staff=True)
        target = UserFactory(username="tempban")

        ban_user(target, reason="Spam temporário", admin_user=admin, duration_days=7)
        target.refresh_from_db()
        assert target.status == target.Status.SUSPENDED
        assert target.ban_expires_at is not None
        assert target.appeal_deadline is None

        # Simula expiração no passado
        target.ban_expires_at = timezone.now() - timedelta(minutes=5)
        target.save(update_fields=["ban_expires_at"])

        client = auth_client(target)
        res = client.get("/api/auth/me/")
        assert res.status_code == status.HTTP_200_OK

        target.refresh_from_db()
        assert target.status == target.Status.ACTIVE
        assert target.is_active is True
        assert target.ban_expires_at is None
        assert ModerationLog.objects.filter(
            target_id=str(target.id), action=ModerationLog.Action.UNBAN
        ).exists()

    def test_expire_temporary_bans_service_e_task(self):
        target = UserFactory()
        ban_user(target, reason="Teste expiração", duration_days=1)
        target.ban_expires_at = timezone.now() - timedelta(hours=1)
        target.save(update_fields=["ban_expires_at"])

        restored = expire_temporary_bans()
        assert restored == 1
        target.refresh_from_db()
        assert target.status == target.Status.ACTIVE

        # Task também executa sem erro
        assert expire_temporary_bans_task() == 0

    def test_validacoes_ban_user(self):
        target = UserFactory()
        with pytest.raises(ValueError):
            ban_user(target, reason="   ")
        with pytest.raises(ValueError):
            ban_user(target, reason="Motivo", duration_days=0)
        with pytest.raises(ValueError):
            ban_user(target, reason="Motivo", duration_days="abc")

    def test_conta_banida_some_de_busca_sugestoes_feed_e_perfil(self):
        admin = UserFactory(is_staff=True)
        target = UserFactory(username="banidoalvo")
        observer = UserFactory(username="observador")
        Follow.objects.create(follower=observer, followed=target, status=Follow.Status.ACTIVE)
        post = PostFactory(author=target, content_text="Publicacao secreta proibida")

        ban_user(target, reason="Assédio", admin_user=admin)

        client = auth_client(observer)

        # Perfil retorna 404
        assert client.get(f"/api/social/profile/{target.username}/").status_code == 404
        # Sugestões não inclui o banido
        sugg = client.get("/api/social/suggestions/").data.get("results", [])
        assert all(u["username"] != target.username for u in sugg)
        # Busca de usuários exclui o banido
        u_search = client.get(f"/api/users/search/?q={target.username[:5]}").data.get("results", [])
        assert all(u["username"] != target.username for u in u_search)
        # Busca de posts exclui posts do banido
        p_search = client.get("/api/posts/search/?q=proibida").data
        assert all(p["id"] != str(post.id) for p in p_search)
        # Feed Seguindo e Explorar excluem posts do banido
        following_feed = client.get("/api/feed/following/").data.get("results", [])
        explore_feed = client.get("/api/feed/explore/").data.get("results", [])
        assert all(p["id"] != str(post.id) for p in following_feed)
        assert all(p["id"] != str(post.id) for p in explore_feed)

    def test_desbanir_restaura_acesso_e_perfil(self):
        admin = UserFactory(is_staff=True)
        target = UserFactory(username="recursook")
        observer = UserFactory(username="obs2")

        ban_user(target, reason="Engano", admin_user=admin)
        unban_user(target, admin_user=admin, reason="Recurso aceito")

        target.refresh_from_db()
        assert target.status == target.Status.ACTIVE
        assert target.is_active is True
        assert target.appeal_deadline is None

        assert auth_client(target).get("/api/auth/me/").status_code == 200
        assert (
            auth_client(observer).get(f"/api/social/profile/{target.username}/").status_code == 200
        )

    def test_exclusao_definitiva_tombstone_marco_civil_e_bloqueio_recadastro(self):
        admin = UserFactory(is_staff=True)
        target = UserFactory(email="infrator@example.com", username="infrator99")
        other = UserFactory(username="inocente99")
        post_other = PostFactory(author=other, content_text="Post preservado")
        post_target = PostFactory(author=target, content_text="Post a remover")

        parent_comment = Comment.objects.create(
            post=post_other, author=target, content_text="Comentário do infrator"
        )
        child_reply = Comment.objects.create(
            post=post_other,
            author=other,
            parent=parent_comment,
            depth=1,
            content_text="Resposta preservada",
        )
        leaf_comment = Comment.objects.create(
            post=post_other, author=target, content_text="Comentário folha"
        )
        access_log = AccessLog.objects.create(user=target, ip_hash="a" * 64, port=12345)

        permanently_delete_user(target, reason="Ban definitivo", admin_user=admin, is_ban=True)

        # Usuário e seus posts/folhas foram removidos
        assert not Post.objects.filter(pk=post_target.pk).exists()
        assert not Comment.objects.filter(pk=leaf_comment.pk).exists()

        # Comentário com resposta vira tombstone
        parent_comment.refresh_from_db()
        assert parent_comment.is_deleted is True
        assert parent_comment.author is None
        assert parent_comment.content_text == ""
        child_reply.refresh_from_db()
        assert child_reply.author == other

        # AccessLog preservado anonimizado (Marco Civil)
        access_log.refresh_from_db()
        assert access_log.user is None

        # PermanentBanRecord bloqueia +tag e maiúsculas no cadastro público
        assert PermanentBanRecord.objects.filter(
            email_hash=get_email_hmac("infrator@example.com"),
            username="infrator99",
        ).exists()
        blocked, _ = is_email_or_username_blocked(email="INFRATOR+novo@example.com")
        assert blocked is True
        blocked_u, _ = is_email_or_username_blocked(username="@INFRATOR99")
        assert blocked_u is True

        client = make_csrf_client()
        res = _csrf_post(
            client,
            "/api/auth/register/",
            {
                "email": "Infrator+tentativa@example.com",
                "username": "novousuario",
                "password": "Password123!",
                "password_confirm": "Password123!",
                "birth_date": "1990-01-01",
                "terms_accepted": True,
            },
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in res.data

    def test_dry_run_e_preservacao_para_autoridades(self):
        expired = UserFactory(username="exp1")
        ban_user(expired, reason="Fraude")
        expired.appeal_deadline = timezone.now() - timedelta(days=1)
        expired.save(update_fields=["appeal_deadline"])

        preserved = UserFactory(username="preservado1")
        ban_user(preserved, reason="Ordem judicial", preserve_for_authorities=True)
        preserved.appeal_deadline = timezone.now() - timedelta(days=1)
        preserved.save(update_fields=["appeal_deadline"])

        dry = purge_expired_banned_accounts(dry_run=True)
        assert len(dry) == 1
        assert dry[0]["username"] == "exp1"

        real = purge_expired_banned_accounts(dry_run=False)
        assert len(real) == 1
        assert not type(expired).objects.filter(pk=expired.pk).exists()
        assert type(preserved).objects.filter(pk=preserved.pk).exists()

        # Task wrapper
        assert purge_expired_banned_accounts_task(dry_run=True) == 0

    def test_login_e_google_oauth_barrados_para_banido_e_bloqueado(self):
        admin = UserFactory(is_staff=True)
        target = UserFactory(email="guser@example.com", username="guser1")
        ban_user(target, reason="Abuso", admin_user=admin)

        # Login tradicional bloqueado
        client = make_csrf_client()
        res_login = _csrf_post(
            client,
            "/api/auth/login/",
            {"email": "guser@example.com", "password": "testpass123"},
        )
        assert res_login.status_code == status.HTTP_400_BAD_REQUEST
        assert res_login.data.get("banned") is True
        assert res_login.data.get("ban_reason") == "Abuso"
        assert res_login.data.get("appeal_email") == "moderacao@spirit.blossom"
        assert res_login.data.get("appeal_days_remaining") is not None

        # Google OAuth barrado com 403 para conta banida
        res_g = _csrf_post(
            client,
            "/api/auth/google/",
            {"id_token": "mock-google-token:sub123:guser@example.com:true"},
        )
        assert res_g.status_code == status.HTTP_403_FORBIDDEN
        assert res_g.data.get("banned") is True
        assert res_g.data.get("ban_reason") == "Abuso"
        assert res_g.data.get("appeal_email") == "moderacao@spirit.blossom"

        # Google OAuth barrado com 403 para e-mail no PermanentBanRecord
        PermanentBanRecord.objects.create(
            username="banold",
            email_hash=get_email_hmac("blocked@example.com"),
            ban_reason="Spam",
        )
        res_g2 = _csrf_post(
            client,
            "/api/auth/google/",
            {"id_token": "mock-google-token:sub999:blocked+alias@example.com:true"},
        )
        assert res_g2.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# Denúncias, Moderação e Painel Admin
# ==============================================================================


@pytest.mark.django_db
class TestModerationAndAdminAPI:
    def test_controle_acesso_admin_endpoints(self):
        common = UserFactory(is_staff=False)
        client = auth_client(common, enforce_csrf=True)

        assert client.get("/api/admin/stats/").status_code == status.HTTP_403_FORBIDDEN
        assert client.get("/api/admin/users/").status_code == status.HTTP_403_FORBIDDEN
        assert client.get(f"/api/admin/users/{common.id}/").status_code == status.HTTP_403_FORBIDDEN
        assert client.get("/api/admin/reports/").status_code == status.HTTP_403_FORBIDDEN
        assert client.get("/api/admin/moderation-logs/").status_code == status.HTTP_403_FORBIDDEN
        assert client.get("/api/admin/feature-flags/").status_code == status.HTTP_403_FORBIDDEN

    def test_fluxo_completo_denuncia_post_ocultar_remover_e_banir(self):
        admin = UserFactory(is_staff=True)
        reporter = UserFactory(username="reporter1")
        author = UserFactory(username="author1")
        post = PostFactory(author=author, content_text="Post ofensivo para moderar")

        rep_client = auth_client(reporter, enforce_csrf=True)

        # Validações de criação
        assert _csrf_post(rep_client, "/api/reports/", {}).status_code == 400
        assert (
            _csrf_post(
                rep_client,
                "/api/reports/",
                {"target_type": "post", "target_id": "invalid-uuid", "reason": "spam"},
            ).status_code
            == 400
        )
        assert (
            _csrf_post(
                rep_client,
                "/api/reports/",
                {
                    "target_type": "post",
                    "target_id": "00000000-0000-0000-0000-000000000099",
                    "reason": "spam",
                },
            ).status_code
            == 404
        )

        # Auto-denúncia bloqueada
        own_post = PostFactory(author=reporter)
        assert (
            _csrf_post(
                rep_client,
                "/api/reports/",
                {"target_type": "post", "target_id": str(own_post.id), "reason": "spam"},
            ).status_code
            == 400
        )

        # Denúncia válida
        res_create = _csrf_post(
            rep_client,
            "/api/reports/",
            {
                "target_type": "post",
                "target_id": str(post.id),
                "reason": "harassment",
                "description": "Ataque pessoal",
            },
        )
        assert res_create.status_code == status.HTTP_201_CREATED
        report_id = res_create.data["id"]

        # Denúncia duplicada pendente rejeitada
        res_dup = _csrf_post(
            rep_client,
            "/api/reports/",
            {"target_type": "post", "target_id": str(post.id), "reason": "spam"},
        )
        assert res_dup.status_code == status.HTTP_400_BAD_REQUEST

        # Admin lista fila pendente
        admin_client = auth_client(admin, enforce_csrf=True)
        queue = admin_client.get("/api/admin/reports/?status=pending&target_type=post")
        assert queue.status_code == 200
        assert len(queue.data) == 1
        assert queue.data[0]["content"]["id"] == str(post.id)

        # Admin oculta post denunciado
        res_hide = _csrf_post(
            admin_client,
            f"/api/admin/reports/{report_id}/action/",
            {"action": "hide", "reason": "Violação das regras"},
        )
        assert res_hide.status_code == 200
        post.refresh_from_db()
        assert post.is_hidden is True

        # Post ocultado pela moderação some de todos os feeds e detalhes
        assert rep_client.get(f"/api/posts/{post.id}/").status_code == 404
        assert auth_client(author).get(f"/api/posts/{post.id}/").status_code == 404
        explore = rep_client.get("/api/feed/explore/").data.get("results", [])
        assert all(p["id"] != str(post.id) for p in explore)

    def test_denuncia_comentario_e_usuario_acoes_remove_ignore_ban_remove(self):
        admin = UserFactory(is_staff=True)
        reporter = UserFactory(username="rep2")
        bad_user = UserFactory(username="bad2")
        post = PostFactory(author=reporter)
        comment_with_reply = Comment.objects.create(
            post=post, author=bad_user, content_text="Comentário ruim"
        )
        Comment.objects.create(
            post=post, author=reporter, parent=comment_with_reply, depth=1, content_text="Resposta"
        )

        rep_client = auth_client(reporter, enforce_csrf=True)
        admin_client = auth_client(admin, enforce_csrf=True)

        # Denuncia comentário -> ação hide (invisível até para o autor)
        r_comm = _csrf_post(
            rep_client,
            "/api/reports/",
            {"target_type": "comment", "target_id": str(comment_with_reply.id), "reason": "spam"},
        )
        assert r_comm.status_code == 201
        _csrf_post(
            admin_client,
            f"/api/admin/reports/{r_comm.data['id']}/action/",
            {"action": "hide"},
        )
        comment_with_reply.refresh_from_db()
        assert comment_with_reply.is_hidden is True
        assert comment_with_reply.hidden_reason == "moderation"
        comments_bad = auth_client(bad_user).get(f"/api/posts/{post.id}/comments/").data["items"]
        assert all(c["id"] != str(comment_with_reply.id) for c in comments_bad)

        # Denuncia usuário -> ação review -> ignore
        r_user = _csrf_post(
            rep_client,
            "/api/reports/",
            {"target_type": "user", "target_id": str(bad_user.id), "reason": "other"},
        )
        assert r_user.status_code == 201
        _csrf_post(
            admin_client,
            f"/api/admin/reports/{r_user.data['id']}/action/",
            {"action": "review", "moderator_notes": "Em verificação"},
        )
        assert Report.objects.get(pk=r_user.data["id"]).status == Report.Status.REVIEWED

        _csrf_post(
            admin_client,
            f"/api/admin/reports/{r_user.data['id']}/action/",
            {"action": "ignore"},
        )
        assert Report.objects.get(pk=r_user.data["id"]).status == Report.Status.DISMISSED

        # Denuncia post de bad_user -> ban_remove
        bad_post = PostFactory(author=bad_user, content_text="Spam grave")
        r_post = _csrf_post(
            rep_client,
            "/api/reports/",
            {"target_type": "post", "target_id": str(bad_post.id), "reason": "illegal"},
        )
        res_br = _csrf_post(
            admin_client,
            f"/api/admin/reports/{r_post.data['id']}/action/",
            {"action": "ban_remove", "reason": "Conteúdo ilegal"},
        )
        assert res_br.status_code == 200
        assert not Post.objects.filter(pk=bad_post.id).exists()
        bad_user.refresh_from_db()
        assert bad_user.status == bad_user.Status.SUSPENDED

    def test_admin_users_stats_logs_e_protecao_self_ban_delete(self):
        admin = UserFactory(is_staff=True, username="bossadmin")
        target = UserFactory(username="useralvo")
        client = auth_client(admin, enforce_csrf=True)

        # Stats
        stats_res = client.get("/api/admin/stats/")
        assert stats_res.status_code == 200
        assert "kpis" in stats_res.data
        assert len(stats_res.data["daily_stats"]) == 7

        # Lista e busca usuários
        list_res = client.get("/api/admin/users/?search=useralvo&status=active")
        assert list_res.status_code == 200
        assert list_res.data["count"] == 1

        # Auto-ban e auto-exclusão proibidos
        assert (
            _csrf_patch(
                client,
                f"/api/admin/users/{admin.id}/",
                {"status": "suspended", "reason": "auto"},
            ).status_code
            == 400
        )
        assert (
            _csrf_delete(
                client,
                f"/api/admin/users/{admin.id}/",
                {"confirm_username": admin.username},
            ).status_code
            == 400
        )

        # Banir -> Inspecionar -> Desbanir -> Banir -> Excluir definitivamente
        assert (
            _csrf_patch(
                client,
                f"/api/admin/users/{target.id}/",
                {"status": "suspended", "reason": "Violação"},
            ).status_code
            == 200
        )
        detail = client.get(f"/api/admin/users/{target.id}/")
        assert detail.status_code == 200
        assert detail.data["status"] == "suspended"

        assert (
            _csrf_patch(
                client,
                f"/api/admin/users/{target.id}/",
                {"status": "active"},
            ).status_code
            == 200
        )
        assert (
            _csrf_delete(
                client,
                f"/api/admin/users/{target.id}/",
                {"confirm_username": "errado"},
            ).status_code
            == 400
        )
        assert (
            _csrf_delete(
                client,
                f"/api/admin/users/{target.id}/",
                {"confirm_username": f"@{target.username}"},
            ).status_code
            == 200
        )
        assert not type(target).objects.filter(pk=target.id).exists()

        # Logs de moderação
        logs_res = client.get("/api/admin/moderation-logs/")
        assert logs_res.status_code == 200
        assert len(logs_res.data) >= 3

    def test_cobertura_extra_acoes_moderacao_e_desativacao(self):
        admin = UserFactory(is_staff=True)
        reporter = UserFactory(username="rep_extra")
        offender = UserFactory(username="off_extra")
        post1 = PostFactory(author=offender, content_text="Post para remover")
        post2 = PostFactory(author=offender, content_text="Post para ban")
        comm_leaf = Comment.objects.create(
            post=post2, author=offender, content_text="Comentário folha"
        )
        comm_parent = Comment.objects.create(
            post=post2, author=offender, content_text="Comentário pai"
        )
        Comment.objects.create(
            post=post2, author=reporter, parent=comm_parent, depth=1, content_text="Filho"
        )

        rep_client = auth_client(reporter, enforce_csrf=True)
        admin_client = auth_client(admin, enforce_csrf=True)

        # Erros de criação de denúncia em comentário/usuário
        assert (
            _csrf_post(
                rep_client,
                "/api/reports/",
                {"target_type": "invalid", "target_id": str(post1.id), "reason": "spam"},
            ).status_code
            == 400
        )
        assert (
            _csrf_post(
                rep_client,
                "/api/reports/",
                {"target_type": "post", "target_id": str(post1.id), "reason": "bad_reason"},
            ).status_code
            == 400
        )
        assert (
            _csrf_post(
                rep_client,
                "/api/reports/",
                {
                    "target_type": "comment",
                    "target_id": "00000000-0000-0000-0000-000000000099",
                    "reason": "spam",
                },
            ).status_code
            == 404
        )
        assert (
            _csrf_post(
                rep_client,
                "/api/reports/",
                {
                    "target_type": "user",
                    "target_id": "00000000-0000-0000-0000-000000000099",
                    "reason": "spam",
                },
            ).status_code
            == 404
        )
        assert (
            _csrf_post(
                rep_client,
                "/api/reports/",
                {"target_type": "user", "target_id": str(reporter.id), "reason": "spam"},
            ).status_code
            == 400
        )
        own_c = Comment.objects.create(post=post2, author=reporter, content_text="Meu")
        assert (
            _csrf_post(
                rep_client,
                "/api/reports/",
                {"target_type": "comment", "target_id": str(own_c.id), "reason": "spam"},
            ).status_code
            == 400
        )

        # Remove post via action=remove
        r_p1 = _csrf_post(
            rep_client,
            "/api/reports/",
            {"target_type": "post", "target_id": str(post1.id), "reason": "spam"},
        )
        assert (
            _csrf_post(
                admin_client,
                f"/api/admin/reports/{r_p1.data['id']}/action/",
                {"action": "remove"},
            ).status_code
            == 200
        )
        assert not Post.objects.filter(pk=post1.id).exists()

        # Remove comentário folha + comentário pai (tombstone)
        r_c1 = _csrf_post(
            rep_client,
            "/api/reports/",
            {"target_type": "comment", "target_id": str(comm_leaf.id), "reason": "spam"},
        )
        assert (
            _csrf_post(
                admin_client,
                f"/api/admin/reports/{r_c1.data['id']}/action/",
                {"action": "remove"},
            ).status_code
            == 200
        )
        assert not Comment.objects.filter(pk=comm_leaf.id).exists()

        r_c2 = _csrf_post(
            rep_client,
            "/api/reports/",
            {"target_type": "comment", "target_id": str(comm_parent.id), "reason": "spam"},
        )
        assert (
            _csrf_post(
                admin_client,
                f"/api/admin/reports/{r_c2.data['id']}/action/",
                {"action": "remove"},
            ).status_code
            == 200
        )
        comm_parent.refresh_from_db()
        assert comm_parent.is_deleted is True

        # Ação ban em post + ação inválida
        r_p2 = _csrf_post(
            rep_client,
            "/api/reports/",
            {"target_type": "post", "target_id": str(post2.id), "reason": "harassment"},
        )
        assert (
            _csrf_post(
                admin_client,
                f"/api/admin/reports/{r_p2.data['id']}/action/",
                {"action": "invalid_act"},
            ).status_code
            == 400
        )
        assert (
            _csrf_post(
                admin_client,
                f"/api/admin/reports/{r_p2.data['id']}/action/",
                {"action": "ban", "duration_days": 3},
            ).status_code
            == 200
        )
        offender.refresh_from_db()
        assert offender.status == offender.Status.SUSPENDED

        # AdminUsersView: page inválida, PATCH motivo vazio, PATCH deactivated, PATCH status inválido
        assert admin_client.get("/api/admin/users/?page=abc").status_code == 200
        u_extra = UserFactory(username="deact1")
        assert (
            _csrf_patch(
                admin_client,
                f"/api/admin/users/{u_extra.id}/",
                {"status": "suspended", "reason": ""},
            ).status_code
            == 400
        )
        assert (
            _csrf_patch(
                admin_client,
                f"/api/admin/users/{u_extra.id}/",
                {"status": "deactivated"},
            ).status_code
            == 200
        )
        assert (
            _csrf_patch(
                admin_client,
                f"/api/admin/users/{u_extra.id}/",
                {"status": "weird"},
            ).status_code
            == 400
        )


# ==============================================================================
# Feature Flags Admin e admin_only
# ==============================================================================


@pytest.mark.django_db
class TestAdminFeatureFlags:
    def setup_method(self):
        cache.clear()

    def test_admin_only_flag_e_invalidation(self):
        admin = UserFactory(is_staff=True)
        regular = UserFactory(is_staff=False)
        flag = FeatureFlag.objects.create(
            key="beta_moderation",
            description="Ferramenta interna",
            is_enabled=True,
            admin_only=True,
            rollout_percentage=100,
        )

        assert is_feature_enabled("beta_moderation", admin) is True
        assert is_feature_enabled("beta_moderation", regular) is False
        assert is_feature_enabled("beta_moderation", None) is False

        # Atualiza via ORM — save() invalida cache automaticamente
        flag.admin_only = False
        flag.save()
        assert is_feature_enabled("beta_moderation", regular) is True

    def test_crud_admin_feature_flags(self):
        admin = UserFactory(is_staff=True)
        client = auth_client(admin, enforce_csrf=True)

        # Criar
        res_create = _csrf_post(
            client,
            "/api/admin/feature-flags/",
            {
                "key": "communities_enabled",
                "description": "Comunidades",
                "is_enabled": False,
                "admin_only": False,
                "rollout_percentage": 50,
            },
        )
        assert res_create.status_code == status.HTTP_201_CREATED

        # Duplicada -> 400
        assert (
            _csrf_post(
                client,
                "/api/admin/feature-flags/",
                {"key": "communities_enabled"},
            ).status_code
            == 400
        )

        # Listar e detalhar
        assert len(client.get("/api/admin/feature-flags/").data) >= 1
        assert client.get("/api/admin/feature-flags/communities_enabled/").status_code == 200

        # Atualizar (toggle + rollout inválido)
        assert (
            _csrf_patch(
                client,
                "/api/admin/feature-flags/communities_enabled/",
                {"rollout_percentage": 150},
            ).status_code
            == 400
        )
        res_patch = _csrf_patch(
            client,
            "/api/admin/feature-flags/communities_enabled/",
            {"is_enabled": True, "rollout_percentage": 100},
        )
        assert res_patch.status_code == 200
        assert res_patch.data["is_enabled"] is True

        # Remover
        assert (
            _csrf_delete(client, "/api/admin/feature-flags/communities_enabled/").status_code == 200
        )
        assert not FeatureFlag.objects.filter(key="communities_enabled").exists()

    def test_validacoes_extras_feature_flags_admin(self):
        admin = UserFactory(is_staff=True)
        client = auth_client(admin, enforce_csrf=True)

        assert _csrf_post(client, "/api/admin/feature-flags/", {"key": ""}).status_code == 400
        assert (
            _csrf_post(
                client,
                "/api/admin/feature-flags/",
                {"key": "f_bad1", "rollout_percentage": "abc"},
            ).status_code
            == 400
        )
        assert (
            _csrf_post(
                client,
                "/api/admin/feature-flags/",
                {"key": "f_bad2", "rollout_percentage": 200},
            ).status_code
            == 400
        )

        _csrf_post(
            client,
            "/api/admin/feature-flags/",
            {"key": "f_ok", "is_enabled": True, "rollout_percentage": 50},
        )
        assert (
            _csrf_patch(
                client, "/api/admin/feature-flags/f_ok/", {"rollout_percentage": "bad"}
            ).status_code
            == 400
        )
        res = _csrf_patch(
            client,
            "/api/admin/feature-flags/f_ok/",
            {"admin_only": True, "description": "Atualizada"},
        )
        assert res.status_code == 200
        assert res.data["admin_only"] is True
        assert res.data["description"] == "Atualizada"

        # Allowlist m2m invalidation
        u = UserFactory()
        flag_obj = FeatureFlag.objects.get(key="f_ok")
        flag_obj.admin_only = False
        flag_obj.rollout_percentage = 0
        flag_obj.save()
        assert is_feature_enabled("f_ok", u) is False
        flag_obj.allowed_users.add(u)
        assert is_feature_enabled("f_ok", u) is True
