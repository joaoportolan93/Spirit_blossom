import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { getUnreadCount } from "../services/api";

/**
 * NotificationBell — ícone de sino com badge de notificações não lidas (Onda 7a).
 *
 * Polling leve via /api/notifications/unread-count/ a cada 60 segundos.
 * aria-live="polite" para atualizações acessíveis do badge.
 */
export function NotificationBell({ className = "" }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    let isMounted = true;

    async function loadCount() {
      try {
        const count = await getUnreadCount();
        if (isMounted) setUnreadCount(count);
      } catch {
        // ignora se não autenticado
      }
    }

    loadCount();
    const interval = setInterval(loadCount, 60_000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <button
      type="button"
      data-testid="notification-bell-btn"
      onClick={() => navigate("/notifications")}
      className={`relative flex items-center justify-center p-1 text-zinc-400 hover:text-zinc-100 transition-colors ${className}`}
      aria-label={t("notifications.title")}
    >
      <Bell className="w-5 h-5 shrink-0" />
      {unreadCount > 0 && (
        <span
          data-testid="unread-badge"
          aria-live="polite"
          aria-atomic="true"
          className="absolute -top-1.5 -right-1.5 bg-rose-600 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-0.5"
        >
          {unreadCount > 99 ? "99+" : unreadCount}
        </span>
      )}
    </button>
  );
}

export default NotificationBell;

