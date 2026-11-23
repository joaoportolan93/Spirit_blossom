import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { updateUserSettings } from "../../services/api";
import { applyTheme } from "../../utils/theme";
import { useAuth } from "../../hooks/useAuth";

const THEMES = [
  { key: "light", labelKey: "settings.theme_light" },
  { key: "dark", labelKey: "settings.theme_dark" },
  { key: "oled", labelKey: "settings.theme_oled" },
];

const LANGUAGES = [
  { key: "pt-BR", labelKey: "settings.lang_pt" },
  { key: "en", labelKey: "settings.lang_en" },
];

export function SettingsAppearance() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();

  const [theme, setTheme] = useState(
    () => localStorage.getItem("spirit_theme") || user?.theme || "dark"
  );
  const [language, setLanguage] = useState(
    () => localStorage.getItem("spirit_language") || user?.language || "pt-BR"
  );
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?.theme) setTheme(user.theme);
    if (user?.language) setLanguage(user.language);
  }, [user?.theme, user?.language]);

  const handleTheme = async (newTheme) => {
    setTheme(newTheme);
    applyTheme(newTheme);
    localStorage.setItem("spirit_theme", newTheme);
    setSaving(true);
    setSuccess("");
    try {
      await updateUserSettings({ theme: newTheme });
      setSuccess(t("settings.saved_success", "Salvo!"));
      setTimeout(() => setSuccess(""), 2000);
    } catch {
      // silently ignore
    } finally {
      setSaving(false);
    }
  };

  const handleLanguage = async (newLang) => {
    setLanguage(newLang);
    i18n.changeLanguage(newLang);
    localStorage.setItem("spirit_language", newLang);
    setSaving(true);
    setSuccess("");
    try {
      await updateUserSettings({ language: newLang });
      setSuccess(t("settings.saved_success", "Salvo!"));
      setTimeout(() => setSuccess(""), 2000);
    } catch {
      // silently ignore
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-8">
      <h2 className="text-lg font-semibold text-white">{t("settings.appearance")}</h2>

      {/* Tema */}
      <section>
        <h3 className="text-sm font-medium text-zinc-300 mb-3">{t("settings.theme")}</h3>
        <div className="flex gap-3 flex-wrap">
          {THEMES.map(({ key, labelKey }) => (
            <button
              key={key}
              type="button"
              data-testid={`theme-${key}-btn`}
              onClick={() => handleTheme(key)}
              disabled={saving}
              className={`flex-1 min-w-[90px] py-6 rounded-xl border-2 font-medium text-sm transition focus:outline-none
                ${
                  theme === key
                    ? "border-indigo-500 ring-2 ring-indigo-500/40"
                    : "border-zinc-700 hover:border-zinc-500"
                }
                ${key === "light" ? "bg-white text-zinc-900" : key === "oled" ? "bg-black text-white" : "bg-zinc-900 text-white"}
              `}
            >
              {t(labelKey)}
            </button>
          ))}
        </div>
      </section>

      {/* Idioma */}
      <section>
        <h3 className="text-sm font-medium text-zinc-300 mb-3">{t("settings.language")}</h3>
        <div className="flex gap-3">
          {LANGUAGES.map(({ key, labelKey }) => (
            <button
              key={key}
              type="button"
              data-testid={`lang-${key === "pt-BR" ? "pt" : "en"}-btn`}
              onClick={() => handleLanguage(key)}
              disabled={saving}
              className={`flex-1 py-3 rounded-xl border-2 font-medium text-sm transition focus:outline-none
                ${
                  language === key
                    ? "border-indigo-500 bg-indigo-500/10 text-white ring-2 ring-indigo-500/40"
                    : "border-zinc-700 text-zinc-300 hover:border-zinc-500"
                }
              `}
            >
              {t(labelKey)}
            </button>
          ))}
        </div>
      </section>

      {success && (
        <p data-testid="appearance-success" className="text-xs text-emerald-400">
          {success}
        </p>
      )}
    </div>
  );
}

export default SettingsAppearance;
