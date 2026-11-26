import { useState, useEffect, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  api,
} from "../services/api";
import { useFeatureFlags } from "../hooks/useFeatureFlags";

const CATEGORIES = ["all", "unread", "likes", "comments", "follows", "mentions"];
const ALL_TABS = [...CATEGORIES, "requests"];

function getCategoryLabel(t, cat) {
  return {
    all: t("notifications.tab_all"),
    unread: t("notifications.tab_unread"),
    likes: t("notifications.tab_likes"),
    comments: t("notifications.tab_comments"),
    follows: t("notifications.tab_follows"),
    mentions: t("notifications.tab_mentions"),
  }[cat] || cat;
}

function NotificationSkeleton() {
  return (
    <div className="p-4 flex items-center gap-3 animate-pulse">
      <div className="w-9 h-9 rounded-full bg-zinc-800 shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-3 bg-zinc-800 rounded w-3/4" />
        <div className="h-2.5 bg-zinc-800 rounded w-1/2" />
      </div>
    </div>
  );
}

function NotificationItem({ notif, onRead }) {
  const { t } = useTranslation();
  const isRead = notif.is_read || notif.read;

  const handleClick = async () => {
    if (!isRead) {
      onRead(notif.id);
    }
  };

  const inner = (
    <div
      data-testid={`notification-item-${notif.id}`}
      className={`p-4 flex items-center gap-3 transition ${isRead ? "opacity-60" : "bg-zinc-800/20"
        } hover:bg-zinc-800/40 cursor-pointer`}
      onClick={handleClick}
      role="listitem"
    >
      {/* Avatar do remetente */}
      {notif.sender?.avatar ? (
        <img
          src={notif.sender.avatar}
          alt={notif.sender.username}
          className="w-9 h-9 rounded-full object-cover bg-zinc-800 shrink-0"
        />
      ) : (
        <div className="w-9 h-9 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-zinc-300 shrink-0 text-sm">
          {(notif.sender?.username || "?")[0].toUpperCase()}
        </div>
      )}

      <div className="flex-1 min-w-0">
        <p className="text-sm text-zinc-200 truncate">
          {notif.sender?.display_name || notif.sender?.username ? (
            <span className="font-semibold text-white mr-1">
              {notif.sender.display_name || notif.sender.username}
            </span>
          ) : null}
          {t(`notifications.verb_${notif.notification_type}`, {
            defaultValue: notif.notification_type,
          })}
        </p>
        <p className="text-xs text-zinc-500 mt-0.5">
          {new Date(notif.created_at).toLocaleDateString()}
        </p>
      </div>

      {!isRead && (
        <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0" aria-label={t("notifications.unread_dot")} />
      )}
    </div>
  );

  if (notif.target_url) {
    return (
      <Link to={notif.target_url} className="block" aria-label={t("notifications.open")}>
        {inner}
      </Link>
    );
  }
  return inner;
}

export function Notifications() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isEnabled } = useFeatureFlags();

  // Abas: tab normal ou categoria de notificação
  const tabParam = searchParams.get("tab") || "all";
  const activeTab = ALL_TABS.includes(tabParam) ? tabParam : "all";

  const [notifications, setNotifications] = useState([]);
  const [loadingNotifs, setLoadingNotifs] = useState(true);
  const [requests, setRequests] = useState([]);
  const [loadingRequests, setLoadingRequests] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [requestFeedback, setRequestFeedback] = useState("");
  const [requestError, setRequestError] = useState("");

  const loadNotifications = useCallback(async (tab) => {
    setLoadingNotifs(true);
    try {
      const isUnread = tab === "unread";
      const category = isUnread ? "all" : tab;
      const data = await getNotifications({ category, unreadOnly: isUnread });
      setNotifications(Array.isArray(data) ? data : data.results || []);
    } catch {
      setNotifications([]);
    } finally {
      setLoadingNotifs(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab !== "requests") {
      loadNotifications(activeTab);
    }
  }, [activeTab, loadNotifications]);

  useEffect(() => {
    if (activeTab !== "requests") {
      setLoadingRequests(false);
      return;
    }
    let isMounted = true;
    setLoadingRequests(true);
    api
      .get("/api/social/follow-requests/")
      .then((res) => {
        if (isMounted) setRequests(res.data?.results || []);
      })
      .catch(() => { })
      .finally(() => {
        if (isMounted) setLoadingRequests(false);
      });
    return () => {
      isMounted = false;
    };
  }, [activeTab]);

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true, is_read: true })));
      window.dispatchEvent(new Event("spirit-notifications-updated"));
    } catch {
      // ignora
    }
  };

  const handleMarkRead = useCallback(async (id) => {
    try {
      await markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: true, is_read: true } : n))
      );
      window.dispatchEvent(new Event("spirit-notifications-updated"));
    } catch {
      // ignora
    }
  }, []);

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

  const hasUnread = notifications.some((n) => !n.is_read && !n.read);
  const isNotifTab = CATEGORIES.includes(activeTab);
  const filtersEnabled = isEnabled("notification_center_filters");

  const visibleTabs = filtersEnabled
    ? [...CATEGORIES, "requests"]
    : ["all", "requests"];

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h1 className="text-xl font-bold text-white mb-6">{t("notifications.title")}</h1>

      {/* Abas */}
      <div
        role="tablist"
        aria-label={t("notifications.tabs_label")}
        className="flex border-b border-zinc-800 mb-6 gap-4 overflow-x-auto"
      >
        {visibleTabs.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            data-testid={`tab-${tab}`}
            onClick={() => setSearchParams(tab === "all" ? {} : { tab })}
            className={`pb-3 text-sm font-medium border-b-2 transition whitespace-nowrap ${activeTab === tab
              ? "border-white text-white"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
              }`}
          >
            {tab === "requests"
              ? t("notifications.tab_requests")
              : getCategoryLabel(t, tab)}
          </button>
        ))}
      </div>

      {/* Conteúdo — abas de notificações */}
      {isNotifTab && (
        <div>
          {hasUnread && (
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
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl divide-y divide-zinc-800">
              {[1, 2, 3].map((k) => (
                <NotificationSkeleton key={k} />
              ))}
            </div>
          ) : notifications.length === 0 ? (
            <div
              data-testid="notifications-empty"
              className="py-12 text-center bg-zinc-900/40 border border-zinc-800 rounded-xl"
            >
              <p className="text-2xl mb-2">🌸</p>
              <p className="text-sm text-zinc-400">{t("notifications.empty")}</p>
            </div>
          ) : (
            <div
              role="list"
              aria-live="polite"
              className="bg-zinc-900 border border-zinc-800 rounded-2xl divide-y divide-zinc-800"
            >
              {notifications.map((n) => (
                <NotificationItem key={n.id} notif={n} onRead={handleMarkRead} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Conteúdo — aba pedidos de seguir */}
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
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl divide-y divide-zinc-800">
              {[1, 2].map((k) => <NotificationSkeleton key={k} />)}
            </div>
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
