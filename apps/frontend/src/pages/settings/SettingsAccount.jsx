import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { changePassword, getUserSettings, updateUserSettings } from "../../services/api";
import { useAuth } from "../../hooks/useAuth";

export function SettingsAccount() {
  const { t } = useTranslation();
  const { user, setUser } = useAuth();

  // Estados de perfil
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(null);
  const [removeAvatar, setRemoveAvatar] = useState(false);

  const [loading, setLoading] = useState(true);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState("");
  const [profileError, setProfileError] = useState("");

  // Estados de troca de senha
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [passwordError, setPasswordError] = useState("");

  const fileInputRef = useRef(null);

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

    loadAccountData();
    return () => {
      isMounted = false;
    };
  }, [user]);

  const handleAvatarFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAvatarFile(file);
    setRemoveAvatar(false);
    setProfileError("");

    const preview = URL.createObjectURL(file);
    setAvatarPreview(preview);
  };

  const handleRemoveAvatar = () => {
    setAvatarFile(null);
    setAvatarPreview(null);
    setAvatarUrl(null);
    setRemoveAvatar(true);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

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

      setProfileSuccess(t("settings.profile_updated", "Perfil atualizado com sucesso."));
    } catch (err) {
      const detail =
        err.response?.data?.username?.[0] ||
        err.response?.data?.display_name?.[0] ||
        err.response?.data?.avatar?.[0] ||
        err.response?.data?.detail ||
        t("settings.profile_update_error", "Erro ao atualizar perfil.");
      setProfileError(detail);
    } finally {
      setProfileSaving(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPasswordSaving(true);
    setPasswordSuccess("");
    setPasswordError("");

    if (newPassword !== newPasswordConfirm) {
      setPasswordError(t("auth.passwords_mismatch", "As senhas não coincidem."));
      setPasswordSaving(false);
      return;
    }

    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
      });

      setPasswordSuccess(t("settings.password_updated", "Senha alterada com sucesso."));
      setCurrentPassword("");
      setNewPassword("");
      setNewPasswordConfirm("");
    } catch (err) {
      const detail =
        err.response?.data?.current_password?.[0] ||
        err.response?.data?.new_password?.[0] ||
        err.response?.data?.new_password_confirm?.[0] ||
        err.response?.data?.detail ||
        t("settings.password_update_error", "Erro ao alterar senha. Verifique os dados digitados.");
      setPasswordError(detail);
    } finally {
      setPasswordSaving(false);
    }
  };

  if (loading) {
    return <div className="text-sm text-zinc-500 py-4">{t("common.loading", "Carregando...")}</div>;
  }

  const currentDisplayAvatar = avatarPreview || avatarUrl;

  return (
    <div className="space-y-8">
      {/* Seção 1: Dados do Perfil */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-1">
          {t("settings.profile_info", "Informações do Perfil")}
        </h2>
        <p className="text-xs text-zinc-400 mb-6">
          {t("settings.account_subtitle", "Gerencie seus dados de perfil e senha de acesso.")}
        </p>

        <form onSubmit={handleSaveProfile} className="space-y-6">
          {/* Avatar com upload e remoção */}
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-2">
              {t("settings.avatar", "Foto de perfil")}
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
                  <span>{((displayName || username)[0] || "U").toUpperCase()}</span>
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
                  {t("settings.change_avatar", "Alterar foto")}
                </button>

                {currentDisplayAvatar && (
                  <button
                    type="button"
                    data-testid="remove-avatar-btn"
                    onClick={handleRemoveAvatar}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-950/40 text-rose-300 border border-rose-800/60 hover:bg-rose-900/40 transition"
                  >
                    {t("settings.remove_avatar", "Remover foto")}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Campo 1: Nome de usuário (@) */}
          <div>
            <label htmlFor="settings-username" className="block text-xs font-medium text-zinc-300 mb-1">
              {t("settings.username", "Nome de usuário")}
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

          {/* Campo 2: Nome completo / Apelido */}
          <div>
            <label htmlFor="settings-display-name" className="block text-xs font-medium text-zinc-300 mb-1">
              {t("settings.display_name", "Nome completo")}
            </label>
            <input
              id="settings-display-name"
              type="text"
              data-testid="display-name-input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={60}
              placeholder={t("settings.display_name_placeholder", "Seu nome ou apelido...")}
              className="w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
            />
          </div>

          {/* Campo 3: Biografia */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="settings-bio" className="block text-xs font-medium text-zinc-300">
                {t("settings.bio", "Biografia")}
              </label>
              <span className="text-xs text-zinc-500">
                {bio.length}/160
              </span>
            </div>
            <textarea
              id="settings-bio"
              rows={3}
              data-testid="bio-input"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              maxLength={160}
              placeholder={t("settings.bio_placeholder", "Escreva uma breve biografia...")}
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
            {profileSaving ? t("settings.saving", "Salvando...") : t("settings.save_profile", "Salvar alterações")}
          </button>
        </form>
      </div>

      {/* Seção 2: Troca de Senha */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-1">
          {t("settings.change_password", "Alterar Senha")}
        </h2>
        <p className="text-xs text-zinc-400 mb-6">
          {t("auth.password_notice", "Altere sua senha informando a senha atual e a nova senha desejada.")}
        </p>

        <form onSubmit={handleChangePassword} className="space-y-4 max-w-md">
          <div>
            <label htmlFor="current-password" className="block text-xs font-medium text-zinc-300 mb-1">
              {t("settings.current_password", "Senha atual")}
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
            <label htmlFor="new-password" className="block text-xs font-medium text-zinc-300 mb-1">
              {t("settings.new_password", "Nova senha")}
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
            <label htmlFor="new-password-confirm" className="block text-xs font-medium text-zinc-300 mb-1">
              {t("settings.new_password_confirm", "Confirmar nova senha")}
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
            {passwordSaving ? t("settings.updating_password", "Atualizando senha...") : t("settings.update_password", "Atualizar senha")}
          </button>
        </form>
      </div>
    </div>
  );
}

export default SettingsAccount;
