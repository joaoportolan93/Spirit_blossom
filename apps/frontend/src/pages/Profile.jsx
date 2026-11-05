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
  const [stats, setStats] = useState({
    followers_count: 0,
    following_count: 0,
    is_following: false,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      try {
        const [postsRes, profileRes] = await Promise.allSettled([
          api.get("/api/posts/"),
          api.get(`/api/social/profile/${currentUsername}/`),
        ]);

        if (isMounted) {
          if (postsRes.status === "fulfilled") {
            const data = postsRes.value.data;
            const userPosts = Array.isArray(data)
              ? data.filter((p) => p.author?.username === currentUsername)
              : [];
            setPosts(userPosts);
          }
          if (profileRes.status === "fulfilled") {
            setStats({
              followers_count: profileRes.value.data.followers_count ?? 0,
              following_count: profileRes.value.data.following_count ?? 0,
              is_following: Boolean(profileRes.value.data.is_following),
            });
          }
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, [currentUsername]);

  const handleFollowToggle = (nowFollowing) => {
    setStats((prev) => ({
      ...prev,
      is_following: nowFollowing,
      followers_count: nowFollowing
        ? prev.followers_count + 1
        : Math.max(0, prev.followers_count - 1),
    }));
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      {/* Header do perfil */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 mb-8">
        <div className="flex items-center justify-between">
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
            <FollowButton
              key={`${currentUsername}-${stats.is_following}`}
              username={currentUsername}
              isFollowing={stats.is_following}
              onToggle={handleFollowToggle}
            />
          )}
        </div>

        {/* Contadores do perfil */}
        <div className="flex items-center gap-6 mt-6 pt-6 border-t border-zinc-800 text-sm">
          <div data-testid="profile-stat-posts" className="flex items-center gap-1.5">
            <span className="font-bold text-white">{posts.length}</span>
            <span className="text-zinc-400">{t("profile.posts")}</span>
          </div>
          <div data-testid="profile-stat-followers" className="flex items-center gap-1.5">
            <span className="font-bold text-white">{stats.followers_count}</span>
            <span className="text-zinc-400">{t("profile.followers")}</span>
          </div>
          <div data-testid="profile-stat-following" className="flex items-center gap-1.5">
            <span className="font-bold text-white">{stats.following_count}</span>
            <span className="text-zinc-400">{t("profile.following")}</span>
          </div>
        </div>
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
