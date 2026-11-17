import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { getUserSettings, updateUserSettings } from "../../services/api";

export function SettingsNotifications() {
  const { t } = useTranslation();

  const [settings, setSettings] = useState({
    notify_likes: true,
    notify_comments: true,
    notify_follows: true,
    notify_mentions: true,
  });

  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState(null);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadSettings() {
      try {
        const data = await getUserSettings();
        if (isMounted && data) {
          setSettings({
            notify_likes: data.notify_likes ?? true,
            notify_comments: data.notify_comments ?? true,
            notify_follows: data.notify_follows ?? true,
            notify_mentions: data.notify_mentions ?? true,
          });
        }
      } catch {
        // Usa valores padrão
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadSettings();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleToggle = async (key) => {
    const nextValue = !settings[key];
    const prevSettings = { ...settings };

    setSettings((prev) => ({ ...prev, [key]: nextValue }));
    setSavingKey(key);
    setError("");
    setSuccess("");

    try {
      await updateUserSettings({ [key]: nextValue });
      setSuccess(t("settings.notifications_updated", "Preferências de notificação salvas."));
    } catch {
      setSettings(prevSettings);
      setError(
        t("settings.notifications_update_error", "Erro ao atualizar preferências de notificação.")
      );
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return <div className="text-sm text-zinc-500 py-4">{t("common.loading", "Carregando...")}</div>;
  }

  const items = [
    {
      key: "notify_likes",
      label: t("settings.notify_likes", "Curtidas"),
      desc: t(
        "settings.notify_likes_desc",
        "Receber notificações quando alguém curtir suas publicações ou comentários."
      ),
      testId: "notify-likes-toggle",
    },
    {
      key: "notify_comments",
      label: t("settings.notify_comments", "Comentários e Respostas"),
      desc: t(
        "settings.notify_comments_desc",
        "Receber notificações quando alguém comentar ou responder suas publicações."
      ),
      testId: "notify-comments-toggle",
    },
    {
      key: "notify_follows",
      label: t("settings.notify_follows", "Novos Seguidores"),
      desc: t(
        "settings.notify_follows_desc",
        "Receber notificações sobre novos seguidores ou solicitações para seguir."
      ),
      testId: "notify-follows-toggle",
    },
    {
      key: "notify_mentions",
      label: t("settings.notify_mentions", "Menções"),
      desc: t(
        "settings.notify_mentions_desc",
        "Receber notificações quando você for mencionado em postagens ou comentários."
      ),
      testId: "notify-mentions-toggle",
    },
  ];

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-1">
        {t("settings.notifications", "Notificações")}
      </h2>
      <p className="text-xs text-zinc-400 mb-6">
        {t(
          "settings.notifications_subtitle",
          "Escolha quais eventos geram notificações para você."
        )}
      </p>

      <div className="space-y-6 divide-y divide-zinc-800/60">
        {items.map((item, idx) => (
          <div key={item.key} className={idx > 0 ? "pt-5 flex items-center justify-between gap-4" : "flex items-center justify-between gap-4"}>
            <div>
              <span className="text-sm font-medium text-white block">
                {item.label}
              </span>
              <p className="text-xs text-zinc-400 mt-0.5">
                {item.desc}
              </p>
            </div>

            <label className="relative inline-flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                data-testid={item.testId}
                checked={settings[item.key]}
                disabled={savingKey === item.key}
                onChange={() => handleToggle(item.key)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-pink-600"></div>
            </label>
          </div>
        ))}
      </div>

      {success && (
        <p data-testid="notifications-success" className="text-xs text-emerald-400 mt-6">
          {success}
        </p>
      )}

      {error && (
        <p data-testid="notifications-error" className="text-xs text-rose-400 mt-6">
          {error}
        </p>
      )}
    </div>
  );
}

export default SettingsNotifications;
