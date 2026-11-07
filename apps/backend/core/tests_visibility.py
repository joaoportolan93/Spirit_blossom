"""
Testes de visibilidade de posts, bloqueio bidirecional, matriz de privacidade e testes adversariais.
Consolidado a partir de test_visibility.py, test_visibility_matrix.py e test_adversarial_and_coverage.py (ADR-N2/ADR-N21).
"""

import ast
import os
import pathlib

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.factories import BlockFactory, FollowFactory, PostFactory, UserFactory
from core.models import Follow, Mute, Notification, PostBookmark, UserProfile
from core.services.notifications import notify_post_liked, notify_user_followed
from core.services.posts import search_posts
from core.utils.visibility import can_view_post, can_view_profile, visible_posts_for

User = get_user_model()


def _client_for(user):
    """Cria APIClient autenticado via cookie para um usuário."""
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


def _follow_active(follower, followed):
    """Cria follow ativo (status=active)."""
    return Follow.objects.create(follower=follower, followed=followed, status=Follow.Status.ACTIVE)


def _follow_pending(follower, followed):
    """Cria follow pendente (status=pending)."""
    return Follow.objects.create(follower=follower, followed=followed, status=Follow.Status.PENDING)


def _follow_circle(follower, followed):
    """Cria follow ativo com is_close_friend=True."""
    return Follow.objects.create(
        follower=follower, followed=followed, status=Follow.Status.ACTIVE, is_close_friend=True
    )


# ---------------------------------------------------------------------------
# Testes básicos de visibilidade (test_visibility.py)
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
        author = UserFactory()
        post = PostFactory(author=author, visibility="followers")
        client = _client_for(author)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) in ids

    def test_post_publico_visivel_para_proprio_autor(self):
        author = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(author)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) in ids

    def test_multiple_posts_visibilidade_mista(self):
        author1 = UserFactory()
        author2 = UserFactory()
        viewer = UserFactory()
        FollowFactory(follower=viewer, followed=author1)

        p1 = PostFactory(author=author1, visibility="followers")
        p2 = PostFactory(author=author2, visibility="followers")
        p3 = PostFactory(author=author2, visibility="public")

        client = _client_for(viewer)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(p1.pk) in ids
        assert str(p2.pk) not in ids
        assert str(p3.pk) in ids


@pytest.mark.django_db
class TestBidirectionalBlock:
    def test_bloqueado_nao_aparece_no_feed_do_bloqueador(self):
        author = UserFactory()
        blocked_user = UserFactory()
        BlockFactory(blocker=author, blocked=blocked_user)
        post = PostFactory(author=blocked_user, visibility="public")
        client = _client_for(author)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) not in ids

    def test_bloqueador_nao_aparece_no_feed_do_bloqueado(self):
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        post = PostFactory(author=blocker, visibility="public")
        client = _client_for(blocked)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) not in ids

    def test_sem_bloqueio_posts_aparecem_normalmente(self):
        user_a = UserFactory()
        user_b = UserFactory()
        post = PostFactory(author=user_a, visibility="public")
        client = _client_for(user_b)
        response = client.get("/api/posts/")
        ids = [str(p["id"]) for p in response.json()]
        assert str(post.pk) in ids

    def test_bloquear_remove_follow_bidirecional(self):
        user_a = UserFactory()
        user_b = UserFactory()
        FollowFactory(follower=user_a, followed=user_b)
        FollowFactory(follower=user_b, followed=user_a)

        assert Follow.objects.filter(follower=user_a, followed=user_b).exists()
        assert Follow.objects.filter(follower=user_b, followed=user_a).exists()

        client = _client_for(user_a)
        response = client.post(f"/api/social/block/{user_b.username}/")
        assert response.status_code == status.HTTP_201_CREATED

        assert not Follow.objects.filter(follower=user_a, followed=user_b).exists()
        assert not Follow.objects.filter(follower=user_b, followed=user_a).exists()

    def test_desbloquear_restaura_visibilidade_no_feed(self):
        blocker = UserFactory()
        blocked = UserFactory()
        block = BlockFactory(blocker=blocker, blocked=blocked)
        post = PostFactory(author=blocked, visibility="public")

        client = _client_for(blocker)
        response = client.get("/api/posts/")
        assert str(post.pk) not in [str(p["id"]) for p in response.json()]

        block.delete()
        response2 = client.get("/api/posts/")
        assert str(post.pk) in [str(p["id"]) for p in response2.json()]

    def test_bloqueio_mutuo_ambos_ocultos_no_feed(self):
        user_a = UserFactory()
        user_b = UserFactory()
        BlockFactory(blocker=user_a, blocked=user_b)
        BlockFactory(blocker=user_b, blocked=user_a)

        post_a = PostFactory(author=user_a, visibility="public")
        post_b = PostFactory(author=user_b, visibility="public")

        client_a = _client_for(user_a)
        response_a = client_a.get("/api/posts/")
        assert str(post_b.pk) not in [str(p["id"]) for p in response_a.json()]

        client_b = _client_for(user_b)
        response_b = client_b.get("/api/posts/")
        assert str(post_a.pk) not in [str(p["id"]) for p in response_b.json()]

    def test_post_detail_bloqueado_retorna_404(self):
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        post = PostFactory(author=blocker, visibility="public")

        client = _client_for(blocked)
        response = client.get(f"/api/posts/{post.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_post_detail_bloqueador_retorna_404(self):
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        post = PostFactory(author=blocked, visibility="public")

        client = _client_for(blocker)
        response = client.get(f"/api/posts/{post.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_busca_exclui_posts_de_bloqueados(self):
        blocker = UserFactory()
        blocked = UserFactory()
        BlockFactory(blocker=blocker, blocked=blocked)
        PostFactory(author=blocked, content_text="palavra-unica-xablau", visibility="public")
        client = _client_for(blocker)
        response = client.get("/api/posts/search/?q=palavra-unica-xablau")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

    def test_busca_exclui_posts_de_bloqueador(self):
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


# ---------------------------------------------------------------------------
# Teste de arquitetura e allowlists (ADR-N21)
# ---------------------------------------------------------------------------


class TestArchitecturePostObjectsDirect:
    def _get_source(self, module_path):
        return pathlib.Path(module_path).read_text(encoding="utf-8")

    def test_post_objects_apenas_em_modulos_permitidos_ast(self):
        backend_dir = pathlib.Path(__file__).parent.parent
        allowed_modules = {
            "core/utils/visibility.py",
            "core/services/posts.py",
            "core/models.py",
            "core/admin.py",
        }

        violations = []
        for py_file in backend_dir.rglob("*.py"):
            rel_parts = py_file.relative_to(backend_dir).parts
            if (
                "migrations" in rel_parts
                or "tests" in rel_parts
                or any(p.startswith("tests_") for p in rel_parts)
            ):
                continue
            rel_path = "/".join(rel_parts)
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr == "objects":
                    if isinstance(node.value, ast.Name) and node.value.id == "Post":
                        if rel_path not in allowed_modules:
                            violations.append(f"{rel_path}:{node.lineno}")

        assert not violations, (
            f"Uso direto de Post.objects proibido fora da allowlist central {allowed_modules}. "
            f"Violações encontradas: {violations}"
        )

    def test_repositorio_inteiro_nao_usa_get_visible_posts_queryset(self):
        backend_dir = pathlib.Path(__file__).parent.parent
        for py_file in backend_dir.rglob("*.py"):
            if "migrations" in str(py_file) or "tests" in str(py_file) or "tests_" in str(py_file):
                continue
            src = py_file.read_text(encoding="utf-8")
            assert (
                "get_visible_posts_queryset" not in src
            ), f"{py_file} ainda usa get_visible_posts_queryset — deve usar visible_posts_for"

    def test_serializers_sem_all(self):
        for rel_path in ["core/serializers/posts.py", "core/serializers/social.py"]:
            path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", rel_path))
            src = self._get_source(path)
            assert "__all__" not in src, f"{rel_path} usa __all__ — proibido (ADR-N21)"


# ---------------------------------------------------------------------------
# Matriz: post público (TestPublicPost)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublicPost:
    def test_post_publico_visivel_para_nao_seguidor(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids

    def test_post_publico_visivel_em_busca(self):
        pytest.skip(
            "NÃO VERIFICADO: search_vector GeneratedField requer Postgres 16 — não pode ser testado em SQLite"
        )

    def test_post_publico_visivel_em_detalhe_por_id(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_post_publico_conta_privada_invisivel_para_nao_seguidor(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_post_publico_conta_privada_visivel_para_seguidor_ativo(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_active(viewer, author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids

    def test_post_publico_conta_privada_invisivel_para_seguidor_pendente(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_pending(viewer, author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids


# ---------------------------------------------------------------------------
# Matriz: post de círculo (TestCirclePost)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCirclePost:
    def test_post_circulo_visivel_para_membro_do_circulo(self):
        author = UserFactory()
        viewer = UserFactory()
        _follow_circle(viewer, author)
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids

    def test_post_circulo_invisivel_para_seguidor_fora_do_circulo(self):
        author = UserFactory()
        viewer = UserFactory()
        _follow_active(viewer, author)
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_post_circulo_invisivel_para_nao_seguidor(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_post_circulo_visivel_para_proprio_autor(self):
        author = UserFactory()
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(author)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids

    def test_post_circulo_invisivel_em_busca_para_nao_membro(self):
        pytest.skip("NÃO VERIFICADO: search_vector GeneratedField requer Postgres 16")

    def test_post_circulo_invisivel_em_detalhe_por_id_para_nao_membro(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_remover_do_circulo_oculta_posts_imediatamente(self):
        author = UserFactory()
        viewer = UserFactory()
        follow = _follow_circle(viewer, author)
        post = PostFactory(author=author, visibility="circle")

        client = _client_for(viewer)
        ids_before = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids_before

        follow.is_close_friend = False
        follow.save()

        ids_after = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids_after


# ---------------------------------------------------------------------------
# Matriz: conta privada perfil (TestPrivateAccountProfile)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPrivateAccountProfile:
    def test_perfil_privado_visivel_para_seguidor_ativo(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_active(viewer, author)
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "username" in data
        assert "posts" in data

    def test_perfil_privado_retorna_perfil_minimo_para_nao_seguidor(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["username"] == author.username
        assert data["is_private"] is True
        assert data["bio"] == ""
        assert data["posts_count"] == 0
        assert data["followers_count"] == 0
        assert data["following_count"] == 0
        assert data["is_following"] is False
        assert data["follow_status"] is None
        assert data["posts"] == []

    def test_perfil_privado_retorna_perfil_minimo_para_seguidor_pendente(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_pending(viewer, author)
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["username"] == author.username
        assert data["is_private"] is True
        assert data["bio"] == ""
        assert data["posts_count"] == 0
        assert data["followers_count"] == 0
        assert data["following_count"] == 0
        assert data["is_following"] is False
        assert data["follow_status"] == "pending"
        assert data["posts"] == []

    def test_perfil_publico_sempre_acessivel(self):
        author = UserFactory()
        viewer = UserFactory()
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_autor_ve_proprio_perfil_privado(self):
        author = UserFactory()
        _make_private(author)
        client = _client_for(author)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Matriz: bloqueio (TestBlockVisibilityMatrix)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBlockVisibilityMatrix:
    def test_viewer_bloqueado_pelo_autor_nao_ve_post_publico_no_feed(self):
        author = UserFactory()
        viewer = UserFactory()
        BlockFactory(blocker=author, blocked=viewer)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_viewer_bloqueado_pelo_autor_nao_ve_post_em_busca(self):
        pytest.skip("NÃO VERIFICADO: search_vector GeneratedField requer Postgres 16")

    def test_viewer_bloqueou_autor_nao_ve_post_em_busca(self):
        pytest.skip("NÃO VERIFICADO: search_vector GeneratedField requer Postgres 16")

    def test_viewer_bloqueado_pelo_autor_perfil_retorna_404(self):
        author = UserFactory()
        viewer = UserFactory()
        BlockFactory(blocker=author, blocked=viewer)
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_viewer_bloqueou_autor_perfil_retorna_404(self):
        author = UserFactory()
        viewer = UserFactory()
        BlockFactory(blocker=viewer, blocked=author)
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Matriz: mute (TestMuteDoesNotHidePosts)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMuteDoesNotHidePosts:
    def test_mute_nao_oculta_posts_no_feed(self):
        author = UserFactory()
        viewer = UserFactory()
        Mute.objects.create(muter=viewer, muted=author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids


# ---------------------------------------------------------------------------
# Matriz: post excluído (TestDeletedPost)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeletedPost:
    def test_post_deletado_retorna_404_em_detalhe(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post_id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_post_deletado_some_do_feed(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        client = _client_for(viewer)
        ids_before = [p["id"] for p in client.get("/api/posts/").json()]
        assert post_id in ids_before

        post.delete()
        ids_after = [p["id"] for p in client.get("/api/posts/").json()]
        assert post_id not in ids_after


# ---------------------------------------------------------------------------
# Funções unitárias can_view (TestCanViewFunctions)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCanViewFunctions:
    def test_can_view_post_publico(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        assert can_view_post(viewer, post) is True

    def test_can_view_post_circulo_sem_ser_membro(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="circle")
        assert can_view_post(viewer, post) is False

    def test_can_view_post_none_retorna_false(self):
        viewer = UserFactory()
        assert can_view_post(viewer, None) is False

    def test_can_view_profile_bloqueio_bilateral(self):
        a = UserFactory()
        b = UserFactory()
        BlockFactory(blocker=a, blocked=b)
        assert can_view_profile(b, a) is False
        assert can_view_profile(a, b) is False

    def test_can_view_profile_conta_privada_sem_follow(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        assert can_view_profile(viewer, author) is False

    def test_can_view_profile_conta_privada_com_follow_ativo(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_active(viewer, author)
        assert can_view_profile(viewer, author) is True

    def test_can_view_profile_proprio_usuario(self):
        user = UserFactory()
        _make_private(user)
        assert can_view_profile(user, user) is True


# ---------------------------------------------------------------------------
# Matriz: Conta Privada x Superfícies (TestPrivateAccountSurfaces)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPrivateAccountSurfaces:
    def test_conta_privada_nao_seguidor_oculto_no_feed(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_conta_privada_nao_seguidor_oculto_no_explorar(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        resp = client.get("/api/feed/explore/")
        assert resp.status_code == status.HTTP_200_OK
        items = resp.json().get("items", [])
        post_ids = [item["post_id"] for item in items]
        assert str(post.pk) not in post_ids

    def test_conta_privada_nao_seguidor_detalhe_retorna_404(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_conta_privada_seguidor_pendente_oculto_no_feed(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_pending(viewer, author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_conta_privada_seguidor_pendente_oculto_no_explorar(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_pending(viewer, author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        resp = client.get("/api/feed/explore/")
        assert resp.status_code == status.HTTP_200_OK
        items = resp.json().get("items", [])
        post_ids = [item["post_id"] for item in items]
        assert str(post.pk) not in post_ids

    def test_conta_privada_seguidor_pendente_detalhe_retorna_404(self):
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_pending(viewer, author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Matriz: Post Excluído x Todas as Superfícies (TestDeletedPostAllSurfaces)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeletedPostAllSurfaces:
    def test_post_excluido_oculto_no_feed(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert post_id not in ids

    def test_post_excluido_oculto_no_explorar(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.get("/api/feed/explore/")
        items = resp.json().get("items", [])
        assert post_id not in [item["post_id"] for item in items]

    def test_post_excluido_detalhe_retorna_404(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post_id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_post_excluido_oculto_no_perfil(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_200_OK
        posts_data = resp.json().get("posts", [])
        assert post_id not in [p["id"] for p in posts_data]

    def test_post_excluido_oculto_nos_favoritos(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        PostBookmark.objects.create(user=viewer, post=post)
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.get("/api/posts/bookmarks/")
        assert resp.status_code == status.HTTP_200_OK
        assert post_id not in [p["id"] for p in resp.json()]

    def test_post_excluido_curtir_retorna_404(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.post(f"/api/posts/{post_id}/like/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_post_excluido_salvar_retorna_404(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.post(f"/api/posts/{post_id}/bookmark/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Matriz: Visitante Anônimo x Endpoints (TestAnonymousVisitorDeniedAllEndpoints)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAnonymousVisitorDeniedAllEndpoints:
    def test_anonimo_negado_no_feed(self):
        client = APIClient()
        resp = client.get("/api/posts/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_no_explorar(self):
        client = APIClient()
        resp = client.get("/api/feed/explore/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_detalhe_de_post(self):
        post = PostFactory(visibility="public")
        client = APIClient()
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_ao_criar_post(self):
        client = APIClient()
        resp = client.post("/api/posts/", {"content_text": "teste anônimo"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_favoritos(self):
        client = APIClient()
        resp = client.get("/api/posts/bookmarks/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_rascunhos(self):
        client = APIClient()
        resp = client.get("/api/posts/drafts/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_ao_curtir(self):
        post = PostFactory(visibility="public")
        client = APIClient()
        resp = client.post(f"/api/posts/{post.pk}/like/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_ao_salvar(self):
        post = PostFactory(visibility="public")
        client = APIClient()
        resp = client.post(f"/api/posts/{post.pk}/bookmark/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_no_perfil(self):
        author = UserFactory()
        client = APIClient()
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_circulo_de_amigos(self):
        client = APIClient()
        resp = client.get("/api/social/close-friends/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_na_busca_de_usuarios(self):
        client = APIClient()
        resp = client.get("/api/users/search/?q=ali")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_notificacoes(self):
        client = APIClient()
        resp = client.get("/api/notifications/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Testes Adversariais Nomeados (TestNamedAdversarialSecurity)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNamedAdversarialSecurity:
    def test_adversarial_direct_id_access_private_and_circle_post(self):
        author = UserFactory()
        _make_private(author)
        attacker = UserFactory()

        private_post = PostFactory(author=author, visibility="public")
        circle_post = PostFactory(author=author, visibility="circle")

        client = _client_for(attacker)

        resp1 = client.get(f"/api/posts/{private_post.pk}/")
        assert resp1.status_code == status.HTTP_404_NOT_FOUND
        assert resp1.json()["detail"] == "Não encontrado."

        Follow.objects.create(
            follower=attacker, followed=author, status="active", is_close_friend=False
        )
        resp2 = client.get(f"/api/posts/{circle_post.pk}/")
        assert resp2.status_code == status.HTTP_404_NOT_FOUND

    def test_adversarial_cursor_pagination_does_not_leak_hidden_posts(self):
        author = UserFactory()
        attacker = UserFactory()
        BlockFactory(blocker=author, blocked=attacker)

        hidden_post = PostFactory(author=author, visibility="public")
        PostFactory(author=attacker, visibility="public")

        client = _client_for(attacker)

        resp = client.get(f"/api/posts/?cursor={hidden_post.pk}")
        assert resp.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in resp.json()]
        assert str(hidden_post.pk) not in ids

    def test_adversarial_counters_cannot_infer_private_activity(self):
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
        author = UserFactory()
        _make_private(author)
        attacker = UserFactory()

        PostFactory(
            author=author, content_text="segredo confidencial absoluto", visibility="public"
        )

        qs = search_posts(query="confidencial", user=attacker)
        assert qs.count() == 0

    def test_adversarial_notification_cannot_leak_to_inaccessible_user(self):
        author = UserFactory()
        target = UserFactory()
        BlockFactory(blocker=target, blocked=author)

        post = PostFactory(author=target, visibility="public")

        notify_post_liked(sender=author, post=post)
        assert Notification.objects.filter(recipient=target, sender=author).count() == 0

        notify_user_followed(follower=author, followed=target)
        assert Notification.objects.filter(recipient=target, sender=author).count() == 0

    def test_adversarial_bookmarks_cannot_retrieve_hidden_or_blocked_posts(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")

        PostBookmark.objects.create(user=viewer, post=post)
        client = _client_for(viewer)

        resp1 = client.get("/api/posts/bookmarks/")
        assert resp1.status_code == status.HTTP_200_OK
        assert str(post.pk) in [p["id"] for p in resp1.json()]

        BlockFactory(blocker=author, blocked=viewer)

        resp2 = client.get("/api/posts/bookmarks/")
        assert resp2.status_code == status.HTTP_200_OK
        assert str(post.pk) not in [p["id"] for p in resp2.json()]


# ---------------------------------------------------------------------------
# Cobertura adicional de visibilidade
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVisibilityEdgeCases:
    def test_visible_posts_for_none_and_anonymous_returns_empty_queryset(self):
        author_public = UserFactory()
        PostFactory(author=author_public, visibility="public")

        qs_none = visible_posts_for(None)
        assert qs_none.count() == 0
        assert list(qs_none) == []

        qs_anon = visible_posts_for(AnonymousUser())
        assert qs_anon.count() == 0
        assert list(qs_anon) == []

    def test_can_view_post_edge_cases(self):
        viewer = UserFactory()
        assert can_view_post(viewer, None) is False
        assert can_view_post(viewer, object()) is False
