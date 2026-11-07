import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";
import { PostCard } from "../components/PostCard";

export function Explore() {
  const { t } = useTranslation();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const loadExplore = useCallback(async (cursor = null) => {
    try {
      const url = cursor ? `/api/feed/explore/?cursor=${cursor}` : "/api/feed/explore/";
      const res = await api.get(url);
      const items = res.data?.items || [];

      // Carrega os detalhes completos de cada publicação retornada no feed explorar
      const postDetails = await Promise.all(
        items.map(async (item) => {
          try {
            const detailRes = await api.get(`/api/posts/${item.post_id}/`);
            return detailRes.data;
          } catch {
            return null;
          }
        })
      );

      const validPosts = postDetails.filter(Boolean);

      if (cursor) {
        setPosts((prev) => [...prev, ...validPosts]);
      } else {
        setPosts(validPosts);
      }

      setNextCursor(res.data?.next_cursor || null);
    } catch {
      // Ignora erro
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    loadExplore();
  }, [loadExplore]);

  const handleLoadMore = () => {
    if (nextCursor && !loadingMore) {
      setLoadingMore(true);
      loadExplore(nextCursor);
    }
  };

  return (
    <div className="max-w-xl mx-auto py-8 px-4">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white mb-1">
          {t("explore.title")}
        </h1>
        <p className="text-sm text-zinc-400">
          {t("explore.subtitle")}
        </p>
      </header>

      {loading ? (
        <div data-testid="explore-loading" className="text-sm text-zinc-500 py-8 text-center">
          Carregando...
        </div>
      ) : posts.length === 0 ? (
        <div data-testid="empty-explore" className="text-sm text-zinc-500 py-8 text-center">
          {t("explore.empty")}
        </div>
      ) : (
        <div data-testid="explore-posts-list">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}

          {nextCursor && (
            <div className="text-center pt-4">
              <button
                type="button"
                data-testid="explore-load-more"
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="text-sm text-zinc-400 hover:text-white px-4 py-2 rounded-lg border border-zinc-800 hover:bg-zinc-900 transition disabled:opacity-50"
              >
                {loadingMore ? "Carregando..." : t("feed.load_more")}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

