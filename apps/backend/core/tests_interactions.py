"""
Testes de interações sociais: curtir, favoritar, rascunhos e paginação de favoritos.
(ADR-N2 / Onda 3b)
"""

import pytest
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.factories import PostFactory, UserFactory
from core.models import Block, Draft, Notification, Post, PostBookmark, PostLike, UserProfile
from core.services.posts import list_bookmarked_posts


def _client_for(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


@pytest.mark.django_db(transaction=True)
class TestPostLike:
    def test_curtir_post_publico_incrementa_contador_e_gera_notificacao(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        client = _client_for(viewer)
        res = client.post(f"/api/posts/{post.id}/like/")
        assert res.status_code == status.HTTP_201_CREATED
        assert res.json()["detail"] == "Publicação curtida."

        post.refresh_from_db()
        assert post.likes_count == 1
        assert PostLike.objects.filter(post=post, user=viewer).exists()

        notif = Notification.objects.filter(
            recipient=author, notification_type=Notification.Type.LIKE
        ).first()
        assert notif is not None
        assert notif.sender == viewer
        assert notif.ref_id == post.id

    def test_curtir_proprio_post_incrementa_contador_mas_nao_notifica(self):
        author = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        client = _client_for(author)
        res = client.post(f"/api/posts/{post.id}/like/")
        assert res.status_code == status.HTTP_201_CREATED

        post.refresh_from_db()
        assert post.likes_count == 1
        assert not Notification.objects.filter(
            recipient=author, notification_type=Notification.Type.LIKE
        ).exists()

    def test_curtir_post_inacessivel_retorna_404(self):
        author = UserFactory()
        prof, _ = UserProfile.objects.get_or_create(user=author)
        prof.is_private = True
        prof.save()

        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        client = _client_for(viewer)
        res = client.post(f"/api/posts/{post.id}/like/")
        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert not PostLike.objects.filter(post=post, user=viewer).exists()

    def test_descurtir_post_decrementa_contador(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC, likes_count=1)
        PostLike.objects.create(post=post, user=viewer)

        client = _client_for(viewer)
        res = client.delete(f"/api/posts/{post.id}/like/")
        assert res.status_code == status.HTTP_204_NO_CONTENT

        post.refresh_from_db()
        assert post.likes_count == 0
        assert not PostLike.objects.filter(post=post, user=viewer).exists()

    def test_descurtir_post_nao_curtido_retorna_404(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        client = _client_for(viewer)
        res = client.delete(f"/api/posts/{post.id}/like/")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_concorrencia_curtidas_constraint_unicidade(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        PostLike.objects.create(post=post, user=viewer)
        with pytest.raises(IntegrityError):
            PostLike.objects.create(post=post, user=viewer)


@pytest.mark.django_db(transaction=True)
class TestPostBookmark:
    def test_salvar_e_remover_favorito(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        client = _client_for(viewer)
        res = client.post(f"/api/posts/{post.id}/bookmark/")
        assert res.status_code == status.HTTP_201_CREATED
        post.refresh_from_db()
        assert post.bookmarks_count == 1
        assert PostBookmark.objects.filter(post=post, user=viewer).exists()

        res_list = client.get("/api/posts/bookmarks/")
        assert res_list.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in res_list.json()]
        assert str(post.id) in ids

        res_del = client.delete(f"/api/posts/{post.id}/bookmark/")
        assert res_del.status_code == status.HTTP_204_NO_CONTENT
        post.refresh_from_db()
        assert post.bookmarks_count == 0
        assert not PostBookmark.objects.filter(post=post, user=viewer).exists()

    def test_favorito_de_post_que_ficou_inacessivel_nao_aparece_na_lista(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        PostBookmark.objects.create(post=post, user=viewer)

        client = _client_for(viewer)
        res_init = client.get("/api/posts/bookmarks/")
        assert str(post.id) in [p["id"] for p in res_init.json()]

        Block.objects.create(blocker=author, blocked=viewer)

        res_after = client.get("/api/posts/bookmarks/")
        assert str(post.id) not in [p["id"] for p in res_after.json()]

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

        qs1 = list_bookmarked_posts(user=user, limit=2)
        assert len(qs1) == 2
        last_id = str(qs1[1].pk)

        resp = client.get(f"/api/posts/bookmarks/?cursor={last_id}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(p1.pk)


@pytest.mark.django_db
class TestDrafts:
    def test_crud_rascunho_isolado_por_autor(self):
        user1 = UserFactory()
        user2 = UserFactory()

        c1 = _client_for(user1)
        c2 = _client_for(user2)

        res = c1.post("/api/posts/drafts/", {"content_text": "Meu rascunho secreto"})
        assert res.status_code == status.HTTP_201_CREATED
        draft_id = res.json()["id"]

        list_res = c1.get("/api/posts/drafts/")
        assert list_res.status_code == status.HTTP_200_OK
        assert len(list_res.json()) == 1
        assert list_res.json()[0]["content_text"] == "Meu rascunho secreto"

        list_res2 = c2.get("/api/posts/drafts/")
        assert list_res2.status_code == status.HTTP_200_OK
        assert len(list_res2.json()) == 0

        del_res2 = c2.delete(f"/api/posts/drafts/{draft_id}/")
        assert del_res2.status_code == status.HTTP_404_NOT_FOUND
        assert Draft.objects.filter(id=draft_id).exists()

        del_res1 = c1.delete(f"/api/posts/drafts/{draft_id}/")
        assert del_res1.status_code == status.HTTP_204_NO_CONTENT
        assert not Draft.objects.filter(id=draft_id).exists()

    def test_draft_max_chars_validation(self):
        user = UserFactory()
        client = _client_for(user)
        res = client.post("/api/posts/drafts/", {"content_text": "x" * 3001})
        assert res.status_code == status.HTTP_400_BAD_REQUEST
