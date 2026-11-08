import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";

export function FollowRequests() {
  const { t } = useTranslation();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadRequests() {
      setLoading(true);
      setError("");
      try {
        const res = await api.get("/api/social/follow-requests/");
        if (isMounted) {
          setRequests(res.data.results || []);
        }
      } catch {
        if (isMounted) {
          setError(t("follow_requests.load_error"));
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadRequests();
    return () => {
      isMounted = false;
    };
  }, [t]);

  const handleAccept = async (username) => {
    setActionLoading((prev) => ({ ...prev, [username]: "accept" }));
    setFeedback("");
    try {
      await api.post(`/api/social/follow-requests/${username}/accept/`);
      setRequests((prev) => prev.filter((r) => r.username !== username));
      setFeedback(t("follow_requests.accepted"));
    } catch {
      setError(t("errors.generic"));
    } finally {
      setActionLoading((prev) => ({ ...prev, [username]: null }));
    }
  };

  const handleReject = async (username) => {
    setActionLoading((prev) => ({ ...prev, [username]: "reject" }));
    setFeedback("");
    try {
      await api.post(`/api/social/follow-requests/${username}/reject/`);
      setRequests((prev) => prev.filter((r) => r.username !== username));
      setFeedback(t("follow_requests.rejected"));
    } catch {
      setError(t("errors.generic"));
    } finally {
      setActionLoading((prev) => ({ ...prev, [username]: null }));
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white">{t("follow_requests.title")}</h1>
        <p className="text-sm text-zinc-400 mt-1">{t("follow_requests.subtitle")}</p>
      </div>

      {feedback && (
        <div data-testid="requests-feedback" className="mb-4 p-3 bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 rounded-lg text-sm">
          {feedback}
        </div>
      )}

      {error && (
        <div data-testid="requests-error" className="mb-4 p-3 bg-rose-950/40 border border-rose-800/60 text-rose-300 rounded-lg text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-zinc-500 py-8 text-center">{t("feed.loading")}</p>
      ) : requests.length === 0 ? (
        <div data-testid="requests-empty" className="py-12 text-center bg-zinc-900/40 border border-zinc-800 rounded-xl">
          <p className="text-sm text-zinc-400">{t("follow_requests.empty")}</p>
        </div>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl divide-y divide-zinc-800">
          {requests.map((req) => (
            <div
              key={req.id}
              data-testid={`follow-request-${req.username}`}
              className="p-4 flex items-center justify-between gap-4"
            >
              <div className="flex items-center gap-3">
                {req.avatar ? (
                  <img
                    src={req.avatar}
                    alt={req.username}
                    className="w-10 h-10 rounded-full object-cover bg-zinc-800"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-zinc-300">
                    {req.username[0]?.toUpperCase()}
                  </div>
                )}
                <Link
                  to={`/profile/${req.username}`}
                  className="font-medium text-white hover:text-zinc-200"
                >
                  @{req.username}
                </Link>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  data-testid={`accept-btn-${req.username}`}
                  onClick={() => handleAccept(req.username)}
                  disabled={Boolean(actionLoading[req.username])}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white text-zinc-900 hover:bg-zinc-200 transition disabled:opacity-50"
                >
                  {actionLoading[req.username] === "accept"
                    ? t("follow_requests.accepting")
                    : t("follow_requests.accept")}
                </button>
                <button
                  type="button"
                  data-testid={`reject-btn-${req.username}`}
                  onClick={() => handleReject(req.username)}
                  disabled={Boolean(actionLoading[req.username])}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700 hover:bg-zinc-700 transition disabled:opacity-50"
                >
                  {actionLoading[req.username] === "reject"
                    ? t("follow_requests.rejecting")
                    : t("follow_requests.reject")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default FollowRequests;

