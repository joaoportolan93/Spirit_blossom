import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  MoreHorizontal,
  Edit2,
  Trash2,
  EyeOff,
  VolumeX,
  Ban,
  Flag,
  Check,
  X,
  CornerDownRight,
  Image as ImageIcon,
  Video as VideoIcon,
} from "lucide-react";
import {
  HeartIcon,
  SpeechBubbleIcon,
  BookmarkIcon,
} from "./CommentIcons";
import { RichText } from "./RichText";
import { MediaPreview, MediaViewer, useMediaSelection } from "./MediaAttachment";
import { ReportModal } from "./ReportModal";
import {
  toggleCommentLike,
  toggleCommentBookmark,
  editComment,
  deleteComment,
  hideComment,
  unhideComment,
  muteUser,
  blockUser,
} from "../services/api";

const LINE_BG = "bg-zinc-700";
const LINE_BORDER = "border-zinc-700";

function stopEventPropagation(e) {
  e.stopPropagation();
}

/**
 * Renderizador de texto seguro com destaque de @menções e #hashtags sem dangerouslySetInnerHTML.
 */
function SafeCommentText({ text, hero = false }) {
  if (!text) return null;

  return (
    <p
      className={`text-zinc-100 break-words whitespace-pre-wrap ${
        hero ? "text-xl leading-snug font-normal" : "text-sm leading-relaxed mt-1"
      }`}
      data-testid="comment-text"
    >
      <RichText text={text} />
    </p>
  );
}

export const CommentItem = React.memo(function CommentItem({
  comment,
  postId,
  postAuthorId,
  postAuthorUsername,
  currentUserId,
  currentUser,
  depth = 0,
  isLast = false,
  flat = false,
  hero = false,
  threadLine = false,
  connectFromAbove = false,
  onFocusThread,
  onDelete,
  onReplySubmit,
  onHideToggle,
  activeReplyId,
  setActiveReplyId,
}) {
  const { t } = useTranslation();

  const [isLiked, setIsLiked] = useState(comment.is_liked || false);
  const [likesCount, setLikesCount] = useState(comment.likes_count || 0);
  const [isBookmarked, setIsBookmarked] = useState(comment.is_bookmarked || false);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(comment.content_text || "");
  const [submitting, setSubmitting] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [showMenu, setShowMenu] = useState(false);
  const [isHidden, setIsHidden] = useState(Boolean(comment.is_hidden));
  const [hidingLoading, setHidingLoading] = useState(false);
  const [showMutedContent, setShowMutedContent] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const {
    selectedImage: replyImage,
    selectedVideo: replyVideo,
    mediaPreview: replyPreview,
    mediaType: replyMediaType,
    mediaError: replyMediaError,
    setMediaError: setReplyMediaError,
    imageInputRef: replyImageInputRef,
    gifInputRef: replyGifInputRef,
    videoInputRef: replyVideoInputRef,
    handleImageSelect: handleReplyImageSelect,
    handleVideoSelect: handleReplyVideoSelect,
    clearMedia: clearReplyMedia,
  } = useMediaSelection(t);

  const hasReplies = comment.preview_replies && comment.preview_replies.length > 0;
  const showInlineReplies = hasReplies && !flat && !hero && depth < 2;
  const isReplying = activeReplyId === comment.id;

  const isDeleted = Boolean(comment.is_deleted);
  const isPlaceholder = Boolean(comment.is_placeholder);
  const isBlockPlaceholder = Boolean(isPlaceholder && comment.placeholder_reason === "block");
  const isMuted = Boolean(comment.is_muted);

  const isAuthor = Boolean(
    comment.can_delete ||
      (currentUserId && comment.author?.id === currentUserId) ||
      (currentUser && comment.author?.username === currentUser.username)
  );

  const isPostOwner = Boolean(
    comment.can_hide ||
      (postAuthorId && currentUserId && postAuthorId === currentUserId) ||
      (postAuthorUsername && currentUser && postAuthorUsername === currentUser.username)
  );

  const handleCardClick = (e) => {
    if (e.target.closest("button, a, input, textarea, video")) return;
    if (window.getSelection()?.toString()) return;

    if (onFocusThread && (depth >= 2 || flat)) {
      onFocusThread(comment);
    }
  };

  const handleOpenEdit = (e) => {
    e.stopPropagation();
    setShowMenu(false);
    setIsEditing(true);
  };

  const handleCancelEdit = (e) => {
    if (e?.stopPropagation) e.stopPropagation();
    setIsEditing(false);
  };

  const handleToggleReply = (e) => {
    e.stopPropagation();
    if (setActiveReplyId) {
      setActiveReplyId(isReplying ? null : comment.id);
    }
  };

  const handleCancelReply = (e) => {
    if (e?.stopPropagation) e.stopPropagation();
    if (setActiveReplyId) {
      setActiveReplyId(null);
    }
  };

  const handleFocusClick = (e) => {
    e.stopPropagation();
    if (onFocusThread) {
      onFocusThread(comment);
    }
  };

  const handleLike = async (e) => {
    e.stopPropagation();
    try {
      const data = await toggleCommentLike(comment.id);
      setIsLiked(data.is_liked);
      setLikesCount(data.likes_count);
    } catch (err) {
      console.error("Erro ao curtir comentário:", err);
    }
  };

  const handleBookmark = async (e) => {
    e.stopPropagation();
    try {
      const data = await toggleCommentBookmark(comment.id);
      setIsBookmarked(data.is_bookmarked);
    } catch (err) {
      console.error("Erro ao salvar comentário:", err);
    }
  };

  const handleSaveEdit = async (e) => {
    e.stopPropagation();
    if (!editText.trim()) return;
    setSubmitting(true);
    try {
      const updated = await editComment(comment.id, editText.trim());
      comment.content_text = updated.content_text;
      comment.is_edited = true;
      setIsEditing(false);
    } catch (err) {
      console.error("Erro ao editar comentário:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (e) => {
    e.stopPropagation();
    setShowMenu(false);
    if (!window.confirm(t("comments.confirmDelete", "Excluir este comentário?"))) return;
    try {
      await deleteComment(comment.id);
      if (onDelete) onDelete(comment.id);
    } catch (err) {
      console.error("Erro ao excluir comentário:", err);
    }
  };

  const handleToggleHide = async (e) => {
    e.stopPropagation();
    setShowMenu(false);
    if (hidingLoading) return;
    setHidingLoading(true);
    try {
      if (isHidden) {
        await unhideComment(comment.id);
        setIsHidden(false);
        comment.is_hidden = false;
        if (onHideToggle) onHideToggle(comment.id, false);
      } else {
        await hideComment(comment.id);
        setIsHidden(true);
        comment.is_hidden = true;
        if (onHideToggle) onHideToggle(comment.id, true);
      }
    } catch (err) {
      console.error("Erro ao alternar ocultação de comentário:", err);
    } finally {
      setHidingLoading(false);
    }
  };

  const handleMuteCommenter = async (e) => {
    e.stopPropagation();
    setShowMenu(false);
    const authorUsername = comment.author?.username;
    if (!authorUsername) return;
    if (
      !window.confirm(
        t("comments.confirmMute", `Deseja silenciar @${authorUsername}?`, {
          username: authorUsername,
        })
      )
    )
      return;
    try {
      await muteUser(authorUsername);
    } catch (err) {
      console.error("Erro ao silenciar autor do comentário:", err);
    }
  };

  const handleBlockCommenter = async (e) => {
    e.stopPropagation();
    setShowMenu(false);
    const authorUsername = comment.author?.username;
    if (!authorUsername) return;
    if (
      !window.confirm(
        t("comments.confirmBlock", `Tem certeza que deseja bloquear @${authorUsername}?`, {
          username: authorUsername,
        })
      )
    )
      return;
    try {
      await blockUser(authorUsername);
      if (onDelete) onDelete(comment.id);
    } catch (err) {
      console.error("Erro ao bloquear autor do comentário:", err);
    }
  };

  const handleReplySubmit = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const trimmed = replyText.trim();
    if ((!trimmed && !replyImage && !replyVideo) || submitting) return;
    setSubmitting(true);
    setReplyMediaError("");
    try {
      const payload =
        replyImage || replyVideo
          ? { content_text: trimmed, image: replyImage, video: replyVideo }
          : trimmed;
      await onReplySubmit(payload, comment.id);
      setReplyText("");
      clearReplyMedia();
      if (setActiveReplyId) setActiveReplyId(null);
    } catch (err) {
      console.error("Erro ao responder comentário:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const renderReplyForm = (isHeroMode = false) => {
    if (!isReplying) return null;
    const canSubmitReply = Boolean(replyText.trim() || replyImage || replyVideo);
    return (
      <form
        onSubmit={handleReplySubmit}
        onClick={stopEventPropagation}
        className={`mt-3 ${isHeroMode ? "pt-3 border-t border-zinc-800/60" : "pt-2"}`}
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder={t("comments.replyPlaceholder", "Postar sua resposta...")}
            className={`flex-1 bg-zinc-900 border border-zinc-700 rounded-full text-zinc-100 text-xs focus:outline-none focus:border-pink-500 ${
              isHeroMode ? "px-3.5 py-1.5" : "px-3 py-1.5"
            }`}
            maxLength={1000}
            autoFocus
            data-testid={`reply-input-${comment.id}`}
          />
          <button
            type="submit"
            disabled={submitting || !canSubmitReply}
            className={`bg-pink-600 hover:bg-pink-500 disabled:opacity-50 text-white text-xs font-medium rounded-full ${
              isHeroMode ? "px-3.5 py-1.5" : "px-3 py-1.5"
            }`}
            data-testid={`reply-submit-btn-${comment.id}`}
          >
            {t("comments.post", "Responder")}
          </button>
          <button
            type="button"
            onClick={(e) => {
              clearReplyMedia();
              handleCancelReply(e);
            }}
            className="px-2 text-zinc-500 hover:text-zinc-300 text-xs"
          >
            {t("comments.cancel", "Cancelar")}
          </button>
        </div>
        <div className="flex items-center gap-1 mt-1.5">
          <input
            ref={replyImageInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            onChange={handleReplyImageSelect}
            data-testid={`reply-image-input-${comment.id}`}
            className="hidden"
          />
          <input
            ref={replyGifInputRef}
            type="file"
            accept="image/gif"
            onChange={handleReplyImageSelect}
            data-testid={`reply-gif-input-${comment.id}`}
            className="hidden"
          />
          <input
            ref={replyVideoInputRef}
            type="file"
            accept="video/mp4,video/webm,video/quicktime"
            onChange={handleReplyVideoSelect}
            data-testid={`reply-video-input-${comment.id}`}
            className="hidden"
          />
          <button
            type="button"
            data-testid={`reply-image-btn-${comment.id}`}
            onClick={() => replyImageInputRef.current?.click()}
            disabled={submitting}
            className="p-1 rounded-lg text-pink-400 hover:text-pink-300 hover:bg-pink-500/10 transition"
            title={t("post.add_media", "Adicionar mídia")}
            aria-label={t("post.add_media", "Adicionar mídia")}
          >
            <ImageIcon size={14} />
          </button>
          <button
            type="button"
            data-testid={`reply-gif-btn-${comment.id}`}
            onClick={() => replyGifInputRef.current?.click()}
            disabled={submitting}
            className="px-1.5 py-0.5 rounded-md text-pink-400 hover:text-pink-300 hover:bg-pink-500/10 text-[10px] font-bold border border-pink-500/30 transition"
            title={t("post.add_gif", "Adicionar GIF")}
            aria-label={t("post.add_gif", "Adicionar GIF")}
          >
            GIF
          </button>
          <button
            type="button"
            data-testid={`reply-video-btn-${comment.id}`}
            onClick={() => replyVideoInputRef.current?.click()}
            disabled={submitting}
            className="p-1 rounded-lg text-pink-400 hover:text-pink-300 hover:bg-pink-500/10 transition"
            title={t("post.add_video", "Adicionar vídeo")}
            aria-label={t("post.add_video", "Adicionar vídeo")}
          >
            <VideoIcon size={14} />
          </button>
        </div>
        <MediaPreview
          previewUrl={replyPreview}
          mediaType={replyMediaType}
          onClear={clearReplyMedia}
          t={t}
          compact
        />
        {replyMediaError && (
          <p className="text-xs text-rose-500 mt-1">{replyMediaError}</p>
        )}
      </form>
    );
  };

  // Linha que chega ao avatar vindo do item de cima na trilha
  const connectLineEl = connectFromAbove ? (
    <span
      aria-hidden="true"
      className={`absolute -top-[13px] left-1/2 h-[9px] w-0.5 -translate-x-1/2 sm:-top-[17px] sm:h-[13px] ${LINE_BG}`}
    />
  ) : null;

  // Avatar neutro sem '?' para excluídos e placeholders
  const avatarEl = (
    <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-300 font-semibold text-xs border-2 border-zinc-700/60 overflow-hidden shrink-0">
      {isDeleted || isPlaceholder ? (
        <div className="w-full h-full bg-zinc-800/80" data-testid="empty-avatar" />
      ) : comment.author?.avatar ? (
        <img
          src={comment.author.avatar}
          alt={comment.author.username}
          className="w-full h-full object-cover"
        />
      ) : (
        <span>{comment.author?.username?.[0]?.toUpperCase() || "U"}</span>
      )}
    </div>
  );

  // Menu «…» de ações do comentário
  const renderMenu = () => {
    if (isDeleted || isPlaceholder) return null;

    const canEdit = Boolean(comment.can_edit && !isEditing);
    const canDelete = Boolean(comment.can_delete);
    const canHide = Boolean(comment.can_hide || (isPostOwner && !isAuthor));
    const isOtherUser = !isAuthor && !canHide;

    if (!canEdit && !canDelete && !canHide && !isOtherUser) return null;

    return (
      <div className="relative" onClick={stopEventPropagation}>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setShowMenu(!showMenu);
          }}
          className="p-1 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded transition"
          data-testid={`comment-menu-btn-${comment.id}`}
          title={t("comments.actions", "Mais opções")}
        >
          <MoreHorizontal size={14} />
        </button>

        {showMenu && (
          <div
            className="fixed inset-0 z-20 cursor-default"
            onClick={(e) => {
              e.stopPropagation();
              setShowMenu(false);
            }}
          />
        )}

        {/* Dropdown Menu */}
        <div
          data-testid={`comment-menu-dropdown-${comment.id}`}
          className={`absolute right-0 top-6 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl z-30 min-w-[150px] py-1 text-xs overflow-hidden ${
            showMenu ? "block" : "hidden"
          }`}
        >
          {canEdit && (
            <button
              type="button"
              onClick={handleOpenEdit}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 text-left transition"
              data-testid={`edit-comment-btn-${comment.id}`}
            >
              <Edit2 size={12} />
              <span>{t("comments.edit", "Editar")}</span>
            </button>
          )}

          {canDelete && (
            <button
              type="button"
              onClick={handleDelete}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-rose-400 hover:bg-rose-950/30 text-left transition"
              data-testid={`delete-comment-btn-${comment.id}`}
            >
              <Trash2 size={12} />
              <span>{t("comments.delete", "Excluir")}</span>
            </button>
          )}

          {canHide && (
            <button
              type="button"
              onClick={handleToggleHide}
              disabled={hidingLoading}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-amber-400 hover:bg-amber-950/30 text-left transition"
              data-testid={
                isHidden
                  ? `unhide-comment-btn-${comment.id}`
                  : `hide-comment-btn-${comment.id}`
              }
            >
              <EyeOff size={12} />
              <span>
                {isHidden
                  ? t("comments.unhideReply", "Reexibir")
                  : t("comments.hideReply", "Ocultar resposta")}
              </span>
            </button>
          )}

          {isOtherUser && (
            <>
              <button
                type="button"
                onClick={handleMuteCommenter}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 text-left transition"
                data-testid={`mute-comment-user-btn-${comment.id}`}
              >
                <VolumeX size={12} />
                <span>
                  {t("comments.muteUser", `Silenciar @${comment.author?.username}`, {
                    username: comment.author?.username,
                  })}
                </span>
              </button>
              <button
                type="button"
                onClick={handleBlockCommenter}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-rose-400 hover:bg-rose-950/30 text-left transition"
                data-testid={`block-comment-user-btn-${comment.id}`}
              >
                <Ban size={12} />
                <span>
                  {t("comments.blockUser", `Bloquear @${comment.author?.username}`, {
                    username: comment.author?.username,
                  })}
                </span>
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMenu(false);
                  setReportOpen(true);
                }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-amber-400 hover:bg-amber-950/30 text-left transition border-t border-zinc-800/80"
                data-testid={`report-comment-btn-${comment.id}`}
              >
                <Flag size={12} />
                <span>{t("report.action", "Denunciar")}</span>
              </button>
            </>
          )}
        </div>
      </div>
    );
  };

  // Barra de ações sociais com Coração, Balão de fala e Marcador
  const renderActions = () => {
    if (isDeleted || isPlaceholder) return null;

    return (
      <div className="flex items-center gap-6 mt-3 text-xs text-zinc-400">
        {/* Curtir (Coração) */}
        <button
          type="button"
          onClick={handleLike}
          className={`group flex items-center gap-1.5 transition-colors ${
            isLiked ? "text-rose-500" : "hover:text-rose-500"
          }`}
          data-testid={`like-btn-${comment.id}`}
          title={isLiked ? t("post.unlike", "Descurtir") : t("post.like", "Curtir")}
        >
          <HeartIcon size={16} filled={isLiked} />
          <span className="text-xs font-medium">{likesCount > 0 ? likesCount : ""}</span>
        </button>

        {/* Responder (Balão de fala) */}
        <button
          type="button"
          onClick={handleToggleReply}
          className={`group flex items-center gap-1.5 transition-colors ${
            isReplying ? "text-sky-400" : "hover:text-sky-400"
          }`}
          data-testid={`reply-btn-${comment.id}`}
          title={t("comments.reply", "Responder")}
        >
          <SpeechBubbleIcon size={16} />
          <span className="text-xs font-medium">
            {comment.replies_count > 0 ? comment.replies_count : ""}
          </span>
        </button>

        {/* Salvar (Marcador) */}
        <button
          type="button"
          onClick={handleBookmark}
          className={`flex items-center gap-1.5 transition-colors ${
            isBookmarked ? "text-pink-400" : "hover:text-pink-400"
          }`}
          data-testid={`bookmark-btn-${comment.id}`}
          title={isBookmarked ? t("bookmarks.saved", "Salvo") : t("bookmarks.save", "Salvar")}
        >
          <BookmarkIcon size={14} filled={isBookmarked} />
        </button>

        {/* Link para Focar se tiver respostas além do inline */}
        {depth >= 2 && comment.replies_count > 0 && !flat && (
          <button
            type="button"
            onClick={handleFocusClick}
            className="ml-auto text-pink-400 hover:underline flex items-center gap-1 text-xs"
            data-testid={`focus-btn-${comment.id}`}
          >
            <span>{t("comments.viewThread", "Ver conversa")}</span>
            <CornerDownRight size={12} />
          </button>
        )}
      </div>
    );
  };

  // ── HERO VIEW (Comentário focado estilo Twitter/X) ─────────────────────────
  if (hero) {
    return (
      <div className="relative" data-testid={`comment-node-${comment.id}`}>
        <article
          id={`comment-${comment.id}`}
          className="relative px-3 pt-3 pb-3 sm:px-4 sm:pt-4 sm:pb-4"
        >
          <div className="flex items-center gap-2.5 sm:gap-3">
            <div className="relative flex-shrink-0 self-start">
              {connectLineEl}
              {comment.author?.username ? (
                <Link to={`/profile/${comment.author.username}`}>{avatarEl}</Link>
              ) : (
                avatarEl
              )}
            </div>

            <div className="min-w-0 flex-1 leading-tight">
              {isDeleted ? (
                <div className="italic text-zinc-500 text-sm">
                  {t("comments.deletedAuthor", "[removido]")}
                </div>
              ) : isBlockPlaceholder ? (
                <div className="italic text-zinc-500 text-sm">
                  {t("comments.blockedAuthor", "[conta bloqueada]")}
                </div>
              ) : isPlaceholder ? (
                <div className="italic text-zinc-500 text-sm">
                  {t("comments.unavailable", "[indisponível]")}
                </div>
              ) : (
                <>
                  <div className="font-bold text-zinc-100 text-[15px] truncate hover:underline cursor-pointer">
                    {comment.author?.username}
                  </div>
                  <div className="text-zinc-400 text-sm truncate">
                    @{comment.author?.username}
                    {comment.is_edited && (
                      <span className="mx-1 text-zinc-500">· {t("comments.edited", "editado")}</span>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Menu «…» de ações */}
            {renderMenu()}
          </div>

          <div className="mt-3">
            {isEditing ? (
              <div className="mt-2" onClick={stopEventPropagation}>
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-2.5 text-zinc-100 text-sm focus:outline-none focus:border-pink-500 resize-none break-words"
                  rows={2}
                  maxLength={1000}
                  autoFocus
                />
                <div className="flex gap-2 mt-1.5 justify-end">
                  <button
                    type="button"
                    onClick={handleCancelEdit}
                    className="px-3 py-1 text-xs text-zinc-400 hover:text-zinc-200 rounded-full"
                  >
                    <X size={12} className="inline mr-1" />
                    {t("comments.cancel", "Cancelar")}
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveEdit}
                    disabled={submitting || !editText.trim()}
                    className="px-3 py-1 bg-pink-600 hover:bg-pink-500 disabled:opacity-50 text-white text-xs font-medium rounded-full"
                    data-testid="save-edit-btn"
                  >
                    <Check size={12} className="inline mr-1" />
                    {t("comments.save", "Salvar")}
                  </button>
                </div>
              </div>
            ) : isDeleted ? (
              <p className="text-zinc-500 text-sm italic" data-testid="tombstone-text">
                {t("comments.deletedText", "[comentário excluído]")}
              </p>
            ) : isBlockPlaceholder ? (
              <p className="text-zinc-500 text-sm italic" data-testid="blocked-comment-text">
                {t("comments.blockedText", "[comentário de conta bloqueada]")}
              </p>
            ) : isPlaceholder ? (
              <p className="text-zinc-600 text-sm italic">
                {t("comments.unavailableText", "[indisponível]")}
              </p>
            ) : isMuted && !showMutedContent ? (
              <button
                type="button"
                onClick={(e) => {
                  stopEventPropagation(e);
                  setShowMutedContent(true);
                }}
                className="text-xs text-zinc-500 hover:text-zinc-300 italic py-1 flex items-center gap-1.5"
                data-testid={`show-muted-comment-${comment.id}`}
              >
                <VolumeX size={12} />
                <span>{t("comments.showMutedComment", "Mostrar comentário")}</span>
              </button>
            ) : (
              <div>
                <SafeCommentText text={comment.content_text} hero={true} />
                <MediaViewer
                  imageUrl={comment.image_url}
                  videoUrl={comment.video_url}
                  alt={t("post.media_alt", "Mídia da publicação")}
                  compact
                />
                {isMuted && (
                  <button
                    type="button"
                    onClick={(e) => {
                      stopEventPropagation(e);
                      setShowMutedContent(false);
                    }}
                    className="text-[11px] text-zinc-500 hover:text-zinc-300 mt-1 block"
                  >
                    {t("comments.hideMutedComment", "Ocultar")}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Data e hora completa no modo Hero */}
          {!isDeleted && !isPlaceholder && comment.created_at && (
            <div className="mt-3 pt-2 text-xs text-zinc-500 border-t border-zinc-800/40">
              <time>{new Date(comment.created_at).toLocaleString()}</time>
            </div>
          )}

          {renderActions()}

          {/* Formulário de resposta quando ativo */}
          {renderReplyForm(true)}
        </article>
      </div>
    );
  }

  // ── MODO NORMAL E ÁRVORE ───────────────────────────────────────────────────
  return (
    <div
      className="relative select-text"
      data-testid={`comment-node-${comment.id}`}
      id={`comment-${comment.id}`}
    >
      {/* Conector em L até o avatar (+ linha contínua se houver irmão abaixo) */}
      {depth > 0 && (
        <>
          <span
            aria-hidden="true"
            className={`pointer-events-none absolute left-0 top-0 h-[31px] w-3 rounded-bl-xl border-b-2 border-l-2 sm:h-[37px] sm:w-4 ${LINE_BORDER}`}
          />
          {!isLast && (
            <span
              aria-hidden="true"
              className={`pointer-events-none absolute inset-y-0 left-0 w-0.5 ${LINE_BG}`}
            />
          )}
        </>
      )}

      <article
        onClick={handleCardClick}
        className={`relative transition-colors ${
          flat ? "" : "rounded-xl"
        } ${
          depth >= 2 && !flat
            ? "cursor-pointer hover:bg-zinc-900/50"
            : ""
        }`}
      >
        <div className="flex gap-2.5 sm:gap-3 px-3 pt-3 sm:px-4 sm:pt-4 relative">
          {/* Coluna do avatar */}
          <div className="relative flex w-9 sm:w-10 flex-shrink-0 flex-col items-center">
            {connectLineEl}
            {comment.author?.username ? (
              <Link to={`/profile/${comment.author.username}`} onClick={stopEventPropagation}>
                {avatarEl}
              </Link>
            ) : (
              avatarEl
            )}
            {threadLine && (
              <div aria-hidden="true" className={`mt-1 min-h-[8px] w-0.5 flex-1 ${LINE_BG}`} />
            )}
            {showInlineReplies && (
              <div aria-hidden="true" className={`mt-1 min-h-[16px] w-0.5 flex-1 ${LINE_BG}`} />
            )}
          </div>

          {/* Coluna de conteúdo */}
          <div className="flex-1 min-w-0 pb-3 sm:pb-4">
            <div className="flex items-center justify-between gap-2 mb-1">
              <div className="flex items-center gap-1.5 truncate text-xs">
                {isDeleted ? (
                  <span className="italic text-zinc-500">
                    {t("comments.deletedAuthor", "[removido]")}
                  </span>
                ) : isBlockPlaceholder ? (
                  <span className="italic text-zinc-500">
                    {t("comments.blockedAuthor", "[conta bloqueada]")}
                  </span>
                ) : isPlaceholder ? (
                  <span className="italic text-zinc-500">
                    {t("comments.unavailable", "[indisponível]")}
                  </span>
                ) : (
                  <>
                    <Link
                      to={`/profile/${comment.author?.username}`}
                      onClick={stopEventPropagation}
                      className="font-semibold text-zinc-200 hover:underline truncate"
                    >
                      {comment.author?.username}
                    </Link>
                    {comment.is_edited && (
                      <span className="text-zinc-500 text-[11px]">
                        · {t("comments.edited", "editado")}
                      </span>
                    )}
                  </>
                )}
              </div>

              {/* Menu «…» de ações */}
              {renderMenu()}
            </div>

            {/* Corpo do comentário ou editor */}
            {isEditing ? (
              <div className="mt-2" onClick={stopEventPropagation}>
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-2.5 text-zinc-100 text-sm focus:outline-none focus:border-pink-500 resize-none break-words"
                  rows={2}
                  maxLength={1000}
                  autoFocus
                />
                <div className="flex gap-2 mt-1.5 justify-end">
                  <button
                    type="button"
                    onClick={handleCancelEdit}
                    className="px-3 py-1 text-xs text-zinc-400 hover:text-zinc-200 rounded-full"
                  >
                    <X size={12} className="inline mr-1" />
                    {t("comments.cancel", "Cancelar")}
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveEdit}
                    disabled={submitting || !editText.trim()}
                    className="px-3 py-1 bg-pink-600 hover:bg-pink-500 disabled:opacity-50 text-white text-xs font-medium rounded-full"
                    data-testid="save-edit-btn"
                  >
                    <Check size={12} className="inline mr-1" />
                    {t("comments.save", "Salvar")}
                  </button>
                </div>
              </div>
            ) : isDeleted ? (
              <p className="text-zinc-500 text-xs italic mt-1" data-testid="tombstone-text">
                {t("comments.deletedText", "[comentário excluído]")}
              </p>
            ) : isBlockPlaceholder ? (
              <p className="text-zinc-500 text-xs italic mt-1" data-testid="blocked-comment-text">
                {t("comments.blockedText", "[comentário de conta bloqueada]")}
              </p>
            ) : isPlaceholder ? (
              <p className="text-zinc-600 text-xs italic mt-1">
                {t("comments.unavailableText", "[indisponível]")}
              </p>
            ) : isMuted && !showMutedContent ? (
              <button
                type="button"
                onClick={(e) => {
                  stopEventPropagation(e);
                  setShowMutedContent(true);
                }}
                className="text-xs text-zinc-500 hover:text-zinc-300 italic py-1 flex items-center gap-1.5"
                data-testid={`show-muted-comment-${comment.id}`}
              >
                <VolumeX size={12} />
                <span>{t("comments.showMutedComment", "Mostrar comentário")}</span>
              </button>
            ) : (
              <div>
                <SafeCommentText text={comment.content_text} hero={false} />
                <MediaViewer
                  imageUrl={comment.image_url}
                  videoUrl={comment.video_url}
                  alt={t("post.media_alt", "Mídia da publicação")}
                  compact
                />
                {isMuted && (
                  <button
                    type="button"
                    onClick={(e) => {
                      stopEventPropagation(e);
                      setShowMutedContent(false);
                    }}
                    className="text-[11px] text-zinc-500 hover:text-zinc-300 mt-1 block"
                  >
                    {t("comments.hideMutedComment", "Ocultar")}
                  </button>
                )}
              </div>
            )}

            {renderActions()}

            {/* Formulário de resposta quando ativo */}
            {renderReplyForm(false)}
          </div>
        </div>
      </article>

      {/* Respostas aninhadas em árvore (inline depth 1 e depth 2) */}
      {showInlineReplies && (
        <div className="relative pl-[29px] sm:pl-[35px]">
          {comment.preview_replies.map((reply, index) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              postId={postId}
              postAuthorId={postAuthorId}
              postAuthorUsername={postAuthorUsername}
              currentUserId={currentUserId}
              currentUser={currentUser}
              depth={depth + 1}
              isLast={index === comment.preview_replies.length - 1}
              onFocusThread={onFocusThread}
              onDelete={onDelete}
              onReplySubmit={onReplySubmit}
              onHideToggle={onHideToggle}
              activeReplyId={activeReplyId}
              setActiveReplyId={setActiveReplyId}
            />
          ))}
        </div>
      )}

      <ReportModal
        isOpen={reportOpen}
        targetType="comment"
        targetId={comment.id}
        targetLabel={comment.author?.username ? `@${comment.author.username}` : ""}
        onClose={() => setReportOpen(false)}
      />
    </div>
  );
});

export default CommentItem;
