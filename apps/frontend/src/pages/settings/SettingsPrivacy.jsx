import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, updateUserSettings } from "../../services/api";
import { useAuth } from "../../hooks/useAuth";

function Toggle({ id, checked, disabled, onChange, label, description, testId }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <label htmlFor={id} className="text-sm font-medium text-white block cursor-pointer">
          {label}
        </label>
        {description && (
          <p className="text-xs text-zinc-400 mt-0.5">{description}</p>
        )}
      </div>

      <label htmlFor={id} className="relative inline-flex items-center cursor-pointer shrink-0">
        <input
          id={id}
          type="checkbox"
          data-testid={testId}
          checked={checked}
          disabled={disabled}
          onChange={onChange}
          className="sr-only peer"
        />
        <div className="w-11 h-6 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-pink-600"></div>
      </label>
    </div>
  );
}

export function SettingsPrivacy() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [isPrivate, setIsPrivate] = useState(false);
  const [showLikesTab, setShowLikesTab] = useState(true);
  const [termsAcceptedAt, setTermsAcceptedAt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let isMounted = true;
    async function load() {
      if (!user?.username) return;
      try {
        const [profileRes, settingsRes] = await Promise.allSettled([
          api.get(`/api/social/profile/${user.username}/`),
          api.get("/api/users/settings/"),
        ]);
        if (isMounted) {
          if (profileRes.status === "fulfilled") {
            setIsPrivate(Boolean(profileRes.value.data.is_private));
          }
          if (settingsRes.status === "fulfilled") {
            setShowLikesTab(settingsRes.value.data.show_likes_tab !== false);
            setTermsAcceptedAt(settingsRes.value.data.terms_accepted_at || null);
          }
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    load();
    return () => { isMounted = false; };
  }, [user?.username]);

  const handlePrivateToggle = async (e) => {
    const next = e.target.checked;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const res = await api.patch("/api/users/profile/", { is_private: next });
      setIsPrivate(Boolean(res.data.is_private));
      setSuccess(t("profile.private_account_toggle_success"));
    } catch {
      setError(t("profile.private_account_toggle_error"));
    } finally {
      setSaving(false);
    }
  };

  const handleLikesTabToggle = async (e) => {
    const next = e.target.checked;
    const prev = showLikesTab;
    setShowLikesTab(next);
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await updateUserSettings({ show_likes_tab: next });
      setSuccess(t("settings.saved_success", "Salvo!"));
      setTimeout(() => setSuccess(""), 2000);
    } catch {
      setShowLikesTab(prev);
      setError(t("settings.error_saving", "Erro ao salvar."));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-sm text-zinc-500 py-4">Carregando...</div>;
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-6">
      <h2 className="text-lg font-semibold text-white">{t("settings.visibility")}</h2>

      {/* Conta Privada */}
      <div className="space-y-3">
        <Toggle
          id="private-account"
          testId="private-account-toggle"
          checked={isPrivate}
          disabled={saving}
          onChange={handlePrivateToggle}
          label={t("profile.private_account")}
          description={t("profile.private_account_help")}
        />
        {isPrivate && (
          <p className="text-xs text-amber-400">
            {t("settings.private_account_notice")}
          </p>
        )}
      </div>

      <div className="border-t border-zinc-800/60 pt-4">
        {/* Exibir aba de curtidas */}
        <Toggle
          id="show-likes-tab"
          testId="show-likes-tab-toggle"
          checked={showLikesTab}
          disabled={saving}
          onChange={handleLikesTabToggle}
          label={t("settings.show_likes_tab")}
          description={t("settings.show_likes_tab_desc")}
        />
      </div>

      {success && (
        <p data-testid="privacy-success" className="text-xs text-emerald-400">
          {success}
        </p>
      )}
      {error && (
        <p data-testid="privacy-error" className="text-xs text-rose-400">
          {error}
        </p>
      )}

      {/* Acesso rápido */}
      <div className="pt-4 border-t border-zinc-800">
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
          {t("settings.quick_links", "Acesso rápido")}
        </h3>
        <nav className="space-y-2">
          <Link
            to="/notifications?tab=requests"
            className="flex items-center justify-between py-2 px-3 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition"
          >
            <span>{t("settings.follow_requests", "Solicitações de seguir")}</span>
            <span className="text-zinc-600">›</span>
          </Link>
          <Link
            to="/settings/circle"
            className="flex items-center justify-between py-2 px-3 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition"
          >
            <span>{t("settings.circle", "Círculo de amigos")}</span>
            <span className="text-zinc-600">›</span>
          </Link>
          <Link
            to="/settings/blocked"
            className="flex items-center justify-between py-2 px-3 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition"
          >
            <span>{t("settings.blocked_accounts", "Contas bloqueadas")}</span>
            <span className="text-zinc-600">›</span>
          </Link>
          <Link
            to="/settings/muted"
            className="flex items-center justify-between py-2 px-3 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition"
          >
            <span>{t("settings.muted_accounts", "Contas silenciadas")}</span>
            <span className="text-zinc-600">›</span>
          </Link>
        </nav>
      </div>

      {/* Documentos Legais e Aceite (Onda 7b) */}
      <div className="pt-4 border-t border-zinc-800 space-y-2">
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
          {t("legal.settings_title")}
        </h3>
        <p className="text-xs text-zinc-400">{t("legal.settings_desc")}</p>
        <p data-testid="terms-accepted-status" className="text-xs text-zinc-300">
          {termsAcceptedAt
            ? t("legal.accepted_at", {
                date: new Date(termsAcceptedAt).toLocaleDateString(),
              })
            : t("legal.accepted_registered")}
        </p>
        <div className="flex items-center gap-4 pt-1 text-xs">
          <Link to="/terms" className="text-pink-400 hover:underline">
            {t("legal.terms_link")}
          </Link>
          <Link to="/privacy" className="text-pink-400 hover:underline">
            {t("legal.privacy_link")}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default SettingsPrivacy;
