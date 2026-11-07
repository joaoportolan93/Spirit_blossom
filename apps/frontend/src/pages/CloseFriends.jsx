import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";

export function CloseFriends() {
  const { t } = useTranslation();
  const [friends, setFriends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newUsername, setNewUsername] = useState("");
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const fetchFriends = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get("/api/social/close-friends/");
      setFriends(res.data.results || []);
    } catch {
      setError(t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchFriends();
  }, [fetchFriends]);

  const handleAdd = async (e) => {
    e.preventDefault();
    const username = newUsername.trim();
    if (!username) return;

    setError("");
    setActionMessage("");

    try {
      await api.post(`/api/social/close-friends/${username}/`);
      setActionMessage(t("close_friends.added_success"));
      setNewUsername("");
      await fetchFriends();
    } catch (err) {
      setError(err.response?.data?.detail || t("errors.generic"));
    }
  };

  const handleRemove = async (username) => {
    setError("");
    setActionMessage("");

    try {
      await api.delete(`/api/social/close-friends/${username}/`);
      setActionMessage(t("close_friends.removed_success"));
      await fetchFriends();
    } catch (err) {
      setError(err.response?.data?.detail || t("errors.generic"));
    }
  };

  return (
    <div className="max-w-xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold tracking-tight text-white mb-1">
        {t("close_friends.title")}
      </h1>
      <p className="text-sm text-zinc-400 mb-6">
        {t("close_friends.subtitle")}
      </p>

      <form onSubmit={handleAdd} className="flex gap-2 mb-6">
        <input
          type="text"
          data-testid="add-close-friend-input"
          value={newUsername}
          onChange={(e) => setNewUsername(e.target.value)}
          placeholder={t("close_friends.add_placeholder")}
          className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
        />
        <button
          type="submit"
          data-testid="add-close-friend-button"
          className="bg-white text-zinc-950 font-medium px-4 py-2 rounded-lg text-sm hover:bg-zinc-200 transition"
        >
          {t("close_friends.add_button")}
        </button>
      </form>

      {error && (
        <div data-testid="close-friends-error" className="text-xs text-rose-500 mb-4">
          {error}
        </div>
      )}

      {actionMessage && (
        <div data-testid="close-friends-action-message" className="text-xs text-emerald-400 mb-4">
          {actionMessage}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-zinc-500">Carregando...</div>
      ) : friends.length === 0 ? (
        <div data-testid="empty-close-friends" className="text-sm text-zinc-500">
          {t("close_friends.empty")}
        </div>
      ) : (
        <ul data-testid="close-friends-list" className="space-y-2">
          {friends.map((friend) => (
            <li
              key={friend.username}
              className="flex items-center justify-between p-3 bg-zinc-900/60 border border-zinc-800/80 rounded-lg"
            >
              <div className="flex items-center gap-3">
                {friend.avatar ? (
                  <img
                    src={friend.avatar}
                    alt={friend.username}
                    className="w-8 h-8 rounded-full object-cover"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs text-zinc-300">
                    {friend.username.slice(0, 2).toUpperCase()}
                  </div>
                )}
                <span className="text-sm text-zinc-200 font-medium">
                  @{friend.username}
                </span>
              </div>
              <button
                type="button"
                data-testid={`remove-friend-${friend.username}`}
                onClick={() => handleRemove(friend.username)}
                className="text-xs text-rose-400 hover:text-rose-300 px-2 py-1 rounded border border-rose-900/40 hover:bg-rose-950/40 transition"
              >
                {t("close_friends.remove")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
