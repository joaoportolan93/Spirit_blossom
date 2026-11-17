import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Composer } from "../components/Composer";
import { PostCard } from "../components/PostCard";
import { api } from "../services/api";
import { Users, TrendingUp } from "lucide-react";

function RightSidebar() {
  return (
    <aside className="w-72 shrink-0 py-6 pr-4 space-y-5 hidden xl:block">
      {/* Sugestões para seguir */}
      <div className="bg-zinc-900 border border-zinc-800/60 rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Users size={15} className="text-violet-400" />
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Sugestões para seguir
          </h2>
        </div>
        <p className="text-xs text-zinc-500">Nenhuma sugestão no momento.</p>
      </div>

      {/* Tendências */}
      <div className="bg-zinc-900 border border-zinc-800/60 rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp size={15} className="text-violet-400" />
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Tendências
          </h2>
        </div>
        <p className="text-xs text-zinc-500">Em breve.</p>
      </div>

      {/* Footer */}
      <p className="text-[11px] text-zinc-600 px-1">
        Sobre · Privacidade · Termos · Ajuda
        <br />© 2026 Spirit Blossom
      </p>
    </aside>
  );
}

export function Feed() {
  const { t } = useTranslation();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const loadFeed = useCallback(async (cursor = null) => {
    try {
      const url = cursor ? `/api/posts/?cursor=${cursor}` : "/api/posts/";
      const res = await api.get(url);
      const data = Array.isArray(res.data) ? res.data : [];

      if (cursor) {
        setPosts((prev) => [...prev, ...data]);
      } else {
        setPosts(data);
      }

      if (data.length === 20) {
        setNextCursor(data[data.length - 1].id);
      } else {
        setNextCursor(null);
      }
    } catch {
      // Ignora erro
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  const handlePostCreated = (newPost) => {
    setPosts((prev) => [newPost, ...prev]);
  };

  const handleLoadMore = () => {
    if (nextCursor && !loadingMore) {
      setLoadingMore(true);
      loadFeed(nextCursor);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 flex gap-6">
      {/* Feed principal */}
      <div className="flex-1 min-w-0">
        {/* Header da seção */}
        <div className="flex items-center justify-between mb-5">
          <h1 className="text-lg font-bold text-white">{t("feed.title")}</h1>
        </div>

        {/* Composer */}
        <Composer onPostCreated={handlePostCreated} />

        {/* Posts */}
        <div data-testid="timeline-container">
          {loading ? (
            <div
              data-testid="feed-loading"
              className="text-center py-10 text-zinc-500 text-sm"
            >
              {t("feed.loading")}
            </div>
          ) : posts.length === 0 ? (
            <div
              data-testid="feed-empty"
              className="text-center py-14 text-zinc-500 text-sm bg-zinc-900/50 border border-zinc-800/60 rounded-2xl"
            >
              {t("feed.empty")}
            </div>
          ) : (
            <div className="space-y-3">
              {posts.map((post) => (
                <PostCard key={post.id} post={post} />
              ))}

              {nextCursor && (
                <div className="text-center pt-4 pb-2">
                  <button
                    type="button"
                    data-testid="load-more-btn"
                    onClick={handleLoadMore}
                    disabled={loadingMore}
                    className="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-all"
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
