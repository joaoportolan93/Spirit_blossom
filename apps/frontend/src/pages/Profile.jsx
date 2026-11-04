import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FollowButton } from "../components/FollowButton";
import { PostCard } from "../components/PostCard";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";

export function Profile() {
  const { t } = useTranslation();
  const { username: routeUsername } = useParams();
  const { user } = useAuth();

  const currentUsername = routeUsername || user?.username || "usuario";
  const isOwnProfile = !routeUsername || routeUsername === user?.username;

  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function loadUserPosts() {
      try {
        const res = await api.get("/api/posts/");
        if (isMounted) {
          const userPosts = Array.isArray(res.data)
            ? res.data.filter((p) => p.author?.username === currentUsername)
            : [];
          setPosts(userPosts);
        }
      } catch {
        // Ignora erro
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadUserPosts();
    return () => {
      isMounted = false;
    };
  }, [currentUsername]);

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      {/* Header do perfil */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 mb-8 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-xl text-zinc-200">
            {currentUsername[0]?.toUpperCase()}
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">@{currentUsername}</h1>
            <p className="text-xs text-zinc-400 mt-1">{t("profile.bio")}</p>
          </div>
        </div>

        {!isOwnProfile && (
          <FollowButton username={currentUsername} isFollowing={false} />
        )}
      </div>

      {/* Lista de publicações */}
      <div>
        <h2 className="text-lg font-bold text-white mb-4">{t("profile.posts")}</h2>

        {loading ? (
          <p className="text-sm text-zinc-500">{t("feed.loading")}</p>
        ) : posts.length === 0 ? (
          <p className="text-sm text-zinc-500 py-8 text-center bg-zinc-900/40 rounded-xl border border-zinc-800">
            {t("profile.empty_posts")}
          </p>
        ) : (
          posts.map((post) => <PostCard key={post.id} post={post} />)
        )}
      </div>
    </div>
  );
}
