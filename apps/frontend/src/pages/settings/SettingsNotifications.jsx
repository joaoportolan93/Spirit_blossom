import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { getUserSettings, updateUserSettings } from "../../services/api";
import { useFeatureFlags } from "../../hooks/useFeatureFlags";
import { usePushNotifications } from "../../hooks/usePushNotifications";

export function SettingsNotifications() {
  const { t } = useTranslation();
  const { isEnabled } = useFeatureFlags();
  const pushEnabled = isEnabled("push_notifications");

  const {
    permission,
    isSupported,
    isRegistered,
    loading: pushLoading,
    requestAndRegister,
    unregister,
  } = usePushNotifications({ enabled: pushEnabled });

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
    return () => { isMounted = false; };
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
      setSuccess(t("settings.notifications_updated"));
    } catch {
      setSettings(prevSettings);
      setError(t("settings.notifications_update_error"));
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return <div className="text-sm text-zinc-500 py-4">{t("common.loading")}</div>;
  }

  const items = [
    {
      key: "notify_likes",
      label: t("settings.notify_likes"),
      desc: t("settings.notify_likes_desc"),
      testId: "notify-likes-toggle",
    },
    {
      key: "notify_comments",
      label: t("settings.notify_comments"),
      desc: t("settings.notify_comments_desc"),
      testId: "notify-comments-toggle",
    },
    {
      key: "notify_follows",
      label: t("settings.notify_follows"),
      desc: t("settings.notify_follows_desc"),
      testId: "notify-follows-toggle",
    },
    {
      key: "notify_mentions",
      label: t("settings.notify_mentions"),
      desc: t("settings.notify_mentions_desc"),
      testId: "notify-mentions-toggle",
    },
  ];

  function PushPermissionBadge() {
    if (!isSupported) {
      return (
        <span className="text-xs text-zinc-500 px-2 py-0.5 bg-zinc-800 rounded-full">
          {t("settings.push_unsupported")}
        </span>
      );
    }
    if (permission === "granted") {
      return (
        <span className="text-xs text-emerald-400 px-2 py-0.5 bg-emerald-900/30 rounded-full">
          {t("settings.push_granted")}
        </span>
      );
    }
    if (permission === "denied") {
      return (
        <span className="text-xs text-rose-400 px-2 py-0.5 bg-rose-900/30 rounded-full">
          {t("settings.push_denied")}
        </span>
      );
    }
    return (
      <span className="text-xs text-zinc-400 px-2 py-0.5 bg-zinc-800 rounded-full">
        {t("settings.push_default")}
      </span>
    );
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-1">
        {t("settings.notifications")}
      </h2>
      <p className="text-xs text-zinc-400 mb-6">{t("settings.notifications_subtitle")}</p>

      {/* Controle de Push Browser */}
      {pushEnabled && (
        <div className="mb-6 p-4 bg-zinc-800/40 border border-zinc-700 rounded-xl">
          <div className="flex items-center justify-between gap-4 mb-2">
            <div>
              <span className="text-sm font-medium text-white block">
                {t("settings.push_browser")}
              </span>
              <p className="text-xs text-zinc-400 mt-0.5">
                {t("settings.push_browser_desc")}
              </p>
            </div>
            <PushPermissionBadge />
          </div>

          {isSupported && permission !== "denied" && (
            <div className="flex gap-2 mt-3">
              {!isRegistered && permission !== "granted" && (
                <button
                  type="button"
                  data-testid="enable-push-btn"
                  onClick={requestAndRegister}
                  disabled={pushLoading}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white text-zinc-900 hover:bg-zinc-200 transition disabled:opacity-50"
                >
                  {pushLoading ? t("common.loading") : t("settings.push_enable")}
                </button>
              )}
              {isRegistered && (
                <button
                  type="button"
                  data-testid="disable-push-btn"
                  onClick={unregister}
                  disabled={pushLoading}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-zinc-700 text-zinc-200 hover:bg-zinc-600 transition disabled:opacity-50"
                >
                  {pushLoading ? t("common.loading") : t("settings.push_disable")}
                </button>
              )}
            </div>
          )}

          {isSupported && permission === "denied" && (
            <p className="text-xs text-zinc-500 mt-2">{t("settings.push_denied_help")}</p>
          )}
        </div>
      )}

      {/* Toggles de notificações in-app */}
      <div className="space-y-6 divide-y divide-zinc-800/60">
        {items.map((item, idx) => (
          <div
            key={item.key}
            className={
              idx > 0
                ? "pt-5 flex items-center justify-between gap-4"
                : "flex items-center justify-between gap-4"
            }
          >
            <div>
              <span className="text-sm font-medium text-white block">{item.label}</span>
              <p className="text-xs text-zinc-400 mt-0.5">{item.desc}</p>
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
              <div className="w-11 h-6 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-pink-600" />
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
