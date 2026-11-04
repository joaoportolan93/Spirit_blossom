import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "../config/brand";
import { useAuth } from "../hooks/useAuth";
import { NotificationBell } from "./NotificationBell";

export function Navbar() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <nav className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur sticky top-0 z-50 px-4 py-3">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        <Link to="/" className="text-xl font-bold tracking-tight text-white hover:text-zinc-200">
          {APP_NAME}
        </Link>

        <div className="flex items-center gap-4">
          {user ? (
            <>
              <Link to="/" className="text-sm text-zinc-300 hover:text-white">
                {t("nav.feed")}
              </Link>
              <Link to="/profile" className="text-sm text-zinc-300 hover:text-white">
                {t("nav.profile")}
              </Link>
              <NotificationBell />
              <button
                onClick={handleLogout}
                className="text-sm bg-zinc-800 hover:bg-zinc-700 text-zinc-200 px-3 py-1.5 rounded transition"
              >
                {t("auth.logout")}
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="text-sm text-zinc-300 hover:text-white px-3 py-1.5 rounded"
              >
                {t("auth.login")}
              </Link>
              <Link
                to="/register"
                className="text-sm bg-white text-zinc-950 font-medium px-3 py-1.5 rounded hover:bg-zinc-200 transition"
              >
                {t("auth.register")}
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
