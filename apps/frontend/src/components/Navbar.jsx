import { Link, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "../config/brand";
import { useAuth } from "../hooks/useAuth";
import { NotificationBell } from "./NotificationBell";
import {
  Home,
  Compass,
  Search,
  Bookmark,
  Settings,
  User,
  LogOut,
} from "lucide-react";

function NavItem({ to, icon: Icon, label, exact = false }) {
  const { pathname } = useLocation();
  const active = exact ? pathname === to : pathname.startsWith(to);

  return (
    <Link
      to={to}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group w-full
        ${active
          ? "bg-violet-600/20 text-violet-400"
          : "text-zinc-400 hover:bg-zinc-800/80 hover:text-zinc-100"
        }`}
    >
      <Icon
        size={20}
        className={`shrink-0 transition-transform group-hover:scale-105 ${active ? "text-violet-400" : ""}`}
      />
      <span>{label}</span>
    </Link>
  );
}

export function Navbar() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  if (!user) {
    return (
      <nav className="border-b border-zinc-800/60 bg-zinc-950/95 backdrop-blur sticky top-0 z-50 px-6 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <Link
            to="/"
            className="text-xl font-bold tracking-tight text-white flex items-center gap-2 hover:text-zinc-200 transition"
          >
            <span className="text-violet-400">✦</span>
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
              className="text-sm bg-violet-600 hover:bg-violet-500 text-white font-semibold px-4 py-2 rounded-xl transition shadow-lg shadow-violet-900/30"
            >
              {t("auth.register")}
            </Link>
          </div>
        </div>
      </nav>
    );
  }

  return (
    <aside className="fixed top-0 left-0 h-screen w-60 bg-zinc-950 border-r border-zinc-800/60 flex flex-col z-50 py-5 px-3">
      {/* Logo */}
      <Link
        to="/"
        className="flex items-center gap-2.5 px-3 mb-6 group"
      >
        <span className="text-violet-400 text-xl transition-transform group-hover:scale-110">✦</span>
        <span className="text-lg font-bold tracking-tight text-white group-hover:text-zinc-200 transition">
          {APP_NAME}
        </span>
      </Link>

      {/* Nav links */}
      <nav className="flex flex-col gap-1 flex-1">
        <NavItem to="/" icon={Home} label={t("nav.feed")} exact />
        <NavItem to="/explore" icon={Compass} label={t("nav.explore")} />
        <NavItem to="/search" icon={Search} label={t("nav.search")} />
        <NavItem to="/bookmarks" icon={Bookmark} label={t("nav.bookmarks")} />
        <NavItem to="/settings" icon={Settings} label={t("nav.settings")} />
        <NavItem to="/profile" icon={User} label={t("nav.profile")} />

        {/* Notification bell */}
        <div className="flex items-center gap-3 px-3 py-2.5 text-zinc-400">
          <NotificationBell />
        </div>
      </nav>

      {/* Logout */}
      <div className="mt-auto pt-4 border-t border-zinc-800/60">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-zinc-400 hover:bg-rose-950/40 hover:text-rose-400 transition-all group"
        >
          <LogOut size={18} className="shrink-0 group-hover:scale-105 transition-transform" />
          <span>{t("auth.logout")}</span>
        </button>
      </div>
    </aside>
  );
}
