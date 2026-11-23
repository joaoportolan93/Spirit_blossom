import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api, getBookmarkedComments } from "../services/api";
import { PostCard } from "../components/PostCard";
import CommentItem from "../components/CommentItem";

export function Bookmarks() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState("posts");
  const [posts, setPosts] = useState([]);
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadBookmarks() {
      setLoading(true);
      try {
        if (activeTab === "posts") {
          const res = await api.get("/api/posts/bookmarks/");
          setPosts(Array.isArray(res.data) ? res.data : []);
        } else {
          const data = await getBookmarkedComments();
          setComments(Array.isArray(data.items) ? data.items : []);
        }
      } catch {
        // Ignora erro
      } finally {
        setLoading(false);
      }
    }

    loadBookmarks();
}, [activeTab]);

return (
    <div className="max-w-xl mx-auto py-8 px-4" data-testid="bookmarks-page">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white mb-1">
          {t("bookmarks.title")}
        </h1>
          <p className="text-sm text-zinc-400 mb-4">
            {t("bookmarks.subtitle")}
          </p>

          {/* Abas Publicações / Comentários */}
          <div className="flex border-b border-zinc-800 gap-4 text-sm">
            <button
              type="button"
              onClick={() => setActiveTab("posts")}
              className={`pb-2.5 font-medium border-b-2 transition-colors ${activeTab === "posts"
                  ? "border-pink-500 text-pink-400"
                  : "border-transparent text-zinc-400 hover:text-zinc-200"
                }`}
              data-testid="tab-posts"
            >
              {t("bookmarks.tabPosts", "Publicações")}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("comments")}
              className={`pb-2.5 font-medium border-b-2 transition-colors ${activeTab === "comments"
                  ? "border-pink-500 text-pink-400"
                  : "border-transparent text-zinc-400 hover:text-zinc-200"
                }`}
              data-testid="tab-comments"
            >
              {t("bookmarks.tabComments", "Comentários")}
            </button>
          </div>
      </header>

      {loading ? (
        <div data-testid="bookmarks-loading" className="text-sm text-zinc-500 py-8 text-center">
          Carregando...
        </div>
      ) : activeTab === "posts" ? (
        posts.length === 0 ? (
          <div data-testid="empty-bookmarks" className="text-sm text-zinc-500 py-8 text-center">
            {t("bookmarks.empty")}
          </div>
        ) : (
          <div data-testid="bookmarks-posts-list">
            {posts.map((post) => (
              <PostCard key={post.id} post={post} />
            ))}
          </div>
        )
      ) : (
        comments.length === 0 ? (
      <div data-testid="empty-comments-bookmarks" className="text-sm text-zinc-500 py-8 text-center">
        {t("bookmarks.emptyComments", "Nenhum comentário salvo ainda.")}
      </div>
      ) : (
      <div className="divide-y divide-zinc-800" data-testid="bookmarks-comments-list">
        {comments.map((comment) => (
          <CommentItem key={comment.id} comment={comment} depth={0} flat={true} />
        ))}
      </div>
      )
      )}
    </div>
    );
}

    export default Bookmarks;
