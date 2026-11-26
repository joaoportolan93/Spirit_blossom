import { useState, useEffect, useCallback, useContext } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Hash, X } from "lucide-react";
import { api, getTrendingHashtags } from "../services/api";
import { PostCard } from "../components/PostCard";
import { FollowSuggestions } from "../components/FollowSuggestions";
import { AuthContext } from "../hooks/useAuth";

export function Explore() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const auth = useContext(AuthContext);
  const isAuthenticated = Boolean(auth?.user);

  const rawHashtag = searchParams.get("hashtag") || "";
  const activeHashtag = rawHashtag
    .replace(/^#+/, "")
    .normalize("NFC")
    .trim()
    .toLowerCase();

  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [trendingTags, setTrendingTags] = useState([]);

  const loadExplore = useCallback(async (cursor = null) => {
    try {
      const params = new URLSearchParams();
      if (cursor) params.append("cursor", cursor);
      if (activeHashtag) params.append("hashtag", activeHashtag);
      const qs = params.toString() ? `?${params.toString()}` : "";
      const url = `/api/feed/explore/${qs}`;
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
      if (!cursor) setPosts([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [activeHashtag]);

  useEffect(() => {
    setLoading(true);
    loadExplore();
  }, [loadExplore]);

  useEffect(() => {
    if (!isAuthenticated) return;
    let isMounted = true;
    getTrendingHashtags(8)
      .then((tags) => {
        if (isMounted) setTrendingTags(Array.isArray(tags) ? tags : []);
      })
      .catch(() => {
        if (isMounted) setTrendingTags([]);
      });
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated]);

  const handleLoadMore = () => {
    if (nextCursor && !loadingMore) {
      setLoadingMore(true);
      loadExplore(nextCursor);
    }
  };

  const handleClearHashtag = () => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("hashtag");
    setSearchParams(nextParams);
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 flex gap-6">
      <div className="flex-1 min-w-0 max-w-xl mx-auto">
        <header className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight text-white mb-1">
            {t("explore.title")}
          </h1>
          <p className="text-sm text-zinc-400">
            {t("explore.subtitle")}
          </p>
        </header>

        {/* Barra de filtro ativo por #hashtag */}
        {activeHashtag && (
          <div
            data-testid="hashtag-filter-banner"
            className="mb-4 flex items-center justify-between gap-3 px-4 py-2.5 bg-zinc-900 border border-pink-500/40 rounded-xl"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-pink-400 min-w-0">
              <Hash size={16} className="shrink-0" />
              <span className="truncate">
                {t("explore.hashtag_filtering", { tag: activeHashtag })}
              </span>
            </div>
            <button
              type="button"
              data-testid="clear-hashtag-filter"
              onClick={handleClearHashtag}
              className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white px-2.5 py-1 rounded-lg hover:bg-zinc-800 transition shrink-0"
            >
              <X size={14} />
              <span>{t("explore.clear_filter")}</span>
            </button>
          </div>
        )}

        {/* Tags populares — exibidas apenas quando houver dados reais */}
        {trendingTags.length > 0 && (
          <div
            data-testid="trending-hashtags"
            className="mb-5 flex items-center gap-2 flex-wrap"
            aria-label={t("explore.trending_tags")}
          >
            {trendingTags.map((tag) => {
              const isSelected = activeHashtag === tag.name;
              return (
                <Link
                  key={tag.name}
                  to={`/explore?hashtag=${encodeURIComponent(tag.name)}`}
                  data-testid={`trending-tag-${tag.name}`}
                  className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium border transition ${
                    isSelected
                      ? "bg-pink-600 text-white border-pink-500"
                      : "bg-zinc-900 text-zinc-300 border-zinc-800 hover:border-pink-500/50 hover:text-pink-400"
                  }`}
                >
                  <span>#{tag.name}</span>
                  <span className="text-[10px] opacity-70">{tag.posts_count}</span>
                </Link>
              );
            })}
          </div>
        )}

        {loading ? (
          <div data-testid="explore-loading" className="text-sm text-zinc-500 py-8 text-center">
            {t("common.loading")}
          </div>
        ) : posts.length === 0 ? (
          <div data-testid="empty-explore" className="text-sm text-zinc-500 py-8 text-center">
            {t("explore.empty")}
          </div>
        ) : (
          <div data-testid="explore-posts-list" className="space-y-3">
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
                  {loadingMore ? t("common.loading") : t("feed.load_more")}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {isAuthenticated && (
        <aside className="w-72 shrink-0 hidden xl:block space-y-4">
          <FollowSuggestions limit={5} />
        </aside>
      )}
    </div>
  );
}

