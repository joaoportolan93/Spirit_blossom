import { useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Send, EyeOff, Eye, Image as ImageIcon, Video as VideoIcon } from "lucide-react";
import { PostCard } from "../components/PostCard";
import { RichText } from "../components/RichText";
import { MediaPreview, MediaViewer, useMediaSelection } from "../components/MediaAttachment";
import CommentItem from "../components/CommentItem";
import FocusedThreadView from "../components/FocusedThreadView";
import { useAuth } from "../hooks/useAuth";
import {
  getPostDetail,
  getPostComments,
  createComment,
  getCommentThread,
  getPostHiddenComments,
  unhideComment,
} from "../services/api";
export default PostPage;

export function PostPage() {
  const { id: postId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user } = useAuth();

  const focusedCommentId = searchParams.get("comment");
  const activeTab = searchParams.get("tab");

  const [post, setPost] = useState(null);
  const [comments, setComments] = useState([]);
  const [, setNextCursor] = useState(null);
  const [sort, setSort] = useState("recent");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Respostas ocultas (dono do post)
  const [hiddenComments, setHiddenComments] = useState([]);
  const [loadingHidden, setLoadingHidden] = useState(false);
  const [unhidingId, setUnhidingId] = useState(null);

  // Estado para foco
  const [threadContext, setThreadContext] = useState(null);
  const [loadingThread, setLoadingThread] = useState(false);

  // Compositor de comentário raiz
  const [rootText, setRootText] = useState("");
  const [submittingRoot, setSubmittingRoot] = useState(false);
  const [rootError, setRootError] = useState("");
  const [activeReplyId, setActiveReplyId] = useState(null);
  const {
    selectedImage: rootImage,
    selectedVideo: rootVideo,
    mediaPreview: rootPreview,
    mediaType: rootMediaType,
    mediaError: rootMediaError,
    setMediaError: setRootMediaError,
    imageInputRef: rootImageInputRef,
    gifInputRef: rootGifInputRef,
    videoInputRef: rootVideoInputRef,
    handleImageSelect: handleRootImageSelect,
    handleVideoSelect: handleRootVideoSelect,
    clearMedia: clearRootMedia,
  } = useMediaSelection(t);

  // Carrega post e comentários raiz
  const loadPostAndComments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [postData, commentsData] = await Promise.all([
        getPostDetail(postId),
        getPostComments(postId, sort),
      ]);
      setPost(postData);
      setComments(commentsData.items || []);
      setNextCursor(commentsData.next_cursor || null);
    } catch (err) {
      setError(
        err.response?.status === 404
          ? t("post.notFound", "Publicação não encontrada ou privada.")
          : t("common.genericError", "Erro ao carregar dados.")
      );
    } finally {
      setLoading(false);
    }
  }, [postId, sort, t]);

  // Carrega thread focada quando ?comment=<id> está presente
  const loadThread = useCallback(async (commentId) => {
    setLoadingThread(true);
    try {
      const data = await getCommentThread(commentId);
      setThreadContext(data);
    } catch (err) {
      console.error("Erro ao carregar thread focada:", err);
      // Se não encontrar o comentário focado, volta para a visualização geral
      setSearchParams({}, { replace: true });
    } finally {
      setLoadingThread(false);
    }
  }, [setSearchParams]);

  // Carrega comentários ocultos (apenas dono do post)
  const loadHiddenComments = useCallback(async () => {
    if (!postId) return;
    setLoadingHidden(true);
    try {
      const data = await getPostHiddenComments(postId);
      setHiddenComments(data.items || []);
    } catch (err) {
      console.error("Erro ao carregar respostas ocultas:", err);
    } finally {
      setLoadingHidden(false);
    }
  }, [postId]);

  useEffect(() => {
    loadPostAndComments();
  }, [loadPostAndComments]);

  useEffect(() => {
    if (focusedCommentId) {
      loadThread(focusedCommentId);
    } else {
      setThreadContext(null);
    }
  }, [focusedCommentId, loadThread]);

  useEffect(() => {
    if (activeTab === "hidden") {
      loadHiddenComments();
    }
  }, [activeTab, loadHiddenComments]);

  const handleUnhideComment = async (commentId) => {
    if (unhidingId) return;
    setUnhidingId(commentId);
    try {
      await unhideComment(commentId);
      setHiddenComments((prev) => prev.filter((c) => c.id !== commentId));
      setPost((prev) =>
        prev
          ? {
            ...prev,
            hidden_comments_count: Math.max(0, (prev.hidden_comments_count || 1) - 1),
            comments_count: (prev.comments_count || 0) + 1,
          }
          : prev
      );
      // Recarrega comentários normais para refletir o comentário reexibido
      const commentsData = await getPostComments(postId, sort);
      setComments(commentsData.items || []);
    } catch (err) {
      console.error("Erro ao reexibir comentário:", err);
    } finally {
      setUnhidingId(null);
    }
  };

  const handleCreateRootComment = async (e) => {
    e.preventDefault();
    const trimmed = rootText.trim();
    if ((!trimmed && !rootImage && !rootVideo) || submittingRoot) return;
    setSubmittingRoot(true);
    setRootError("");
    setRootMediaError("");
    try {
      const payload =
        rootImage || rootVideo
          ? { content_text: trimmed, image: rootImage, video: rootVideo }
          : { content_text: trimmed };
      const created = await createComment(postId, payload);
      setComments((prev) => [created, ...prev]);
      setRootText("");
      clearRootMedia();
    } catch (err) {
      console.error("Erro ao criar comentário:", err);
      const msg =
        err.response?.data?.image ||
        err.response?.data?.video ||
        err.response?.data?.detail ||
        t("errors.generic");
      setRootError(Array.isArray(msg) ? msg[0] : msg);
    } finally {
      setSubmittingRoot(false);
    }
  };

  const handleReplySubmit = async (replyPayload, parentId) => {
    try {
      const payload =
        typeof replyPayload === "string"
          ? { content_text: replyPayload, parent_id: parentId }
          : { ...replyPayload, parent_id: parentId };
      const created = await createComment(postId, payload);

      // Atualiza recursivamente a árvore raiz se estiver no modo normal
      const updateTree = (list) => {
        return list.map((item) => {
          if (item.id === parentId) {
            return {
              ...item,
              replies_count: (item.replies_count || 0) + 1,
              preview_replies: [...(item.preview_replies || []), created],
            };
          }
          if (item.preview_replies && item.preview_replies.length > 0) {
            return {
              ...item,
              preview_replies: updateTree(item.preview_replies),
            };
          }
          return item;
        });
      };

      setComments((prev) => updateTree(prev));
      return created;
    } catch (err) {
      console.error("Erro ao responder comentário:", err);
      return null;
    }
  };

  const handleDeleteComment = (commentId) => {
    // Poda ou marca como tombstone na árvore
    const pruneOrTombstone = (list) => {
      return list
        .map((item) => {
          if (item.id === commentId) {
            if (item.preview_replies && item.preview_replies.length > 0) {
              return {
                ...item,
                is_deleted: true,
                content_text: "[comment deleted]",
                author: null,
              };
            }
            return null;
          }
          if (item.preview_replies && item.preview_replies.length > 0) {
            return {
              ...item,
              preview_replies: pruneOrTombstone(item.preview_replies),
            };
          }
          return item;
        })
        .filter(Boolean);
    };

    setComments((prev) => pruneOrTombstone(prev));
  };

  const handleFocusComment = (comment) => {
    setSearchParams({ comment: comment.id }, { replace: true });
  };

  const handleExitFocus = () => {
    setSearchParams({}, { replace: true });
  };

  const handleBackToParent = () => {
    if (threadContext?.ancestors && threadContext.ancestors.length > 0) {
      const immediateParent = threadContext.ancestors[threadContext.ancestors.length - 1];
      setSearchParams({ comment: immediateParent.id }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  };

  const handleBack = () => {
    if (window.history.state && window.history.state.idx > 0) {
      navigate(-1);
    } else {
      navigate("/");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh] text-zinc-500 text-sm">
        {t("common.loading", "Carregando...")}
      </div>
    );
  }

  if (error || !post) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-center">
        <p className="text-zinc-400 text-sm mb-4">{error || t("post.notFound", "Publicação não encontrada.")}</p>
        <button
          type="button"
          onClick={handleBack}
          className="text-pink-400 hover:underline text-sm font-medium inline-flex items-center gap-1"
        >
          <ArrowLeft size={14} />
          {t("common.back", "Voltar")}
        </button>
      </div>
    );
  }

  // ── MODO FOCADO (Twitter/X Thread Focus) ──────────────────────────────────
  if (focusedCommentId) {
    if (loadingThread || !threadContext) {
      return (
        <div className="flex items-center justify-center min-h-[50vh] text-zinc-500 text-sm">
          {t("common.loading", "Carregando conversa...")}
        </div>
      );
    }

    return (
      <FocusedThreadView
        post={threadContext.post}
        ancestors={threadContext.ancestors}
        focusedComment={threadContext.comment}
        replies={threadContext.replies}
        nextCursor={threadContext.next_cursor}
        onExitFocus={handleExitFocus}
        onBackToParent={handleBackToParent}
        onFocusThread={handleFocusComment}
        onDeleteComment={handleDeleteComment}
        onReplySubmit={handleReplySubmit}
        currentUserId={user?.id}
      />
    );
  }

  const isOwner = Boolean(
    user && post?.author && (user.id === post.author.id || user.username === post.author.username)
  );

  // ── MODO PADRÃO (Post + Árvore de Comentários ou Respostas Ocultas) ───────
  return (
    <div className="max-w-2xl mx-auto px-3 sm:px-4 py-4 sm:py-6" data-testid="post-page">
      {/* Botão voltar */}
      <div className="mb-3">
        <button
          type="button"
          onClick={handleBack}
          className="text-zinc-400 hover:text-zinc-100 flex items-center gap-1.5 text-xs sm:text-sm font-medium transition-colors"
          data-testid="post-back-btn"
        >
          <ArrowLeft size={16} />
          {t("common.back", "Voltar")}
        </button>
      </div>

      {/* Post original */}
      <div className="mb-4">
        <PostCard
          post={post}
          isDetail={true}
          onDelete={() => navigate("/")}
          onViewHidden={() => setSearchParams({ tab: "hidden" }, { replace: true })}
        />
      </div>

      {activeTab === "hidden" ? (
        /* Painel de Respostas Ocultas */
        <div id="hidden-comments-section" data-testid="hidden-comments-section" className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-3 sm:p-4">
          <div className="flex items-center justify-between gap-2 pb-3 mb-3 border-b border-zinc-800">
            <button
              type="button"
              onClick={() => setSearchParams({}, { replace: true })}
              className="text-zinc-400 hover:text-zinc-100 flex items-center gap-1 text-xs transition-colors"
              data-testid="back-to-comments-btn"
            >
              <ArrowLeft size={14} />
              <span>{t("comments.backToPost", "Ver todos os comentários")}</span>
            </button>
            <span className="text-amber-400 text-xs font-medium flex items-center gap-1.5">
              <EyeOff size={14} />
              {t("comments.hiddenReplies", "Respostas ocultas")}
            </span>
          </div>

          {loadingHidden ? (
            <div className="py-8 text-center text-sm text-zinc-500">
              {t("common.loading", "Carregando...")}
            </div>
          ) : hiddenComments.length === 0 ? (
            <div className="py-8 text-center text-sm text-zinc-500" data-testid="no-hidden-comments">
              {t("comments.noHiddenReplies", "Nenhuma resposta oculta nesta publicação.")}
            </div>
          ) : (
            <div className="divide-y divide-zinc-800/40" data-testid="hidden-comments-list">
              {hiddenComments.map((item) => (
                <div key={item.id} className="py-3 flex items-start justify-between gap-3" data-testid={`hidden-comment-${item.id}`}>
                  <div className="flex items-start gap-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-300 font-semibold text-xs border border-zinc-700/60 overflow-hidden shrink-0 mt-0.5">
                      {item.author?.avatar ? (
                        <img src={item.author.avatar} alt={item.author.username} className="w-full h-full object-cover" />
                      ) : (
                        <span>{item.author?.username?.[0]?.toUpperCase() || "U"}</span>
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 text-xs mb-0.5">
                        <span className="font-semibold text-zinc-200">
                          @{item.author?.username}
                        </span>
                        <span className="text-zinc-500 text-[11px]">
                          · {item.created_at ? new Date(item.created_at).toLocaleDateString() : ""}
                        </span>
                      </div>
                      {item.content_text && (
                        <p className="text-sm text-zinc-300 whitespace-pre-wrap break-words">
                          <RichText text={item.content_text} />
                        </p>
                      )}
                      <MediaViewer
                        imageUrl={item.image_url}
                        videoUrl={item.video_url}
                        alt={t("post.media_alt", "Mídia da publicação")}
                        compact
                      />
                    </div>
                  </div>

                  <button
                    type="button"
                    data-testid="unhide-comment-btn"
                    onClick={() => handleUnhideComment(item.id)}
                    disabled={unhidingId === item.id}
                    className="shrink-0 px-2.5 py-1 text-xs font-medium text-amber-400 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 rounded-lg flex items-center gap-1 transition"
                  >
                    <Eye size={12} />
                    <span>{t("comments.unhideReply", "Reexibir")}</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Seção de comentários normal */
        <div id="comments-section" data-testid="comments-section" className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-3 sm:p-4">
          {/* Header da seção e ordenação */}
          <div className="flex items-center justify-between gap-2 pb-3 mb-3 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-zinc-200 text-sm">
                {t("comments.title", "Comentários")}
              </h3>
              {isOwner && (post.hidden_comments_count || 0) > 0 && (
                <button
                  type="button"
                  data-testid="hidden-comments-tab-badge"
                  onClick={() => setSearchParams({ tab: "hidden" }, { replace: true })}
                  className="text-xs text-amber-400 hover:text-amber-300 flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 transition"
                  title={t("comments.hiddenReplies", "Respostas ocultas")}
                >
                  <EyeOff size={11} />
                  <span>{post.hidden_comments_count}</span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-zinc-500 hidden sm:inline">{t("comments.sortBy", "Ordenar:")}</span>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                className="bg-zinc-800 border border-zinc-700 text-zinc-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-pink-500"
                data-testid="sort-select"
              >
                <option value="recent">{t("comments.sortRecent", "Mais recentes")}</option>
                <option value="likes">{t("comments.sortLikes", "Mais curtidos")}</option>
                <option value="relevance">{t("comments.sortRelevance", "Mais relevantes")}</option>
              </select>
            </div>
          </div>

          {/* Compositor de comentário raiz */}
          <form onSubmit={handleCreateRootComment} className="mb-4" data-testid="root-comment-form">
            <div className="flex gap-2">
              <input
                type="text"
                value={rootText}
                onChange={(e) => setRootText(e.target.value)}
                placeholder={t("comments.inputPlaceholder", "Escreva um comentário...")}
                className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-zinc-100 text-sm focus:outline-none focus:border-pink-500"
                maxLength={1000}
                data-testid="root-comment-input"
              />
              <button
                type="submit"
                disabled={submittingRoot || (!rootText.trim() && !rootImage && !rootVideo)}
                className="px-4 py-2 bg-pink-600 hover:bg-pink-500 disabled:opacity-50 text-white text-xs font-medium rounded-xl flex items-center gap-1.5 transition-colors"
                data-testid="root-comment-submit"
              >
                <Send size={13} />
                <span className="hidden sm:inline">{t("comments.send", "Enviar")}</span>
              </button>
            </div>
            <div className="flex items-center gap-1 mt-2">
              <input
                ref={rootImageInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                onChange={handleRootImageSelect}
                data-testid="root-comment-image-input"
                className="hidden"
              />
              <input
                ref={rootGifInputRef}
                type="file"
                accept="image/gif"
                onChange={handleRootImageSelect}
                data-testid="root-comment-gif-input"
                className="hidden"
              />
              <input
                ref={rootVideoInputRef}
                type="file"
                accept="video/mp4,video/webm,video/quicktime"
                onChange={handleRootVideoSelect}
                data-testid="root-comment-video-input"
                className="hidden"
              />
              <button
                type="button"
                data-testid="root-comment-image-btn"
                onClick={() => rootImageInputRef.current?.click()}
                disabled={submittingRoot}
                className="p-1.5 rounded-lg text-pink-400 hover:text-pink-300 hover:bg-pink-500/10 transition disabled:opacity-50"
                title={t("post.add_media", "Adicionar mídia")}
                aria-label={t("post.add_media", "Adicionar mídia")}
              >
                <ImageIcon size={16} />
              </button>
              <button
                type="button"
                data-testid="root-comment-gif-btn"
                onClick={() => rootGifInputRef.current?.click()}
                disabled={submittingRoot}
                className="px-1.5 py-0.5 rounded-lg text-pink-400 hover:text-pink-300 hover:bg-pink-500/10 text-[11px] font-bold border border-pink-500/30 hover:border-pink-500/60 transition disabled:opacity-50"
                title={t("post.add_gif", "Adicionar GIF")}
                aria-label={t("post.add_gif", "Adicionar GIF")}
              >
                GIF
              </button>
              <button
                type="button"
                data-testid="root-comment-video-btn"
                onClick={() => rootVideoInputRef.current?.click()}
                disabled={submittingRoot}
                className="p-1.5 rounded-lg text-pink-400 hover:text-pink-300 hover:bg-pink-500/10 transition disabled:opacity-50"
                title={t("post.add_video", "Adicionar vídeo")}
                aria-label={t("post.add_video", "Adicionar vídeo")}
              >
                <VideoIcon size={16} />
              </button>
            </div>
            <MediaPreview
              previewUrl={rootPreview}
              mediaType={rootMediaType}
              onClear={clearRootMedia}
              t={t}
              compact
            />
            {(rootError || rootMediaError) && (
              <p data-testid="root-comment-error" className="text-xs text-rose-500 mt-1.5">
                {rootError || rootMediaError}
              </p>
            )}
          </form>

          {/* Lista de comentários em árvore */}
          {comments.length === 0 ? (
            <div className="py-8 text-center text-sm text-zinc-500" data-testid="no-comments-message">
              {t("comments.empty", "Nenhum comentário ainda. Inicie a conversa!")}
            </div>
          ) : (
            <div className="divide-y divide-zinc-800/40" data-testid="comments-tree">
              {comments.map((comment) => (
                <CommentItem
                  key={comment.id}
                  comment={comment}
                  postId={postId}
                  currentUserId={user?.id}
                  depth={0}
                  onFocusThread={handleFocusComment}
                  onDelete={handleDeleteComment}
                  onReplySubmit={handleReplySubmit}
                  activeReplyId={activeReplyId}
                  setActiveReplyId={setActiveReplyId}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );


}