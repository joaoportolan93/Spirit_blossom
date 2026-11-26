"""Testes do comando de gerenciamento seed_dev_data."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from comments.models import Comment
from core.factories import UserFactory
from core.models import Follow, Notification, PostLike
from core.services.posts import create_post


@pytest.mark.django_db
class TestSeedDevDataCommand:
    def test_falha_quando_usuario_alvo_nao_existe(self):
        with pytest.raises(CommandError, match="não encontrado"):
            call_command("seed_dev_data", "--target", "inexistente_xyz")

    def test_falha_quando_usuario_alvo_nao_tem_post(self):
        target = UserFactory(username="sempost_alvo")
        with pytest.raises(CommandError, match="não tem nenhum post"):
            call_command("seed_dev_data", "--target", target.username)

    def test_cria_20_seeds_interacoes_e_faz_purge_idempotente(self):
        target = UserFactory(username="alvoseedteste")
        post = create_post(author=target, content_text="Meu primeiro post!")

        out = StringIO()
        call_command("seed_dev_data", "--purge", "--target", target.username, stdout=out)

        assert Follow.objects.filter(followed=target, status=Follow.Status.ACTIVE).count() == 5
        assert PostLike.objects.filter(post=post).count() == 5
        assert Comment.objects.filter(post=post, is_deleted=False).count() == 5
        assert (
            Notification.objects.filter(
                recipient=target, notification_type=Notification.Type.MENTION
            ).count()
            == 5
        )

        # Reexecução com --purge remove seeds anteriores, limpa órfãos e recria limpo
        out2 = StringIO()
        call_command("seed_dev_data", "--purge", "--target", target.username, stdout=out2)
        post.refresh_from_db()
        assert Follow.objects.filter(followed=target, status=Follow.Status.ACTIVE).count() == 5
        assert PostLike.objects.filter(post=post).count() == 5
        assert post.likes_count == 5
        assert Comment.objects.filter(post=post, is_deleted=False).count() == 5
        assert post.comments_count == 5

        # Sem --purge reaproveita os 20 seeds existentes
        out3 = StringIO()
        call_command("seed_dev_data", "--target", target.username, stdout=out3)
        assert "já existe" in out3.getvalue()
