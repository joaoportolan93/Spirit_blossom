import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { getMutedUsers, unmuteUser, muteUser } from "../../services/api";

export function SettingsMuted() {
  const { t } = useTranslation();
  const [mutedUsers, setMutedUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [toast, setToast] = useState(null);
  const [error, setError] = useState("");

  const fetchMuted = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const items = await getMutedUsers();
      setMutedUsers(items);
    } catch {
      setError(t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchMuted();
  }, [fetchMuted]);

  const handleUnmute = async (user) => {
    setActionLoading((prev) => ({ ...prev, [user.username]: true }));
    setError("");
    try {
      await unmuteUser(user.username);
      setMutedUsers((prev) => prev.filter((u) => u.username !== user.username));
      setToast({
        message: t("settings.unmuted_success", `@${user.username} foi reativado.`, {
          username: user.username,
        }),
        user,
      });
    } catch {
      setError(t("errors.generic"));
    } finally {
      setActionLoading((prev) => ({ ...prev, [user.username]: false }));
    }
  };

  const handleUndo = async () => {
    if (!toast?.user) return;
    const target = toast.user;
    setActionLoading((prev) => ({ ...prev, [target.username]: true }));
    try {
      await muteUser(target.username);
      setMutedUsers((prev) => [target, ...prev]);
      setToast({
        message: t("settings.action_undone", "Ação desfeita."),
        user: null,
      });
    } catch {
      setError(t("errors.generic"));
    } finally {
      setActionLoading((prev) => ({ ...prev, [target.username]: false }));
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6" data-testid="settings-muted-container">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-white">
          {t("settings.muted_accounts", "Contas silenciadas")}
        </h2>
        <p className="text-sm text-zinc-400 mt-1">
          {t(
            "settings.muted_accounts_subtitle",
            "Posts e comentários de contas silenciadas não aparecem nos seus feeds e notificações."
          )}
        </p>
      </div>

      {toast && (
        <div className="mb-4 p-3 bg-violet-950/60 border border-violet-800/60 rounded-lg flex items-center justify-between text-sm text-violet-200">
          <span>{toast.message}</span>
          {toast.user && (
            <button
              type="button"
              onClick={handleUndo}
              className="text-xs font-semibold text-violet-300 hover:text-white underline ml-3"
              data-testid="undo-unmute-btn"
            >
              {t("settings.undo", "Desfazer")}
            </button>
          )}
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-rose-950/40 border border-rose-800/40 rounded-lg text-sm text-rose-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-zinc-500 py-6 text-center">
          {t("common.loading", "Carregando...")}
        </div>
      ) : mutedUsers.length === 0 ? (
        <div className="text-sm text-zinc-500 py-6 text-center" data-testid="empty-muted-list">
          {t("settings.no_muted_users", "Nenhuma conta silenciada.")}
        </div>
      ) : (
        <ul className="divide-y divide-zinc-800/60">
          {mutedUsers.map((u) => (
            <li key={u.id || u.username} className="py-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-300 font-semibold text-xs border border-zinc-700 overflow-hidden shrink-0">
                  {u.avatar ? (
                    <img src={u.avatar} alt={u.username} className="w-full h-full object-cover" />
                  ) : (
                    <span>{u.username[0]?.toUpperCase()}</span>
                  )}
                </div>
                <div className="min-w-0">
                  <div className="font-semibold text-sm text-zinc-200 truncate">@{u.username}</div>
                  {u.muted_at && (
                    <div className="text-xs text-zinc-500">
                      {new Date(u.muted_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleUnmute(u)}
                disabled={Boolean(actionLoading[u.username])}
                className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition shrink-0 disabled:opacity-50"
                data-testid={`unmute-btn-${u.username}`}
              >
                {actionLoading[u.username]
                  ? t("common.loading", "Carregando...")
                  : t("settings.unmute", "Reativar")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default SettingsMuted;

