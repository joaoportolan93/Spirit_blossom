import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bell } from "lucide-react";
import { api } from "../services/api";

export function NotificationBell() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    let isMounted = true;
    async function loadPendingCount() {
      try {
        const res = await api.get("/api/social/follow-requests/");
        if (isMounted) {
          const count = res.data?.results?.length || 0;
          setPendingCount(count);
        }
      } catch {
        // Ignora erro se não autenticado
      }
    }
    loadPendingCount();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <button
      type="button"
      data-testid="notification-bell-btn"
      onClick={() => navigate("/notifications")}
      className="relative p-1.5 text-zinc-300 hover:text-white rounded-full hover:bg-zinc-800 transition"
      aria-label={t("notifications.title")}
    >
      <Bell className="w-5 h-5" />
      {pendingCount > 0 && (
        <span
          data-testid="unread-badge"
          className="absolute -top-1 -right-1 bg-rose-600 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center"
        >
          {pendingCount}
        </span>
      )}
    </button>
  );
}

export default NotificationBell;
