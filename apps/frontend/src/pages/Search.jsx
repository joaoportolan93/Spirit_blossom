import { useState, useEffect, useCallback, useContext } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";
import { PostCard } from "../components/PostCard";
import { FollowSuggestions } from "../components/FollowSuggestions";
import { AuthContext } from "../hooks/useAuth";

export function Search() {
  const { t } = useTranslation();
  const auth = useContext(AuthContext);
  const isAuthenticated = Boolean(auth?.user);
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") || "";
  const initialTab = searchParams.get("tab") || "people";

  const [query, setQuery] = useState(initialQuery);
  const [tab, setTab] = useState(initialTab);
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [posts, setPosts] = useState([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  const executeSearch = useCallback(async (searchTerm, currentTab) => {
    const q = searchTerm.trim();
    if (q.length < 2) {
      setUsers([]);
      setPosts([]);
      setSearched(false);
      return;
    }

    setLoading(true);
    setError("");
    setSearched(true);

    try {
      if (currentTab === "people") {
        const res = await api.get(`/api/users/search/?q=${encodeURIComponent(q)}`);
        setUsers(res.data.results || []);
      } else {
        const res = await api.get(`/api/posts/search/?q=${encodeURIComponent(q)}`);
        setPosts(res.data || []);
      }
    } catch {
      setError(t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    const q = searchParams.get("q") || "";
    if (q.length >= 2) {
      executeSearch(q, tab);
    }
  }, [searchParams, tab, executeSearch]);

  const handleSubmit = (e) => {
    e.preventDefault();
    setSearchParams({ q: query, tab });
  };

  const handleTabChange = (newTab) => {
    setTab(newTab);
    setSearchParams({ q: query, tab: newTab });
  };

  return (
    <div className="max-w-xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold tracking-tight text-white mb-4">
        {t("search.title")}
      </h1>

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            data-testid="search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("search.placeholder")}
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <button
            type="submit"
            data-testid="search-submit"
            className="bg-white text-zinc-950 font-medium px-4 py-2 rounded-lg text-sm hover:bg-zinc-200 transition"
          >
            {t("search.title")}
          </button>
        </div>
        {query.length > 0 && query.length < 2 && (
          <p className="text-xs text-zinc-500 mt-1">
            {t("search.min_chars")}
          </p>
        )}
      </form>

      <div className="flex border-b border-zinc-800 mb-6">
        <button
          type="button"
          data-testid="tab-people"
          onClick={() => handleTabChange("people")}
          className={`pb-2 px-4 text-sm font-medium border-b-2 transition ${
            tab === "people"
              ? "border-white text-white"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          {t("search.tab_people")}
        </button>
        <button
          type="button"
          data-testid="tab-posts"
          onClick={() => handleTabChange("posts")}
          className={`pb-2 px-4 text-sm font-medium border-b-2 transition ${
            tab === "posts"
              ? "border-white text-white"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          {t("search.tab_posts")}
        </button>
      </div>

      {error && (
        <div data-testid="search-error" className="text-xs text-rose-500 mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-zinc-500">Carregando...</div>
      ) : tab === "people" ? (
        searched && users.length === 0 ? (
          <div data-testid="empty-search-people" className="text-sm text-zinc-500">
            {t("search.empty_people")}
          </div>
        ) : (
          <ul data-testid="search-people-list" className="space-y-2">
            {users.map((u) => (
              <li
                key={u.username}
                className="p-3 bg-zinc-900/60 border border-zinc-800/80 rounded-lg flex items-center justify-between"
              >
                <Link
                  to={`/profile/${u.username}`}
                  className="flex items-center gap-3 hover:opacity-80 transition"
                >
                  {u.avatar ? (
                    <img
                      src={u.avatar}
                      alt={u.username}
                      className="w-8 h-8 rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs text-zinc-300">
                      {u.username.slice(0, 2).toUpperCase()}
                    </div>
                  )}
                  <div>
                    <span className="text-sm text-zinc-200 font-medium">
                      @{u.username}
                    </span>
                    {u.is_private && (
                      <span className="ml-2 text-xs text-zinc-500">🔒</span>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )
      ) : (
        searched && posts.length === 0 ? (
          <div data-testid="empty-search-posts" className="text-sm text-zinc-500">
            {t("search.empty_posts")}
          </div>
        ) : (
          <div data-testid="search-posts-list" className="space-y-3">
            {posts.map((post) => (
              <PostCard key={post.id} post={post} />
            ))}
          </div>
        )
      )}

      {isAuthenticated && (
        <div className="mt-8">
          <FollowSuggestions limit={5} />
        </div>
      )}
    </div>
  );
}
