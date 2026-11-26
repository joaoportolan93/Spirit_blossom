"""
Suíte de testes da Onda 7b:
- Extração pura de @menções e #hashtags (text_entities)
- Sincronização transacional de Hashtag, filtro ?hashtag= e /api/hashtags/trending/ (ADR-N21/N24)
- Notificações de menção em posts e comentários (privacidade, círculo, bloqueio, mute, dedup)
- Sugestões éticas para seguir (/api/social/suggestions/) e FeatureFlag follow_suggestions
- terms_accepted_at em /api/users/settings/
"""

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from conftest import set_auth_cookies
from core.factories import BlockFactory, FollowFactory, PostFactory, UserFactory
from core.models import (
    FeatureFlag,
    Follow,
    Hashtag,
    Mute,
    Notification,
    Post,
    User,
    UserProfile,
)
from core.services.posts import create_post, update_post
from core.services.social import suggest_users_to_follow
from core.utils.text_entities import extract_hashtags, extract_mentions


def _client_for(user):
    client = APIClient()
    set_auth_cookies(client, user)
    return client


def _make_private(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.is_private = True
    profile.save(update_fields=["is_private"])
    if hasattr(user, "__dict__") and "profile" in user.__dict__:
        del user.__dict__["profile"]


# =============================================================================
# 1. Parsing Puro de Entidades (@menções e #hashtags)
# =============================================================================


class TestTextEntitiesParsing:
    def test_extract_mentions_valid_and_normalized(self):
        text = "Oi @Alice, (@bob123)! Veja @ALICE e @Carol99."
        assert extract_mentions(text) == ["alice", "bob123", "carol99"]

    def test_extract_mentions_ignores_emails_urls_and_invalid(self):
        text = (
            "Contato user@domain.com e a.b+c@alice.org. "
            "Link https://example.com/@alice e www.site.com/@bob. "
            "Curtas @ab, longas @" + "a" * 31 + ", underscore @foo_bar."
        )
        assert extract_mentions(text) == []

    def test_extract_mentions_empty_inputs(self):
        assert extract_mentions("") == []
        assert extract_mentions(None) == []

    def test_extract_hashtags_valid_unicode_and_dedup(self):
        text = "Hoje #Spirit_Blossom #Ação #ação #py3 (#Café2026)!"
        assert extract_hashtags(text) == ["spirit_blossom", "ação", "py3", "café2026"]

    def test_extract_hashtags_ignores_numeric_urls_and_entities(self):
        text = (
            "Números #123 #2026 #12_34 #___ e curta #a e longa #" + "z" * 51 + " "
            "URL https://example.com/page#section e www.site.org/#top e HTML &#123;"
        )
        assert extract_hashtags(text) == []

    def test_extract_hashtags_empty_inputs(self):
        assert extract_hashtags("") == []
        assert extract_hashtags(None) == []


# =============================================================================
# 2. Hashtags: Sync Transacional, Filtro e Trending com Privacidade (ADR-N21)
# =============================================================================


@pytest.mark.django_db
class TestHashtagsAndPrivacy:
    def test_create_and_edit_post_syncs_hashtags(self):
        author = UserFactory()
        client = _client_for(author)

        res = client.post(
            "/api/posts/",
            {"content_text": "Explorando #Lumen e #Python!"},
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED
        post_id = res.data["id"]

        post = Post.objects.get(pk=post_id)
        assert set(post.hashtags.values_list("name", flat=True)) == {"lumen", "python"}
        tag_obj = Hashtag.objects.get(name="lumen")
        assert str(tag_obj) == "#lumen"

        # Editar post substitui hashtags antigas pelas novas
        res_edit = client.patch(
            f"/api/posts/{post_id}/",
            {"content_text": "Agora só #Django"},
            format="json",
        )
        assert res_edit.status_code == status.HTTP_200_OK
        post.refresh_from_db()
        assert set(post.hashtags.values_list("name", flat=True)) == {"django"}

    def test_filter_posts_by_hashtag_respects_visibility_and_blocks(self):
        viewer = UserFactory()
        public_author = UserFactory()
        private_author = UserFactory()
        _make_private(private_author)
        circle_author = UserFactory()
        blocked_author = UserFactory()
        BlockFactory(blocker=viewer, blocked=blocked_author)

        p_public = create_post(
            author=public_author, content_text="Olá #Comunidade", visibility="public"
        )
        p_private = create_post(
            author=private_author, content_text="Privado #Comunidade", visibility="public"
        )
        p_circle = create_post(
            author=circle_author, content_text="Círculo #Comunidade", visibility="circle"
        )
        p_blocked = create_post(
            author=blocked_author, content_text="Bloq #Comunidade", visibility="public"
        )

        client = _client_for(viewer)
        res = client.get("/api/posts/?hashtag=comunidade")
        assert res.status_code == status.HTTP_200_OK
        ids = {p["id"] for p in res.json()}

        assert str(p_public.id) in ids
        assert str(p_private.id) not in ids
        assert str(p_circle.id) not in ids
        assert str(p_blocked.id) not in ids

        # Membro do círculo passa a ver o post de círculo no filtro
        Follow.objects.create(
            follower=viewer,
            followed=circle_author,
            status=Follow.Status.ACTIVE,
            is_close_friend=True,
        )
        res_circle = client.get("/api/posts/?hashtag=%23Comunidade")
        ids_circle = {p["id"] for p in res_circle.json()}
        assert str(p_circle.id) in ids_circle

    def test_explore_feed_filter_by_hashtag(self):
        viewer = UserFactory()
        author = UserFactory()
        muted_author = UserFactory()
        Mute.objects.create(muter=viewer, muted=muted_author)

        p_match = create_post(author=author, content_text="Post #arte", visibility="public")
        p_other = create_post(author=author, content_text="Post #musica", visibility="public")
        p_muted = create_post(author=muted_author, content_text="Post #arte", visibility="public")

        client = _client_for(viewer)
        res = client.get("/api/feed/explore/?hashtag=arte")
        assert res.status_code == status.HTTP_200_OK
        post_ids = {item["post_id"] for item in res.json()["items"]}
        assert str(p_match.id) in post_ids
        assert str(p_other.id) not in post_ids
        assert str(p_muted.id) not in post_ids

    def test_trending_hashtags_excludes_private_circle_and_blocked(self):
        viewer = UserFactory()
        pub1 = UserFactory()
        pub2 = UserFactory()
        priv = UserFactory()
        _make_private(priv)
        blocked = UserFactory()
        BlockFactory(blocker=blocked, blocked=viewer)

        create_post(author=pub1, content_text="Publico #aberta", visibility="public")
        create_post(author=pub2, content_text="Publico 2 #aberta", visibility="public")
        create_post(author=pub1, content_text="Só círculo #segredo", visibility="circle")
        create_post(author=priv, content_text="Conta privada #privada #aberta", visibility="public")
        create_post(
            author=blocked, content_text="Bloqueado #bloqueada #aberta", visibility="public"
        )

        client = _client_for(viewer)
        res = client.get("/api/hashtags/trending/?limit=10")
        assert res.status_code == status.HTTP_200_OK
        results = res.json()["results"]
        by_name = {item["name"]: item["posts_count"] for item in results}

        # Apenas os 2 posts públicos abertos contam para #aberta
        assert by_name == {"aberta": 2}
        assert "segredo" not in by_name
        assert "privada" not in by_name
        assert "bloqueada" not in by_name


# =============================================================================
# 3. Notificações de Menção (@username) com Privacidade, Bloqueio, Mute e Dedup
# =============================================================================


@pytest.mark.django_db(transaction=True)
class TestMentionNotifications:
    def test_post_mention_notifies_eligible_user_and_dedups_on_edit(self):
        author = UserFactory(username="author1")
        mentioned = UserFactory(username="alice1")
        client = _client_for(author)

        res = client.post(
            "/api/posts/",
            {"content_text": "Olá @alice1, veja isso!"},
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED
        post_id = res.data["id"]

        notifs = Notification.objects.filter(
            recipient=mentioned,
            sender=author,
            notification_type=Notification.Type.MENTION,
            ref_id=post_id,
        )
        assert notifs.count() == 1

        # Editar mantendo @alice1 não duplica notificação
        res_edit = client.patch(
            f"/api/posts/{post_id}/",
            {"content_text": "Editado para @alice1 novamente!"},
            format="json",
        )
        assert res_edit.status_code == status.HTTP_200_OK
        assert notifs.count() == 1

    def test_self_mention_and_inactive_and_preference_off_suppressed(self):
        author = UserFactory(username="selfuser")
        inactive = UserFactory(username="inactiveuser", is_active=False)
        muted_pref = UserFactory(username="noprefuser")
        muted_pref.profile.notify_mentions = False
        muted_pref.profile.save(update_fields=["notify_mentions"])

        create_post(
            author=author,
            content_text="Oi @selfuser @inactiveuser @noprefuser @naoexiste",
            visibility="public",
        )
        assert Notification.objects.filter(notification_type=Notification.Type.MENTION).count() == 0

    def test_mention_suppressed_by_block_and_mute_both_directions(self):
        author = UserFactory(username="sender1")
        u_blocked_by_author = UserFactory(username="blocked1")
        u_blocker_of_author = UserFactory(username="blocker1")
        u_muted_by_author = UserFactory(username="muted1")
        u_muter_of_author = UserFactory(username="muter1")

        BlockFactory(blocker=author, blocked=u_blocked_by_author)
        BlockFactory(blocker=u_blocker_of_author, blocked=author)
        Mute.objects.create(muter=author, muted=u_muted_by_author)
        Mute.objects.create(muter=u_muter_of_author, muted=author)

        create_post(
            author=author,
            content_text="Chamando @blocked1 @blocker1 @muted1 @muter1",
            visibility="public",
        )
        assert Notification.objects.filter(notification_type=Notification.Type.MENTION).count() == 0

    def test_mention_respects_circle_and_private_account_visibility(self):
        circle_author = UserFactory(username="circleowner")
        not_friend = UserFactory(username="stranger1")
        friend = UserFactory(username="closepal")
        Follow.objects.create(
            follower=friend,
            followed=circle_author,
            status=Follow.Status.ACTIVE,
            is_close_friend=True,
        )

        create_post(
            author=circle_author,
            content_text="Segredo para @stranger1 e @closepal",
            visibility="circle",
        )
        assert not Notification.objects.filter(recipient=not_friend).exists()
        assert Notification.objects.filter(
            recipient=friend, notification_type=Notification.Type.MENTION
        ).exists()

        # Conta privada: só seguidor aprovado recebe menção
        priv_author = UserFactory(username="privowner")
        _make_private(priv_author)
        pending_user = UserFactory(username="pendingpal")
        active_user = UserFactory(username="activepal")
        Follow.objects.create(
            follower=pending_user, followed=priv_author, status=Follow.Status.PENDING
        )
        Follow.objects.create(
            follower=active_user, followed=priv_author, status=Follow.Status.ACTIVE
        )

        create_post(
            author=priv_author,
            content_text="Olá @pendingpal e @activepal",
            visibility="public",
        )
        assert not Notification.objects.filter(recipient=pending_user).exists()
        assert Notification.objects.filter(
            recipient=active_user, notification_type=Notification.Type.MENTION
        ).exists()

    def test_comment_mention_on_create_and_edit_and_target_url(self):
        from comments.services import create_comment, edit_comment

        post_author = UserFactory(username="postowner")
        commenter = UserFactory(username="commenter1")
        mentioned = UserFactory(username="target1")
        mentioned2 = UserFactory(username="target2")
        post = PostFactory(author=post_author, visibility="public")

        comment = create_comment(
            author=commenter,
            post=post,
            content_text="Concordo com @target1!",
        )
        notif = Notification.objects.filter(
            recipient=mentioned,
            notification_type=Notification.Type.MENTION,
            ref_id=comment.id,
        ).first()
        assert notif is not None

        # target_url aponta para ?comment=
        client = _client_for(mentioned)
        res = client.get("/api/notifications/?category=mentions")
        assert res.status_code == status.HTTP_200_OK
        items = res.json()
        assert len(items) == 1
        assert items[0]["target_url"] == f"/posts/{post.id}?comment={comment.id}"

        # Editar comentário mantém sem duplicar target1 e notifica target2
        edit_comment(
            comment=comment,
            user=commenter,
            content_text="Concordo com @target1 e @target2!",
        )
        assert (
            Notification.objects.filter(
                recipient=mentioned,
                notification_type=Notification.Type.MENTION,
                ref_id=comment.id,
            ).count()
            == 1
        )
        assert Notification.objects.filter(
            recipient=mentioned2,
            notification_type=Notification.Type.MENTION,
            ref_id=comment.id,
        ).exists()


# =============================================================================
# 4. Sugestões Éticas para Seguir & Feature Flag follow_suggestions
# =============================================================================


@pytest.mark.django_db
class TestFollowSuggestions:
    def test_suggestions_require_authentication(self):
        client = APIClient()
        res = client.get("/api/social/suggestions/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_suggestions_prioritize_mutuals_and_apply_exclusions(self):
        viewer = UserFactory(username="viewer1")
        connector = UserFactory(username="connector1")
        FollowFactory(follower=viewer, followed=connector, status=Follow.Status.ACTIVE)

        # Candidato mútuo (seguido por connector)
        mutual_candidate = UserFactory(username="mutual1")
        mutual_candidate.profile.display_name = "Mutual User"
        mutual_candidate.profile.is_private = True
        mutual_candidate.profile.bio = "Bio privada não deve vazar"
        mutual_candidate.profile.save()
        FollowFactory(follower=connector, followed=mutual_candidate, status=Follow.Status.ACTIVE)

        # Candidato público ativo da comunidade
        public_candidate = UserFactory(username="public1")
        public_candidate.profile.display_name = "Public User"
        public_candidate.profile.save()

        # Excluídos obrigatórios
        already_followed = UserFactory(username="already1")
        FollowFactory(follower=viewer, followed=already_followed, status=Follow.Status.ACTIVE)

        pending_user = UserFactory(username="pending1")
        FollowFactory(follower=viewer, followed=pending_user, status=Follow.Status.PENDING)

        blocked_out = UserFactory(username="blockedout")
        BlockFactory(blocker=viewer, blocked=blocked_out)

        blocked_in = UserFactory(username="blockedin")
        BlockFactory(blocker=blocked_in, blocked=viewer)

        muted_out = UserFactory(username="mutedout")
        Mute.objects.create(muter=viewer, muted=muted_out)

        muted_in = UserFactory(username="mutedin")
        Mute.objects.create(muter=muted_in, muted=viewer)

        inactive = UserFactory(username="inactive1", is_active=False)
        suspended = UserFactory(username="suspended1", status=User.Status.SUSPENDED)

        client = _client_for(viewer)
        res = client.get("/api/social/suggestions/?limit=10")
        assert res.status_code == status.HTTP_200_OK
        results = res.json()["results"]
        usernames = [r["username"] for r in results]

        # Primeiro resultado deve ser o mútuo
        assert usernames[0] == "mutual1"
        assert results[0]["reason"] == "mutual"
        assert results[0]["mutual_count"] == 1
        assert results[0]["mutual_sample_username"] == "connector1"
        assert results[0]["bio"] == ""  # bio privada ocultada

        # Público da comunidade também aparece
        assert "public1" in usernames

        # Todos os excluídos estão ausentes
        for excluded in [
            "viewer1",
            "connector1",
            "already1",
            "pending1",
            "blockedout",
            "blockedin",
            "mutedout",
            "mutedin",
            "inactive1",
            "suspended1",
        ]:
            assert excluded not in usernames

        # Anônimo retorna []
        assert suggest_users_to_follow(None) == []

    def test_suggestions_respect_feature_flag(self):
        viewer = UserFactory()
        UserFactory()
        flag = FeatureFlag.objects.create(
            key="follow_suggestions",
            is_enabled=False,
            rollout_percentage=100,
        )
        client = _client_for(viewer)
        res_off = client.get("/api/social/suggestions/")
        assert res_off.status_code == status.HTTP_200_OK
        assert res_off.json()["results"] == []

        flag.is_enabled = True
        flag.save(update_fields=["is_enabled"])
        res_on = client.get("/api/social/suggestions/")
        assert res_on.status_code == status.HTTP_200_OK
        assert len(res_on.json()["results"]) >= 1


# =============================================================================
# 5. Settings & Legal Consent Timestamp
# =============================================================================


@pytest.mark.django_db
class TestLegalConsentSettings:
    def test_user_settings_exposes_terms_accepted_at(self):
        user = UserFactory()
        accepted_at = timezone.now()
        user.profile.terms_accepted_at = accepted_at
        user.profile.save(update_fields=["terms_accepted_at"])

        client = _client_for(user)
        res = client.get("/api/users/settings/")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["terms_accepted_at"] is not None

        res_me = client.get("/api/auth/me/")
        assert res_me.status_code == status.HTTP_200_OK
        assert res_me.json()["terms_accepted_at"] is not None


@pytest.mark.django_db
class TestWave7bEdgeCases:
    def test_nfd_unicode_hashtag_and_ftp_url_ignored(self):
        text = "Tomando #cafe\u0301 vendo ftp://files.example.com/dir#anchor"
        assert extract_hashtags(text) == ["café"]

    def test_wikipedia_url_with_parentheses_does_not_leak_hashtag_or_mention(self):
        text = (
            "Leia https://en.wikipedia.org/wiki/Python_(programming_language)#History "
            "e https://example.com/(v1)/@alice e (https://example.com/@bob#top)!"
        )
        assert extract_hashtags(text) == []
        assert extract_mentions(text) == []

    def test_explore_feed_nfd_hashtag_query_matches_nfc_tag(self):
        viewer = UserFactory()
        author = UserFactory()
        p = create_post(author=author, content_text="Café da manhã #café", visibility="public")
        client = _client_for(viewer)
        res = client.get("/api/feed/explore/?hashtag=cafe%CC%81")
        assert res.status_code == status.HTTP_200_OK
        assert [item["post_id"] for item in res.json()["items"]] == [str(p.id)]

    def test_mention_notification_created_synchronously_in_standard_django_db(self):
        from comments.services import create_comment, edit_comment

        author = UserFactory(username="syncauthor")
        target = UserFactory(username="synctarget")
        target2 = UserFactory(username="synctarget2")

        post = create_post(author=author, content_text="Olá @synctarget!", visibility="public")
        assert Notification.objects.filter(
            recipient=target,
            notification_type=Notification.Type.MENTION,
            ref_id=post.id,
        ).exists()

        update_post(post=post, user=author, content_text="Olá @synctarget e @synctarget2!")
        assert (
            Notification.objects.filter(
                recipient=target,
                notification_type=Notification.Type.MENTION,
                ref_id=post.id,
            ).count()
            == 1
        )
        assert Notification.objects.filter(
            recipient=target2,
            notification_type=Notification.Type.MENTION,
            ref_id=post.id,
        ).exists()

        comment = create_comment(author=author, post=post, content_text="Ping @synctarget")
        assert Notification.objects.filter(
            recipient=target,
            notification_type=Notification.Type.MENTION,
            ref_id=comment.id,
        ).exists()

        edit_comment(comment=comment, user=author, content_text="Ping @synctarget @synctarget2")
        assert Notification.objects.filter(
            recipient=target2,
            notification_type=Notification.Type.MENTION,
            ref_id=comment.id,
        ).exists()

    def test_empty_hash_filter_and_invalid_limit_and_muted_trending_exclusion(self):
        viewer = UserFactory()
        pub = UserFactory()
        muted = UserFactory()
        Mute.objects.create(muter=viewer, muted=muted)

        create_post(author=pub, content_text="Post aberto #lumen", visibility="public")
        create_post(author=pub, content_text="Post círculo #lumen", visibility="circle")
        create_post(
            author=muted, content_text="Post silenciado #lumen #mutetag", visibility="public"
        )

        client = _client_for(viewer)
        # Filter with literal '#' returns empty instead of leaking all posts
        res_empty_tag = client.get("/api/posts/?hashtag=%23")
        assert res_empty_tag.status_code == status.HTTP_200_OK
        assert res_empty_tag.json() == []

        res_explore_empty_tag = client.get("/api/feed/explore/?hashtag=%23")
        assert res_explore_empty_tag.status_code == status.HTTP_200_OK
        assert res_explore_empty_tag.json()["items"] == []

        # Trending excludes circle & muted posts and falls back on invalid limit
        res_trending = client.get("/api/hashtags/trending/?limit=invalid")
        assert res_trending.status_code == status.HTTP_200_OK
        by_name = {item["name"]: item["posts_count"] for item in res_trending.json()["results"]}
        assert by_name == {"lumen": 1}
        assert "mutetag" not in by_name

        # Suggestions falls back on invalid limit
        res_sugg = client.get("/api/social/suggestions/?limit=abc")
        assert res_sugg.status_code == status.HTTP_200_OK
        assert "results" in res_sugg.json()

    def test_suspended_connector_excluded_from_mutual_suggestions(self):
        viewer = UserFactory(username="viewer_susp")
        suspended_connector = UserFactory(username="susp_conn", status=User.Status.SUSPENDED)
        target = UserFactory(username="target_susp")
        FollowFactory(follower=viewer, followed=suspended_connector, status=Follow.Status.ACTIVE)
        FollowFactory(follower=suspended_connector, followed=target, status=Follow.Status.ACTIVE)

        results = suggest_users_to_follow(viewer, limit=5)
        target_item = next((r for r in results if r["username"] == "target_susp"), None)
        assert target_item is not None
        assert target_item["reason"] == "active_community"
        assert target_item["mutual_sample_username"] is None

    def test_post_deletion_unlinks_hashtag_and_trending_drops(self):
        author = UserFactory()
        viewer = UserFactory()
        post = create_post(author=author, content_text="Temporário #efemera", visibility="public")

        client = _client_for(viewer)
        res_before = client.get("/api/hashtags/trending/")
        assert any(t["name"] == "efemera" for t in res_before.json()["results"])

        post.delete()
        res_after = client.get("/api/hashtags/trending/")
        assert not any(t["name"] == "efemera" for t in res_after.json()["results"])

    @pytest.mark.django_db(transaction=True)
    def test_mention_triggers_push_task_when_feature_flag_enabled(self, monkeypatch):
        from core.models import PushDevice
        from core.tasks import send_push_notification_task

        FeatureFlag.objects.create(
            key="push_notifications", is_enabled=True, rollout_percentage=100
        )
        author = UserFactory(username="pushsender")
        recipient = UserFactory(username="pushreceiver")
        PushDevice.objects.create(
            user=recipient, token="tok-mention-1", platform="web", is_active=True
        )

        dispatched = []
        monkeypatch.setattr(
            send_push_notification_task,
            "delay",
            lambda *args, **kwargs: dispatched.append((args, kwargs)),
        )

        create_post(author=author, content_text="Oi @pushreceiver!", visibility="public")
        assert len(dispatched) == 1
        assert dispatched[0][1]["data"]["type"] == "mention"

    def test_unicode_prefix_mention_ignored_and_turkish_i_casefold_overflow_safe(self):
        author = UserFactory()
        assert extract_mentions("olá@alice josé@empresa.com @validUser") == ["validuser"]

        overflow_tag = "#" + ("İ" * 40)
        assert extract_hashtags(overflow_tag) == []

        post = create_post(author=author, content_text=f"Texto {overflow_tag}", visibility="public")
        assert post.hashtags.count() == 0

    def test_trending_same_tag_not_inflated_by_accessible_circle_or_private_posts(self):
        viewer = UserFactory()
        pub_author = UserFactory()
        circle_author = UserFactory()
        priv_author = UserFactory()
        _make_private(priv_author)
        muted_author = UserFactory()
        blocked_author = UserFactory()

        Follow.objects.create(
            follower=viewer,
            followed=circle_author,
            status=Follow.Status.ACTIVE,
            is_close_friend=True,
        )
        Follow.objects.create(
            follower=viewer,
            followed=priv_author,
            status=Follow.Status.ACTIVE,
        )
        Mute.objects.create(muter=viewer, muted=muted_author)
        BlockFactory(blocker=blocked_author, blocked=viewer)

        create_post(author=pub_author, content_text="Público #shared", visibility="public")
        create_post(author=circle_author, content_text="Círculo #shared", visibility="circle")
        create_post(author=priv_author, content_text="Privado #shared", visibility="public")
        create_post(author=muted_author, content_text="Silenciado #shared", visibility="public")
        create_post(author=blocked_author, content_text="Bloqueado #shared", visibility="public")

        client = _client_for(viewer)
        res = client.get("/api/hashtags/trending/?limit=10")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["results"] == [{"name": "shared", "posts_count": 1}]

    def test_profile_case_insensitive_lookup_and_settings_username_lowercase(self):
        target = UserFactory(username="AliceMixed99")
        viewer = UserFactory()

        res = _client_for(viewer).get("/api/social/profile/alicemixed99/")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["username"] == "AliceMixed99"

        res_patch = _client_for(target).patch(
            "/api/users/settings/",
            {"username": "AliceNew99"},
            format="json",
        )
        assert res_patch.status_code == status.HTTP_200_OK
        assert res_patch.json()["username"] == "alicenew99"

    def test_suggestions_user_without_profile_and_limit_clamping(self):
        viewer = UserFactory(username="viewer_noprof")
        no_prof = User.objects.create_user(
            email="noprof@example.com",
            username="noprofileuser",
            password="testpass123",
        )
        create_post(author=no_prof, content_text="Post sem profile #noprof", visibility="public")

        results_clamped_low = suggest_users_to_follow(viewer, limit=0)
        assert len(results_clamped_low) == 1

        results = suggest_users_to_follow(viewer, limit=50)
        usernames = [r["username"] for r in results]
        assert "noprofileuser" in usernames
        assert len(usernames) == len(set(usernames))

        res_explore = _client_for(viewer).get("/api/feed/explore/?hashtag=noprof")
        assert res_explore.status_code == status.HTTP_200_OK
        assert len(res_explore.json()["items"]) == 1

    def test_comment_edit_mentions_mixed_block_mute_circle_and_dedup(self):
        from comments.services import create_comment, edit_comment

        post_owner = UserFactory(username="owner_mix")
        commenter = UserFactory(username="comm_mix")
        eligible1 = UserFactory(username="elig1")
        eligible2 = UserFactory(username="elig2")
        blocked_u = UserFactory(username="blkmix")
        muted_u = UserFactory(username="mutmix")
        non_circle = UserFactory(username="outsidermix")

        for u in (commenter, eligible1, eligible2, blocked_u, muted_u):
            Follow.objects.create(
                follower=u,
                followed=post_owner,
                status=Follow.Status.ACTIVE,
                is_close_friend=True,
            )

        BlockFactory(blocker=blocked_u, blocked=commenter)
        Mute.objects.create(muter=muted_u, muted=commenter)

        circle_post = create_post(
            author=post_owner, content_text="Post círculo", visibility="circle"
        )
        comment = create_comment(
            author=commenter,
            post=circle_post,
            content_text="Oi @elig1",
        )
        assert (
            Notification.objects.filter(
                recipient=eligible1, notification_type=Notification.Type.MENTION, ref_id=comment.id
            ).count()
            == 1
        )

        edit_comment(
            comment=comment,
            user=commenter,
            content_text="Oi @elig1 @elig2 @blkmix @mutmix @outsidermix",
        )
        assert (
            Notification.objects.filter(
                recipient=eligible1, notification_type=Notification.Type.MENTION, ref_id=comment.id
            ).count()
            == 1
        )
        assert (
            Notification.objects.filter(
                recipient=eligible2, notification_type=Notification.Type.MENTION, ref_id=comment.id
            ).count()
            == 1
        )
        for suppressed in (blocked_u, muted_u, non_circle):
            assert not Notification.objects.filter(
                recipient=suppressed, notification_type=Notification.Type.MENTION
            ).exists()
