import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  MoreHorizontal,
  Edit2,
  Trash2,
  EyeOff,
  VolumeX,
  Ban,
  Check,
  X,
} from "lucide-react";
import { HeartIcon, SpeechBubbleIcon, BookmarkIcon } from "./CommentIcons";
import { RichText } from "./RichText";
import { MediaViewer } from "./MediaAttachment";
import { formatDistanceToNow } from "../utils/date";
import { useAuth } from "../hooks/useAuth";
import {
  editPost,
  deletePost,
  muteUser,
  blockUser,
  api,
} from "../services/api";

const MAX_COLLAPSED_LENGTH = 280;

export function PostCard({
  post,
  isDetail = false,
  onDelete,
  onViewHidden,
  currentUser,
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  let authUser = null;
  try {
    const auth = useAuth();
    authUser = auth?.user || null;
  } catch {
    authUser = null;
  }
  const user = currentUser || authUser;

  const authorName = post.author?.username || "anônimo";
  const dateFormatted = post.created_at ? formatDistanceToNow(post.created_at) : "";
  const isOwner = Boolean(user && user.username === authorName);

  const [contentText, setContentText] = useState(post.content_text || "");
  const [isEdited, setIsEdited] = useState(Boolean(post.is_edited));
  const [isLiked, setIsLiked] = useState(Boolean(post.is_liked));
  const [likesCount, setLikesCount] = useState(post.likes_count || 0);
  const [isBookmarked, setIsBookmarked] = useState(Boolean(post.is_bookmarked));
  const [bookmarksCount, setBookmarksCount] = useState(post.bookmarks_count || 0);
  const commentsCount = post.comments_count || 0;
  const hiddenCount = post.hidden_comments_count || 0;

  const [showMenu, setShowMenu] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(post.content_text || "");
  const [submittingEdit, setSubmittingEdit] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [isMuted, setIsMuted] = useState(false);

  const handleToggleLike = async () => {
    if (actionLoading) return;
    setActionLoading(true);
    const prevLiked = isLiked;
    const prevCount = likesCount;

    setIsLiked(!prevLiked);
    setLikesCount(prevLiked ? Math.max(0, prevCount - 1) : prevCount + 1);

    try {
      if (prevLiked) {
        await api.delete(`/api/posts/${post.id}/like/`);
      } else {
        await api.post(`/api/posts/${post.id}/like/`);
      }
    } catch {
      setIsLiked(prevLiked);
      setLikesCount(prevCount);
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleBookmark = async () => {
    if (actionLoading) return;
    setActionLoading(true);
    const prevBookmarked = isBookmarked;
    const prevCount = bookmarksCount;

    setIsBookmarked(!prevBookmarked);
    setBookmarksCount(prevBookmarked ? Math.max(0, prevCount - 1) : prevCount + 1);

    try {
      if (prevBookmarked) {
        await api.delete(`/api/posts/${post.id}/bookmark/`);
      } else {
        await api.post(`/api/posts/${post.id}/bookmark/`);
      }
    } catch {
      setIsBookmarked(prevBookmarked);
      setBookmarksCount(prevCount);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCardClick = (e) => {
    if (isDetail) return;
    if (e.target.closest("a, button, input, textarea, video")) return;
    navigate(`/posts/${post.id}`);
  };

  const handleCommentClick = (e) => {
    e.stopPropagation();
    if (isDetail) {
      const inputEl = document.querySelector("[data-testid='root-comment-input']");
      if (inputEl) {
        inputEl.focus();
      }
      return;
    }
    navigate(`/posts/${post.id}`);
  };

  const handleStartEdit = (e) => {
    e.stopPropagation();
    setShowMenu(false);
    setEditText(contentText);
    setIsEditing(true);
  };

  const handleCancelEdit = (e) => {
    e.stopPropagation();
    setIsEditing(false);
    setEditText(contentText);
  };

  const handleSaveEdit = async (e) => {
    e.stopPropagation();
    const trimmed = editText.trim();
    if (!trimmed || submittingEdit) return;
    setSubmittingEdit(true);
    try {
      const updated = await editPost(post.id, trimmed);
      setContentText(updated?.content_text || trimmed);
      setIsEdited(true);
      setIsEditing(false);
    } catch (err) {
      console.error("Erro ao editar publicação:", err);
    } finally {
      setSubmittingEdit(false);
    }
  };

  const handleDeletePost = async (e) => {
    e.stopPropagation();
    setShowMenu(false);
    const confirmed = window.confirm(
      t("post.confirmDelete", "Tem certeza que deseja excluir esta publicação? Esta ação é irreversível.")
    );
    if (!confirmed || isDeleting) return;

    setIsDeleting(true);
    try {
      await deletePost(post.id);
      if (onDelete) {
        onDelete(post.id);
      } else if (isDetail) {
        navigate("/");
      }
    } catch (err) {
      console.error("Erro ao excluir publicação:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleMuteToggle = async (e) => {
    e.stopPropagation();
    setShowMenu(false);
    const confirmed = window.confirm(
      t("post.confirmMute", `Deseja silenciar @${authorName}?`, { username: authorName })
    );
    if (!confirmed) return;

    try {
      await muteUser(authorName);
      setIsMuted(true);
    } catch (err) {
      console.error("Erro ao silenciar usuário:", err);
    }
  };

  const handleBlockToggle = async (e) => {
    e.stopPropagation();
    setShowMenu(false);
    const confirmed = window.confirm(
      t("post.confirmBlock", `Tem certeza que deseja bloquear @${authorName}?`, { username: authorName })
    );
    if (!confirmed) return;

    try {
      await blockUser(authorName);
      if (onDelete) {
        onDelete(post.id);
      } else if (isDetail) {
        navigate("/");
      }
    } catch (err) {
      console.error("Erro ao bloquear usuário:", err);
    }
  };

  const handleViewHiddenReplies = (e) => {
    e.stopPropagation();
    setShowMenu(false);
    if (onViewHidden) {
      onViewHidden(post.id);
    } else {
      navigate(`/posts/${post.id}?tab=hidden`);
    }
  };

  // Truncamento de texto para feeds, explorar e busca
  const shouldTruncate = !isDetail && contentText.length > MAX_COLLAPSED_LENGTH;
  const displayedText = shouldTruncate && !isExpanded
    ? `${contentText.slice(0, MAX_COLLAPSED_LENGTH)}...`
    : contentText;

  return (
    <article
      data-testid="post-card"
      onClick={handleCardClick}
      className={`bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 hover:border-zinc-700 hover:bg-zinc-900/90 transition-all relative shadow-sm ${
        isDetail ? "" : "cursor-pointer"
      }`}
    >
      <header className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full overflow-hidden bg-zinc-800 border-2 border-zinc-700/60 flex items-center justify-center font-bold text-sm text-zinc-300 shrink-0 ring-2 ring-zinc-900">
            {post.author?.avatar ? (
              <img
                src={post.author.avatar}
                alt={post.author?.display_name || authorName}
                className="w-full h-full object-cover"
              />
            ) : (
              ((post.author?.display_name || authorName)[0] || "U").toUpperCase()
            )}
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {post.author?.display_name && (
              <span className="font-semibold text-sm text-zinc-100">
                {post.author.display_name}
              </span>
            )}
            <Link
              to={`/profile/${authorName}`}
              onClick={(e) => e.stopPropagation()}
              className="text-xs text-zinc-400 hover:text-pink-400 hover:underline transition"
            >
              @{authorName}
            </Link>
          </div>
          {post.visibility === "circle" && (
            <span
              data-testid="post-circle-badge"
              className="text-xs bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 px-1.5 py-0.5 rounded"
            >
              {t("post.visibility_circle")}
            </span>
          )}
          {isEdited && (
            <span className="text-xs text-zinc-500 font-normal">
              · {t("post.edited", "editado")}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {dateFormatted && (
            <time className="text-xs text-zinc-500">{dateFormatted}</time>
          )}

          {/* Menu «…» no estilo do Lumem */}
          <div className="relative">
            <button
              type="button"
              data-testid="post-menu-btn"
              onClick={(e) => {
                e.stopPropagation();
                setShowMenu(!showMenu);
              }}
              className="p-1.5 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-full transition-colors"
              title={t("post.actions", "Mais opções")}
            >
              <MoreHorizontal size={16} />
            </button>

            {showMenu && (
              <>
                <div
                  className="fixed inset-0 z-20 cursor-default"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowMenu(false);
                  }}
                />
                <div
                  data-testid="post-menu-dropdown"
                  onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 top-8 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl z-30 min-w-[170px] py-1 overflow-hidden"
                >
                  {isOwner ? (
                    <>
                      <button
                        type="button"
                        data-testid="post-edit-btn"
                        onClick={handleStartEdit}
                        className="w-full flex items-center gap-2 px-3.5 py-2 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 text-xs transition"
                      >
                        <Edit2 size={14} />
                        <span>{t("post.edit", "Editar")}</span>
                      </button>
                      <button
                        type="button"
                        data-testid="post-delete-btn"
                        onClick={handleDeletePost}
                        disabled={isDeleting}
                        className="w-full flex items-center gap-2 px-3.5 py-2 text-rose-400 hover:bg-rose-950/30 text-xs transition"
                      >
                        <Trash2 size={14} />
                        <span>{t("post.delete", "Excluir")}</span>
                      </button>
                      {hiddenCount > 0 && (
                        <button
                          type="button"
                          data-testid="post-hidden-replies-btn"
                          onClick={handleViewHiddenReplies}
                          className="w-full flex items-center gap-2 px-3.5 py-2 text-amber-400 hover:bg-amber-950/30 text-xs transition border-t border-zinc-800/80"
                        >
                          <EyeOff size={14} />
                          <span>
                            {t("post.hiddenRepliesCount", `Respostas ocultas (${hiddenCount})`, {
                              count: hiddenCount,
                            })}
                          </span>
                        </button>
                      )}
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        data-testid="post-mute-btn"
                        onClick={handleMuteToggle}
                        className="w-full flex items-center gap-2 px-3.5 py-2 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 text-xs transition"
                      >
                        <VolumeX size={14} />
                        <span>
                          {isMuted
                            ? t("post.unmuteUser", `Desilenciar @${authorName}`, { username: authorName })
                            : t("post.muteUser", `Silenciar @${authorName}`, { username: authorName })}
                        </span>
                      </button>
                      <button
                        type="button"
                        data-testid="post-block-btn"
                        onClick={handleBlockToggle}
                        className="w-full flex items-center gap-2 px-3.5 py-2 text-rose-400 hover:bg-rose-950/30 text-xs transition"
                      >
                        <Ban size={14} />
                        <span>
                          {t("post.blockUser", `Bloquear @${authorName}`, { username: authorName })}
                        </span>
                      </button>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Editor de texto inline */}
      {isEditing ? (
        <div className="mb-3" onClick={(e) => e.stopPropagation()}>
          <textarea
            data-testid="post-edit-textarea"
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg p-2.5 text-zinc-100 text-sm focus:outline-none focus:border-pink-500 resize-none break-words"
            rows={3}
            maxLength={3000}
            autoFocus
          />
          <div className="flex items-center justify-between mt-1 text-xs text-zinc-400">
            <span>{3000 - editText.length}</span>
            <div className="flex gap-2">
              <button
                type="button"
                data-testid="cancel-post-edit-btn"
                onClick={handleCancelEdit}
                className="px-3 py-1 text-zinc-400 hover:text-zinc-200 text-xs"
              >
                <X size={12} className="inline mr-1" />
                {t("comments.cancel", "Cancelar")}
              </button>
              <button
                type="button"
                data-testid="save-post-edit-btn"
                onClick={handleSaveEdit}
                disabled={submittingEdit || !editText.trim()}
                className="px-3 py-1 bg-pink-600 hover:bg-pink-500 disabled:opacity-50 text-white rounded-full text-xs font-medium"
              >
                <Check size={12} className="inline mr-1" />
                {t("comments.save", "Salvar")}
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* RENDERIZADO ESTRITAMENTE COMO ELEMENTOS REACT SEGUROS (SEM dangerouslySetInnerHTML) */
        <div className="mb-3">
          {displayedText && (
            <p
              data-testid="post-content"
              className="text-sm text-zinc-100 whitespace-pre-wrap break-words overflow-hidden"
            >
              <RichText text={displayedText} />
            </p>
          )}
          {shouldTruncate && (
            <button
              type="button"
              data-testid="show-more-btn"
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(!isExpanded);
              }}
              className="text-xs text-pink-400 hover:underline mt-1 font-medium"
            >
              {isExpanded ? t("post.showLess", "Mostrar menos") : t("post.showMore", "Mostrar mais")}
            </button>
          )}
          <MediaViewer
            imageUrl={post.image_url}
            videoUrl={post.video_url}
            alt={t("post.media_alt", "Mídia da publicação")}
          />
        </div>
      )}

      {/* Barra de ações sociais com Coração, Balão de fala e Marcador */}
      <footer className="flex items-center gap-6 pt-2 border-t border-zinc-800/50 text-xs">
        {/* Curtir (Coração) */}
        <button
          type="button"
          data-testid="like-button"
          onClick={handleToggleLike}
          disabled={actionLoading}
          className={`group flex items-center gap-1.5 transition-colors ${
            isLiked ? "text-rose-500" : "text-zinc-400 hover:text-rose-500"
          }`}
          title={isLiked ? t("post.unlike", "Descurtir") : t("post.like", "Curtir")}
        >
          <HeartIcon size={16} filled={isLiked} />
          <span data-testid="likes-count">{likesCount}</span>
        </button>

        {/* Comentários (Balão de fala) */}
        <button
          type="button"
          data-testid="comment-button"
          onClick={handleCommentClick}
          className="group flex items-center gap-1.5 text-zinc-400 hover:text-sky-400 transition-colors"
          title={t("comments.title", "Comentários")}
        >
          <SpeechBubbleIcon size={16} />
          <span data-testid="comments-count">{commentsCount}</span>
        </button>

        {/* Salvar (Marcador) */}
        <button
          type="button"
          data-testid="bookmark-button"
          onClick={handleToggleBookmark}
          disabled={actionLoading}
          className={`group flex items-center gap-1.5 transition-colors ${
            isBookmarked ? "text-pink-400" : "text-zinc-400 hover:text-pink-400"
          }`}
          title={isBookmarked ? t("bookmarks.saved", "Salvo") : t("bookmarks.save", "Salvar")}
        >
          <BookmarkIcon size={15} filled={isBookmarked} />
          <span data-testid="bookmarks-count">{bookmarksCount}</span>
        </button>
      </footer>
    </article>
  );
}

export default PostCard;
