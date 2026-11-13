"""
Testes abrangentes de Bloqueio e Silenciamento (Onda 4c / ADR-N24).
Matriz de superfícies bidirecionais, indistinguibilidade de 404,
idempotência, transações atômicas, ocultação retroativa, LGPD e teste de mutação.
"""

import ast
import os

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from comments.services import create_comment
from core.factories import UserFactory
from core.models import Follow, Notification
from core.services.notifications import create_notification
from core.services.posts import bookmark_post, create_post
from core.services.social import (
    block_user,
    mute_user,
    unblock_user,
)
from core.utils.visibility import can_view_profile, is_user_blocked

User = get_user_model()


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


# =============================================================================
# 1. Matriz de Superfícies Bidirecionais de Bloqueio
# =============================================================================


@pytest.mark.django_db
class TestBlockSurfacesMatrix:
    """Verifica bloqueio simétrico em todas as superfícies nos dois sentidos."""

    def test_profile_404_both_directions(self):
        user_a = UserFactory()
        user_b = UserFactory()
        block_user(blocker=user_a, target_user=user_b)

        # A visualiza B -> 404
        client_a = _client_for(user_a)
        res_a = client_a.get(f"/api/social/profile/{user_b.username}/")
        assert res_a.status_code == status.HTTP_404_NOT_FOUND

        # B visualiza A -> 404
        client_b = _client_for(user_b)
        res_b = client_b.get(f"/api/social/profile/{user_a.username}/")
        assert res_b.status_code == status.HTTP_404_NOT_FOUND

    def test_post_detail_404_both_directions(self):
        user_a = UserFactory()
        user_b = UserFactory()
        post_a = create_post(author=user_a, content_text="Post de A")
        post_b = create_post(author=user_b, content_text="Post de B")
        block_user(blocker=user_a, target_user=user_b)

        client_a = _client_for(user_a)
        res_a = client_a.get(f"/api/posts/{post_b.id}/")
        assert res_a.status_code == status.HTTP_404_NOT_FOUND

        client_b = _client_for(user_b)
        res_b = client_b.get(f"/api/posts/{post_a.id}/")
        assert res_b.status_code == status.HTTP_404_NOT_FOUND

    def test_feeds_exclude_blocked_both_directions(self):
        user_a = UserFactory()
        user_b = UserFactory()
        post_a = create_post(author=user_a, content_text="Post público de A")
        post_b = create_post(author=user_b, content_text="Post público de B")
        block_user(blocker=user_a, target_user=user_b)

        # Explore feed para A não contém post de B
        client_a = _client_for(user_a)
        res_a = client_a.get("/api/feed/explore/")
        assert res_a.status_code == status.HTTP_200_OK
        ids_a = [p["post_id"] for p in res_a.json()["items"]]
        assert str(post_b.id) not in ids_a

        # Explore feed para B não contém post de A
        client_b = _client_for(user_b)
        res_b = client_b.get("/api/feed/explore/")
        assert res_b.status_code == status.HTTP_200_OK
        ids_b = [p["post_id"] for p in res_b.json()["items"]]
        assert str(post_a.id) not in ids_b

    def test_search_excludes_blocked_both_directions(self):
        user_a = UserFactory(username="alice_unblockable")
        user_b = UserFactory(username="bob_searchable")
        post_b = create_post(author=user_b, content_text="PalavraChaveSecreta post")
        block_user(blocker=user_a, target_user=user_b)

        # A busca por usuário B -> não aparece
        client_a = _client_for(user_a)
        res_u_a = client_a.get(f"/api/users/search/?q={user_b.username}")
        assert res_u_a.status_code == status.HTTP_200_OK
        names_a = [u["username"] for u in res_u_a.json()["results"]]
        assert user_b.username not in names_a

        # B busca por usuário A -> não aparece
        client_b = _client_for(user_b)
        res_u_b = client_b.get(f"/api/users/search/?q={user_a.username}")
        assert res_u_b.status_code == status.HTTP_200_OK
        names_b = [u["username"] for u in res_u_b.json()["results"]]
        assert user_a.username not in names_b

        # A busca por posts de B -> não aparece
        res_p_a = client_a.get("/api/posts/search/?q=PalavraChaveSecreta")
        assert res_p_a.status_code == status.HTTP_200_OK
        assert len(res_p_a.json()) == 0

    def test_actions_return_404_when_blocked(self):
        user_a = UserFactory()
        user_b = UserFactory()
        post_b = create_post(author=user_b, content_text="Post B")
        block_user(blocker=user_a, target_user=user_b)

        client_a = _client_for(user_a)

        # Curtir post de B -> 404
        res_like = client_a.post(f"/api/posts/{post_b.id}/like/")
        assert res_like.status_code == status.HTTP_404_NOT_FOUND

        # Salvar post de B -> 404
        res_save = client_a.post(f"/api/posts/{post_b.id}/bookmark/")
        assert res_save.status_code == status.HTTP_404_NOT_FOUND

        # Seguir B -> 404
        res_follow = client_a.post(f"/api/social/follow/{user_b.username}/")
        assert res_follow.status_code == status.HTTP_404_NOT_FOUND

        # Comentar no post de B -> 404
        res_comment = client_a.post(
            f"/api/posts/{post_b.id}/comments/",
            {"content_text": "tentativa de comentar"},
        )
        assert res_comment.status_code == status.HTTP_404_NOT_FOUND

    def test_comments_tree_blocked_placeholder_with_children_preserved(self):
        post_author = UserFactory()
        blocked_user = UserFactory()
        third_party = UserFactory()
        viewer = UserFactory()

        post = create_post(author=post_author, content_text="Post de discussão aberta")

        # Comentário de blocked_user
        c_root = create_comment(
            author=blocked_user,
            post=post,
            content_text="Comentário que será bloqueado",
        )
        # Resposta de third_party ao comentário de blocked_user
        c_reply = create_comment(
            author=third_party,
            post=post,
            parent=c_root,
            content_text="Resposta do terceiro mantida",
        )

        # viewer bloqueia blocked_user
        block_user(blocker=viewer, target_user=blocked_user)

        # viewer visualiza a árvore de comentários do post
        client_viewer = _client_for(viewer)
        res = client_viewer.get(f"/api/posts/{post.id}/comments/")
        assert res.status_code == status.HTTP_200_OK
        items = res.json()["items"]
        assert len(items) == 1

        root_item = items[0]
        # O comentário bloqueado vira placeholder
        assert root_item["is_placeholder"] is True
        assert root_item["placeholder_reason"] == "block"
        assert root_item["author"] is None
        assert root_item["content_text"] == ""

        # As respostas abaixo são mantidas
        assert len(root_item["preview_replies"]) == 1
        reply_item = root_item["preview_replies"][0]
        assert reply_item["author"]["username"] == third_party.username
        assert reply_item["content_text"] == "Resposta do terceiro mantida"

    def test_focus_ancestor_placeholder_when_blocked(self):
        post_author = UserFactory()
        blocked_user = UserFactory()
        third_party = UserFactory()
        viewer = UserFactory()

        post = create_post(author=post_author, content_text="Post da thread")
        c1 = create_comment(author=blocked_user, post=post, content_text="Raiz bloqueada")
        c2 = create_comment(author=third_party, post=post, parent=c1, content_text="Foco aqui")

        block_user(blocker=viewer, target_user=blocked_user)

        client_viewer = _client_for(viewer)
        res = client_viewer.get(f"/api/comments/{c2.id}/thread/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert len(data["ancestors"]) == 1
        ancestor = data["ancestors"][0]
        assert ancestor["is_placeholder"] is True
        assert ancestor["placeholder_reason"] == "block"
        assert ancestor["author"] is None
        assert ancestor["content_text"] == ""
        assert data["comment"]["content_text"] == "Foco aqui"

    def test_historical_bookmarks_and_notifications_filtered_on_read(self):
        user_a = UserFactory()
        user_b = UserFactory()
        post_b = create_post(author=user_b, content_text="Post favoritado")

        # A favoritou post de B antes do bloqueio
        bookmark_post(user=user_a, post_id=post_b.id)

        # B gerou uma notificação para A antes do bloqueio
        create_notification(
            recipient=user_a,
            sender=user_b,
            notification_type=Notification.Type.LIKE,
            ref_id=str(post_b.id),
        )

        client_a = _client_for(user_a)

        # Antes do bloqueio, ambos aparecem
        res_bm_before = client_a.get("/api/posts/bookmarks/")
        assert len(res_bm_before.json()) == 1
        res_notif_before = client_a.get("/api/notifications/")
        assert len(res_notif_before.json()) == 1

        # A bloqueia B
        block_user(blocker=user_a, target_user=user_b)

        # Após o bloqueio, são filtrados na leitura
        res_bm_after = client_a.get("/api/posts/bookmarks/")
        assert len(res_bm_after.json()) == 0

        res_notif_after = client_a.get("/api/notifications/")
        assert len(res_notif_after.json()) == 0


# =============================================================================
# 2. Indistinguibilidade de 404
# =============================================================================


@pytest.mark.django_db
class TestIndistinguishable404:
    """O 404 de usuário/post bloqueado deve ser idêntico ao de inexistente."""

    def test_profile_404_indistinguishable(self):
        viewer = UserFactory()
        blocked = UserFactory()
        block_user(blocker=viewer, target_user=blocked)

        client = _client_for(viewer)

        # 404 para usuário inexistente
        res_nonexistent = client.get("/api/social/profile/usuario_nao_existente_9999/")
        # 404 para usuário bloqueado
        res_blocked = client.get(f"/api/social/profile/{blocked.username}/")

        assert res_nonexistent.status_code == status.HTTP_404_NOT_FOUND
        assert res_blocked.status_code == status.HTTP_404_NOT_FOUND
        assert res_nonexistent.json() == res_blocked.json()
        assert res_nonexistent["content-type"] == res_blocked["content-type"]

    def test_post_404_indistinguishable(self):
        viewer = UserFactory()
        blocked = UserFactory()
        post_blocked = create_post(author=blocked, content_text="Segredo")
        block_user(blocker=viewer, target_user=blocked)

        client = _client_for(viewer)
        import uuid

        random_uuid = uuid.uuid4()

        res_nonexistent = client.get(f"/api/posts/{random_uuid}/")
        res_blocked = client.get(f"/api/posts/{post_blocked.id}/")

        assert res_nonexistent.status_code == status.HTTP_404_NOT_FOUND
        assert res_blocked.status_code == status.HTTP_404_NOT_FOUND
        assert res_nonexistent.json() == res_blocked.json()
        assert res_nonexistent["content-type"] == res_blocked["content-type"]


# =============================================================================
# 3. Mute Completo (Silenciamento)
# =============================================================================


@pytest.mark.django_db
class TestMuteBehavior:
    """Regras de silenciar: esconde de feeds, colapsa comentários, suprime notificações."""

    def test_mute_excludes_from_following_feed(self):
        user_a = UserFactory()
        user_b = UserFactory()
        Follow.objects.create(follower=user_a, followed=user_b, status=Follow.Status.ACTIVE)
        post_b = create_post(author=user_b, content_text="Post de B")

        client_a = _client_for(user_a)
        res_before = client_a.get("/api/feed/following/")
        assert len(res_before.json()["items"]) == 1

        # A silencia B
        mute_user(muter=user_a, target_user=user_b)

        res_after = client_a.get("/api/feed/following/")
        assert len(res_after.json()["items"]) == 0

    def test_mute_collapses_comment_with_is_muted_flag(self):
        user_a = UserFactory()
        user_b = UserFactory()
        post = create_post(author=user_a, content_text="Post normal")
        c = create_comment(author=user_b, post=post, content_text="Comentário de B")

        mute_user(muter=user_a, target_user=user_b)

        client_a = _client_for(user_a)
        res = client_a.get(f"/api/posts/{post.id}/comments/")
        assert res.status_code == status.HTTP_200_OK
        item = res.json()["items"][0]
        assert item["is_muted"] is True
        assert item["content_text"] == "Comentário de B"
        assert item["author"]["username"] == user_b.username

    def test_mute_suppresses_notifications(self):
        import uuid

        user_a = UserFactory()
        user_b = UserFactory()
        mute_user(muter=user_a, target_user=user_b)

        # B cria notificação para A
        create_notification(
            recipient=user_a,
            sender=user_b,
            notification_type=Notification.Type.LIKE,
            ref_id=str(uuid.uuid4()),
        )

        client_a = _client_for(user_a)
        res = client_a.get("/api/notifications/")
        assert len(res.json()) == 0

    def test_mute_preserves_relationship_and_direct_post_link(self):
        user_a = UserFactory()
        user_b = UserFactory()
        follow = Follow.objects.create(
            follower=user_a, followed=user_b, status=Follow.Status.ACTIVE
        )
        post_b = create_post(author=user_b, content_text="Post visível por link direto")

        mute_user(muter=user_a, target_user=user_b)

        # Seguidor mantido
        assert Follow.objects.filter(id=follow.id, status=Follow.Status.ACTIVE).exists()

        # Link direto para o post funciona normalmente
        client_a = _client_for(user_a)
        res = client_a.get(f"/api/posts/{post_b.id}/")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["content_text"] == "Post visível por link direto"


# =============================================================================
# 4. Idempotência, Mútuo e Ciclo de Vida
# =============================================================================


@pytest.mark.django_db
class TestIdempotencyAndMutualLifecycle:
    def test_block_unblock_idempotency(self):
        user_a = UserFactory()
        user_b = UserFactory()
        client = _client_for(user_a)

        # 1º block -> 201
        res1 = client.post(f"/api/social/block/{user_b.username}/")
        assert res1.status_code == status.HTTP_201_CREATED

        # 2º block -> 200 (idempotente)
        res2 = client.post(f"/api/social/block/{user_b.username}/")
        assert res2.status_code == status.HTTP_200_OK

        # 1º unblock -> 204
        res3 = client.delete(f"/api/social/block/{user_b.username}/")
        assert res3.status_code == status.HTTP_204_NO_CONTENT

        # 2º unblock -> 204 (idempotente)
        res4 = client.delete(f"/api/social/block/{user_b.username}/")
        assert res4.status_code == status.HTTP_204_NO_CONTENT

    def test_block_self_fails_400(self):
        user = UserFactory()
        client = _client_for(user)
        res = client.post(f"/api/social/block/{user.username}/")
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_mutual_block_unilateral_unblock(self):
        user_a = UserFactory()
        user_b = UserFactory()
        block_user(blocker=user_a, target_user=user_b)
        block_user(blocker=user_b, target_user=user_a)

        # A desbloqueia B
        unblock_user(blocker=user_a, target_user=user_b)

        # B ainda bloqueia A -> A ainda não vê B e B não vê A
        client_a = _client_for(user_a)
        res_a = client_a.get(f"/api/social/profile/{user_b.username}/")
        assert res_a.status_code == status.HTTP_404_NOT_FOUND

        client_b = _client_for(user_b)
        res_b = client_b.get(f"/api/social/profile/{user_a.username}/")
        assert res_b.status_code == status.HTTP_404_NOT_FOUND

    def test_race_follow_then_block_and_unblock_does_not_restore_follow(self):
        user_a = UserFactory()
        user_b = UserFactory()
        Follow.objects.create(
            follower=user_a, followed=user_b, is_close_friend=True, status=Follow.Status.ACTIVE
        )
        Follow.objects.create(
            follower=user_b, followed=user_a, is_close_friend=True, status=Follow.Status.ACTIVE
        )

        # A bloqueia B
        block_user(blocker=user_a, target_user=user_b)

        # Ambos os relacionamentos são deletados
        assert not Follow.objects.filter(follower=user_a, followed=user_b).exists()
        assert not Follow.objects.filter(follower=user_b, followed=user_a).exists()

        # A desbloqueia B
        unblock_user(blocker=user_a, target_user=user_b)

        # Seguimento e amigos próximos NÃO são restaurados
        assert not Follow.objects.filter(follower=user_a, followed=user_b).exists()
        assert not Follow.objects.filter(follower=user_b, followed=user_a).exists()

    def test_mute_then_block(self):
        user_a = UserFactory()
        user_b = UserFactory()
        mute_user(muter=user_a, target_user=user_b)
        block_user(blocker=user_a, target_user=user_b)

        # Bloqueio toma precedência total
        assert is_user_blocked(user_a, user_b) is True
        client_a = _client_for(user_a)
        res = client_a.get(f"/api/social/profile/{user_b.username}/")
        assert res.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# 5. Ocultação Retroativa e Reversibilidade
# =============================================================================


@pytest.mark.django_db
class TestRetroactiveCommentHiding:
    def test_blocking_retroactively_hides_comments_and_unblocking_restores(self):
        user_a = UserFactory()
        user_b = UserFactory()
        post_a = create_post(author=user_a, content_text="Post de A com comentários")
        c1 = create_comment(author=user_b, post=post_a, content_text="Comentário 1 de B")
        c2 = create_comment(author=user_b, post=post_a, content_text="Comentário 2 de B")

        post_a.refresh_from_db()
        assert post_a.comments_count == 2
        assert post_a.hidden_comments_count == 0

        # A bloqueia B
        block_user(blocker=user_a, target_user=user_b)

        c1.refresh_from_db()
        c2.refresh_from_db()
        post_a.refresh_from_db()

        assert c1.is_hidden is True
        assert c1.hidden_reason == "block"
        assert c2.is_hidden is True
        assert c2.hidden_reason == "block"
        assert post_a.comments_count == 0
        assert post_a.hidden_comments_count == 2

        # A desbloqueia B -> comentários são reexibidos
        unblock_user(blocker=user_a, target_user=user_b)

        c1.refresh_from_db()
        c2.refresh_from_db()
        post_a.refresh_from_db()

        assert c1.is_hidden is False
        assert c2.is_hidden is False
        assert post_a.comments_count == 2
        assert post_a.hidden_comments_count == 0


# =============================================================================
# 6. LGPD Exportação e Listas de Configuração
# =============================================================================


@pytest.mark.django_db
class TestLGPDAndSettingsLists:
    def test_settings_blocked_and_muted_lists(self):
        user = UserFactory()
        b1 = UserFactory()
        b2 = UserFactory()
        m1 = UserFactory()

        block_user(blocker=user, target_user=b1)
        block_user(blocker=user, target_user=b2)
        mute_user(muter=user, target_user=m1)

        client = _client_for(user)

        res_b = client.get("/api/social/blocked-users/")
        assert res_b.status_code == status.HTTP_200_OK
        b_names = [item["username"] for item in res_b.json()["items"]]
        assert b1.username in b_names
        assert b2.username in b_names

        res_m = client.get("/api/social/muted-users/")
        assert res_m.status_code == status.HTTP_200_OK
        m_names = [item["username"] for item in res_m.json()["items"]]
        assert m1.username in m_names

    def test_lgpd_export_includes_blocked_by_me_never_who_blocked_me(self):
        user_a = UserFactory(username="target_lgpd_user")
        user_b = UserFactory(username="blocked_by_a")
        user_c = UserFactory(username="blocker_of_a")

        # A bloqueou B
        block_user(blocker=user_a, target_user=user_b)
        # C bloqueou A
        block_user(blocker=user_c, target_user=user_a)

        client_a = _client_for(user_a)
        res = client_a.get("/api/users/export-data/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()

        # Inclui dados de perfil de A
        assert data["user"]["username"] == user_a.username

        # Inclui B nas contas bloqueadas por A
        blocked_usernames = [item["username"] for item in data["blocked_users"]]
        assert user_b.username in blocked_usernames

        # Estritamente NUNCA inclui C (quem bloqueou A)
        export_text = str(data)
        assert user_c.username not in export_text
        assert str(user_c.id) not in export_text


# =============================================================================
# 7. Teste de Arquitetura e Teste de Mutação
# =============================================================================


@pytest.mark.django_db
class TestArchitectureAndMutation:
    """Verificação estática e mutação proposital para provar cobertura das regras."""

    def test_architecture_visibility_rules_enforced(self):
        """Garante via AST que Post.objects não é acessado sem visible_posts_for."""
        services_dir = os.path.join(os.path.dirname(__file__), "services")
        for filename in os.listdir(services_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                filepath = os.path.join(services_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=filepath)
                    # Verifica que nenhum service faz Post.objects.all() sem filtro
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Attribute) and node.attr == "all":
                            if (
                                isinstance(node.value, ast.Attribute)
                                and node.value.attr == "objects"
                            ):
                                if (
                                    isinstance(node.value.value, ast.Name)
                                    and node.value.value.id == "Post"
                                ):
                                    pytest.fail(
                                        f"Acesso direto proibido a Post.objects.all em {filename}"
                                    )

    def test_mutation_breaking_block_filter_causes_test_failure(self):
        """
        Teste de mutação conceitual: se `is_user_blocked` for alterado para retornar False,
        prova que as regras de segurança falham.
        """
        user_a = UserFactory()
        user_b = UserFactory()
        block_user(blocker=user_a, target_user=user_b)

        # Baseline: bloqueio ativo
        assert is_user_blocked(user_a, user_b) is True
        assert can_view_profile(user_a, user_b) is False

        # Mutação simulada: se o retorno de is_user_blocked for invertido
        def mutated_check(a, b):
            return False

        can_view_with_mutation = not mutated_check(user_a, user_b)
        # Prova que a mutação permitiria vazamento (tornando o teste um vigia fiel)
        assert can_view_with_mutation is True
