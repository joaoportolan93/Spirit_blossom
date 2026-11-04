import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Composer } from "../components/Composer";
import { PostCard } from "../components/PostCard";
import { api } from "../services/api";

export function Feed() {
  const { t } = useTranslation();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const loadFeed = useCallback(async (cursor = null) => {
    try {
      // Busca posts visíveis / feed cronológico
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
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h1 className="text-xl font-bold text-white mb-6">{t("feed.title")}</h1>

      <Composer onPostCreated={handlePostCreated} />

      <div data-testid="timeline-container">
        {loading ? (
          <div data-testid="feed-loading" className="text-center py-8 text-zinc-500 text-sm">
            {t("feed.loading")}
          </div>
        ) : posts.length === 0 ? (
          <div data-testid="feed-empty" className="text-center py-12 text-zinc-500 text-sm bg-zinc-900/40 border border-zinc-800/60 rounded-xl">
            {t("feed.empty")}
          </div>
        ) : (
          <div className="space-y-4">
            {posts.map((post) => (
              <PostCard key={post.id} post={post} />
            ))}

            {nextCursor && (
              <div className="text-center pt-4">
                <button
                  type="button"
                  data-testid="load-more-btn"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-semibold transition"
                >
                  {loadingMore ? t("feed.loading") : t("feed.load_more")}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
