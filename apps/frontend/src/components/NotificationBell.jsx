import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Bell } from "lucide-react";
import { api } from "../services/api";

export function NotificationBell() {
  const { t } = useTranslation();
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function loadNotifications() {
      try {
        const res = await api.get("/api/notifications/");
        if (isMounted) {
          setNotifications(Array.isArray(res.data) ? res.data : []);
        }
      } catch {
        // Ignora erro se não autenticado
      }
    }
    loadNotifications();
    return () => {
      isMounted = false;
    };
  }, []);

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const markAsRead = async (id) => {
    try {
      await api.post(`/api/notifications/${id}/read/`);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch {
      // Ignora erro
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        data-testid="notification-bell-btn"
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-1.5 text-zinc-300 hover:text-white rounded-full hover:bg-zinc-800 transition"
        aria-label={t("notifications.title")}
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span
            data-testid="unread-badge"
            className="absolute -top-1 -right-1 bg-rose-600 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center"
          >
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          data-testid="notifications-dropdown"
          className="absolute right-0 mt-2 w-80 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl py-2 z-50"
        >
          <div className="px-3 py-1.5 border-b border-zinc-800 font-semibold text-sm text-zinc-200">
            {t("notifications.title")}
          </div>
          <div className="max-h-64 overflow-y-auto divide-y divide-zinc-800/50">
            {notifications.length === 0 ? (
              <p className="p-4 text-xs text-zinc-400 text-center">
                {t("notifications.empty")}
              </p>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => !n.is_read && markAsRead(n.id)}
                  className={`p-3 text-xs cursor-pointer hover:bg-zinc-800/60 transition ${
                    n.is_read ? "text-zinc-400" : "text-zinc-100 font-medium"
                  }`}
                >
                  <p>{n.verb || n.action || "Nova notificação"}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
