import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";

export function Notifications() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") === "requests" ? "requests" : "all";

  // Estado da aba 'Todas'
  const [notifications, setNotifications] = useState([]);
  const [loadingNotifs, setLoadingNotifs] = useState(true);

  // Estado da aba 'Pedidos de seguir'
  const [requests, setRequests] = useState([]);
  const [loadingRequests, setLoadingRequests] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [requestFeedback, setRequestFeedback] = useState("");
  const [requestError, setRequestError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadAllNotifications() {
      setLoadingNotifs(true);
      try {
        const res = await api.get("/api/notifications/");
        if (isMounted) {
          setNotifications(Array.isArray(res.data) ? res.data : []);
        }
      } catch {
        // Ignora erro
      } finally {
        if (isMounted) setLoadingNotifs(false);
      }
    }

    async function loadRequests() {
      setLoadingRequests(true);
      try {
        const res = await api.get("/api/social/follow-requests/");
        if (isMounted) {
          setRequests(res.data?.results || []);
        }
      } catch {
        // Ignora erro
      } finally {
        if (isMounted) setLoadingRequests(false);
      }
    }

    loadAllNotifications();
    loadRequests();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleMarkAllRead = async () => {
    try {
      await api.post("/api/notifications/mark-all-read/");
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch {
      // Ignora erro
    }
  };

  const handleAccept = async (username) => {
    setActionLoading((prev) => ({ ...prev, [username]: "accept" }));
    setRequestFeedback("");
    try {
      await api.post(`/api/social/follow-requests/${username}/accept/`);
      setRequests((prev) => prev.filter((r) => r.username !== username));
      setRequestFeedback(t("follow_requests.accepted"));
    } catch {
      setRequestError(t("errors.generic"));
    } finally {
      setActionLoading((prev) => ({ ...prev, [username]: null }));
    }
  };

  const handleReject = async (username) => {
    setActionLoading((prev) => ({ ...prev, [username]: "reject" }));
    setRequestFeedback("");
    try {
      await api.post(`/api/social/follow-requests/${username}/reject/`);
      setRequests((prev) => prev.filter((r) => r.username !== username));
      setRequestFeedback(t("follow_requests.rejected"));
    } catch {
      setRequestError(t("errors.generic"));
    } finally {
      setActionLoading((prev) => ({ ...prev, [username]: null }));
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h1 className="text-xl font-bold text-white mb-6">{t("notifications.title")}</h1>

      {/* Abas */}
      <div className="flex border-b border-zinc-800 mb-6 gap-6">
        <button
          type="button"
          data-testid="tab-all-notifications"
          onClick={() => setSearchParams({})}
          className={`pb-3 text-sm font-medium border-b-2 transition ${
            activeTab === "all"
              ? "border-white text-white"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          {t("notifications.tab_all")}
        </button>
        <button
          type="button"
          data-testid="tab-follow-requests"
          onClick={() => setSearchParams({ tab: "requests" })}
          className={`pb-3 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
            activeTab === "requests"
              ? "border-white text-white"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <span>{t("notifications.tab_requests")}</span>
          {requests.length > 0 && (
            <span
              data-testid="requests-count-badge"
              className="bg-zinc-800 text-zinc-300 text-xs px-2 py-0.5 rounded-full"
            >
              {requests.length}
            </span>
          )}
        </button>
      </div>

      {/* Conteúdo Aba 'Todas' */}
      {activeTab === "all" && (
        <div>
          {notifications.some((n) => !n.is_read) && (
            <div className="flex justify-end mb-4">
              <button
                type="button"
                data-testid="mark-all-read-btn"
                onClick={handleMarkAllRead}
                className="text-xs text-zinc-400 hover:text-white transition"
              >
                {t("notifications.mark_all_read")}
              </button>
            </div>
          )}

          {loadingNotifs ? (
            <p className="text-sm text-zinc-500 py-8 text-center">{t("feed.loading")}</p>
          ) : notifications.length === 0 ? (
            <div
              data-testid="notifications-empty"
              className="py-12 text-center bg-zinc-900/40 border border-zinc-800 rounded-xl"
            >
              <p className="text-sm text-zinc-400">{t("notifications.empty")}</p>
            </div>
          ) : (
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl divide-y divide-zinc-800">
              {notifications.map((n) => (
                <div
                  key={n.id}
                  data-testid={`notification-item-${n.id}`}
                  className={`p-4 flex items-center justify-between ${
                    n.is_read ? "opacity-70" : "bg-zinc-800/20"
                  }`}
                >
                  <div className="text-sm text-zinc-200">
                    <p>
                      {n.actor?.username && (
                        <span className="font-semibold text-white mr-1.5">
                          {n.actor.username}
                        </span>
                      )}
                      {n.verb || n.action || "Nova notificação"}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Conteúdo Aba 'Pedidos de seguir' */}
      {activeTab === "requests" && (
        <div>
          {requestFeedback && (
            <div
              data-testid="requests-feedback"
              className="mb-4 p-3 bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 rounded-lg text-sm"
            >
              {requestFeedback}
            </div>
          )}

          {requestError && (
            <div
              data-testid="requests-error"
              className="mb-4 p-3 bg-rose-950/40 border border-rose-800/60 text-rose-300 rounded-lg text-sm"
            >
              {requestError}
            </div>
          )}

          {loadingRequests ? (
            <p className="text-sm text-zinc-500 py-8 text-center">{t("feed.loading")}</p>
          ) : requests.length === 0 ? (
            <div
              data-testid="requests-empty"
              className="py-12 text-center bg-zinc-900/40 border border-zinc-800 rounded-xl"
            >
              <p className="text-sm text-zinc-400">{t("follow_requests.empty")}</p>
            </div>
          ) : (
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl divide-y divide-zinc-800">
              {requests.map((req) => (
                <div
                  key={req.id || req.username}
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
      )}
    </div>
  );
}

export default Notifications;
