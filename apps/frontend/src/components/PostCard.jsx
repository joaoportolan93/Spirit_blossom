import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { formatDistanceToNow } from "../utils/date";
import { api } from "../services/api";

export function PostCard({ post }) {
  const { t } = useTranslation();
  const authorName = post.author?.username || "anônimo";
  const dateFormatted = post.created_at ? formatDistanceToNow(post.created_at) : "";

  const [isLiked, setIsLiked] = useState(Boolean(post.is_liked));
  const [likesCount, setLikesCount] = useState(post.likes_count || 0);
  const [isBookmarked, setIsBookmarked] = useState(Boolean(post.is_bookmarked));
  const [bookmarksCount, setBookmarksCount] = useState(post.bookmarks_count || 0);
  const [actionLoading, setActionLoading] = useState(false);

  const handleToggleLike = async () => {
    if (actionLoading) return;
    setActionLoading(true);
    const prevLiked = isLiked;
    const prevCount = likesCount;

    // Otimista
    setIsLiked(!prevLiked);
    setLikesCount(prevLiked ? Math.max(0, prevCount - 1) : prevCount + 1);

    try {
      if (prevLiked) {
        await api.delete(`/api/posts/${post.id}/like/`);
      } else {
        await api.post(`/api/posts/${post.id}/like/`);
      }
    } catch {
      // Reverte em caso de erro
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

    // Otimista
    setIsBookmarked(!prevBookmarked);
    setBookmarksCount(prevBookmarked ? Math.max(0, prevCount - 1) : prevCount + 1);

    try {
      if (prevBookmarked) {
        await api.delete(`/api/posts/${post.id}/bookmark/`);
      } else {
        await api.post(`/api/posts/${post.id}/bookmark/`);
      }
    } catch {
      // Reverte em caso de erro
      setIsBookmarked(prevBookmarked);
      setBookmarksCount(prevCount);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <article
      data-testid="post-card"
      className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 mb-4 hover:border-zinc-700 transition"
    >
      <header className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-xs text-zinc-300">
            {authorName[0]?.toUpperCase()}
          </div>
          <Link
            to={`/profile/${authorName}`}
            className="font-semibold text-sm text-zinc-200 hover:text-white hover:underline transition"
          >
            @{authorName}
          </Link>
          {post.visibility === "circle" && (
            <span
              data-testid="post-circle-badge"
              className="text-xs bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 px-1.5 py-0.5 rounded"
            >
              {t("post.visibility_circle")}
            </span>
          )}
        </div>
        {dateFormatted && (
          <time className="text-xs text-zinc-500">{dateFormatted}</time>
        )}
      </header>

      {/* RENDERIZADO ESTRITAMENTE COMO TEXTO PURO (SEM RISCO DE XSS) */}
      <p
        data-testid="post-content"
        className="text-sm text-zinc-100 whitespace-pre-wrap break-words mb-3"
      >
        {post.content_text}
      </p>

      {/* Barra de ações sociais: Curtir e Salvar */}
      <footer className="flex items-center gap-4 pt-2 border-t border-zinc-800/50 text-xs">
        <button
          type="button"
          data-testid="like-button"
          onClick={handleToggleLike}
          disabled={actionLoading}
          className={`flex items-center gap-1.5 px-2 py-1 rounded transition ${
            isLiked
              ? "text-rose-400 bg-rose-950/30 border border-rose-900/40"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
          }`}
        >
          <span>{isLiked ? "♥" : "♡"}</span>
          <span data-testid="likes-count">{likesCount}</span>
        </button>

        <button
          type="button"
          data-testid="bookmark-button"
          onClick={handleToggleBookmark}
          disabled={actionLoading}
          className={`flex items-center gap-1.5 px-2 py-1 rounded transition ${
            isBookmarked
              ? "text-amber-400 bg-amber-950/30 border border-amber-900/40"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
          }`}
        >
          <span>{isBookmarked ? "🔖" : "🏷"}</span>
          <span data-testid="bookmarks-count">{bookmarksCount}</span>
        </button>
      </footer>
    </article>
  );
}
