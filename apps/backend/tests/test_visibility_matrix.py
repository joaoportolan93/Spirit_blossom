"""
Testes da matriz de vazamento de visibilidade — ADR-N21 (Onda 3a).

Escrito a partir do ADR-N21, não do código.
Cobre as linhas da matriz:
  - post público: conta pública e privada
  - post de círculo: viewer no círculo, seguidor fora, não-seguidor
  - conta privada: seguidor ativo, pendente, não-seguidor
  - viewer bloqueado pelo autor
  - viewer que bloqueou o autor
  - viewer que silenciou o autor (mute não bloqueia posts)
  - post excluído
  - autor vendo o próprio conteúdo
  - perfil de conta privada: visibilidade de bio/contadores/posts

Também inclui:
  - teste de arquitetura: listar posts sem módulo central detecta uso direto de Post.objects
  - allowlist de campos dos serializers (sem __all__)
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile
from social.models import Follow, Mute

from .factories import BlockFactory, PostFactory, UserFactory

User = get_user_model()


def _client_for(user):
    """APIClient autenticado via cookie JWT."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


def _make_private(user):
    """Marca conta do user como privada e atualiza o objeto em memória."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.is_private = True
    profile.save(update_fields=["is_private"])
    # Invalidar cache do descriptor OneToOne
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
# Teste de arquitetura: uso direto de Post.objects em listagem
# ---------------------------------------------------------------------------


class TestArchitecturePostObjectsDirect:
    """
    Varredura AST no backend inteiro: proíbe uso de Post.objects fora da allowlist explícita.
    Garante que nenhum seletor, view ou serviço leia posts fora do seletor central visible_posts_for.
    """

    def _get_source(self, module_path):
        import pathlib

        return pathlib.Path(module_path).read_text(encoding="utf-8")

    def test_post_objects_apenas_em_modulos_permitidos_ast(self):
        """
        Varredura AST no backend inteiro: proíbe Post.objects fora da allowlist explícita (ADR-N21).
        """
        import ast
        import pathlib

        backend_dir = pathlib.Path(__file__).parent.parent
        allowed_modules = {
            "social/selectors.py",
            "posts/services.py",
            "posts/models.py",
            "posts/admin.py",
        }

        violations = []
        for py_file in backend_dir.rglob("*.py"):
            rel_parts = py_file.relative_to(backend_dir).parts
            if "migrations" in rel_parts or "tests" in rel_parts:
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
        """get_visible_posts_queryset foi descontinuado; todo o repositório deve usar visible_posts_for."""
        import pathlib

        backend_dir = pathlib.Path(__file__).parent.parent
        for py_file in backend_dir.rglob("*.py"):
            if "migrations" in str(py_file) or "tests" in str(py_file):
                continue
            src = py_file.read_text(encoding="utf-8")
            assert "get_visible_posts_queryset" not in src, (
                f"{py_file} ainda usa get_visible_posts_queryset — deve usar visible_posts_for"
            )

    def test_serializers_sem_all(self):
        """Nenhum serializer de posts ou social pode usar fields = '__all__'."""
        import os

        for rel_path in ["posts/serializers.py", "social/serializers.py"]:
            path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", rel_path))
            src = self._get_source(path)
            assert "__all__" not in src, f"{rel_path} usa __all__ — proibido (ADR-N21)"


# ---------------------------------------------------------------------------
# Matriz: post público
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublicPost:
    def test_post_publico_visivel_para_nao_seguidor(self):
        """Post público de conta pública: qualquer autenticado vê."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids

    def test_post_publico_visivel_em_busca(self):
        """Post público aparece na busca full-text. NÃO VERIFICADO em SQLite (search_vector Postgres-only)."""
        pytest.skip(
            "NÃO VERIFICADO: search_vector GeneratedField requer Postgres 16 — não pode ser testado em SQLite"
        )

    def test_post_publico_visivel_em_detalhe_por_id(self):
        """GET /api/posts/<id>/ funciona para post público."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_post_publico_conta_privada_invisivel_para_nao_seguidor(self):
        """Post público de conta privada: não-seguidor NÃO vê."""
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_post_publico_conta_privada_visivel_para_seguidor_ativo(self):
        """Post público de conta privada: seguidor ativo VÊ."""
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_active(viewer, author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids

    def test_post_publico_conta_privada_invisivel_para_seguidor_pendente(self):
        """Post público de conta privada: seguidor pendente NÃO vê."""
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_pending(viewer, author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids


# ---------------------------------------------------------------------------
# Matriz: post de círculo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCirclePost:
    def test_post_circulo_visivel_para_membro_do_circulo(self):
        """Post de círculo: viewer que é close friend ativo VÊ."""
        author = UserFactory()
        viewer = UserFactory()
        _follow_circle(viewer, author)
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids

    def test_post_circulo_invisivel_para_seguidor_fora_do_circulo(self):
        """Post de círculo: seguidor ativo sem is_close_friend NÃO vê."""
        author = UserFactory()
        viewer = UserFactory()
        _follow_active(viewer, author)  # seguidor ativo mas NÃO no círculo
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_post_circulo_invisivel_para_nao_seguidor(self):
        """Post de círculo: não-seguidor NÃO vê."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_post_circulo_visivel_para_proprio_autor(self):
        """Autor sempre vê seu próprio post de círculo."""
        author = UserFactory()
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(author)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids

    def test_post_circulo_invisivel_em_busca_para_nao_membro(self):
        """Post de círculo não aparece em busca full-text para não-membro. NÃO VERIFICADO em SQLite."""
        pytest.skip("NÃO VERIFICADO: search_vector GeneratedField requer Postgres 16")

    def test_post_circulo_invisivel_em_detalhe_por_id_para_nao_membro(self):
        """GET /api/posts/<id>/ com post de círculo → 404 para não-membro."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="circle")
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_remover_do_circulo_oculta_posts_imediatamente(self):
        """Ao setar is_close_friend=False, posts de círculo somem imediatamente."""
        author = UserFactory()
        viewer = UserFactory()
        follow = _follow_circle(viewer, author)
        post = PostFactory(author=author, visibility="circle")

        client = _client_for(viewer)
        ids_before = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) in ids_before

        # Remove do círculo
        follow.is_close_friend = False
        follow.save()

        ids_after = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids_after


# ---------------------------------------------------------------------------
# Matriz: conta privada (perfil)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPrivateAccountProfile:
    def test_perfil_privado_visivel_para_seguidor_ativo(self):
        """Seguidor ativo de conta privada acessa perfil completo."""
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
        """Não-seguidor de conta privada vê perfil mínimo (200 OK) para poder pedir para seguir."""
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
        """Seguidor pendente de conta privada vê perfil mínimo com follow_status=pending."""
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
        """Conta pública: qualquer autenticado acessa perfil completo."""
        author = UserFactory()
        viewer = UserFactory()
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_200_OK

    def test_autor_ve_proprio_perfil_privado(self):
        """Autor sempre vê seu próprio perfil, mesmo privado."""
        author = UserFactory()
        _make_private(author)
        client = _client_for(author)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Matriz: bloqueio
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBlockVisibilityMatrix:
    def test_viewer_bloqueado_pelo_autor_nao_ve_post_publico_no_feed(self):
        """Viewer bloqueado pelo autor → não vê posts no feed."""
        author = UserFactory()
        viewer = UserFactory()
        BlockFactory(blocker=author, blocked=viewer)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_viewer_bloqueado_pelo_autor_nao_ve_post_em_busca(self):
        """Viewer bloqueado pelo autor → não vê em busca. NÃO VERIFICADO em SQLite."""
        pytest.skip("NÃO VERIFICADO: search_vector GeneratedField requer Postgres 16")

    def test_viewer_bloqueou_autor_nao_ve_post_em_busca(self):
        """Viewer que bloqueou o autor → não vê em busca. NÃO VERIFICADO em SQLite."""
        pytest.skip("NÃO VERIFICADO: search_vector GeneratedField requer Postgres 16")

    def test_viewer_bloqueado_pelo_autor_perfil_retorna_404(self):
        """Viewer bloqueado pelo autor → perfil retorna 404."""
        author = UserFactory()
        viewer = UserFactory()
        BlockFactory(blocker=author, blocked=viewer)
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_viewer_bloqueou_autor_perfil_retorna_404(self):
        """Viewer que bloqueou o autor → perfil retorna 404."""
        author = UserFactory()
        viewer = UserFactory()
        BlockFactory(blocker=viewer, blocked=author)
        client = _client_for(viewer)
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Matriz: mute (silenciamento não bloqueia posts)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMuteDoesNotHidePosts:
    def test_mute_nao_oculta_posts_no_feed(self):
        """Silenciar usuário não oculta posts no feed (apenas em Explorar/For You)."""
        author = UserFactory()
        viewer = UserFactory()
        Mute.objects.create(muter=viewer, muted=author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        # Mute no feed principal (Seguindo) não filtra — posts ainda aparecem
        assert str(post.pk) in ids


# ---------------------------------------------------------------------------
# Matriz: post excluído
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeletedPost:
    def test_post_deletado_retorna_404_em_detalhe(self):
        """Post deletado → 404 no endpoint de detalhe."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post_id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_post_deletado_some_do_feed(self):
        """Post deletado não aparece mais no feed."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        # Verifica que aparecia antes
        client = _client_for(viewer)
        ids_before = [p["id"] for p in client.get("/api/posts/").json()]
        assert post_id in ids_before
        # Deleta e verifica que sumiu
        post.delete()
        ids_after = [p["id"] for p in client.get("/api/posts/").json()]
        assert post_id not in ids_after


# ---------------------------------------------------------------------------
# can_view_profile / can_view_post unitários
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCanViewFunctions:
    def test_can_view_post_publico(self):
        from social.selectors import can_view_post

        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        assert can_view_post(viewer, post) is True

    def test_can_view_post_circulo_sem_ser_membro(self):
        from social.selectors import can_view_post

        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="circle")
        assert can_view_post(viewer, post) is False

    def test_can_view_post_none_retorna_false(self):
        from social.selectors import can_view_post

        viewer = UserFactory()
        assert can_view_post(viewer, None) is False

    def test_can_view_profile_bloqueio_bilateral(self):
        from social.selectors import can_view_profile

        a = UserFactory()
        b = UserFactory()
        BlockFactory(blocker=a, blocked=b)
        assert can_view_profile(b, a) is False
        assert can_view_profile(a, b) is False

    def test_can_view_profile_conta_privada_sem_follow(self):
        from social.selectors import can_view_profile

        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        assert can_view_profile(viewer, author) is False

    def test_can_view_profile_conta_privada_com_follow_ativo(self):
        from social.selectors import can_view_profile

        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_active(viewer, author)
        assert can_view_profile(viewer, author) is True

    def test_can_view_profile_proprio_usuario(self):
        from social.selectors import can_view_profile

        user = UserFactory()
        _make_private(user)
        assert can_view_profile(user, user) is True


# ---------------------------------------------------------------------------
# Matriz: Conta Privada (nao-seguidor e seguidor pendente) x Superficies
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPrivateAccountSurfaces:
    def test_conta_privada_nao_seguidor_oculto_no_feed(self):
        """Não-seguidor de conta privada não vê posts no feed."""
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_conta_privada_nao_seguidor_oculto_no_explorar(self):
        """Não-seguidor de conta privada não vê posts no Explorar."""
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
        """Não-seguidor de conta privada recebe 404 no detalhe por ID."""
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_conta_privada_seguidor_pendente_oculto_no_feed(self):
        """Seguidor pendente de conta privada não vê posts no feed."""
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_pending(viewer, author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert str(post.pk) not in ids

    def test_conta_privada_seguidor_pendente_oculto_no_explorar(self):
        """Seguidor pendente de conta privada não vê posts no Explorar."""
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
        """Seguidor pendente de conta privada recebe 404 no detalhe por ID."""
        author = UserFactory()
        _make_private(author)
        viewer = UserFactory()
        _follow_pending(viewer, author)
        post = PostFactory(author=author, visibility="public")
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Matriz: Post Excluido x Todas as Superficies
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeletedPostAllSurfaces:
    def test_post_excluido_oculto_no_feed(self):
        """Post excluído não aparece no feed."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        ids = [p["id"] for p in client.get("/api/posts/").json()]
        assert post_id not in ids

    def test_post_excluido_oculto_no_explorar(self):
        """Post excluído não aparece no feed Explorar."""
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
        """Post excluído retorna 404 no detalhe por ID."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.get(f"/api/posts/{post_id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_post_excluido_oculto_no_perfil(self):
        """Post excluído não aparece na listagem de publicações do perfil."""
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
        """Post salvo antes da exclusão desaparece dos favoritos."""
        from posts.models import PostBookmark

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
        """Curtir post excluído retorna 404."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.post(f"/api/posts/{post_id}/like/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_post_excluido_salvar_retorna_404(self):
        """Salvar post excluído retorna 404."""
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility="public")
        post_id = str(post.pk)
        post.delete()
        client = _client_for(viewer)
        resp = client.post(f"/api/posts/{post_id}/bookmark/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Matriz: Visitante Anonimo x Todos os Endpoints (deve ser negado 401)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAnonymousVisitorDeniedAllEndpoints:
    def test_anonimo_negado_no_feed(self):
        """Visitante anônimo é negado (401) em GET /api/posts/."""
        client = APIClient()
        resp = client.get("/api/posts/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_no_explorar(self):
        """Visitante anônimo é negado (401) em GET /api/feed/explore/."""
        client = APIClient()
        resp = client.get("/api/feed/explore/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_detalhe_de_post(self):
        """Visitante anônimo é negado (401) em GET /api/posts/<id>/."""
        post = PostFactory(visibility="public")
        client = APIClient()
        resp = client.get(f"/api/posts/{post.pk}/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_ao_criar_post(self):
        """Visitante anônimo é negado (401) em POST /api/posts/."""
        client = APIClient()
        resp = client.post("/api/posts/", {"content_text": "teste anônimo"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_favoritos(self):
        """Visitante anônimo é negado (401) em GET /api/posts/bookmarks/."""
        client = APIClient()
        resp = client.get("/api/posts/bookmarks/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_rascunhos(self):
        """Visitante anônimo é negado (401) em GET /api/posts/drafts/."""
        client = APIClient()
        resp = client.get("/api/posts/drafts/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_ao_curtir(self):
        """Visitante anônimo é negado (401) em POST /api/posts/<id>/like/."""
        post = PostFactory(visibility="public")
        client = APIClient()
        resp = client.post(f"/api/posts/{post.pk}/like/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_ao_salvar(self):
        """Visitante anônimo é negado (401) em POST /api/posts/<id>/bookmark/."""
        post = PostFactory(visibility="public")
        client = APIClient()
        resp = client.post(f"/api/posts/{post.pk}/bookmark/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_no_perfil(self):
        """Visitante anônimo é negado (401) em GET /api/social/profile/<username>/."""
        author = UserFactory()
        client = APIClient()
        resp = client.get(f"/api/social/profile/{author.username}/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_circulo_de_amigos(self):
        """Visitante anônimo é negado (401) em GET /api/social/close-friends/."""
        client = APIClient()
        resp = client.get("/api/social/close-friends/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_na_busca_de_usuarios(self):
        """Visitante anônimo é negado (401) em GET /api/users/search/?q=ali."""
        client = APIClient()
        resp = client.get("/api/users/search/?q=ali")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_anonimo_negado_em_notificacoes(self):
        """Visitante anônimo é negado (401) em GET /api/notifications/."""
        client = APIClient()
        resp = client.get("/api/notifications/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
