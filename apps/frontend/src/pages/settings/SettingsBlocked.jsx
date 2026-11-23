import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { getBlockedUsers, unblockUser, blockUser } from "../../services/api";

export function SettingsBlocked() {
  const { t } = useTranslation();
  const [blockedUsers, setBlockedUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [toast, setToast] = useState(null); // { message, lastUnblockedUser }
  const [error, setError] = useState("");

  const fetchBlocked = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const items = await getBlockedUsers();
      setBlockedUsers(items);
    } catch {
      setError(t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchBlocked();
  }, [fetchBlocked]);

  const handleUnblock = async (user) => {
    setActionLoading((prev) => ({ ...prev, [user.username]: true }));
    setError("");
    try {
      await unblockUser(user.username);
      setBlockedUsers((prev) => prev.filter((u) => u.username !== user.username));
      setToast({
        message: t("settings.unblocked_success", `@${user.username} foi desbloqueado.`, {
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
      await blockUser(target.username);
      setBlockedUsers((prev) => [target, ...prev]);
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
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6" data-testid="settings-blocked-container">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-white">
          {t("settings.blocked_accounts", "Contas bloqueadas")}
        </h2>
        <p className="text-sm text-zinc-400 mt-1">
          {t(
            "settings.blocked_accounts_subtitle",
            "Usuários bloqueados não podem ver seus posts, perfil ou interagir com você."
          )}
        </p>
      </div>

      {toast && (
        <div className="mb-4 p-3 bg-pink-950/60 border border-pink-800/60 rounded-lg flex items-center justify-between text-sm text-pink-200">
          <span>{toast.message}</span>
          {toast.user && (
            <button
              type="button"
              onClick={handleUndo}
              className="text-xs font-semibold text-pink-300 hover:text-white underline ml-3"
              data-testid="undo-unblock-btn"
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
      ) : blockedUsers.length === 0 ? (
        <div className="text-sm text-zinc-500 py-6 text-center" data-testid="empty-blocked-list">
          {t("settings.no_blocked_users", "Nenhuma conta bloqueada.")}
        </div>
      ) : (
        <ul className="divide-y divide-zinc-800/60">
          {blockedUsers.map((u) => (
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
                  {u.blocked_at && (
                    <div className="text-xs text-zinc-500">
                      {new Date(u.blocked_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleUnblock(u)}
                disabled={Boolean(actionLoading[u.username])}
                className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition shrink-0 disabled:opacity-50"
                data-testid={`unblock-btn-${u.username}`}
              >
                {actionLoading[u.username]
                  ? t("common.loading", "Carregando...")
                  : t("settings.unblock", "Desbloquear")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default SettingsBlocked;

