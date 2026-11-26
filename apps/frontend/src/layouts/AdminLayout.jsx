import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  ShieldAlert,
  Users,
  History,
  Flag,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { APP_NAME } from "../config/brand";

export function AdminLayout({ children }) {
  const { t } = useTranslation();
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div
        data-testid="admin-loading"
        className="min-h-screen bg-zinc-950 flex items-center justify-center"
      >
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-pink-500" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!user.is_staff && !user.is_superuser) {
    return <Navigate to="/" replace />;
  }

  const menuItems = [
    { path: "/admin", icon: LayoutDashboard, label: t("admin.nav.dashboard", "Dashboard"), exact: true },
    { path: "/admin/moderation", icon: ShieldAlert, label: t("admin.nav.moderation", "Moderação") },
    { path: "/admin/users", icon: Users, label: t("admin.nav.users", "Usuários") },
    { path: "/admin/logs", icon: History, label: t("admin.nav.logs", "Auditoria") },
    { path: "/admin/settings", icon: Flag, label: t("admin.nav.settings", "Feature Flags") },
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex">
      <aside
        className="w-64 bg-zinc-900 border-r border-zinc-800 fixed h-full flex flex-col justify-between z-40"
        aria-label="Navegação administrativa"
      >
        <div>
          <div className="p-6 border-b border-zinc-800">
            <Link to="/admin" className="flex items-center gap-2.5">
              <ShieldCheck className="text-pink-400" size={22} />
              <span className="text-lg font-bold tracking-tight">
                <span className="text-pink-400">{APP_NAME}</span>
                <span className="text-white ml-1.5 font-medium">Admin</span>
              </span>
            </Link>
          </div>

          <nav className="p-4 space-y-1.5">
            {menuItems.map((item) => {
              const active = item.exact
                ? location.pathname === item.path
                : location.pathname.startsWith(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition ${
                    active
                      ? "bg-pink-600/20 text-pink-400 border-l-4 border-pink-500"
                      : "text-zinc-400 hover:bg-zinc-800/80 hover:text-white"
                  }`}
                >
                  <item.icon size={18} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="p-4 border-t border-zinc-800 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-pink-600/20 text-pink-400 flex items-center justify-center font-bold text-sm">
              {(user.display_name || user.username || "A")[0].toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white truncate">
                {user.display_name || `@${user.username}`}
              </p>
              <p className="text-xs text-pink-400">Administrador</p>
            </div>
          </div>
          <Link
            to="/"
            className="flex items-center gap-2 text-zinc-400 hover:text-white text-sm transition"
          >
            <LogOut size={15} />
            <span>{t("admin.nav.backToSite", "Voltar ao Site")}</span>
          </Link>
        </div>
      </aside>

      <main className="flex-1 ml-64 p-8 min-w-0">
        {children || <Outlet />}
      </main>
    </div>
  );
}

export default AdminLayout;
