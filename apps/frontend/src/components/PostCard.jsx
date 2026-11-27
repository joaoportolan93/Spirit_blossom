import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
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
  Clock,
  ChevronLeft,
  ChevronRight,
  Image as ImageIcon,
} from "lucide-react";
import { HeartIcon, SpeechBubbleIcon, BookmarkIcon } from "./CommentIcons";
import { RichText } from "./RichText";
import { MediaViewer } from "./MediaAttachment";
import { ReportModal } from "./ReportModal";
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

// ---------------------------------------------------------------------------
// Onda 9 — Helpers
// ---------------------------------------------------------------------------

/** Formata tempo restante de expiração em horas/dias — sem segundos. */
function formatEphemeralRemaining(expiresAt, t) {
  if (!expiresAt) return null;
  const ms = new Date(expiresAt).getTime() - Date.now();
  if (ms <= 0) return null;
  const totalHours = Math.ceil(ms / (1000 * 60 * 60));
  if (totalHours >= 24) {
    const days = Math.ceil(totalHours / 24);
    return t("post.ephemeral_days", { count: days });
  }
  return t("post.ephemeral_hours", { count: totalHours });
}

/** Grid adaptativo compacto de 1–4 imagens com respiro em relação ao texto. */
export function PostMediaGrid({ media, authorName, t, onOpenLightbox, compact = true }) {
  const [visibleAltIndex, setVisibleAltIndex] = useState(null);

  if (!media || media.length === 0) return null;

  const isSingle = media.length === 1;
  const isThree = media.length === 3;
  const maxWidthClass = compact ? "max-w-lg" : "max-w-full";
  const gridClass = isSingle
    ? "grid grid-cols-1"
    : "grid grid-cols-2 gap-1.5";

  return (
    <div
      data-testid="post-media-grid"
      className={`${gridClass} ${maxWidthClass} mt-3 rounded-xl overflow-hidden border border-zinc-800/50`}
    >
      {media.map((pm, idx) => {
        const altText =
          pm.alt_text ||
          t("post.media_alt_fallback", { username: authorName });
        const showingAlt = visibleAltIndex === idx;

        let cellSizeClass;
        if (isSingle) {
          cellSizeClass = compact ? "max-h-64 sm:max-h-72" : "max-h-96";
        } else if (media.length === 2) {
          cellSizeClass = compact ? "h-40 sm:h-44" : "h-56";
        } else if (isThree) {
          if (idx === 0) {
            cellSizeClass = compact ? "row-span-2 h-64 sm:h-72" : "row-span-2 h-80";
          } else {
            cellSizeClass = compact ? "h-[125px] sm:h-[141px]" : "h-[157px]";
          }
        } else {
          cellSizeClass = compact ? "h-32 sm:h-36" : "h-44";
        }

        return (
          <div
            key={pm.id || idx}
            className={`relative overflow-hidden bg-zinc-800 ${cellSizeClass}`}
          >
            <img
              data-testid={`post-media-${idx}`}
              src={pm.url}
              alt={altText}
              loading="lazy"
              className="w-full h-full object-cover cursor-pointer hover:opacity-90 transition"
              onClick={(e) => {
                e.stopPropagation();
                onOpenLightbox(idx);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onOpenLightbox(idx);
                }
              }}
              tabIndex={0}
              role="button"
              aria-label={t("post.open_image")}
            />
            {pm.alt_text && (
              <>
                <button
                  type="button"
                  data-testid={`post-alt-badge-${idx}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setVisibleAltIndex(showingAlt ? null : idx);
                  }}
                  aria-expanded={showingAlt}
                  aria-label={`${t("post.alt_badge")}: ${pm.alt_text}`}
                  title={pm.alt_text}
                  className="overlay-contrast absolute bottom-1.5 left-1.5 text-[10px] font-bold bg-black/75 text-white px-1.5 py-0.5 rounded hover:bg-black/90 transition"
                >
                  {t("post.alt_badge")}
                </button>
                {showingAlt && (
                  <div
                    role="note"
                    onClick={(e) => e.stopPropagation()}
                    className="overlay-contrast absolute inset-x-1.5 bottom-8 z-10 rounded-lg bg-black/85 text-white text-[11px] p-2 leading-snug shadow-lg"
                  >
                    {pm.alt_text}
                  </div>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Lightbox acessível por teclado. */
export function PostLightbox({ media, initialIndex, authorName, t, onClose }) {
  const [current, setCurrent] = useState(initialIndex);
  const closeBtnRef = useRef(null);

  useEffect(() => {
    const previousFocus = document.activeElement;
    closeBtnRef.current?.focus();
    return () => {
      if (previousFocus && typeof previousFocus.focus === "function") {
        previousFocus.focus();
      }
    };
  }, []);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") setCurrent((i) => (i - 1 + media.length) % media.length);
      else if (e.key === "ArrowRight") setCurrent((i) => (i + 1) % media.length);
    },
    [media.length, onClose],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const pm = media[current];
  const altText = pm?.alt_text || t("post.media_alt_fallback", { username: authorName });

  return (
    <div
      data-testid="post-lightbox"
      role="dialog"
      aria-modal="true"
      aria-label={t("post.open_image")}
      className="fixed inset-0 z-[200] flex flex-col items-center justify-center bg-black/90 p-4"
      onClick={onClose}
    >
      <button
        ref={closeBtnRef}
        type="button"
        onClick={onClose}
        className="overlay-contrast absolute top-4 right-4 p-2 text-white/90 hover:text-white bg-black/60 rounded-full focus:outline-none focus:ring-2 focus:ring-white/60"
        aria-label={t("post.close_lightbox")}
      >
        <X size={20} />
      </button>

      {media.length > 1 && (
        <>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setCurrent((i) => (i - 1 + media.length) % media.length); }}
            className="overlay-contrast absolute left-4 p-2 text-white/90 hover:text-white bg-black/60 rounded-full focus:outline-none focus:ring-2 focus:ring-white/60"
            aria-label={t("post.prev_image")}
          >
            <ChevronLeft size={24} />
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setCurrent((i) => (i + 1) % media.length); }}
            className="overlay-contrast absolute right-4 p-2 text-white/90 hover:text-white bg-black/60 rounded-full focus:outline-none focus:ring-2 focus:ring-white/60"
            aria-label={t("post.next_image")}
          >
            <ChevronRight size={24} />
          </button>
        </>
      )}

      <img
        src={pm?.url}
        alt={altText}
        className="max-w-[90vw] max-h-[80vh] object-contain rounded-xl"
        onClick={(e) => e.stopPropagation()}
      />

      {pm?.alt_text && (
        <p
          onClick={(e) => e.stopPropagation()}
          className="overlay-contrast mt-3 max-w-xl text-center text-xs text-white/90 bg-black/70 px-3 py-1.5 rounded-lg"
        >
          {pm.alt_text}
        </p>
      )}

      {media.length > 1 && (
        <div className="mt-3 flex gap-1.5">
          {media.map((_, i) => (
            <span
              key={i}
              className={`w-1.5 h-1.5 rounded-full transition ${i === current ? "bg-white" : "bg-white/40"}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

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
  const [mediaList, setMediaList] = useState(post.media || []);
  const [legacyImageUrl, setLegacyImageUrl] = useState(post.image_url || null);
  const [legacyVideoUrl, setLegacyVideoUrl] = useState(post.video_url || null);
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
  const [editKeptMedia, setEditKeptMedia] = useState([]);
  const [removedMediaIds, setRemovedMediaIds] = useState([]);
  const [editNewImages, setEditNewImages] = useState([]);
  const [editNewPreviewUrls, setEditNewPreviewUrls] = useState([]);
  const [editNewAltTexts, setEditNewAltTexts] = useState([]);
  const [removeLegacyImage, setRemoveLegacyImage] = useState(false);
  const [removeLegacyVideo, setRemoveLegacyVideo] = useState(false);
  const [editLegacyFile, setEditLegacyFile] = useState(null);
  const [editLegacyKind, setEditLegacyKind] = useState(null); // "image" | "video"
  const [editLegacyPreviewUrl, setEditLegacyPreviewUrl] = useState(null);
  const [editError, setEditError] = useState("");
  const [submittingEdit, setSubmittingEdit] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  // Onda 9: lightbox
  const [lightboxIndex, setLightboxIndex] = useState(null);
  const editMediaInputRef = useRef(null);
  const editPreviewsRef = useRef([]);
  const editLegacyPreviewRef = useRef(null);

  useEffect(() => {
    editPreviewsRef.current = editNewPreviewUrls;
  }, [editNewPreviewUrls]);

  useEffect(() => {
    editLegacyPreviewRef.current = editLegacyPreviewUrl;
  }, [editLegacyPreviewUrl]);

  useEffect(() => {
    return () => {
      editPreviewsRef.current.forEach((url) => URL.revokeObjectURL?.(url));
      if (editLegacyPreviewRef.current) URL.revokeObjectURL?.(editLegacyPreviewRef.current);
    };
  }, []);

  const clearEditMediaState = () => {
    editPreviewsRef.current.forEach((url) => URL.revokeObjectURL?.(url));
    if (editLegacyPreviewRef.current) URL.revokeObjectURL?.(editLegacyPreviewRef.current);
    setEditKeptMedia([]);
    setRemovedMediaIds([]);
    setEditNewImages([]);
    setEditNewPreviewUrls([]);
    setEditNewAltTexts([]);
    setRemoveLegacyImage(false);
    setRemoveLegacyVideo(false);
    setEditLegacyFile(null);
    setEditLegacyKind(null);
    setEditLegacyPreviewUrl(null);
    setEditError("");
  };

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
    clearEditMediaState();
    setEditText(contentText);
    setEditKeptMedia(mediaList.map((pm) => ({ ...pm })));
    setIsEditing(true);
  };

  const handleCancelEdit = (e) => {
    e.stopPropagation();
    clearEditMediaState();
    setIsEditing(false);
    setEditText(contentText);
  };

  const handleEditMediaSelect = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setEditError("");

    const isVideoFile = (f) =>
      f.type?.startsWith("video/") || /\.(mp4|webm|mov)$/i.test(f.name || "");
    const isGifFile = (f) =>
      f.type === "image/gif" || /\.gif$/i.test(f.name || "");

    const hasVideo = files.some(isVideoFile);
    const hasGif = files.some(isGifFile);
    const hasExistingMulti = editKeptMedia.length > 0 || editNewImages.length > 0;

    if (hasVideo || hasGif) {
      if (files.length > 1 || hasExistingMulti) {
        setEditError(t("post.media_mix_error"));
        e.target.value = "";
        return;
      }
      const single = files[0];
      const maxSize = hasVideo ? 50 * 1024 * 1024 : 5 * 1024 * 1024;
      if (single.size > maxSize) {
        setEditError(hasVideo ? t("post.video_too_large") : t("post.image_too_large"));
        e.target.value = "";
        return;
      }
      if (editLegacyPreviewRef.current) URL.revokeObjectURL?.(editLegacyPreviewRef.current);
      setEditLegacyFile(single);
      setEditLegacyKind(hasVideo ? "video" : "image");
      setEditLegacyPreviewUrl(URL.createObjectURL(single));
      if (hasVideo && legacyImageUrl) setRemoveLegacyImage(true);
      if (!hasVideo && legacyVideoUrl) setRemoveLegacyVideo(true);
      e.target.value = "";
      return;
    }

    if ((legacyImageUrl && !removeLegacyImage) || (legacyVideoUrl && !removeLegacyVideo) || editLegacyFile) {
      setEditError(t("post.media_mix_error"));
      e.target.value = "";
      return;
    }

    const oversized = files.find((f) => f.size > 5 * 1024 * 1024);
    if (oversized) {
      setEditError(t("post.image_too_large"));
      e.target.value = "";
      return;
    }

    const slots = 4 - (editKeptMedia.length + editNewImages.length);
    if (slots <= 0 || files.length > slots) {
      setEditError(t("post.max_images"));
    }
    const accepted = files.slice(0, Math.max(0, slots));
    if (accepted.length > 0) {
      const urls = accepted.map((f) => URL.createObjectURL(f));
      setEditNewImages((prev) => [...prev, ...accepted]);
      setEditNewPreviewUrls((prev) => [...prev, ...urls]);
      setEditNewAltTexts((prev) => [...prev, ...accepted.map(() => "")]);
    }
    e.target.value = "";
  };

  const handleEditRemoveKeptMedia = (mediaId) => {
    setEditKeptMedia((prev) => prev.filter((m) => m.id !== mediaId));
    setRemovedMediaIds((prev) => [...prev, mediaId]);
  };

  const handleEditKeptAltChange = (mediaId, value) => {
    setEditKeptMedia((prev) =>
      prev.map((m) => (m.id === mediaId ? { ...m, alt_text: value } : m))
    );
  };

  const handleEditRemoveNewImage = (idx) => {
    URL.revokeObjectURL?.(editNewPreviewUrls[idx]);
    setEditNewImages((prev) => prev.filter((_, i) => i !== idx));
    setEditNewPreviewUrls((prev) => prev.filter((_, i) => i !== idx));
    setEditNewAltTexts((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleEditNewAltChange = (idx, value) => {
    setEditNewAltTexts((prev) => {
      const next = [...prev];
      next[idx] = value;
      return next;
    });
  };

  const hasAnyEditedMedia =
    editKeptMedia.length > 0 ||
    editNewImages.length > 0 ||
    Boolean(legacyImageUrl && !removeLegacyImage) ||
    Boolean(legacyVideoUrl && !removeLegacyVideo) ||
    Boolean(editLegacyFile);

  const handleSaveEdit = async (e) => {
    e.stopPropagation();
    const trimmed = editText.trim();
    if ((!trimmed && !hasAnyEditedMedia) || submittingEdit) return;
    setSubmittingEdit(true);
    setEditError("");
    try {
      const altUpdates = {};
      editKeptMedia.forEach((kept) => {
        const orig = mediaList.find((m) => m.id === kept.id);
        if (orig && (orig.alt_text || "") !== (kept.alt_text || "")) {
          altUpdates[kept.id] = kept.alt_text || "";
        }
      });

      const hasMediaChanges =
        removedMediaIds.length > 0 ||
        editNewImages.length > 0 ||
        Object.keys(altUpdates).length > 0 ||
        removeLegacyImage ||
        removeLegacyVideo ||
        Boolean(editLegacyFile);

      let updated;
      if (!hasMediaChanges) {
        updated = await editPost(post.id, trimmed);
      } else {
        const formData = new FormData();
        formData.append("content_text", trimmed);
        if (removedMediaIds.length > 0) {
          formData.append("remove_media_ids", JSON.stringify(removedMediaIds));
        }
        if (Object.keys(altUpdates).length > 0) {
          formData.append("media_alt_updates", JSON.stringify(altUpdates));
        }
        editNewImages.forEach((img) => formData.append("images", img));
        editNewAltTexts.forEach((alt) => formData.append("alt_texts", alt));
        if (removeLegacyImage) formData.append("remove_image", "true");
        if (removeLegacyVideo) formData.append("remove_video", "true");
        if (editLegacyFile && editLegacyKind === "image") {
          formData.append("image", editLegacyFile);
        }
        if (editLegacyFile && editLegacyKind === "video") {
          formData.append("video", editLegacyFile);
        }
        updated = await editPost(post.id, formData);
      }

      setContentText(updated?.content_text ?? trimmed);
      if (Array.isArray(updated?.media)) setMediaList(updated.media);
      if (updated && "image_url" in updated) setLegacyImageUrl(updated.image_url);
      if (updated && "video_url" in updated) setLegacyVideoUrl(updated.video_url);
      setIsEdited(true);
      clearEditMediaState();
      setIsEditing(false);
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.content_text?.[0] ||
        t("errors.generic");
      setEditError(Array.isArray(msg) ? msg[0] : msg);
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
                      <button
                        type="button"
                        data-testid="post-report-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowMenu(false);
                          setReportOpen(true);
                        }}
                        className="w-full flex items-center gap-2 px-3.5 py-2 text-amber-400 hover:bg-amber-950/30 text-xs transition border-t border-zinc-800/80"
                      >
                        <Flag size={14} />
                        <span>{t("report.action", "Denunciar")}</span>
                      </button>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Editor inline de texto e mídias */}
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

          {/* Mídias multi-imagem mantidas e novas */}
          {(editKeptMedia.length > 0 || editNewPreviewUrls.length > 0) && (
            <div data-testid="edit-media-grid" className="mt-2.5 grid grid-cols-2 sm:grid-cols-4 gap-2">
              {editKeptMedia.map((pm, idx) => (
                <div key={pm.id} className="relative rounded-lg overflow-hidden bg-zinc-800 border border-zinc-700/60">
                  <img
                    src={pm.url}
                    alt={pm.alt_text || t("post.media_alt_fallback", { username: authorName })}
                    className="w-full h-24 object-cover"
                  />
                  <button
                    type="button"
                    data-testid={`edit-remove-existing-media-${idx}`}
                    onClick={() => handleEditRemoveKeptMedia(pm.id)}
                    className="overlay-contrast absolute top-1 right-1 w-6 h-6 rounded-full bg-black/75 text-white flex items-center justify-center hover:bg-black transition"
                    aria-label={t("post.remove_image")}
                  >
                    <X size={12} />
                  </button>
                  <input
                    type="text"
                    value={pm.alt_text || ""}
                    onChange={(e) => handleEditKeptAltChange(pm.id, e.target.value)}
                    maxLength={300}
                    placeholder={t("post.alt_text_placeholder")}
                    className="w-full bg-zinc-950/90 text-zinc-100 text-[10px] px-1.5 py-1 border-t border-zinc-800 focus:outline-none"
                    aria-label={t("post.alt_text_label")}
                  />
                </div>
              ))}
              {editNewPreviewUrls.map((url, idx) => (
                <div key={url + idx} className="relative rounded-lg overflow-hidden bg-zinc-800 border border-pink-500/40">
                  <img
                    src={url}
                    alt={editNewAltTexts[idx] || t("post.media_alt")}
                    className="w-full h-24 object-cover"
                  />
                  <button
                    type="button"
                    data-testid={`edit-remove-new-media-${idx}`}
                    onClick={() => handleEditRemoveNewImage(idx)}
                    className="overlay-contrast absolute top-1 right-1 w-6 h-6 rounded-full bg-black/75 text-white flex items-center justify-center hover:bg-black transition"
                    aria-label={t("post.remove_image")}
                  >
                    <X size={12} />
                  </button>
                  <input
                    type="text"
                    value={editNewAltTexts[idx] || ""}
                    onChange={(e) => handleEditNewAltChange(idx, e.target.value)}
                    maxLength={300}
                    placeholder={t("post.alt_text_placeholder")}
                    className="w-full bg-zinc-950/90 text-zinc-100 text-[10px] px-1.5 py-1 border-t border-zinc-800 focus:outline-none"
                    aria-label={t("post.alt_text_label")}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Mídia legada (GIF ou vídeo único) */}
          {((legacyImageUrl && !removeLegacyImage) ||
            (legacyVideoUrl && !removeLegacyVideo) ||
            editLegacyPreviewUrl) && (
            <div data-testid="edit-legacy-media" className="relative mt-2.5 max-w-xs rounded-xl overflow-hidden border border-zinc-700 bg-black/30">
              {(editLegacyKind === "video" || (legacyVideoUrl && !removeLegacyVideo && !editLegacyPreviewUrl)) ? (
                <video
                  src={editLegacyPreviewUrl || legacyVideoUrl}
                  controls
                  className="w-full max-h-40 object-contain bg-black"
                />
              ) : (
                <img
                  src={editLegacyPreviewUrl || legacyImageUrl}
                  alt={t("post.media_alt")}
                  className="w-full max-h-40 object-cover"
                />
              )}
              <button
                type="button"
                data-testid="edit-remove-legacy-media"
                onClick={() => {
                  if (editLegacyPreviewUrl) {
                    URL.revokeObjectURL?.(editLegacyPreviewUrl);
                    setEditLegacyFile(null);
                    setEditLegacyKind(null);
                    setEditLegacyPreviewUrl(null);
                  }
                  if (legacyImageUrl) setRemoveLegacyImage(true);
                  if (legacyVideoUrl) setRemoveLegacyVideo(true);
                }}
                className="overlay-contrast absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-black/75 text-white flex items-center justify-center hover:bg-black transition"
                aria-label={t("post.remove_media")}
              >
                <X size={12} />
              </button>
            </div>
          )}

          {editError && (
            <p data-testid="post-edit-error" className="text-xs text-rose-500 mt-1.5">
              {editError}
            </p>
          )}

          <div className="flex items-center justify-between mt-2 text-xs text-zinc-400">
            <div className="flex items-center gap-2">
              <input
                ref={editMediaInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm,video/quicktime"
                multiple
                onChange={handleEditMediaSelect}
                data-testid="edit-media-input"
                className="hidden"
              />
              <button
                type="button"
                data-testid="edit-add-media-btn"
                onClick={() => editMediaInputRef.current?.click()}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-pink-400 hover:text-pink-300 hover:bg-pink-500/10 transition"
                title={t("post.add_media_unified")}
              >
                <ImageIcon size={14} />
                <span>{t("post.add_media_unified")}</span>
              </button>
              <span>{3000 - editText.length}</span>
            </div>
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
                disabled={submittingEdit || (!editText.trim() && !hasAnyEditedMedia)}
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
            imageUrl={legacyImageUrl}
            videoUrl={legacyVideoUrl}
            alt={t("post.media_alt", "Mídia da publicação")}
          />

          {/* Onda 9: Grid de múltiplas imagens */}
          {mediaList.length > 0 && (
            <PostMediaGrid
              media={mediaList}
              authorName={authorName}
              t={t}
              compact={!isDetail}
              onOpenLightbox={(idx) => setLightboxIndex(idx)}
            />
          )}

          {/* Onda 9: Badge efêmero */}
          {post.is_ephemeral && post.expires_at && (() => {
            const remaining = formatEphemeralRemaining(post.expires_at, t);
            if (!remaining) return null;
            return (
              <div
                data-testid="post-ephemeral-badge"
                className="ephemeral-pill inline-flex items-center gap-1 text-[10px] text-amber-400 bg-amber-950/40 border border-amber-800/40 rounded-full px-2 py-0.5 mt-2"
              >
                <Clock size={10} />
                <span>{t("post.ephemeral_badge", { time: remaining })}</span>
              </div>
            );
          })()}
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

      <ReportModal
        isOpen={reportOpen}
        targetType="post"
        targetId={post.id}
        targetLabel={`@${authorName}`}
        onClose={() => setReportOpen(false)}
      />

      {/* Onda 9: Lightbox */}
      {lightboxIndex !== null && mediaList.length > 0 && (
        <PostLightbox
          media={mediaList}
          initialIndex={lightboxIndex}
          authorName={authorName}
          t={t}
          onClose={() => setLightboxIndex(null)}
        />
      )}
    </article>
  );
}

export default PostCard;
