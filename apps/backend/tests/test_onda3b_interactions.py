"""
Testes dedicados às interações sociais e notificações da Onda 3b (T9 / Gate G4):
- Curtidas (PostLike) e contagem atômica
- Favoritos (PostBookmark) e isolamento quando post torna-se inacessível
- Rascunhos (Draft) e isolamento rigoroso por autor
- Motor de notificações: disparo em on_commit, idempotência, filtros de privacidade (bloqueio/mute/self/post inacessível)
- Concorrência de curtidas (Postgres constraint check)
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile
from notifications.models import Notification
from posts.models import Draft, Post, PostBookmark, PostLike
from social.models import Block, Follow, Mute
from tests.factories import PostFactory, UserFactory

User = get_user_model()


def _client_for(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.cookies["access_token"] = str(refresh.access_token)
    return client


# ---------------------------------------------------------------------------
# Curtidas (PostLike)
# ---------------------------------------------------------------------------


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

        # Verifica se gerou notificação para o autor
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

        viewer = UserFactory()  # não segue
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


# ---------------------------------------------------------------------------
# Favoritos (PostBookmark)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestPostBookmark:
    def test_salvar_e_remover_favorito(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        client = _client_for(viewer)
        # Salva
        res = client.post(f"/api/posts/{post.id}/bookmark/")
        assert res.status_code == status.HTTP_201_CREATED
        post.refresh_from_db()
        assert post.bookmarks_count == 1
        assert PostBookmark.objects.filter(post=post, user=viewer).exists()

        # Lista favoritos
        res_list = client.get("/api/posts/bookmarks/")
        assert res_list.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in res_list.json()]
        assert str(post.id) in ids

        # Remove
        res_del = client.delete(f"/api/posts/{post.id}/bookmark/")
        assert res_del.status_code == status.HTTP_204_NO_CONTENT
        post.refresh_from_db()
        assert post.bookmarks_count == 0
        assert not PostBookmark.objects.filter(post=post, user=viewer).exists()

    def test_favorito_de_post_que_ficou_inacessivel_nao_aparece_na_lista(self):
        """
        Requisito crítico: se o usuário favoritou um post, mas o autor depois
        bloqueou o usuário ou tornou a conta privada, o post NÃO deve vazar
        na listagem de favoritos.
        """
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        # Favorita enquanto público
        PostBookmark.objects.create(post=post, user=viewer)

        client = _client_for(viewer)
        # Visível inicialmente
        res_init = client.get("/api/posts/bookmarks/")
        assert str(post.id) in [p["id"] for p in res_init.json()]

        # Autor bloqueia o viewer
        Block.objects.create(blocker=author, blocked=viewer)

        # Post não pode mais aparecer nos favoritos
        res_after = client.get("/api/posts/bookmarks/")
        assert str(post.id) not in [p["id"] for p in res_after.json()]


# ---------------------------------------------------------------------------
# Rascunhos (Draft)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDrafts:
    def test_crud_rascunho_isolado_por_autor(self):
        user1 = UserFactory()
        user2 = UserFactory()

        c1 = _client_for(user1)
        c2 = _client_for(user2)

        # User 1 cria rascunho
        res = c1.post("/api/posts/drafts/", {"content_text": "Meu rascunho secreto"})
        assert res.status_code == status.HTTP_201_CREATED
        draft_id = res.json()["id"]

        # User 1 lista seus rascunhos
        list_res = c1.get("/api/posts/drafts/")
        assert list_res.status_code == status.HTTP_200_OK
        assert len(list_res.json()) == 1
        assert list_res.json()[0]["content_text"] == "Meu rascunho secreto"

        # User 2 lista seus rascunhos (deve vir vazio!)
        list_res2 = c2.get("/api/posts/drafts/")
        assert list_res2.status_code == status.HTTP_200_OK
        assert len(list_res2.json()) == 0

        # User 2 tenta excluir rascunho de User 1 (404)
        del_res2 = c2.delete(f"/api/posts/drafts/{draft_id}/")
        assert del_res2.status_code == status.HTTP_404_NOT_FOUND
        assert Draft.objects.filter(id=draft_id).exists()

        # User 1 exclui seu próprio rascunho (204)
        del_res1 = c1.delete(f"/api/posts/drafts/{draft_id}/")
        assert del_res1.status_code == status.HTTP_204_NO_CONTENT
        assert not Draft.objects.filter(id=draft_id).exists()


# ---------------------------------------------------------------------------
# Motor de Notificações e Privacidade
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestNotificationEnginePrivacy:
    def test_curtir_post_com_bloqueio_mutuo_nao_gera_notificacao(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        # Autor bloqueou viewer
        Block.objects.create(blocker=author, blocked=viewer)

        # Tentar curtir diretamente via serviço
        from posts.services import like_post

        success = like_post(user=viewer, post_id=post.id)
        assert success is False
        assert not Notification.objects.filter(recipient=author).exists()

    def test_curtir_post_quando_autor_silenciou_sender_nao_gera_notificacao(self):
        author = UserFactory()
        viewer = UserFactory()
        post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC)

        # Autor silenciou viewer
        Mute.objects.create(muter=author, muted=viewer)

        client = _client_for(viewer)
        res = client.post(f"/api/posts/{post.id}/like/")
        assert res.status_code == status.HTTP_201_CREATED

        # Curtida registrada, mas notificação suprimida por mute
        assert not Notification.objects.filter(recipient=author, sender=viewer).exists()

    def test_seguir_usuario_gera_notificacao(self):
        follower = UserFactory()
        followed = UserFactory()

        client = _client_for(follower)
        res = client.post(f"/api/social/follow/{followed.username}/")
        assert res.status_code == status.HTTP_201_CREATED

        notif = Notification.objects.filter(
            recipient=followed, sender=follower, notification_type=Notification.Type.FOLLOW
        ).first()
        assert notif is not None

    def test_notificacao_idempotencia(self):
        from notifications.services import create_notification

        user1 = UserFactory()
        user2 = UserFactory()
        post = PostFactory(author=user1)

        n1 = create_notification(
            recipient=user1,
            sender=user2,
            notification_type=Notification.Type.LIKE,
            ref_id=str(post.id),
        )
        n2 = create_notification(
            recipient=user1,
            sender=user2,
            notification_type=Notification.Type.LIKE,
            ref_id=str(post.id),
        )
        assert n1.id == n2.id
        assert Notification.objects.filter(recipient=user1, ref_id=post.id).count() == 1


# ---------------------------------------------------------------------------
# Testes complementares para cobertura > 93% (Serializers e Views)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCoverageEnhancements:
    def test_follow_serializer(self):
        from social.serializers import FollowSerializer

        u1 = UserFactory(username="f_user1")
        u2 = UserFactory(username="f_user2")
        f = Follow.objects.create(follower=u1, followed=u2, is_close_friend=True)
        data = FollowSerializer(f).data
        assert data["follower_username"] == "f_user1"
        assert data["followed_username"] == "f_user2"
        assert data["is_close_friend"] is True

    def test_notification_views_mark_read_and_mark_all(self):
        user = UserFactory()
        other = UserFactory()
        n1 = Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.FOLLOW
        )
        n2 = Notification.objects.create(
            recipient=user, sender=other, notification_type=Notification.Type.FOLLOW
        )

        client = _client_for(user)

        # GET lista notificações
        res_list = client.get("/api/notifications/")
        assert res_list.status_code == status.HTTP_200_OK
        assert len(res_list.json()) == 2

        # PATCH marca uma como lida
        res_patch = client.patch(f"/api/notifications/{n1.id}/read/")
        assert res_patch.status_code == status.HTTP_200_OK
        n1.refresh_from_db()
        assert n1.read is True

        # PATCH notificação inexistente dá 404
        res_patch_404 = client.patch("/api/notifications/999999/read/")
        assert res_patch_404.status_code == status.HTTP_404_NOT_FOUND

        # POST marca todas como lidas
        res_all = client.post("/api/notifications/mark-all-read/")
        assert res_all.status_code == status.HTTP_200_OK
        n2.refresh_from_db()
        assert n2.read is True

    def test_delete_post_by_third_party_returns_403(self):
        author = UserFactory()
        other = UserFactory()
        post = PostFactory(author=author)

        client = _client_for(other)
        res = client.delete(f"/api/posts/{post.id}/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_draft_max_chars_validation(self):
        user = UserFactory()
        client = _client_for(user)
        res = client.post("/api/posts/drafts/", {"content_text": "a" * 3001})
        assert res.status_code == status.HTTP_400_BAD_REQUEST
