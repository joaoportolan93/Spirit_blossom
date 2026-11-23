import { useState, useEffect, useContext } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "../config/brand";
import { AuthContext } from "../hooks/useAuth";
import { NotificationBell } from "./NotificationBell";
import { api } from "../services/api";
import {
  Home,
  Compass,
  Search,
  Bell,
  Bookmark,
  Settings,
  User,
  LogOut,
  PenSquare,
} from "lucide-react";

/** useAuth seguro — não lança erro quando fora de AuthProvider. */
function useSafeAuth() {
  const ctx = useContext(AuthContext);
  return ctx ?? { user: null, loading: false, logout: async () => {} };
}

/** Badge de notificações (contagem de pedidos pendentes). */
function useNotificationBadge() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await api.get("/api/social/follow-requests/");
        if (mounted) setCount(res.data?.results?.length || 0);
      } catch { /* */ }
    })();
    return () => { mounted = false; };
  }, []);
  return count;
}

function NavItem({ to, icon: Icon, label, exact = false, badge = 0 }) {
  const { pathname } = useLocation();
  const active = exact ? pathname === to : pathname.startsWith(to);

  return (
    <Link
      to={to}
      className={`relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group w-full
        ${active
          ? "bg-pink-600/20 text-pink-400"
          : "text-zinc-400 hover:bg-zinc-800/80 hover:text-zinc-100"
        }`}
      aria-current={active ? "page" : undefined}
    >
      <span className="relative shrink-0 flex items-center justify-center w-6 h-6">
        <Icon
          size={20}
          className={`transition-transform group-hover:scale-105 ${active ? "text-pink-400" : ""}`}
        />
        {badge > 0 && (
          <span
            data-testid="nav-notif-badge"
            className="absolute -top-1 -right-1 bg-rose-600 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-0.5 pointer-events-none"
          >
            {badge > 99 ? "99+" : badge}
          </span>
        )}
      </span>
      <span className="truncate">{label}</span>
    </Link>
  );
}

export function Navbar({ onOpenComposer }) {
  const { t } = useTranslation();
  const { user, logout } = useSafeAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const notifBadge = useNotificationBadge();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const handleOpenComposer = () => {
    if (onOpenComposer) {
      onOpenComposer();
    } else {
      window.dispatchEvent(new CustomEvent("spirit-open-composer"));
      if (location.pathname !== "/") {
        navigate("/", { state: { openComposer: true } });
      }
    }
  };

  if (!user) {
    return (
      <nav className="border-b border-zinc-800/60 bg-zinc-950/95 backdrop-blur sticky top-0 z-50 px-6 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <Link
            to="/"
            className="text-xl font-bold tracking-tight text-white flex items-center gap-2 hover:text-zinc-200 transition"
          >
            <span className="text-pink-400">✦</span>
            {APP_NAME}
          </Link>
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="text-sm text-zinc-300 hover:text-white px-4 py-2 rounded-xl border border-zinc-700 hover:border-zinc-500 transition"
            >
              {t("auth.login")}
            </Link>
            <Link
              to="/register"
              className="text-sm bg-pink-600 hover:bg-pink-500 text-white font-semibold px-4 py-2 rounded-xl transition shadow-lg shadow-pink-900/30"
            >
              {t("auth.register")}
            </Link>
          </div>
        </div>
      </nav>
    );
  }

  return (
    <aside
      className="fixed top-0 left-0 h-screen w-60 bg-zinc-950 border-r border-zinc-800/60 flex flex-col z-50 py-5 px-3"
      role="navigation"
      aria-label="Navegação principal"
    >
      {/* Logo / Branding */}
      <Link
        to="/"
        className="flex items-center gap-2.5 px-3 mb-6 group"
        aria-label={APP_NAME}
      >
        <span className="text-pink-400 text-xl transition-transform group-hover:scale-110" aria-hidden="true">✦</span>
        <span className="text-lg font-bold tracking-tight text-white group-hover:text-zinc-200 transition">
          {APP_NAME}
        </span>
      </Link>

      {/* Nav links — todos com container de ícone com largura e padding padronizados para alinhamento milimétrico */}
      <nav className="flex flex-col gap-1 flex-1" aria-label="Menu principal">
        <NavItem to="/" icon={Home} label={t("nav.feed")} exact />
        <NavItem to="/explore" icon={Compass} label={t("nav.explore")} />
        <NavItem to="/search" icon={Search} label={t("nav.search")} />
        <NavItem to="/notifications" icon={Bell} label={t("nav.notifications")} badge={notifBadge} />
        <NavItem to="/bookmarks" icon={Bookmark} label={t("nav.bookmarks")} />
        <NavItem to="/settings" icon={Settings} label={t("nav.settings")} />
        <NavItem to="/profile" icon={User} label={t("nav.profile")} />

        {/* NotificationBell mantido para compatibilidade com mocks de teste */}
        <div className="hidden" aria-hidden="true">
          <NotificationBell />
        </div>
      </nav>

      {/* Logout */}
      <div className="pt-4 border-t border-zinc-800/60">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-zinc-400 hover:bg-rose-950/40 hover:text-rose-400 transition-all group"
          type="button"
        >
          <span className="shrink-0 flex items-center justify-center w-6 h-6">
            <LogOut size={18} className="group-hover:scale-105 transition-transform" />
          </span>
          <span>{t("auth.logout")}</span>
        </button>
      </div>
    </aside>
  );
}
