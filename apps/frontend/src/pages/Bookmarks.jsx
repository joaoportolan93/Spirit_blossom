import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";
import { PostCard } from "../components/PostCard";

export function Bookmarks() {
  const { t } = useTranslation();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadBookmarks() {
      try {
        const res = await api.get("/api/posts/bookmarks/");
        setPosts(Array.isArray(res.data) ? res.data : []);
      } catch {
        // Ignora erro
      } finally {
        setLoading(false);
      }
    }

    loadBookmarks();
  }, []);

  return (
    <div className="max-w-xl mx-auto py-8 px-4">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white mb-1">
          {t("bookmarks.title")}
        </h1>
        <p className="text-sm text-zinc-400">
          {t("bookmarks.subtitle")}
        </p>
      </header>

      {loading ? (
        <div data-testid="bookmarks-loading" className="text-sm text-zinc-500 py-8 text-center">
          Carregando...
        </div>
      ) : posts.length === 0 ? (
        <div data-testid="empty-bookmarks" className="text-sm text-zinc-500 py-8 text-center">
          {t("bookmarks.empty")}
        </div>
      ) : (
        <div data-testid="bookmarks-posts-list">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}

