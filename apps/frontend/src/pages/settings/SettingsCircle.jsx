import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../services/api";

export function SettingsCircle() {
  const { t } = useTranslation();
  const [candidates, setCandidates] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const fetchCandidates = useCallback(async (q = "") => {
    setLoading(true);
    setError("");
    try {
      const params = q.trim() ? { q: q.trim() } : {};
      const res = await api.get("/api/social/close-friends/candidates/", { params });
      setCandidates(res.data?.results || []);
    } catch {
      setError(t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchCandidates(query);
  }, [fetchCandidates, query]);

  const handleToggle = async (username, currentlyInCircle) => {
    setActionLoading((prev) => ({ ...prev, [username]: true }));
    setMessage("");
    setError("");

    try {
      if (currentlyInCircle) {
        await api.delete(`/api/social/close-friends/${username}/`);
        setCandidates((prev) =>
          prev.map((c) =>
            c.username === username ? { ...c, is_close_friend: false } : c
          )
        );
        setMessage(t("close_friends.removed_success"));
      } else {
        await api.post(`/api/social/close-friends/${username}/`);
        setCandidates((prev) =>
          prev.map((c) =>
            c.username === username ? { ...c, is_close_friend: true } : c
          )
        );
        setMessage(t("close_friends.added_success"));
      }
    } catch (err) {
      setError(err.response?.data?.detail || t("errors.generic"));
    } finally {
      setActionLoading((prev) => ({ ...prev, [username]: false }));
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-1">
        {t("settings.circle")}
      </h2>
      <p className="text-xs text-zinc-400 mb-6">
        {t("settings.circle_subtitle")}
      </p>

      {/* Busca de seguidores */}
      <div className="mb-6">
        <label htmlFor="circle-search-input" className="sr-only">
          {t("settings.search_followers_placeholder")}
        </label>
        <input
          id="circle-search-input"
          type="text"
          data-testid="circle-search-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("settings.search_followers_placeholder")}
          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
        />
      </div>

      {message && (
        <div data-testid="circle-message" className="text-xs text-emerald-400 mb-4">
          {message}
        </div>
      )}

      {error && (
        <div data-testid="circle-error" className="text-xs text-rose-400 mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-zinc-500">Carregando...</div>
      ) : candidates.length === 0 ? (
        <p data-testid="circle-empty" className="text-sm text-zinc-500">
          {t("settings.no_candidates")}
        </p>
      ) : (
        <ul data-testid="circle-candidates-list" className="divide-y divide-zinc-800">
          {candidates.map((candidate) => {
            const isLoading = Boolean(actionLoading[candidate.username]);
            return (
              <li
                key={candidate.username}
                data-testid={`candidate-item-${candidate.username}`}
                className="py-3 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-sm text-zinc-200">
                    {candidate.username[0]?.toUpperCase()}
                  </div>
                  <div>
                    <span className="text-sm font-medium text-white block">
                      @{candidate.username}
                    </span>
                    {candidate.is_close_friend && (
                      <span className="text-xs text-emerald-400">
                        {t("settings.in_circle")}
                      </span>
                    )}
                  </div>
                </div>

                <button
                  type="button"
                  data-testid={`toggle-circle-btn-${candidate.username}`}
                  disabled={isLoading}
                  onClick={() => handleToggle(candidate.username, candidate.is_close_friend)}
                  className={`text-xs px-3 py-1.5 rounded-lg font-medium transition ${
                    candidate.is_close_friend
                      ? "bg-rose-950/40 text-rose-400 border border-rose-800/60 hover:bg-rose-900/40"
                      : "bg-white text-zinc-950 hover:bg-zinc-200"
                  } disabled:opacity-50`}
                >
                  {isLoading
                    ? "..."
                    : candidate.is_close_friend
                    ? t("settings.remove_from_circle")
                    : t("settings.add_to_circle")}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default SettingsCircle;

