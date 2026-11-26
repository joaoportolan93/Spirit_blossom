"""
Camada de consultas e seletores para Comentários (Onda 4 / ADR-N24).
Consultas em lote sem N+1, cursores estáveis e contexto de focar.
"""

import base64
import json
from typing import Any, Dict, List, Optional, Set

from django.db.models import F, Q
from django.utils.dateparse import parse_datetime

from comments.models import Comment, CommentBookmark, CommentLike
from core.models import Block, Mute, Post
from core.utils.visibility import can_view_post

# -----------------------------------------------------------------------------
# Auxiliares de Cursor Composto Estável
# -----------------------------------------------------------------------------


def encode_cursor(values: List[Any], sort: str) -> str:
    """Codifica tupla de valores em cursor base64 URL-safe."""
    payload = {"v": values, "s": sort}
    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii")


def decode_cursor(raw_cursor: Optional[str], expected_sort: str) -> Optional[List[Any]]:
    """Decodifica e valida cursor base64 URL-safe."""
    if not raw_cursor:
        return None
    try:
        decoded_bytes = base64.urlsafe_b64decode(raw_cursor.encode("ascii"))
        payload = json.loads(decoded_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        if payload.get("s") != expected_sort:
            return None
        values = payload.get("v")
        if not isinstance(values, list) or not values:
            return None
        return values
    except Exception:
        return None


def get_blocked_user_ids(user) -> Set[Any]:
    """Retorna conjunto de IDs de usuários com bloqueio mútuo em relação a user."""
    if not user or not user.is_authenticated:
        return set()
    return set(
        Block.objects.filter(Q(blocker=user) | Q(blocked=user))
        .values_list("blocker_id", "blocked_id")
        .distinct()
    ).union()


def _extract_blocked_ids(user) -> Set[Any]:
    if not user or not user.is_authenticated:
        return set()
    blocks = Block.objects.filter(Q(blocker=user) | Q(blocked=user)).values(
        "blocker_id", "blocked_id"
    )
    blocked = set()
    for b in blocks:
        if b["blocker_id"] == user.id:
            blocked.add(b["blocked_id"])
        else:
            blocked.add(b["blocker_id"])
    return blocked


def _extract_muted_ids(user) -> Set[Any]:
    if not user or not user.is_authenticated:
        return set()
    return set(Mute.objects.filter(muter=user).values_list("muted_id", flat=True))


# -----------------------------------------------------------------------------
# Consultas em Lote de Comentários
# -----------------------------------------------------------------------------


def list_post_comments_with_preview(
    *,
    post: Post,
    viewer,
    sort: str = "recent",
    cursor: Optional[str] = None,
    page_size: int = 20,
) -> Dict[str, Any]:
    """
    Lista comentários raiz (depth 0) de um post com prévia de respostas até depth 2.
    Executado em exatamente 3 consultas em lote no banco (O(1) queries), sem N+1:
      1. Raízes paginadas via cursor composto (depth 0).
      2. Respostas diretas das raízes (depth 1).
      3. Respostas das respostas de nível 1 (depth 2).
    Montagem da árvore em memória.
    """
    if not can_view_post(viewer, post):
        return {"items": [], "next_cursor": None}

    blocked_ids = _extract_blocked_ids(viewer)
    muted_ids = _extract_muted_ids(viewer)

    # Consulta 1: Raízes (depth 0)
    qs = Comment.objects.filter(post=post, parent__isnull=True).select_related("author")
    if viewer and viewer.is_authenticated:
        qs = qs.filter(
            Q(is_hidden=False) | (Q(is_hidden=True, author=viewer) & ~Q(hidden_reason="moderation"))
        )
    else:
        qs = qs.filter(is_hidden=False)

    # Ordenação e filtros de cursor composto
    decoded = decode_cursor(cursor, sort)
    if sort == "likes":
        qs = qs.order_by("-likes_count", "-created_at", "-id")
        if decoded and len(decoded) == 3:
            cur_likes, cur_dt_raw, cur_id = decoded[0], parse_datetime(decoded[1]), decoded[2]
            if cur_dt_raw:
                qs = qs.filter(
                    Q(likes_count__lt=cur_likes)
                    | Q(likes_count=cur_likes, created_at__lt=cur_dt_raw)
                    | Q(likes_count=cur_likes, created_at=cur_dt_raw, id__lt=cur_id)
                )
    elif sort == "relevance":
        qs = qs.annotate(engagement=F("likes_count") + F("replies_count")).order_by(
            "-engagement", "-created_at", "-id"
        )
        if decoded and len(decoded) == 3:
            cur_eng, cur_dt_raw, cur_id = decoded[0], parse_datetime(decoded[1]), decoded[2]
            if cur_dt_raw:
                qs = qs.filter(
                    Q(engagement__lt=cur_eng)
                    | Q(engagement=cur_eng, created_at__lt=cur_dt_raw)
                    | Q(engagement=cur_eng, created_at=cur_dt_raw, id__lt=cur_id)
                )
    else:  # recent
        sort = "recent"
        qs = qs.order_by("-created_at", "-id")
        if decoded and len(decoded) == 2:
            cur_dt_raw, cur_id = parse_datetime(decoded[0]), decoded[1]
            if cur_dt_raw:
                qs = qs.filter(
                    Q(created_at__lt=cur_dt_raw) | Q(created_at=cur_dt_raw, id__lt=cur_id)
                )

    roots = list(qs[: page_size + 1])
    has_more = len(roots) > page_size
    roots = roots[:page_size]

    next_cursor = None
    if has_more and roots:
        last = roots[-1]
        if sort == "likes":
            next_cursor = encode_cursor(
                [last.likes_count, last.created_at.isoformat(), str(last.id)], sort
            )
        elif sort == "relevance":
            eng = getattr(last, "engagement", last.likes_count + last.replies_count)
            next_cursor = encode_cursor([eng, last.created_at.isoformat(), str(last.id)], sort)
        else:
            next_cursor = encode_cursor([last.created_at.isoformat(), str(last.id)], sort)

    if not roots:
        return {"items": [], "next_cursor": None}

    # Consulta 2: Filhos diretos (depth 1)
    root_ids = [r.id for r in roots]
    level1_qs = (
        Comment.objects.filter(parent_id__in=root_ids)
        .select_related("author")
        .order_by("created_at", "id")
    )
    if viewer and viewer.is_authenticated:
        level1_qs = level1_qs.filter(
            Q(is_hidden=False) | (Q(is_hidden=True, author=viewer) & ~Q(hidden_reason="moderation"))
        )
    else:
        level1_qs = level1_qs.filter(is_hidden=False)
    level1_items = list(level1_qs)

    # Consulta 3: Filhos de nível 2
    level2_items = []
    if level1_items:
        level1_ids = [c.id for c in level1_items]
        level2_qs = (
            Comment.objects.filter(parent_id__in=level1_ids)
            .select_related("author")
            .order_by("created_at", "id")
        )
        if viewer and viewer.is_authenticated:
            level2_qs = level2_qs.filter(
                Q(is_hidden=False)
                | (Q(is_hidden=True, author=viewer) & ~Q(hidden_reason="moderation"))
            )
        else:
            level2_qs = level2_qs.filter(is_hidden=False)
        level2_items = list(level2_qs)

    # Identifica curtidas e favoritos em lote
    all_ids = [r.id for r in roots] + [c.id for c in level1_items] + [c.id for c in level2_items]
    liked_ids: Set[Any] = set()
    bookmarked_ids: Set[Any] = set()
    if viewer and viewer.is_authenticated and all_ids:
        liked_ids = set(
            CommentLike.objects.filter(user=viewer, comment_id__in=all_ids).values_list(
                "comment_id", flat=True
            )
        )
        bookmarked_ids = set(
            CommentBookmark.objects.filter(user=viewer, comment_id__in=all_ids).values_list(
                "comment_id", flat=True
            )
        )

    # Monta a árvore em memória
    for item in roots + level1_items + level2_items:
        is_blocked = (item.author_id in blocked_ids) if item.author_id else False
        if is_blocked:
            item.is_placeholder = True
            item.placeholder_reason = "block"
            item.author = None
            item.content_text = ""
            item.likes_count = 0
            item.is_liked = False
            item.is_bookmarked = False
        else:
            item.is_liked = item.id in liked_ids
            item.is_bookmarked = item.id in bookmarked_ids
            item.placeholder_reason = (
                "deleted" if item.is_deleted else getattr(item, "placeholder_reason", None)
            )
        item.is_muted = (item.author_id in muted_ids) if item.author_id else False
        item.preview_replies = []

    level2_by_parent: Dict[Any, List[Comment]] = {}
    for c in level2_items:
        level2_by_parent.setdefault(c.parent_id, []).append(c)

    for c in level1_items:
        c.preview_replies = level2_by_parent.get(c.id, [])

    level1_by_parent: Dict[Any, List[Comment]] = {}
    for c in level1_items:
        level1_by_parent.setdefault(c.parent_id, []).append(c)

    for r in roots:
        r.preview_replies = level1_by_parent.get(r.id, [])

    return {"items": roots, "next_cursor": next_cursor}


def list_comment_replies(
    *,
    comment: Comment,
    viewer,
    sort: str = "recent",
    cursor: Optional[str] = None,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Lista respostas diretas a um comentário, paginadas por cursor."""
    if not can_view_post(viewer, comment.post):
        return {"items": [], "next_cursor": None}

    blocked_ids = _extract_blocked_ids(viewer)
    muted_ids = _extract_muted_ids(viewer)

    # Se o comentário for oculto, apenas o autor ou o dono do post podem acessar replies
    # (exceto se ocultado pela moderação)
    if comment.is_hidden:
        is_allowed = (
            comment.hidden_reason != "moderation"
            and viewer
            and viewer.is_authenticated
            and (comment.author_id == viewer.id or comment.post.author_id == viewer.id)
        )
        if not is_allowed:
            return {"items": [], "next_cursor": None}

    qs = Comment.objects.filter(parent=comment).select_related("author")
    if viewer and viewer.is_authenticated:
        qs = qs.filter(
            Q(is_hidden=False) | (Q(is_hidden=True, author=viewer) & ~Q(hidden_reason="moderation"))
        )
    else:
        qs = qs.filter(is_hidden=False)

    # Ordenação cronológica estável por padrão para replies
    qs = qs.order_by("created_at", "id")
    decoded = decode_cursor(cursor, sort)
    if decoded and len(decoded) == 2:
        cur_dt_raw, cur_id = parse_datetime(decoded[0]), decoded[1]
        if cur_dt_raw:
            qs = qs.filter(Q(created_at__gt=cur_dt_raw) | Q(created_at=cur_dt_raw, id__gt=cur_id))

    replies = list(qs[: page_size + 1])
    has_more = len(replies) > page_size
    replies = replies[:page_size]

    next_cursor = None
    if has_more and replies:
        last = replies[-1]
        next_cursor = encode_cursor([last.created_at.isoformat(), str(last.id)], sort)

    if viewer and viewer.is_authenticated and replies:
        rep_ids = [r.id for r in replies]
        liked_ids = set(
            CommentLike.objects.filter(user=viewer, comment_id__in=rep_ids).values_list(
                "comment_id", flat=True
            )
        )
        bookmarked_ids = set(
            CommentBookmark.objects.filter(user=viewer, comment_id__in=rep_ids).values_list(
                "comment_id", flat=True
            )
        )
        for r in replies:
            is_blocked = (r.author_id in blocked_ids) if r.author_id else False
            if is_blocked:
                r.is_placeholder = True
                r.placeholder_reason = "block"
                r.author = None
                r.content_text = ""
                r.likes_count = 0
                r.is_liked = False
                r.is_bookmarked = False
            else:
                r.is_liked = r.id in liked_ids
                r.is_bookmarked = r.id in bookmarked_ids
                r.placeholder_reason = (
                    "deleted" if r.is_deleted else getattr(r, "placeholder_reason", None)
                )
            r.is_muted = (r.author_id in muted_ids) if r.author_id else False
            r.preview_replies = []
    else:
        for r in replies:
            is_blocked = (r.author_id in blocked_ids) if r.author_id else False
            if is_blocked:
                r.is_placeholder = True
                r.placeholder_reason = "block"
                r.author = None
                r.content_text = ""
                r.likes_count = 0
            else:
                r.placeholder_reason = (
                    "deleted" if r.is_deleted else getattr(r, "placeholder_reason", None)
                )
            r.is_liked = False
            r.is_bookmarked = False
            r.is_muted = (r.author_id in muted_ids) if r.author_id else False
            r.preview_replies = []

    return {"items": replies, "next_cursor": next_cursor}


def get_comment_thread_context(
    *,
    comment_id,
    viewer,
    replies_page_size: int = 20,
) -> Optional[Dict[str, Any]]:
    """
    Retorna o contexto completo do Focar em uma única chamada:
    - Resumo do post pai.
    - Trilha de ancestrais da raiz até o pai imediato.
      (Ancestrais bloqueados ou excluídos viram placeholder sem autor nem texto).
    - O comentário focado (se inacessível ou autor bloqueado, retorna None -> 404).
    - Primeira página de respostas diretas.
    """
    comment = (
        Comment.objects.select_related("post", "post__author", "author", "parent")
        .filter(pk=comment_id)
        .first()
    )
    if not comment:
        return None

    if not can_view_post(viewer, comment.post):
        return None

    blocked_ids = _extract_blocked_ids(viewer)
    muted_ids = _extract_muted_ids(viewer)
    if comment.author_id in blocked_ids:
        return None

    # Se o comentário focado for oculto, apenas o autor e o dono do post podem visualizá-lo no Focar
    # (exceto se ocultado pela moderação)
    if comment.is_hidden:
        is_allowed = (
            comment.hidden_reason != "moderation"
            and viewer
            and viewer.is_authenticated
            and (comment.author_id == viewer.id or comment.post.author_id == viewer.id)
        )
        if not is_allowed:
            return None

    comment.is_muted = (comment.author_id in muted_ids) if comment.author_id else False

    # Constrói trilha de ancestrais subindo pelos ponteiros parent
    raw_ancestors = []
    curr = comment.parent
    visited = set()
    while curr:
        if curr.id in visited:
            break
        visited.add(curr.id)
        raw_ancestors.append(curr)
        curr = curr.parent
    raw_ancestors.reverse()  # da raiz ao pai imediato

    # Identifica likes e bookmarks para o contexto todo
    ancestor_ids = [a.id for a in raw_ancestors]
    context_ids = [comment.id, *ancestor_ids]
    liked_ids: Set[Any] = set()
    bookmarked_ids: Set[Any] = set()
    if viewer and viewer.is_authenticated:
        liked_ids = set(
            CommentLike.objects.filter(user=viewer, comment_id__in=context_ids).values_list(
                "comment_id", flat=True
            )
        )
        bookmarked_ids = set(
            CommentBookmark.objects.filter(user=viewer, comment_id__in=context_ids).values_list(
                "comment_id", flat=True
            )
        )

    comment.is_liked = comment.id in liked_ids
    comment.is_bookmarked = comment.id in bookmarked_ids

    # Formata ancestrais com placeholder seguro para nós bloqueados, excluídos ou ocultos
    ancestors = []
    for a in raw_ancestors:
        is_blocked = a.author_id in blocked_ids if a.author_id else False
        is_hidden_from_viewer = a.is_hidden and not (
            viewer
            and viewer.is_authenticated
            and (a.author_id == viewer.id or a.post.author_id == viewer.id)
        )
        is_placeholder = is_blocked or a.is_deleted or is_hidden_from_viewer
        if is_placeholder:
            a.author = None
            a.content_text = ""
        a.placeholder_reason = (
            "block"
            if is_blocked
            else ("hidden" if is_hidden_from_viewer else ("deleted" if a.is_deleted else None))
        )
        a.is_liked = a.id in liked_ids if not is_blocked else False
        a.is_bookmarked = a.id in bookmarked_ids if not is_blocked else False
        a.is_placeholder = is_placeholder
        a.is_muted = (a.author_id in muted_ids) if a.author_id else False
        ancestors.append(a)

    # Primeira página de respostas diretas
    replies_data = list_comment_replies(
        comment=comment,
        viewer=viewer,
        sort="recent",
        cursor=None,
        page_size=replies_page_size,
    )

    return {
        "post": comment.post,
        "ancestors": ancestors,
        "comment": comment,
        "replies": replies_data["items"],
        "next_cursor": replies_data["next_cursor"],
    }


def list_post_hidden_comments(
    *,
    post: Post,
    user,
    cursor: Optional[str] = None,
    page_size: int = 20,
) -> Dict[str, Any]:
    """
    Lista comentários ocultos de uma publicação (exclusivo para o proprietário do post).
    """
    if post.author_id != user.id:
        return {"items": [], "next_cursor": None}

    qs = (
        Comment.objects.filter(post=post, is_hidden=True)
        .select_related("author")
        .order_by("-hidden_at", "-created_at", "-id")
    )

    decoded = decode_cursor(cursor, "hidden")
    if decoded and len(decoded) == 2:
        cur_dt_raw, cur_id = parse_datetime(decoded[0]), decoded[1]
        if cur_dt_raw:
            qs = qs.filter(Q(hidden_at__lt=cur_dt_raw) | Q(hidden_at=cur_dt_raw, id__lt=cur_id))

    items = list(qs[: page_size + 1])
    has_more = len(items) > page_size
    items = items[:page_size]

    next_cursor = None
    if has_more and items:
        last = items[-1]
        dt = last.hidden_at or last.created_at
        next_cursor = encode_cursor([dt.isoformat(), str(last.id)], "hidden")

    return {"items": items, "next_cursor": next_cursor}
