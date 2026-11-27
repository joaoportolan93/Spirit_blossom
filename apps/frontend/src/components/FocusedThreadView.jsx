import { useRef, useLayoutEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, ChevronLeft } from "lucide-react";
import CommentItem from "./CommentItem";
import { RichText } from "./RichText";
import { MediaViewer } from "./MediaAttachment";
import { PostMediaGrid, PostLightbox } from "./PostCard";
import { getCommentReplies } from "../services/api";

const LINE_BG = "bg-zinc-700";

export function FocusedThreadView({
  post,
  ancestors = [],
  focusedComment,
  replies: initialReplies = [],
  nextCursor: initialNextCursor = null,
  onExitFocus,
  onBackToParent,
  onFocusThread,
  onDeleteComment,
  onReplySubmit,
  currentUserId,
}) {
  const { t } = useTranslation();
  const rootRef = useRef(null);

  const [replies, setReplies] = useState(initialReplies);
  const [nextCursor, setNextCursor] = useState(initialNextCursor);
  const [loadingMore, setLoadingMore] = useState(false);
  const [activeReplyId, setActiveReplyId] = useState(null);
  const [lightboxIndex, setLightboxIndex] = useState(null);

  // Ancoragem de scroll via useLayoutEffect
  useLayoutEffect(() => {
    if (!focusedComment) return;

    const heroEl = rootRef.current?.querySelector("[data-thread-hero]");
    if (heroEl && typeof heroEl.scrollIntoView === "function") {
      heroEl.scrollIntoView({ behavior: "instant", block: "nearest" });
    }
  }, [focusedComment]);

  const handleLoadMoreReplies = async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const data = await getCommentReplies(focusedComment.id, "recent", nextCursor);
      setReplies((prev) => [...prev, ...data.items]);
      setNextCursor(data.next_cursor);
    } catch (err) {
      console.error("Erro ao carregar mais respostas:", err);
    } finally {
      setLoadingMore(false);
    }
  };

  const handleLocalReplySubmit = async (text, parentId) => {
    const created = await onReplySubmit(text, parentId);
    if (created && parentId === focusedComment.id) {
      setReplies((prev) => [...prev, created]);
    }
  };

  const handleLocalDelete = (deletedId) => {
    if (deletedId === focusedComment.id) {
      onDeleteComment(deletedId);
    } else {
      setReplies((prev) => prev.filter((r) => r.id !== deletedId));
      onDeleteComment(deletedId);
    }
  };

  const hasAncestors = ancestors && ancestors.length > 0;
  const hasPost = Boolean(post);

  return (
    <div ref={rootRef} className="max-w-2xl mx-auto pb-16" data-testid="focused-thread-view">
      {/* Cabeçalho da conversa com botões de navegação */}
      <div
        className="sticky top-0 z-20 bg-zinc-950/90 backdrop-blur-md border-b border-zinc-800 py-3 px-4 flex items-center justify-between"
        data-thread-header=""
      >
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onExitFocus}
            className="p-1.5 -ml-1 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-full transition-colors"
            title={t("comments.backToPost", "Ver todos os comentários")}
            data-testid="exit-focus-btn"
          >
            <ArrowLeft size={18} />
          </button>
          <h2 className="font-semibold text-zinc-100 text-base">
            {t("comments.conversation", "Conversa")}
          </h2>
        </div>

        {hasAncestors && (
          <button
            type="button"
            onClick={onBackToParent}
            className="text-xs text-pink-400 hover:underline flex items-center gap-1 font-medium"
            data-testid="back-to-parent-btn"
          >
            <ChevronLeft size={14} />
            <span>{t("comments.backToParent", "Voltar ao anterior")}</span>
          </button>
        )}
      </div>

      {/* Post original no topo da conversa (estilo Twitter/X do Lumem com linha descendo) */}
      {hasPost && (
        <div className="px-3 pt-3 sm:px-4 sm:pt-4">
          <div className="flex gap-2.5 sm:gap-3 relative">
            <div className="relative flex w-9 sm:w-10 flex-shrink-0 flex-col items-center">
              <Link to={`/profile/${post.author?.username}`}>
                <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-300 font-semibold text-xs border-2 border-zinc-700/60 overflow-hidden shrink-0">
                  {post.author?.avatar ? (
                    <img src={post.author.avatar} alt={post.author.username} className="w-full h-full object-cover" />
                  ) : (
                    <span>{post.author?.username?.[0]?.toUpperCase() || "U"}</span>
                  )}
                </div>
              </Link>
              {/* Linha que desce do avatar do post para o primeiro ancestral ou Hero */}
              <div aria-hidden="true" className={`mt-1 min-h-[16px] w-0.5 flex-1 ${LINE_BG}`} />
            </div>

            <div className="flex-1 min-w-0 pb-3 sm:pb-4">
              <div className="flex items-center gap-1.5 truncate text-xs mb-1">
                <Link
                  to={`/profile/${post.author?.username}`}
                  className="font-semibold text-zinc-200 hover:underline truncate"
                >
                  @{post.author?.username}
                </Link>
              </div>
              {post.content_text && (
                <p className="text-sm text-zinc-100 whitespace-pre-wrap break-words">
                  <RichText text={post.content_text} />
                </p>
              )}
              <MediaViewer
                imageUrl={post.image_url}
                videoUrl={post.video_url}
                alt={t("post.media_alt", "Mídia da publicação")}
              />
              {post.media && post.media.length > 0 && (
                <div className="mt-2">
                  <PostMediaGrid
                    media={post.media}
                    authorName={post.author?.username || "anônimo"}
                    t={t}
                    onOpenLightbox={(idx) => setLightboxIndex(idx)}
                  />
                </div>
              )}
              {lightboxIndex !== null && post.media && post.media.length > 0 && (
                <PostLightbox
                  media={post.media}
                  initialIndex={lightboxIndex}
                  authorName={post.author?.username || "anônimo"}
                  t={t}
                  onClose={() => setLightboxIndex(null)}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Trilha de ancestrais: Post -> Bisavô -> Avô -> Pai */}
      {hasAncestors && (
        <div>
          {ancestors.map((ancestor, index) => (
            <div key={ancestor.id} className="relative">
              <CommentItem
                comment={ancestor}
                postId={post?.id}
                currentUserId={currentUserId}
                depth={0}
                flat={true}
                threadLine={true}
                connectFromAbove={hasPost || index > 0}
                onFocusThread={onFocusThread}
                onDelete={onDeleteComment}
                onReplySubmit={handleLocalReplySubmit}
                activeReplyId={activeReplyId}
                setActiveReplyId={setActiveReplyId}
              />
            </div>
          ))}
        </div>
      )}

      {/* Comentário Focado ("HERO") com texto destacado em largura total */}
      <div data-thread-hero="" className="border-b border-zinc-800/80 bg-zinc-900/10">
        <CommentItem
          comment={focusedComment}
          postId={post?.id}
          currentUserId={currentUserId}
          depth={0}
          hero={true}
          flat={true}
          connectFromAbove={hasPost || hasAncestors}
          onFocusThread={onFocusThread}
          onDelete={handleLocalDelete}
          onReplySubmit={handleLocalReplySubmit}
          activeReplyId={activeReplyId}
          setActiveReplyId={setActiveReplyId}
        />
      </div>

      {/* Lista plana de respostas diretas ao comentário focado */}
      <div className="divide-y divide-zinc-800/60 mt-1">
        {replies.length === 0 ? (
          <div className="py-8 text-center text-sm text-zinc-500">
            {t("comments.noRepliesYet", "Nenhuma resposta ainda. Seja o primeiro a responder!")}
          </div>
        ) : (
          replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              postId={post?.id}
              currentUserId={currentUserId}
              depth={0}
              flat={true}
              onFocusThread={onFocusThread}
              onDelete={handleLocalDelete}
              onReplySubmit={handleLocalReplySubmit}
              activeReplyId={activeReplyId}
              setActiveReplyId={setActiveReplyId}
            />
          ))
        )}
      </div>

      {/* Botão de carregar mais respostas paginadas */}
      {nextCursor && (
        <div className="text-center py-4">
          <button
            type="button"
            onClick={handleLoadMoreReplies}
            disabled={loadingMore}
            className="text-xs text-pink-400 hover:text-pink-300 font-medium py-1.5 px-4 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 rounded-full transition-colors disabled:opacity-50"
            data-testid="load-more-replies-btn"
          >
            {loadingMore
              ? t("common.loading", "Carregando...")
              : t("comments.loadMoreReplies", "Carregar mais respostas")}
          </button>
        </div>
      )}
    </div>
  );
}

export default FocusedThreadView;
