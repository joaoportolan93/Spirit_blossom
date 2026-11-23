import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { api } from "../services/api";

/**
 * NotificationBell — ícone de sino com badge de pedidos pendentes.
 *
 * Renderiza um botão que navega para /notifications ao ser clicado.
 * No Navbar, é embutido dentro de um <Link> (que trata a navegação),
 * então o onClick interno é redundante mas inofensivo (event bubbles para o Link).
 */
export function NotificationBell({ className = "" }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    let isMounted = true;
    async function loadPendingCount() {
      try {
        const res = await api.get("/api/social/follow-requests/");
        if (isMounted) {
          setPendingCount(res.data?.results?.length || 0);
        }
      } catch {
        // ignora se não autenticado
      }
    }
    loadPendingCount();
    return () => { isMounted = false; };
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
      {pendingCount > 0 && (
        <span
          data-testid="unread-badge"
          className="absolute -top-1.5 -right-1.5 bg-rose-600 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-0.5"
        >
          {pendingCount > 99 ? "99+" : pendingCount}
        </span>
      )}
    </button>
  );
}

export default NotificationBell;
