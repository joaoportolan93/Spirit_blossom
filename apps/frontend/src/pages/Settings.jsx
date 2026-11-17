import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function Settings() {
  const { t } = useTranslation();

  const navItems = [
    { to: "/settings/account", label: t("settings.account") },
    { to: "/settings/notifications", label: t("settings.notifications") },
    { to: "/settings/privacy", label: t("settings.visibility") },
    { to: "/settings/appearance", label: t("settings.appearance") },
  ];

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <h1 role="heading" className="text-2xl font-bold text-white mb-6">
        {t("settings.title")}
      </h1>

      <div className="flex flex-col md:flex-row gap-8">
        {/* Menu lateral de abas */}
        <nav
          aria-label="Configurações"
          className="w-full md:w-64 flex flex-row md:flex-col gap-2 border-b md:border-b-0 md:border-r border-zinc-800 pb-4 md:pb-0 md:pr-4"
        >
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm font-medium transition ${
                  isActive
                    ? "bg-zinc-800 text-white"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Conteúdo da aba */}
        <section className="flex-1">
          <Outlet />
        </section>
      </div>
    </div>
  );
}

export default Settings;
