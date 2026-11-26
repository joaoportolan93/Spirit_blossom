import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";

export function FollowButton({
  username,
  isFollowing: initialIsFollowing = false,
  followStatus: initialFollowStatus = null,
  onToggle,
}) {
  const { t } = useTranslation();
  const [isFollowing, setIsFollowing] = useState(initialIsFollowing);
  const [isPending, setIsPending] = useState(initialFollowStatus === "pending");
  const [loading, setLoading] = useState(false);

  const handleToggle = async () => {
    if (loading) return;
    setLoading(true);
    try {
      if (isFollowing || isPending) {
        await api.delete(`/api/social/follow/${username}/`);
        setIsFollowing(false);
        setIsPending(false);
        if (onToggle) onToggle(false);
      } else {
        const res = await api.post(`/api/social/follow/${username}/`);
        if (res?.data?.status === "pending") {
          setIsPending(true);
          setIsFollowing(false);
          if (onToggle) onToggle(false);
        } else {
          setIsFollowing(true);
          setIsPending(false);
          if (onToggle) onToggle(true);
        }
      }
    } catch {
      // Reverte em caso de erro
    } finally {
      setLoading(false);
    }
  };

  const active = isFollowing || isPending;

  return (
    <button
      type="button"
      data-testid="follow-button"
      onClick={handleToggle}
      disabled={loading}
      className={`px-4 py-1.5 rounded-full text-sm font-semibold transition ${
        active
          ? "border border-zinc-700 bg-transparent text-zinc-300 hover:border-rose-600 hover:text-rose-500"
          : "bg-white text-zinc-950 hover:bg-zinc-200"
      }`}
    >
      {isPending
        ? t("profile.follow_pending")
        : isFollowing
        ? t("profile.unfollow")
        : t("profile.follow")}
    </button>
  );
}
