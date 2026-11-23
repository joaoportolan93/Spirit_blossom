import { useState, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FeedTabs } from "../components/FeedTabs";
import { PostComposer } from "../components/PostComposer";
import { PostCard } from "../components/PostCard";
import { UserMiniCard } from "../components/UserMiniCard";
import { APP_NAME } from "../config/brand";
import { api } from "../services/api";
import {
  PenSquare,
} from "lucide-react";

/** Sidebar direita minimalista: card do usuário autenticado + footer */
function RightSidebar() {
  return (
    <aside
      className="w-72 shrink-0 py-6 pr-4 space-y-5 hidden xl:block"
      aria-label="Informações do usuário"
    >
      <UserMiniCard />
      <p className="text-[11px] text-zinc-600 px-1 leading-relaxed">
        Sobre · Privacidade · Termos · Ajuda
        <br />© 2026 {APP_NAME}
      </p>
    </aside>
  );
}

/**
 * Busca o feed "Seguindo".
 * Suporta resposta de lista plana (legado / testes) e paginada ({items, next_cursor}).
 */
async function fetchFollowingFeed(cursor = null) {
  const url = cursor
    ? `/api/posts/?cursor=${cursor}`
    : "/api/posts/";
  const res = await api.get(url);

  if (Array.isArray(res.data)) {
    const items = res.data;
    const nextCursor =
      items.length === 20 ? items[items.length - 1].id : null;
    return { items, nextCursor };
  }

  const rawItems = res.data?.items || [];
  const postDetails = await Promise.allSettled(
    rawItems.map((item) =>
      api.get(`/api/posts/${item.post_id || item.id}/`)
    )
  );
  const posts = postDetails
    .filter((r) => r.status === "fulfilled")
    .map((r) => r.value.data);

  return { items: posts, nextCursor: res.data?.next_cursor || null };
}

/** Busca o feed "Para você" (endpoint /api/feed/explore/ do backend). */
async function fetchForYouFeed(cursor = null) {
  const url = cursor
    ? `/api/feed/explore/?cursor=${cursor}`
    : "/api/feed/explore/";
  const res = await api.get(url);

  if (Array.isArray(res.data)) {
    return { items: res.data, nextCursor: null };
  }

  const rawItems = res.data?.items || [];
  const postDetails = await Promise.allSettled(
    rawItems.map((item) =>
      api.get(`/api/posts/${item.post_id || item.id}/`)
    )
  );
  const posts = postDetails
    .filter((r) => r.status === "fulfilled")
    .map((r) => r.value.data);

  return { items: posts, nextCursor: res.data?.next_cursor || null };
}

export function Feed() {
  const { t } = useTranslation();
  const location = useLocation();

  const [activeTab, setActiveTab] = useState("following");
  const [isComposerOpen, setIsComposerOpen] = useState(false);

  // Estado da aba "Seguindo"
  const [followingPosts, setFollowingPosts] = useState([]);
  const [followingCursor, setFollowingCursor] = useState(null);
  const [followingLoading, setFollowingLoading] = useState(true);
  const [followingLoadingMore, setFollowingLoadingMore] = useState(false);

  // Estado da aba "Para você"
  const [forYouPosts, setForYouPosts] = useState([]);
  const [forYouCursor, setForYouCursor] = useState(null);
  const [forYouLoading, setForYouLoading] = useState(false);
  const [forYouLoadingMore, setForYouLoadingMore] = useState(false);
  const [forYouLoaded, setForYouLoaded] = useState(false);


  // Escuta evento customizado disparado pela Sidebar
  useEffect(() => {
    const handleOpen = () => setIsComposerOpen(true);
    window.addEventListener("spirit-open-composer", handleOpen);
    return () => window.removeEventListener("spirit-open-composer", handleOpen);
  }, []);

  // Abre modal se veio de redirecionamento com state.openComposer
  useEffect(() => {
    if (location.state?.openComposer) {
      setIsComposerOpen(true);
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  const loadFollowing = useCallback(async (cursor = null) => {
    try {
      const { items, nextCursor } = await fetchFollowingFeed(cursor);
      if (cursor) {
        setFollowingPosts((prev) => [...prev, ...items]);
      } else {
        setFollowingPosts(items);
      }
      setFollowingCursor(nextCursor);
    } catch {
      // silêncio
    } finally {
      setFollowingLoading(false);
      setFollowingLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    loadFollowing();
  }, [loadFollowing]);

  const loadForYou = useCallback(async (cursor = null) => {
    try {
      const { items, nextCursor } = await fetchForYouFeed(cursor);
      if (cursor) {
        setForYouPosts((prev) => [...prev, ...items]);
      } else {
        setForYouPosts(items);
      }
      setForYouCursor(nextCursor);
      setForYouLoaded(true);
    } catch {
      // silêncio
    } finally {
      setForYouLoading(false);
      setForYouLoadingMore(false);
    }
  }, []);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === "for_you" && !forYouLoaded) {
      setForYouLoading(true);
      loadForYou();
    }
  };

  const handlePostCreated = (newPost) => {
    setFollowingPosts((prev) => [newPost, ...prev]);
    setActiveTab("following");
    setIsComposerOpen(false);
  };

  const handleLoadMore = () => {
    if (activeTab === "following" && followingCursor && !followingLoadingMore) {
      setFollowingLoadingMore(true);
      loadFollowing(followingCursor);
    } else if (activeTab === "for_you" && forYouCursor && !forYouLoadingMore) {
      setForYouLoadingMore(true);
      loadForYou(forYouCursor);
    }
  };

  const posts = activeTab === "following" ? followingPosts : forYouPosts;
  const loading = activeTab === "following" ? followingLoading : forYouLoading;
  const loadingMore = activeTab === "following" ? followingLoadingMore : forYouLoadingMore;
  const cursor = activeTab === "following" ? followingCursor : forYouCursor;

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 flex gap-6">
      {/* Coluna central do Feed */}
      <div role="main" className="flex-1 min-w-0 max-w-[640px]">
        {/* Header do Feed: Título e Botão "+ Novo Post" */}
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-xl font-bold tracking-tight text-white">
            {t("nav.feed", "Feed")}
          </h1>
          <button
            type="button"
            data-testid="feed-new-post-btn"
            onClick={() => setIsComposerOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-pink-600 hover:bg-pink-500 text-white font-semibold rounded-xl text-xs sm:text-sm transition shadow-lg shadow-pink-900/30 active:scale-95"
          >
            <PenSquare size={15} />
            <span>+ {t("post.new_post", "Novo Post")}</span>
          </button>
        </div>

        {/* Abas editoriais: "Seguindo" / "Para você" */}
        <FeedTabs activeTab={activeTab} onTabChange={handleTabChange} />


        {/* Modal do PostComposer acionado pelos botões e pelo card */}
        <PostComposer
          isOpen={isComposerOpen}
          onClose={() => setIsComposerOpen(false)}
          onPostCreated={handlePostCreated}
        />

        {/* Timeline */}
        <div
          id={`tabpanel-${activeTab}`}
          role="tabpanel"
          aria-labelledby={`tab-${activeTab}`}
          data-testid="timeline-container"
        >
          {loading ? (
            <div
              data-testid="feed-loading"
              className="space-y-3"
              aria-label={t("feed.loading")}
            >
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  aria-hidden="true"
                  className="bg-zinc-900 border border-zinc-800/60 rounded-2xl p-4 shadow-sm animate-pulse"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-full bg-zinc-800 shrink-0" />
                    <div className="flex-1 space-y-2">
                      <div className="h-3 bg-zinc-800 rounded-full w-28" />
                      <div className="h-2.5 bg-zinc-800/70 rounded-full w-20" />
                    </div>
                  </div>
                  <div className="space-y-2 mb-4">
                    <div className="h-3 bg-zinc-800 rounded-full w-full" />
                    <div className="h-3 bg-zinc-800 rounded-full w-5/6" />
                  </div>
                  <div className="flex gap-6 pt-2 border-t border-zinc-800/50">
                    <div className="h-3 bg-zinc-800 rounded-full w-10" />
                    <div className="h-3 bg-zinc-800 rounded-full w-10" />
                  </div>
                </div>
              ))}
            </div>
          ) : posts.length === 0 ? (
            <div
              data-testid="feed-empty"
              role="status"
              aria-live="polite"
              className="flex flex-col items-center justify-center py-16 px-6 text-center bg-zinc-900/40 border border-zinc-800/40 rounded-2xl"
            >
              <p className="text-zinc-400 text-sm leading-relaxed max-w-xs">
                {activeTab === "following"
                  ? t("feed.empty")
                  : t("feed.for_you_empty", "Nenhuma recomendação para você no momento.")}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {posts.map((post) => (
                <PostCard key={post.id} post={post} />
              ))}

              {cursor && (
                <div className="text-center pt-4 pb-2">
                  <button
                    type="button"
                    data-testid="load-more-btn"
                    onClick={handleLoadMore}
                    disabled={loadingMore}
                    className="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-all disabled:opacity-50"
                  >
                    {loadingMore ? t("feed.loading") : t("feed.load_more")}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Sidebar direita */}
      <RightSidebar />
    </div>
  );
}
