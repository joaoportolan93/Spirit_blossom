import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../services/api";
import { useAuth } from "../../hooks/useAuth";

export function SettingsPrivacy() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [isPrivate, setIsPrivate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadPrivacyState() {
      if (!user?.username) return;
      try {
        const res = await api.get(`/api/social/profile/${user.username}/`);
        if (isMounted) {
          setIsPrivate(Boolean(res.data.is_private));
        }
      } catch {
        // Ignora falha inicial
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadPrivacyState();
    return () => {
      isMounted = false;
    };
  }, [user?.username]);

  const handleToggle = async (e) => {
    const nextState = e.target.checked;
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const res = await api.patch("/api/users/profile/", { is_private: nextState });
      setIsPrivate(Boolean(res.data.is_private));
      setSuccess(t("profile.private_account_toggle_success"));
    } catch {
      setError(t("profile.private_account_toggle_error"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-sm text-zinc-500">Carregando...</div>;
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-4">
        {t("settings.privacy")}
      </h2>

      <label className="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          data-testid="private-account-toggle"
          checked={isPrivate}
          disabled={saving}
          onChange={handleToggle}
          className="mt-1 w-4 h-4 rounded bg-zinc-800 border-zinc-700 text-indigo-600 focus:ring-0 cursor-pointer"
        />
        <div>
          <span className="text-sm font-medium text-white block">
            {t("profile.private_account")}
          </span>
          <p className="text-xs text-zinc-400 mt-0.5">
            {t("profile.private_account_help")}
          </p>
        </div>
      </label>

      {success && (
        <p data-testid="privacy-success" className="text-xs text-emerald-400 mt-4">
          {success}
        </p>
      )}

      {error && (
        <p data-testid="privacy-error" className="text-xs text-rose-400 mt-4">
          {error}
        </p>
      )}
    </div>
  );
}

export default SettingsPrivacy;

