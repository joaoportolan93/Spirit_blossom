import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";

export function FollowButton({ username, isFollowing: initialIsFollowing = false, onToggle }) {
  const { t } = useTranslation();
  const [isFollowing, setIsFollowing] = useState(initialIsFollowing);
  const [loading, setLoading] = useState(false);

  const handleToggle = async () => {
    if (loading) return;
    setLoading(true);
    try {
      if (isFollowing) {
        await api.delete(`/api/social/follow/${username}/`);
        setIsFollowing(false);
        if (onToggle) onToggle(false);
      } else {
        await api.post(`/api/social/follow/${username}/`);
        setIsFollowing(true);
        if (onToggle) onToggle(true);
      }
    } catch {
      // Reverte em caso de erro
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      data-testid="follow-button"
      onClick={handleToggle}
      disabled={loading}
      className={`px-4 py-1.5 rounded-full text-sm font-semibold transition ${
        isFollowing
          ? "border border-zinc-700 bg-transparent text-zinc-300 hover:border-rose-600 hover:text-rose-500"
          : "bg-white text-zinc-950 hover:bg-zinc-200"
      }`}
    >
      {isFollowing ? t("profile.unfollow") : t("profile.follow")}
    </button>
  );
}
