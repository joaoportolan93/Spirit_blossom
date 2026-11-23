import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  changePassword,
  getUserSettings,
  updateUserSettings,
  exportUserData,
  deleteAccount,
} from "../../services/api";
import { useAuth } from "../../hooks/useAuth";

// ---------------------------------------------------------------------------
// Modal de Exclusão de Conta (Zona de Perigo)
// ---------------------------------------------------------------------------
function DeleteAccountModal({ open, onClose, hasPassword, onConfirm, isDeleting, error }) {
  const { t } = useTranslation();
  const [confirmValue, setConfirmValue] = useState("");
  const firstInputRef = useRef(null);

  // Foco no primeiro campo ao abrir
  useEffect(() => {
    if (open) {
      setConfirmValue("");
      setTimeout(() => firstInputRef.current?.focus(), 50);
    }
  }, [open]);

  // Fecha com Escape
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Escape" && !isDeleting) onClose();
    },
    [onClose, isDeleting]
  );

  if (!open) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirm(confirmValue);
  };

  return (
    /* Overlay */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-modal-title"
      onKeyDown={handleKeyDown}
    >
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl max-w-md w-full mx-4 p-6 space-y-5">
        {/* Cabeçalho */}
        <div className="flex items-start gap-3">
          <span className="text-2xl mt-0.5">⚠️</span>
          <div>
            <h2
              id="delete-modal-title"
              className="text-base font-bold text-white"
            >
              {t("settings.delete_account_modal_title")}
            </h2>
            <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
              {t("settings.delete_account_modal_desc")}
            </p>
          </div>
        </div>

        {/* Formulário */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {hasPassword ? (
            <div>
              <label
                htmlFor="delete-confirm-password"
                className="block text-xs font-medium text-zinc-300 mb-1"
              >
                {t("settings.delete_confirm_password")}
              </label>
              <input
                id="delete-confirm-password"
                type="password"
                ref={firstInputRef}
                data-testid="delete-confirm-password-input"
                value={confirmValue}
                onChange={(e) => setConfirmValue(e.target.value)}
                required
                disabled={isDeleting}
                className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-white focus:outline-none focus:border-rose-600 disabled:opacity-50"
              />
            </div>
          ) : (
            <div>
              <label
                htmlFor="delete-confirm-username"
                className="block text-xs font-medium text-zinc-300 mb-1"
              >
                {t("settings.delete_confirm_username")}
              </label>
              <input
                id="delete-confirm-username"
                type="text"
                ref={firstInputRef}
                data-testid="delete-confirm-username-input"
                value={confirmValue}
                onChange={(e) => setConfirmValue(e.target.value)}
                placeholder={t("settings.delete_confirm_username_placeholder")}
                required
                disabled={isDeleting}
                autoComplete="off"
                className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-rose-600 disabled:opacity-50"
              />
            </div>
          )}

          {/* Erro */}
          {error && (
            <p
              role="alert"
              aria-live="polite"
              data-testid="delete-modal-error"
              className="text-xs text-rose-400"
            >
              {error}
            </p>
          )}

          {/* Botões */}
          <div className="flex gap-3 pt-1">
            <button
              type="button"
              data-testid="delete-modal-cancel-btn"
              onClick={onClose}
              disabled={isDeleting}
              className="flex-1 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg border border-zinc-700 transition"
            >
              {t("comments.cancel")}
            </button>
            <button
              type="submit"
              data-testid="delete-modal-confirm-btn"
              disabled={isDeleting || !confirmValue.trim()}
              className="flex-1 px-4 py-2 bg-rose-700 hover:bg-rose-600 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition"
            >
              {isDeleting
                ? t("settings.deleting_account")
                : t("settings.delete_account_modal_title")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------
export function SettingsAccount() {
  const { t } = useTranslation();
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();

  // ── Estados de perfil ──────────────────────────────────────────────────
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(null);
  const [removeAvatar, setRemoveAvatar] = useState(false);
  const [hasPassword, setHasPassword] = useState(true); // para OAuth

  const [loading, setLoading] = useState(true);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState("");
  const [profileError, setProfileError] = useState("");

  // ── Estados de troca de senha ──────────────────────────────────────────
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [passwordError, setPasswordError] = useState("");

  // ── Estados de exportação de dados ────────────────────────────────────
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");

  // ── Estados de exclusão de conta ──────────────────────────────────────
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const fileInputRef = useRef(null);

  // ── Carregamento inicial ───────────────────────────────────────────────
  useEffect(() => {
    let isMounted = true;

    async function loadAccountData() {
      try {
        const data = await getUserSettings();
        if (isMounted && data) {
          setUsername(data.username || user?.username || "");
          setDisplayName(data.display_name || user?.display_name || "");
          setBio(data.bio || "");
          setAvatarUrl(data.avatar || null);
        }
      } catch {
        if (isMounted) {
          setUsername(user?.username || "");
          setDisplayName(user?.display_name || "");
          setBio(user?.bio || "");
          setAvatarUrl(user?.avatar || null);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    // Detecta conta OAuth (sem senha utilizável)
    if (user && user.has_usable_password === false) {
      setHasPassword(false);
    }

    loadAccountData();
    return () => {
      isMounted = false;
    };
  }, [user]);

  // ── Avatar ─────────────────────────────────────────────────────────────
  const handleAvatarFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAvatarFile(file);
    setRemoveAvatar(false);
    setProfileError("");
    setAvatarPreview(URL.createObjectURL(file));
  };

  const handleRemoveAvatar = () => {
    setAvatarFile(null);
    setAvatarPreview(null);
    setAvatarUrl(null);
    setRemoveAvatar(true);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // ── Salvar Perfil ──────────────────────────────────────────────────────
  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setProfileSaving(true);
    setProfileSuccess("");
    setProfileError("");

    try {
      let dataToSend;
      if (avatarFile) {
        dataToSend = new FormData();
        dataToSend.append("username", username.trim());
        dataToSend.append("display_name", displayName.trim());
        dataToSend.append("bio", bio.trim());
        dataToSend.append("avatar", avatarFile);
      } else if (removeAvatar) {
        dataToSend = {
          username: username.trim(),
          display_name: displayName.trim(),
          bio: bio.trim(),
          remove_avatar: true,
        };
      } else {
        dataToSend = {
          username: username.trim(),
          display_name: displayName.trim(),
          bio: bio.trim(),
        };
      }

      const updated = await updateUserSettings(dataToSend);
      setUsername(updated.username);
      setDisplayName(updated.display_name || "");
      setBio(updated.bio || "");
      setAvatarUrl(updated.avatar);
      setAvatarFile(null);
      setAvatarPreview(null);
      setRemoveAvatar(false);

      if (setUser) {
        setUser((prev) => ({
          ...(prev || {}),
          username: updated.username,
          display_name: updated.display_name,
          bio: updated.bio,
          avatar: updated.avatar,
        }));
      }

      setProfileSuccess(t("settings.profile_updated"));
    } catch (err) {
      const detail =
        err.response?.data?.username?.[0] ||
        err.response?.data?.display_name?.[0] ||
        err.response?.data?.avatar?.[0] ||
        err.response?.data?.detail ||
        t("settings.profile_update_error");
      setProfileError(detail);
    } finally {
      setProfileSaving(false);
    }
  };

  // ── Trocar Senha ───────────────────────────────────────────────────────
  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPasswordSaving(true);
    setPasswordSuccess("");
    setPasswordError("");

    if (newPassword !== newPasswordConfirm) {
      setPasswordError(t("auth.passwords_mismatch"));
      setPasswordSaving(false);
      return;
    }

    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
      });
      setPasswordSuccess(t("settings.password_updated"));
      setCurrentPassword("");
      setNewPassword("");
      setNewPasswordConfirm("");
    } catch (err) {
      const detail =
        err.response?.data?.current_password?.[0] ||
        err.response?.data?.new_password?.[0] ||
        err.response?.data?.new_password_confirm?.[0] ||
        err.response?.data?.detail ||
        t("settings.password_update_error");
      setPasswordError(detail);
    } finally {
      setPasswordSaving(false);
    }
  };

  // ── Exportar Dados (LGPD) ──────────────────────────────────────────────
  const handleExportData = async () => {
    setExporting(true);
    setExportError("");

    try {
      const data = await exportUserData();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const dateStr = new Date().toISOString().slice(0, 10);
      a.download = `spirit-blossom-data-${dateStr}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      const status = err.response?.status;
      if (status === 429) {
        setExportError(t("settings.download_rate_limit"));
      } else {
        setExportError(t("settings.download_error"));
      }
    } finally {
      setExporting(false);
    }
  };

  // ── Excluir Conta ──────────────────────────────────────────────────────
  const handleDeleteConfirm = async (confirmValue) => {
    setDeleting(true);
    setDeleteError("");

    const payload = hasPassword
      ? { current_password: confirmValue }
      : { confirm_username: confirmValue };

    try {
      await deleteAccount(payload);
      setDeleteModalOpen(false);
      await logout();
      navigate("/login", { replace: true });
    } catch (err) {
      const detail =
        err.response?.data?.current_password?.[0] ||
        err.response?.data?.confirm_username?.[0] ||
        err.response?.data?.detail ||
        t("settings.delete_account_error");
      setDeleteError(detail);
    } finally {
      setDeleting(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="text-sm text-zinc-500 py-4">{t("common.loading")}</div>
    );
  }

  const currentDisplayAvatar = avatarPreview || avatarUrl;

  return (
    <div className="space-y-8">
      {/* ── Seção 1: Dados do Perfil ───────────────────────────────────── */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-1">
          {t("settings.profile_info")}
        </h2>
        <p className="text-xs text-zinc-400 mb-6">
          {t("settings.account_subtitle")}
        </p>

        <form onSubmit={handleSaveProfile} className="space-y-6">
          {/* Avatar */}
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-2">
              {t("settings.avatar")}
            </label>
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-full overflow-hidden bg-zinc-800 border border-zinc-700 flex items-center justify-center text-xl font-bold text-zinc-300 shrink-0">
                {currentDisplayAvatar ? (
                  <img
                    src={currentDisplayAvatar}
                    alt={displayName || username}
                    className="w-full h-full object-cover"
                    data-testid="avatar-preview-img"
                  />
                ) : (
                  <span>
                    {((displayName || username)[0] || "U").toUpperCase()}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                  onChange={handleAvatarFileChange}
                  className="hidden"
                  data-testid="avatar-upload-input"
                />
                <button
                  type="button"
                  data-testid="change-avatar-btn"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-200 border border-zinc-700 hover:bg-zinc-700 transition"
                >
                  {t("settings.change_avatar")}
                </button>

                {currentDisplayAvatar && (
                  <button
                    type="button"
                    data-testid="remove-avatar-btn"
                    onClick={handleRemoveAvatar}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-950/40 text-rose-300 border border-rose-800/60 hover:bg-rose-900/40 transition"
                  >
                    {t("settings.remove_avatar")}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Username */}
          <div>
            <label
              htmlFor="settings-username"
              className="block text-xs font-medium text-zinc-300 mb-1"
            >
              {t("settings.username")}
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-500 text-sm">
                @
              </span>
              <input
                id="settings-username"
                type="text"
                data-testid="username-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                maxLength={30}
                required
                className="w-full pl-8 pr-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-white focus:outline-none focus:border-zinc-600"
              />
            </div>
          </div>

          {/* Display name */}
          <div>
            <label
              htmlFor="settings-display-name"
              className="block text-xs font-medium text-zinc-300 mb-1"
            >
              {t("settings.display_name")}
            </label>
            <input
              id="settings-display-name"
              type="text"
              data-testid="display-name-input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={60}
              placeholder={t("settings.display_name_placeholder")}
              className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
            />
          </div>

          {/* Bio */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label
                htmlFor="settings-bio"
                className="block text-xs font-medium text-zinc-300"
              >
                {t("settings.bio")}
              </label>
              <span className="text-xs text-zinc-500">{bio.length}/160</span>
            </div>
            <textarea
              id="settings-bio"
              rows={3}
              data-testid="bio-input"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              maxLength={160}
              placeholder={t("settings.bio_placeholder")}
              className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-zinc-600 resize-none"
            />
          </div>

          {profileSuccess && (
            <p data-testid="profile-success" className="text-xs text-emerald-400">
              {profileSuccess}
            </p>
          )}
          {profileError && (
            <p data-testid="profile-error" className="text-xs text-rose-400">
              {profileError}
            </p>
          )}

          <button
            type="submit"
            data-testid="save-profile-btn"
            disabled={profileSaving}
            className="px-4 py-2 bg-pink-600 hover:bg-pink-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition"
          >
            {profileSaving
              ? t("settings.saving")
              : t("settings.save_profile")}
          </button>
        </form>
      </div>

      {/* ── Seção 2: Troca de Senha ────────────────────────────────────── */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-1">
          {t("settings.change_password")}
        </h2>
        <p className="text-xs text-zinc-400 mb-6">
          {t("auth.password_notice",
            "Altere sua senha informando a senha atual e a nova senha desejada.")}
        </p>

        <form onSubmit={handleChangePassword} className="space-y-4 max-w-md">
          <div>
            <label
              htmlFor="current-password"
              className="block text-xs font-medium text-zinc-300 mb-1"
            >
              {t("settings.current_password")}
            </label>
            <input
              id="current-password"
              type="password"
              data-testid="current-password-input"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-white focus:outline-none focus:border-zinc-600"
            />
          </div>

          <div>
            <label
              htmlFor="new-password"
              className="block text-xs font-medium text-zinc-300 mb-1"
            >
              {t("settings.new_password")}
            </label>
            <input
              id="new-password"
              type="password"
              data-testid="new-password-input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-white focus:outline-none focus:border-zinc-600"
            />
          </div>

          <div>
            <label
              htmlFor="new-password-confirm"
              className="block text-xs font-medium text-zinc-300 mb-1"
            >
              {t("settings.new_password_confirm")}
            </label>
            <input
              id="new-password-confirm"
              type="password"
              data-testid="new-password-confirm-input"
              value={newPasswordConfirm}
              onChange={(e) => setNewPasswordConfirm(e.target.value)}
              required
              minLength={8}
              className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-white focus:outline-none focus:border-zinc-600"
            />
          </div>

          {passwordSuccess && (
            <p data-testid="password-success" className="text-xs text-emerald-400">
              {passwordSuccess}
            </p>
          )}
          {passwordError && (
            <p data-testid="password-error" className="text-xs text-rose-400">
              {passwordError}
            </p>
          )}

          <button
            type="submit"
            data-testid="change-password-btn"
            disabled={passwordSaving}
            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg border border-zinc-700 transition"
          >
            {passwordSaving
              ? t("settings.updating_password")
              : t("settings.update_password")}
          </button>
        </form>
      </div>

      {/* ── Seção 3: Portabilidade de Dados (LGPD) ────────────────────── */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-1">
          {t("settings.data_portability")}
        </h2>
        <p className="text-xs text-zinc-400 mb-5">
          {t("settings.data_portability_desc")}
        </p>

        {exportError && (
          <p
            role="alert"
            aria-live="polite"
            data-testid="export-error"
            className="text-xs text-rose-400 mb-3"
          >
            {exportError}
          </p>
        )}

        <button
          type="button"
          data-testid="export-data-btn"
          onClick={handleExportData}
          disabled={exporting}
          className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg border border-zinc-700 transition flex items-center gap-2"
        >
          <span>📦</span>
          {exporting
            ? t("settings.downloading")
            : t("settings.download_my_data")}
        </button>
      </div>

      {/* ── Seção 4: Zona de Perigo ────────────────────────────────────── */}
      <div className="bg-zinc-900 border border-rose-900/60 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-rose-400 mb-1">
          ⚠️ {t("settings.danger_zone")}
        </h2>
        <p className="text-xs text-zinc-400 mb-5">
          {t("settings.danger_zone_desc")}
        </p>

        <button
          type="button"
          data-testid="open-delete-modal-btn"
          onClick={() => {
            setDeleteError("");
            setDeleteModalOpen(true);
          }}
          className="px-4 py-2 bg-rose-900/30 hover:bg-rose-900/50 text-rose-300 text-xs font-semibold rounded-lg border border-rose-800/60 transition"
        >
          {t("settings.delete_account")}
        </button>
      </div>

      {/* ── Modal de Exclusão ──────────────────────────────────────────── */}
      <DeleteAccountModal
        open={deleteModalOpen}
        onClose={() => !deleting && setDeleteModalOpen(false)}
        hasPassword={hasPassword}
        onConfirm={handleDeleteConfirm}
        isDeleting={deleting}
        error={deleteError}
      />
    </div>
  );
}

export default SettingsAccount;
