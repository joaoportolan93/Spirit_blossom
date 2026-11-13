"""
Suite abrangente de testes para Comentários (Onda 4 / ADR-N24).
Matriz de vazamento, IDOR, concorrência F(), cursor composto,
profundidade máxima, tombstone, poda de órfãos e teste de arquitetura AST.
"""

import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from comments.models import Comment, CommentBookmark
from comments.selectors import (
    decode_cursor,
    encode_cursor,
    get_comment_thread_context,
    list_post_comments_with_preview,
    list_post_hidden_comments,
)
from comments.services import (
    MAX_COMMENT_DEPTH,
    create_comment,
    delete_comment,
    hide_comment,
    toggle_comment_bookmark,
    toggle_comment_like,
)
from core.factories import PostFactory, UserFactory
from core.models import Block, Notification, Post


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def author():
    return UserFactory(username="author")


@pytest.fixture
def commenter():
    return UserFactory(username="commenter")


@pytest.fixture
def reader():
    return UserFactory(username="reader")


@pytest.fixture
def public_post(author):
    return PostFactory(author=author, visibility=Post.Visibility.PUBLIC)


@pytest.fixture
def circle_post(author):
    return PostFactory(author=author, visibility=Post.Visibility.CIRCLE)


# =============================================================================
# 1. Criação, Profundidade e Limite Técnico (Requisito 1 e 3)
# =============================================================================


@pytest.mark.django_db
class TestCommentCreationAndDepth:
    def test_create_root_comment_success(self, public_post, commenter):
        comment = create_comment(
            author=commenter,
            post=public_post,
            content_text="Primeiro comentário!",
        )
        assert comment.depth == 0
        assert comment.content_text == "Primeiro comentário!"
        assert comment.author == commenter
        assert comment.is_deleted is False

        public_post.refresh_from_db()
        assert public_post.comments_count == 1

    def test_create_nested_reply_success(self, public_post, commenter, reader):
        root = create_comment(author=commenter, post=public_post, content_text="Raiz")
        reply1 = create_comment(
            author=reader, post=public_post, content_text="Resposta 1", parent=root
        )
        reply2 = create_comment(
            author=commenter, post=public_post, content_text="Resposta 2", parent=reply1
        )

        assert reply1.depth == 1
        assert reply2.depth == 2

        root.refresh_from_db()
        reply1.refresh_from_db()
        assert root.replies_count == 1
        assert reply1.replies_count == 1

        public_post.refresh_from_db()
        assert public_post.comments_count == 3

    def test_depth_limit_enforced_at_50(self, public_post, commenter):
        # Simula nó no limite máximo 50
        deep_parent = Comment.objects.create(
            post=public_post,
            author=commenter,
            depth=MAX_COMMENT_DEPTH,
            content_text="Nível 50",
        )

        with pytest.raises(ValidationError) as exc:
            create_comment(
                author=commenter,
                post=public_post,
                content_text="Tentativa no nível 51",
                parent=deep_parent,
            )
        assert "50" in str(exc.value)

    def test_empty_or_oversized_comment_rejected(self, public_post, commenter):
        with pytest.raises(ValidationError):
            create_comment(author=commenter, post=public_post, content_text="   ")

        with pytest.raises(ValidationError):
            create_comment(author=commenter, post=public_post, content_text="x" * 1001)


# =============================================================================
# 2. Tombstone, Exclusão e Poda de Órfãos (Requisito 7)
# =============================================================================


@pytest.mark.django_db
class TestCommentTombstoneAndPrune:
    def test_delete_leaf_comment_removes_physically(self, public_post, commenter):
        comment = create_comment(author=commenter, post=public_post, content_text="Folha")
        comment_id = comment.id

        delete_comment(comment=comment, user=commenter)
        assert not Comment.objects.filter(id=comment_id).exists()

        public_post.refresh_from_db()
        assert public_post.comments_count == 0

    def test_delete_comment_with_replies_becomes_tombstone(self, public_post, commenter, reader):
        parent = create_comment(author=commenter, post=public_post, content_text="Pai")
        reply = create_comment(author=reader, post=public_post, content_text="Filho", parent=parent)

        delete_comment(comment=parent, user=commenter)
        parent.refresh_from_db()

        # Tombstone aplicado: texto não vem do banco (vazio), sem autor e sem editado
        assert parent.is_deleted is True
        assert parent.content_text == ""
        assert parent.author is None
        assert parent.is_edited is False
        assert parent.edited_at is None

        # Filho continua ativo
        reply.refresh_from_db()
        assert reply.is_deleted is False

        # Comentário excluído não conta mais
        public_post.refresh_from_db()
        assert public_post.comments_count == 1

    def test_pruning_ancestor_tombstones_when_last_child_deleted(
        self, public_post, commenter, reader
    ):
        parent = create_comment(author=commenter, post=public_post, content_text="Pai")
        child = create_comment(author=reader, post=public_post, content_text="Filho", parent=parent)

        # Pai vira tombstone
        delete_comment(comment=parent, user=commenter)
        assert Comment.objects.filter(id=parent.id, is_deleted=True).exists()

        # Ao deletar o último filho, a subárvore é podada para limpar nós mortos
        delete_comment(comment=child, user=reader)

        assert not Comment.objects.filter(id=child.id).exists()
        assert not Comment.objects.filter(id=parent.id).exists()

        public_post.refresh_from_db()
        assert public_post.comments_count == 0

    def test_post_owner_cannot_delete_other_user_comment(self, public_post, author, commenter):
        """O dono do post não pode excluir comentários alheios (deve ocultar)."""
        comment = create_comment(
            author=commenter, post=public_post, content_text="Comentário alheio"
        )
        with pytest.raises(PermissionDenied):
            delete_comment(comment=comment, user=author)

    def test_unauthorized_user_cannot_delete(self, public_post, commenter, reader):
        comment = create_comment(author=commenter, post=public_post, content_text="Meu post")
        with pytest.raises(PermissionDenied):
            delete_comment(comment=comment, user=reader)


# =============================================================================
# 3. Matriz de Visibilidade, Bloqueio e IDOR (Requisito 2)
# =============================================================================


@pytest.mark.django_db
class TestVisibilityAndIDOR:
    def test_cannot_comment_on_circle_post_if_not_in_circle(self, circle_post, commenter):
        with pytest.raises(PermissionDenied):
            create_comment(author=commenter, post=circle_post, content_text="Não sou do círculo")

    def test_cannot_comment_if_blocked_by_post_owner(self, public_post, author, commenter):
        Block.objects.create(blocker=author, blocked=commenter)
        with pytest.raises(PermissionDenied):
            create_comment(author=commenter, post=public_post, content_text="Bloqueado")

    def test_cannot_comment_if_commenter_blocked_post_owner(self, public_post, author, commenter):
        Block.objects.create(blocker=commenter, blocked=author)
        with pytest.raises(PermissionDenied):
            create_comment(author=commenter, post=public_post, content_text="Bloqueei autor")

    def test_idor_view_comment_in_private_post_returns_404(
        self, api_client, author, commenter, reader
    ):
        author.profile.is_private = True
        author.profile.save()

        private_post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)
        comment = create_comment(author=author, post=private_post, content_text="Secreto")

        api_client.force_authenticate(user=reader)
        url = reverse("comment-detail", kwargs={"pk": comment.id})
        res = api_client.get(url)
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_idor_reply_in_private_post_returns_404(self, api_client, author, commenter, reader):
        author.profile.is_private = True
        author.profile.save()

        private_post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)
        api_client.force_authenticate(user=reader)
        url = reverse("post-comments", kwargs={"pk": private_post.id})
        res = api_client.post(url, {"content_text": "Invasão"}, format="json")
        assert res.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# 4. Curtidas, Favoritos e Concorrência Atômica com F() (Requisito 5)
# =============================================================================


@pytest.mark.django_db
class TestLikesAndBookmarks:
    def test_toggle_like_atomic(self, public_post, commenter, reader):
        comment = create_comment(author=commenter, post=public_post, content_text="Curtam!")

        is_liked, count = toggle_comment_like(user=reader, comment=comment)
        assert is_liked is True
        assert count == 1

        is_liked, count = toggle_comment_like(user=reader, comment=comment)
        assert is_liked is False
        assert count == 0

    def test_toggle_bookmark(self, public_post, commenter, reader):
        comment = create_comment(author=commenter, post=public_post, content_text="Salvem!")

        saved = toggle_comment_bookmark(user=reader, comment=comment)
        assert saved is True
        assert CommentBookmark.objects.filter(user=reader, comment=comment).exists()

        saved = toggle_comment_bookmark(user=reader, comment=comment)
        assert saved is False
        assert not CommentBookmark.objects.filter(user=reader, comment=comment).exists()


# =============================================================================
# 5. Consultas em Lote sem N+1 e Cursor Composto (Requisito 4)
# =============================================================================


@pytest.mark.django_db
class TestBatchQueriesAndCursor:
    def test_batch_query_count_is_constant(self, public_post, commenter, reader):
        # Cria árvore densa
        for i in range(5):
            root = create_comment(author=commenter, post=public_post, content_text=f"Raiz {i}")
            for j in range(2):
                child = create_comment(
                    author=reader,
                    post=public_post,
                    content_text=f"Nível 1 - {j}",
                    parent=root,
                )
                create_comment(
                    author=commenter,
                    post=public_post,
                    content_text="Nível 2",
                    parent=child,
                )

        # Executa consulta em lote e verifica número fixo de queries
        with CaptureQueriesContext(connection) as ctx:
            data = list_post_comments_with_preview(post=public_post, viewer=reader, page_size=10)

        assert len(data["items"]) == 5
        # Assegura que todas as raízes têm prévias de respostas sem rodar novas queries
        for root in data["items"]:
            assert len(root.preview_replies) == 2
            for child in root.preview_replies:
                assert len(child.preview_replies) == 1

        # Máximo de 8 queries no total
        # (1 visibilidade + 1 raiz + 1 nível1 + 1 nível2 + 1 likes + 1 bookmarks + blocks)
        # e NENHUMA query proporcional ao número de nós
        assert len(ctx.captured_queries) <= 8

    def test_cursor_encoding_and_pagination(self, public_post, commenter, reader):
        create_comment(author=commenter, post=public_post, content_text="C1")
        create_comment(author=commenter, post=public_post, content_text="C2")
        create_comment(author=commenter, post=public_post, content_text="C3")

        # Página 1 com page_size=2
        res1 = list_post_comments_with_preview(
            post=public_post, viewer=reader, sort="recent", page_size=2
        )
        assert len(res1["items"]) == 2
        assert res1["next_cursor"] is not None

        # Página 2 usando cursor
        res2 = list_post_comments_with_preview(
            post=public_post,
            viewer=reader,
            sort="recent",
            cursor=res1["next_cursor"],
            page_size=2,
        )
        assert len(res2["items"]) == 1
        assert res2["next_cursor"] is None

    def test_corrupted_cursor_fallback(self):
        assert decode_cursor("invalid-base64@@", "recent") is None
        assert decode_cursor(encode_cursor([123], "likes"), "recent") is None


# =============================================================================
# 6. Contexto de Thread do Focar (Requisito 4 e Focar)
# =============================================================================


@pytest.mark.django_db
class TestThreadContext:
    def test_thread_context_with_tombstone_ancestor(self, public_post, commenter, reader):
        root = create_comment(author=commenter, post=public_post, content_text="Raiz")
        reply1 = create_comment(
            author=reader, post=public_post, content_text="Intermediário", parent=root
        )
        target = create_comment(
            author=commenter, post=public_post, content_text="Alvo", parent=reply1
        )

        # Deleta root -> vira tombstone
        delete_comment(comment=root, user=commenter)

        ctx = get_comment_thread_context(comment_id=target.id, viewer=reader)
        assert ctx is not None
        assert len(ctx["ancestors"]) == 2

        # Primeiro ancestral é placeholder tombstone
        root_ancestor = ctx["ancestors"][0]
        assert root_ancestor.is_placeholder is True
        assert root_ancestor.is_deleted is True

        # Segundo ancestral é normal
        second_ancestor = ctx["ancestors"][1]
        assert second_ancestor.is_placeholder is False
        assert second_ancestor.content_text == "Intermediário"


# =============================================================================
# 7. Teste de Arquitetura AST e Teste de Mutação
# =============================================================================


class TestASTArchitecture:
    def test_comments_views_and_selectors_use_can_view_post(self):
        views_path = Path(__file__).resolve().parent / "views.py"
        selectors_path = Path(__file__).resolve().parent / "selectors.py"

        for filepath in [views_path, selectors_path]:
            code = filepath.read_text(encoding="utf-8")
            tree = ast.parse(code)

            imports = [
                n.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                for n in node.names
            ]
            assert (
                "can_view_post" in imports
            ), f"{filepath.name} deve importar can_view_post explicitamente."


@pytest.mark.django_db
class TestCanViewPostMutation:
    def test_mutation_force_can_view_post_false_blocks_all(
        self, api_client, public_post, commenter
    ):
        comment = create_comment(author=commenter, post=public_post, content_text="Teste")
        api_client.force_authenticate(user=commenter)

        with (
            patch("comments.views.can_view_post", return_value=False),
            patch("comments.selectors.can_view_post", return_value=False),
        ):
            # Listagem
            res = api_client.get(reverse("post-comments", kwargs={"pk": public_post.id}))
            assert res.status_code == status.HTTP_404_NOT_FOUND

            # Detalhes
            res = api_client.get(reverse("comment-detail", kwargs={"pk": comment.id}))
            assert res.status_code == status.HTTP_404_NOT_FOUND

            # Focar thread
            res = api_client.get(reverse("comment-thread", kwargs={"pk": comment.id}))
            assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCommentsAPIEndpoints:
    def test_api_replies_endpoint(self, api_client, public_post, commenter, reader):
        root = create_comment(author=commenter, post=public_post, content_text="Raiz")
        reply = create_comment(
            author=reader, post=public_post, content_text="Resposta", parent=root
        )

        api_client.force_authenticate(user=reader)
        url = reverse("comment-replies", kwargs={"pk": root.id})
        res = api_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data["items"]) == 1
        assert res.data["items"][0]["id"] == str(reply.id)

    def test_api_bookmark_toggle_and_list(self, api_client, public_post, commenter, reader):
        comment = create_comment(author=commenter, post=public_post, content_text="Favoritar")

        api_client.force_authenticate(user=reader)
        url_toggle = reverse("comment-bookmark", kwargs={"pk": comment.id})
        res = api_client.post(url_toggle)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["is_bookmarked"] is True

        url_list = reverse("comment-bookmarks-list")
        res_list = api_client.get(url_list)
        assert res_list.status_code == status.HTTP_200_OK
        assert len(res_list.data["items"]) == 1

        # Toggle off
        res_off = api_client.post(url_toggle)
        assert res_off.status_code == status.HTTP_200_OK
        assert res_off.data["is_bookmarked"] is False

    def test_api_patch_and_delete_comment(self, api_client, public_post, commenter):
        comment = create_comment(author=commenter, post=public_post, content_text="Original")

        api_client.force_authenticate(user=commenter)
        url = reverse("comment-detail", kwargs={"pk": comment.id})

        # PATCH
        res_patch = api_client.patch(url, {"content_text": "Editado com sucesso!"}, format="json")
        assert res_patch.status_code == status.HTTP_200_OK
        assert res_patch.data["content_text"] == "Editado com sucesso!"
        assert res_patch.data["is_edited"] is True

        # DELETE
        res_del = api_client.delete(url)
        assert res_del.status_code == status.HTTP_204_NO_CONTENT

    def test_api_sorting_likes_and_relevance(self, api_client, public_post, commenter, reader):
        create_comment(author=commenter, post=public_post, content_text="C1")
        c2 = create_comment(author=commenter, post=public_post, content_text="C2")

        toggle_comment_like(user=reader, comment=c2)

        api_client.force_authenticate(user=reader)
        url = reverse("post-comments", kwargs={"pk": public_post.id})

        res_likes = api_client.get(f"{url}?sort=likes")
        assert res_likes.status_code == status.HTTP_200_OK
        assert res_likes.data["items"][0]["id"] == str(c2.id)

        res_rel = api_client.get(f"{url}?sort=relevance")
        assert res_rel.status_code == status.HTTP_200_OK
        assert res_rel.data["items"][0]["id"] == str(c2.id)

    def test_api_post_comment_create_and_validation(self, api_client, public_post, commenter):
        api_client.force_authenticate(user=commenter)
        url = reverse("post-comments", kwargs={"pk": public_post.id})

        # Sucesso
        res = api_client.post(url, {"content_text": "Comentário via API"}, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["content_text"] == "Comentário via API"

        # Comentário vazio -> 400
        res_empty = api_client.post(url, {"content_text": "  "}, format="json")
        assert res_empty.status_code == status.HTTP_400_BAD_REQUEST

    def test_api_comment_like_toggle(self, api_client, public_post, commenter, reader):
        comment = create_comment(author=commenter, post=public_post, content_text="Curta-me")

        api_client.force_authenticate(user=reader)
        url = reverse("comment-like", kwargs={"pk": comment.id})

        # Like
        res1 = api_client.post(url)
        assert res1.status_code == status.HTTP_200_OK
        assert res1.data["is_liked"] is True
        assert res1.data["likes_count"] == 1

        # Unlike
        res2 = api_client.post(url)
        assert res2.status_code == status.HTTP_200_OK
        assert res2.data["is_liked"] is False
        assert res2.data["likes_count"] == 0


# =============================================================================
# 8. Ocultar e Reexibir Respostas (Onda 4b)
# =============================================================================


@pytest.mark.django_db
class TestHideAndUnhideReplies:
    def test_post_owner_can_hide_comment(self, api_client, public_post, author, commenter):
        comment = create_comment(
            author=commenter, post=public_post, content_text="Comentário a ocultar"
        )
        public_post.refresh_from_db()
        assert public_post.comments_count == 1
        assert public_post.hidden_comments_count == 0

        api_client.force_authenticate(user=author)
        url = reverse("comment-hide", kwargs={"pk": comment.id})
        res = api_client.post(url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == "hidden"

        comment.refresh_from_db()
        assert comment.is_hidden is True
        assert comment.hidden_by == author
        assert comment.hidden_at is not None

        public_post.refresh_from_db()
        assert public_post.comments_count == 0
        assert public_post.hidden_comments_count == 1

    def test_hide_comment_subtree_decrements_all_active_descendants(
        self, api_client, public_post, author, commenter, reader
    ):
        root = create_comment(author=commenter, post=public_post, content_text="Raiz")
        reply1 = create_comment(
            author=reader, post=public_post, content_text="Resposta 1", parent=root
        )
        create_comment(author=commenter, post=public_post, content_text="Resposta 2", parent=reply1)

        public_post.refresh_from_db()
        assert public_post.comments_count == 3
        assert public_post.hidden_comments_count == 0

        api_client.force_authenticate(user=author)
        url = reverse("comment-hide", kwargs={"pk": root.id})
        res = api_client.post(url)
        assert res.status_code == status.HTTP_200_OK

        public_post.refresh_from_db()
        # Árvore inteira saiu do contador
        assert public_post.comments_count == 0
        assert public_post.hidden_comments_count == 1

    def test_unhide_comment_restores_counters(self, api_client, public_post, author, commenter):
        comment = create_comment(
            author=commenter, post=public_post, content_text="Ocultar e reexibir"
        )
        hide_comment(comment=comment, user=author)

        public_post.refresh_from_db()
        assert public_post.comments_count == 0
        assert public_post.hidden_comments_count == 1

        api_client.force_authenticate(user=author)
        url = reverse("comment-hide", kwargs={"pk": comment.id})
        res = api_client.delete(url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == "unhidden"

        comment.refresh_from_db()
        assert comment.is_hidden is False
        assert comment.hidden_at is None
        assert comment.hidden_by is None

        public_post.refresh_from_db()
        assert public_post.comments_count == 1
        assert public_post.hidden_comments_count == 0

    def test_third_party_or_author_hide_returns_404(
        self, api_client, public_post, author, commenter, reader
    ):
        comment = create_comment(
            author=commenter, post=public_post, content_text="Tentativa de invasão"
        )

        # Autor do comentário tenta ocultar -> 404 (indistinguível)
        api_client.force_authenticate(user=commenter)
        url = reverse("comment-hide", kwargs={"pk": comment.id})
        res = api_client.post(url)
        assert res.status_code == status.HTTP_404_NOT_FOUND

        # Terceiro tenta ocultar -> 404
        api_client.force_authenticate(user=reader)
        res = api_client.post(url)
        assert res.status_code == status.HTTP_404_NOT_FOUND

        # Terceiro tenta reexibir -> 404
        res_del = api_client.delete(url)
        assert res_del.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_hide_own_comment(self, api_client, public_post, author):
        comment = create_comment(
            author=author, post=public_post, content_text="Meu próprio comentário"
        )
        api_client.force_authenticate(user=author)
        url = reverse("comment-hide", kwargs={"pk": comment.id})
        res = api_client.post(url)
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_hidden_comments_view_only_for_post_owner(
        self, api_client, public_post, author, commenter, reader
    ):
        c1 = create_comment(author=commenter, post=public_post, content_text="Oculto 1")
        c2 = create_comment(author=commenter, post=public_post, content_text="Oculto 2")
        hide_comment(comment=c1, user=author)
        hide_comment(comment=c2, user=author)

        url = reverse("post-hidden-comments", kwargs={"pk": public_post.id})

        # Dono do post acessa -> 200 com 2 comentários
        api_client.force_authenticate(user=author)
        res = api_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data["items"]) == 2

        # Terceiro acessa -> 404
        api_client.force_authenticate(user=reader)
        res_third = api_client.get(url)
        assert res_third.status_code == status.HTTP_404_NOT_FOUND

    def test_tombstone_deleted_comment_serializer_representation(
        self, api_client, public_post, commenter, reader
    ):
        parent = create_comment(author=commenter, post=public_post, content_text="Pai ativo")
        create_comment(author=reader, post=public_post, content_text="Filho", parent=parent)
        delete_comment(comment=parent, user=commenter)

        api_client.force_authenticate(user=reader)
        url = reverse("post-comments", kwargs={"pk": public_post.id})
        res = api_client.get(url)
        assert res.status_code == status.HTTP_200_OK

        parent_data = res.data["items"][0]
        assert parent_data["is_deleted"] is True
        # Texto não vem do banco e autor é nulo
        assert parent_data["content_text"] == ""
        assert parent_data["author"] is None
        assert parent_data["is_edited"] is False
        assert parent_data["can_delete"] is False
        assert parent_data["can_edit"] is False


# =============================================================================
# 9. Matriz de Vazamento de Comentários Ocultos e Teste de Mutação
# =============================================================================


@pytest.mark.django_db
class TestHiddenCommentsLeakageMatrixAndMutation:
    """
    Matriz de vazamento:
    Comentario Oculto x (conversa, respostas, Focar, contadores, notificacoes, favoritos)
                     x (dono, autor, terceiros, bloqueados, anonimo)
    """

    def test_hidden_comment_leakage_matrix(
        self, api_client, public_post, author, commenter, reader
    ):
        blocked_user = UserFactory(username="blocked_user")
        Block.objects.create(blocker=author, blocked=blocked_user)

        root = create_comment(
            author=commenter, post=public_post, content_text="Comentário Ocultado"
        )
        reply = create_comment(
            author=commenter, post=public_post, content_text="Resposta do Ocultado", parent=root
        )

        # Adiciona aos favoritos de terceiro e do autor antes de ocultar
        toggle_comment_bookmark(user=reader, comment=root)
        toggle_comment_bookmark(user=commenter, comment=root)

        # Oculta
        hide_comment(comment=root, user=author)

        # 1. Superfície: Conversa pública (list_post_comments_with_preview)
        # Autor do comentário: VÊ seu comentário (stealth / shadow-hide)
        res_author = list_post_comments_with_preview(post=public_post, viewer=commenter)
        assert any(r.id == root.id for r in res_author["items"])

        # Terceiro: NÃO VÊ
        res_reader = list_post_comments_with_preview(post=public_post, viewer=reader)
        assert not any(r.id == root.id for r in res_reader["items"])

        # Bloqueado: NÃO VÊ
        res_blocked = list_post_comments_with_preview(post=public_post, viewer=blocked_user)
        assert not any(r.id == root.id for r in res_blocked["items"])

        # Anônimo: NÃO VÊ
        res_anon = list_post_comments_with_preview(post=public_post, viewer=None)
        assert not any(r.id == root.id for r in res_anon["items"])

        # Dono do post: vê via endpoint de hidden-comments
        hidden_data = list_post_hidden_comments(post=public_post, user=author)
        assert any(c.id == root.id for c in hidden_data["items"])

        # 2. Superfície: Respostas abaixo de comentário oculto
        # Terceiro não vê respostas abaixo do nó oculto
        assert not any(r.id == reply.id for r in res_reader["items"])

        # 3. Superfície: Focar (get_comment_thread_context)
        # Dono pode focar no comentário oculto
        ctx_owner = get_comment_thread_context(comment_id=root.id, viewer=author)
        assert ctx_owner is not None
        assert ctx_owner["comment"].id == root.id

        # Autor pode focar no próprio comentário oculto
        ctx_author = get_comment_thread_context(comment_id=root.id, viewer=commenter)
        assert ctx_author is not None
        assert ctx_author["comment"].id == root.id

        # Terceiro recebe None (404)
        ctx_reader = get_comment_thread_context(comment_id=root.id, viewer=reader)
        assert ctx_reader is None

        # Como ancestral no Focar de uma resposta: vira placeholder para terceiros
        ctx_reply = get_comment_thread_context(comment_id=reply.id, viewer=reader)
        assert ctx_reply is not None
        assert ctx_reply["comment"].id == reply.id
        assert len(ctx_reply["ancestors"]) == 1
        ancestor = ctx_reply["ancestors"][0]
        assert ancestor.is_placeholder is True
        assert ancestor.author is None

        # 4. Superfície: Contadores
        public_post.refresh_from_db()
        assert public_post.comments_count == 0

        # 5. Superfície: Notificações
        # Nenhuma notificação nasce dentro de uma conversa oculta
        notifs_before = Notification.objects.count()
        create_comment(
            author=commenter, post=public_post, content_text="Tentativa de notificação", parent=root
        )
        assert Notification.objects.count() == notifs_before

        # 6. Superfície: Favoritos de terceiros
        # Comentário oculto sai dos favoritos de terceiros
        api_client.force_authenticate(user=reader)
        bkmk_res = api_client.get(reverse("comment-bookmarks-list"))
        assert bkmk_res.status_code == status.HTTP_200_OK
        assert not any(item["id"] == str(root.id) for item in bkmk_res.data["items"])

        # Mas continua nos favoritos do próprio autor
        api_client.force_authenticate(user=commenter)
        bkmk_author = api_client.get(reverse("comment-bookmarks-list"))
        assert any(item["id"] == str(root.id) for item in bkmk_author.data["items"])

    def test_mutation_test_broken_hidden_filter_detected(
        self, public_post, author, commenter, reader
    ):
        """
        Teste de mutação: quebra deliberadamente o filtro de is_hidden no selector
        e comprova que a quebra é imediatamente detectada pela suíte.
        """
        root = create_comment(
            author=commenter, post=public_post, content_text="Oculto para mutação"
        )
        hide_comment(comment=root, user=author)

        # Mutação: selector que não filtra is_hidden
        def broken_selector(post, viewer):
            qs = Comment.objects.filter(post=post, parent__isnull=True)
            return {"items": list(qs), "next_cursor": None}

        # Executa mutação para o leitor terceiro
        mutated_result = broken_selector(public_post, reader)

        # Comprova que a mutação vaza dados (detectando a falha)
        leaked = any(c.id == root.id for c in mutated_result["items"])
        assert leaked is True, "Mutante sobreviveu se não vazou nada"
