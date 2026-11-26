"""
moderation.py — Serviços de denúncias (Reports) e moderação administrativa (Onda 8).
"""

import uuid
from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext as _

from core.models import ModerationLog, Report
from core.services.posts import get_post_by_id_for_moderation

User = get_user_model()


def create_report(
    *,
    reporter,
    target_type: str,
    target_id: str,
    reason: str,
    description: str = "",
) -> Report:
    """
    Cria uma denúncia contra publicação, comentário ou usuário.
    Valida tipo, motivo, existência do alvo, impede auto-denúncia e duplicidade pendente.
    """
    valid_types = {choice[0] for choice in Report.TargetType.choices}
    if target_type not in valid_types:
        raise ValueError(_("Tipo de alvo inválido."))

    valid_reasons = {choice[0] for choice in Report.Reason.choices}
    if reason not in valid_reasons:
        raise ValueError(_("Motivo de denúncia inválido."))

    target_id_str = str(target_id or "").strip()
    if not target_id_str:
        raise ValueError(_("ID do conteúdo denunciado é obrigatório."))

    try:
        uuid.UUID(target_id_str)
    except (ValueError, AttributeError) as exc:
        raise ValueError(_("ID do conteúdo denunciado inválido.")) from exc

    # Verifica existência do alvo e impede denúncia do próprio conteúdo/perfil
    if target_type == Report.TargetType.POST:
        post = get_post_by_id_for_moderation(target_id_str)
        if not post:
            raise LookupError(_("Publicação não encontrada."))
        if post.author_id == reporter.id:
            raise ValueError(_("Você não pode denunciar sua própria publicação."))
    elif target_type == Report.TargetType.COMMENT:
        from comments.models import Comment

        comment = Comment.objects.filter(pk=target_id_str).first()
        if not comment or comment.is_deleted:
            raise LookupError(_("Comentário não encontrado."))
        if comment.author_id == reporter.id:
            raise ValueError(_("Você não pode denunciar seu próprio comentário."))
    elif target_type == Report.TargetType.USER:
        target_user = User.objects.filter(pk=target_id_str).first()
        if not target_user:
            raise LookupError(_("Usuário não encontrado."))
        if target_user.id == reporter.id:
            raise ValueError(_("Você não pode denunciar a sua própria conta."))

    if Report.objects.filter(
        reporter=reporter,
        target_type=target_type,
        target_id=target_id_str,
        status=Report.Status.PENDING,
    ).exists():
        raise ValueError(_("Você já possui uma denúncia pendente para este conteúdo."))

    return Report.objects.create(
        reporter=reporter,
        target_type=target_type,
        target_id=target_id_str,
        reason=reason,
        description=(description or "").strip()[:1000],
        status=Report.Status.PENDING,
    )


def _hide_target_content(*, report: Report, moderator, reason: str) -> Optional[User]:
    """Oculta publicação ou comentário pela moderação. Retorna o autor afetado se existir."""
    now = timezone.now()
    if report.target_type == Report.TargetType.POST:
        post = get_post_by_id_for_moderation(report.target_id)
        if not post:
            return None
        post.is_hidden = True
        post.hidden_reason = reason
        post.hidden_at = now
        post.hidden_by = moderator
        post.save(update_fields=["is_hidden", "hidden_reason", "hidden_at", "hidden_by"])
        ModerationLog.objects.create(
            target_type="post",
            target_id=str(post.id),
            affected_user=post.author,
            moderator=moderator,
            report=report,
            action=ModerationLog.Action.HIDE_CONTENT,
            reason=reason,
            content_snapshot=post.content_text[:300],
        )
        return post.author

    if report.target_type == Report.TargetType.COMMENT:
        from comments.models import Comment
        from core.services.posts import (
            decrement_post_comments_count,
            increment_post_hidden_comments_count,
        )

        comment = Comment.objects.filter(pk=report.target_id).select_related("author").first()
        if not comment:
            return None
        if not comment.is_hidden:
            comment.is_hidden = True
            comment.hidden_reason = "moderation"
            comment.hidden_at = now
            comment.hidden_by = moderator
            comment.save(
                update_fields=["is_hidden", "hidden_reason", "hidden_at", "hidden_by", "updated_at"]
            )
            if not comment.is_deleted:
                decrement_post_comments_count(comment.post_id, amount=1)
                increment_post_hidden_comments_count(comment.post_id)
                if comment.parent_id:
                    Comment.objects.filter(pk=comment.parent_id, replies_count__gt=0).update(
                        replies_count=F("replies_count") - 1
                    )
        ModerationLog.objects.create(
            target_type="comment",
            target_id=str(comment.id),
            affected_user=comment.author,
            moderator=moderator,
            report=report,
            action=ModerationLog.Action.HIDE_CONTENT,
            reason=reason,
            content_snapshot=comment.content_text[:300],
        )
        return comment.author

    return None


def _remove_target_content(*, report: Report, moderator, reason: str) -> Optional[User]:
    """Remove conteúdo denunciado (ou aplica tombstone em comentário com respostas)."""
    if report.target_type == Report.TargetType.POST:
        post = get_post_by_id_for_moderation(report.target_id)
        if not post:
            return None
        author = post.author
        snapshot = post.content_text[:300]
        from core.utils.media_security import delete_media_file

        delete_media_file(post.image)
        delete_media_file(post.video)
        post.delete()
        ModerationLog.objects.create(
            target_type="post",
            target_id=str(report.target_id),
            affected_user=author,
            moderator=moderator,
            report=report,
            action=ModerationLog.Action.REMOVE_CONTENT,
            reason=reason,
            content_snapshot=snapshot,
        )
        return author

    if report.target_type == Report.TargetType.COMMENT:
        from comments.models import Comment
        from core.services.posts import (
            decrement_post_comments_count,
            decrement_post_hidden_comments_count,
        )
        from core.utils.media_security import delete_media_file

        comment = Comment.objects.filter(pk=report.target_id).select_related("author").first()
        if not comment:
            return None
        author = comment.author
        snapshot = comment.content_text[:300]
        if not comment.is_deleted:
            if not comment.is_hidden:
                decrement_post_comments_count(comment.post_id)
                if comment.parent_id:
                    Comment.objects.filter(pk=comment.parent_id, replies_count__gt=0).update(
                        replies_count=F("replies_count") - 1
                    )
            else:
                decrement_post_hidden_comments_count(comment.post_id)

        delete_media_file(comment.image)
        delete_media_file(comment.video)

        if comment.replies.exists():
            comment.is_deleted = True
            comment.content_text = ""
            comment.image = None
            comment.video = None
            comment.author = None
            comment.is_edited = False
            comment.edited_at = None
            comment.save(
                update_fields=[
                    "is_deleted",
                    "content_text",
                    "image",
                    "video",
                    "author",
                    "is_edited",
                    "edited_at",
                    "updated_at",
                ]
            )
        else:
            comment.delete()

        ModerationLog.objects.create(
            target_type="comment",
            target_id=str(report.target_id),
            affected_user=author,
            moderator=moderator,
            report=report,
            action=ModerationLog.Action.REMOVE_CONTENT,
            reason=reason,
            content_snapshot=snapshot,
        )
        return author

    return None


def _resolve_target_author(report: Report) -> Optional[User]:
    """Identifica o usuário alvo de uma denúncia."""
    if report.target_type == Report.TargetType.POST:
        post = get_post_by_id_for_moderation(report.target_id)
        return post.author if post else None
    if report.target_type == Report.TargetType.COMMENT:
        from comments.models import Comment

        comment = Comment.objects.filter(pk=report.target_id).select_related("author").first()
        return comment.author if comment else None
    if report.target_type == Report.TargetType.USER:
        return User.objects.filter(pk=report.target_id).first()
    return None


@transaction.atomic
def execute_report_action(
    *,
    report: Report,
    moderator,
    action: str,
    reason: str = "",
    duration_days: Optional[int] = None,
    moderator_notes: str = "",
    preserve_for_authorities: bool = False,
) -> Report:
    """
    Executa uma ação de moderação sobre uma denúncia:
    - `ignore` / `dismiss`: descarta a denúncia (status=dismissed).
    - `review`: marca como em análise (status=reviewed).
    - `hide`: oculta o conteúdo denunciado e resolve a denúncia.
    - `remove`: remove o conteúdo denunciado e resolve a denúncia.
    - `ban`: suspende/bane o autor e resolve a denúncia.
    - `ban_remove`: remove o conteúdo e bane/suspende o autor.
    """
    from core.services.user_lifecycle import ban_user

    valid_actions = {"ignore", "dismiss", "review", "hide", "remove", "ban", "ban_remove"}
    if action not in valid_actions:
        raise ValueError(_("Ação de moderação inválida."))

    now = timezone.now()
    default_reason = dict(Report.Reason.choices).get(report.reason, "Violação das diretrizes")
    effective_reason = (reason or "").strip() or str(default_reason)

    if action == "review":
        report.status = Report.Status.REVIEWED
        report.moderator = moderator
        if moderator_notes:
            report.moderator_notes = moderator_notes
        report.save(update_fields=["status", "moderator", "moderator_notes"])
        return report

    if action in {"ignore", "dismiss"}:
        report.status = Report.Status.DISMISSED
        report.action_taken = Report.ActionTaken.NONE
        report.moderator = moderator
        report.moderator_notes = moderator_notes or report.moderator_notes
        report.resolved_at = now
        report.save(
            update_fields=[
                "status",
                "action_taken",
                "moderator",
                "moderator_notes",
                "resolved_at",
            ]
        )
        ModerationLog.objects.create(
            target_type=report.target_type,
            target_id=report.target_id,
            affected_user=_resolve_target_author(report),
            moderator=moderator,
            report=report,
            action=ModerationLog.Action.DISMISS_REPORT,
            reason=moderator_notes or "Denúncia descartada",
        )
        return report

    if action == "hide":
        _hide_target_content(report=report, moderator=moderator, reason=effective_reason)
        report.status = Report.Status.RESOLVED
        report.action_taken = Report.ActionTaken.CONTENT_HIDDEN
        report.moderator = moderator
        report.moderator_notes = moderator_notes or report.moderator_notes
        report.resolved_at = now
        report.save()
        return report

    if action == "remove":
        _remove_target_content(report=report, moderator=moderator, reason=effective_reason)
        report.status = Report.Status.RESOLVED
        report.action_taken = Report.ActionTaken.CONTENT_REMOVED
        report.moderator = moderator
        report.moderator_notes = moderator_notes or report.moderator_notes
        report.resolved_at = now
        report.save()
        return report

    if action == "ban":
        target_user = _resolve_target_author(report)
        if target_user:
            if target_user.id == moderator.id:
                raise ValueError(_("Você não pode banir a sua própria conta."))
            ban_user(
                target_user,
                reason=effective_reason,
                admin_user=moderator,
                duration_days=duration_days,
                preserve_for_authorities=preserve_for_authorities,
            )
        report.status = Report.Status.RESOLVED
        report.action_taken = (
            Report.ActionTaken.USER_SUSPENDED if duration_days else Report.ActionTaken.USER_BANNED
        )
        report.moderator = moderator
        report.moderator_notes = moderator_notes or report.moderator_notes
        report.resolved_at = now
        report.save()
        return report

    # action == "ban_remove"
    target_user = _resolve_target_author(report)
    if target_user and target_user.id == moderator.id:
        raise ValueError(_("Você não pode banir a sua própria conta."))

    removed_author = _remove_target_content(
        report=report, moderator=moderator, reason=effective_reason
    )
    user_to_ban = target_user or removed_author
    if user_to_ban:
        ban_user(
            user_to_ban,
            reason=effective_reason,
            admin_user=moderator,
            duration_days=duration_days,
            preserve_for_authorities=preserve_for_authorities,
        )

    report.status = Report.Status.RESOLVED
    report.action_taken = (
        Report.ActionTaken.USER_SUSPENDED if duration_days else Report.ActionTaken.USER_BANNED
    )
    report.moderator = moderator
    report.moderator_notes = moderator_notes or report.moderator_notes
    report.resolved_at = now
    report.save()
    return report
