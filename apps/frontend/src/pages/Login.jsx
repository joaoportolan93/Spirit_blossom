import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Ban, ArrowLeft } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";
import { APP_NAME, MODERATION_EMAIL } from "../config/brand";

function extractBannedInfo(err, fallbackEmail) {
  const data = err?.response?.data;
  if (!data?.banned) {
    return null;
  }
  return {
    reason: data.ban_reason || "",
    appealEmail: data.appeal_email || MODERATION_EMAIL,
    appealDaysRemaining: data.appeal_days_remaining ?? null,
    banExpiresAt: data.ban_expires_at || null,
    accountEmail: fallbackEmail || "",
  };
}

export function Login() {
  const { t, i18n } = useTranslation();
  const { login, setUser } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [bannedInfo, setBannedInfo] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage(t("errors.required_field"));
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");
    setBannedInfo(null);

    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      const banData = extractBannedInfo(err, email);
      if (banData) {
        setBannedInfo(banData);
      } else if (err.response?.status === 429) {
        setErrorMessage(t("auth.throttle_error"));
      } else {
        const detail =
          err.response?.data?.detail ||
          err.response?.data?.non_field_errors?.[0] ||
          t("errors.generic");
        setErrorMessage(detail);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleLogin = async (googleIdToken) => {
    setIsSubmitting(true);
    setErrorMessage("");
    setBannedInfo(null);

    try {
      // Se não passado token diretamente, solicita via prompt para facilitar testes manuais em dev
      const idToken =
        googleIdToken ||
        window.__GOOGLE_TEST_TOKEN__ ||
        prompt("Cole seu Google ID Token para autenticar:") ||
        "";

      if (!idToken) {
        setIsSubmitting(false);
        return;
      }

      const res = await api.post("/api/auth/google/", { id_token: idToken });
      if (res.data.status === "needs_signup") {
        navigate("/complete-signup", {
          state: {
            onboarding_token: res.data.onboarding_token,
            email: res.data.email,
          },
        });
      } else {
        setUser({ is_authenticated: true });
        navigate("/");
      }
    } catch (err) {
      const banData = extractBannedInfo(err);
      if (banData) {
        setBannedInfo(banData);
      } else {
        const detail =
          err.response?.data?.detail ||
          "Falha na autenticação com Google. Tente novamente.";
        setErrorMessage(detail);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (bannedInfo) {
    const appealEmail = bannedInfo.appealEmail;
    const displayReason = bannedInfo.reason || t("auth.banned_reason_fallback");
    const mailSubject = encodeURIComponent(`Revisão de suspensão - ${APP_NAME}`);
    const mailBody = encodeURIComponent(
      `Olá equipe de moderação (${APP_NAME}),\n\n` +
        (bannedInfo.accountEmail ? `Conta: ${bannedInfo.accountEmail}\n` : "") +
        `Motivo exibido: ${displayReason}\n\n` +
        `O que aconteceu:\n`
    );
    const mailtoHref = `mailto:${appealEmail}?subject=${mailSubject}&body=${mailBody}`;

    return (
      <div className="max-w-lg mx-auto mt-12 p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-lg">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-white mb-1">{APP_NAME}</h1>
          <p className="text-xs text-zinc-400">{t("app.tagline")}</p>
        </div>

        <div
          data-testid="banned-account-card"
          className="p-6 rounded-xl bg-rose-950/35 border border-rose-800/60 space-y-4"
        >
          <div className="flex items-center gap-2.5 text-rose-400 font-semibold text-base">
            <Ban className="w-5 h-5 shrink-0" />
            <span>{t("auth.banned_title")}</span>
          </div>

          <p className="text-sm text-zinc-300">{t("auth.banned_subtitle")}</p>

          <div className="p-4 min-h-[96px] rounded-lg bg-zinc-950/85 border border-zinc-800 space-y-1.5">
            <p className="text-[11px] uppercase tracking-wider text-zinc-400 font-medium">
              {t("auth.banned_reason_label")}
            </p>
            <p
              data-testid="banned-reason-text"
              className="text-base text-zinc-100 leading-relaxed whitespace-pre-wrap break-words"
            >
              {displayReason}
            </p>
          </div>

          {(bannedInfo.banExpiresAt || bannedInfo.appealDaysRemaining !== null) && (
            <div className="text-xs text-zinc-400 pt-1">
              {bannedInfo.banExpiresAt ? (
                <p>
                  {t("auth.banned_expires_label")}:{" "}
                  <strong className="text-zinc-200">
                    {new Date(bannedInfo.banExpiresAt).toLocaleString(i18n.language)}
                  </strong>
                </p>
              ) : (
                <p>
                  {t("auth.banned_appeal_days", {
                    count: bannedInfo.appealDaysRemaining,
                  })}
                </p>
              )}
            </div>
          )}
        </div>

        <div className="mt-4 text-center">
          <a
            href={mailtoHref}
            data-testid="banned-appeal-link"
            title={appealEmail}
            className="text-[11px] text-zinc-400 hover:text-zinc-200 hover:underline transition"
          >
            {t("auth.banned_appeal_link_text")} ({appealEmail})
          </a>
        </div>

        <div className="mt-4 pt-3 border-t border-zinc-800/60 flex justify-center">
          <button
            type="button"
            data-testid="banned-back-button"
            onClick={() => setBannedInfo(null)}
            className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>{t("auth.banned_back_to_login")}</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto mt-12 p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-lg">
      <div className="text-center mb-6">
        <h1 className="text-2xl font-bold text-white mb-1">{APP_NAME}</h1>
        <p className="text-xs text-zinc-400">{t("app.tagline")}</p>
      </div>

      <form onSubmit={handleSubmit} data-testid="login-form" className="space-y-4">
        {errorMessage && (
          <div
            data-testid="login-error"
            className="p-3 bg-rose-950/50 border border-rose-800/80 rounded-lg text-xs text-rose-300"
          >
            {errorMessage}
          </div>
        )}

        <div>
          <label
            htmlFor="login-email"
            className="block text-xs font-medium text-zinc-300 mb-1"
          >
            {t("auth.email")}
          </label>
          <input
            id="login-email"
            type="email"
            data-testid="email-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            required
          />
        </div>

        <div>
          <div className="flex justify-between items-center mb-1">
            <label
              htmlFor="login-password"
              className="block text-xs font-medium text-zinc-300"
            >
              {t("auth.password")}
            </label>
            <Link
              to="/forgot-password"
              data-testid="forgot-password-link"
              className="text-xs text-zinc-400 hover:text-zinc-200 transition"
            >
              Esqueci a senha
            </Link>
          </div>
          <input
            id="login-password"
            type="password"
            data-testid="password-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            required
          />
        </div>

        <button
          type="submit"
          data-testid="login-submit"
          disabled={isSubmitting}
          className="w-full bg-white text-zinc-950 font-semibold py-2 rounded-lg text-sm hover:bg-zinc-200 transition disabled:opacity-50"
        >
          {isSubmitting ? t("auth.login_submitting") : t("auth.login")}
        </button>

        <div className="relative my-4">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-zinc-800" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-zinc-900 px-2 text-zinc-500">ou</span>
          </div>
        </div>

        <button
          type="button"
          data-testid="google-login-button"
          onClick={() => handleGoogleLogin()}
          disabled={isSubmitting}
          className="w-full border border-zinc-700 bg-zinc-950 text-zinc-200 font-medium py-2 rounded-lg text-sm hover:bg-zinc-800 transition disabled:opacity-50 flex items-center justify-center gap-2"
        >
          <span>Entrar com Google</span>
        </button>
      </form>

      <div className="mt-6 text-center text-xs text-zinc-400">
        <Link to="/register" className="hover:text-zinc-200 transition">
          {t("auth.dont_have_account")}
        </Link>
      </div>

      <div className="mt-4 pt-3 border-t border-zinc-800/60 flex items-center justify-center gap-3 text-[11px] text-zinc-500">
        <Link to="/terms" className="hover:text-zinc-300 hover:underline transition">
          {t("legal.terms_link")}
        </Link>
        <span aria-hidden="true">·</span>
        <Link to="/privacy" className="hover:text-zinc-300 hover:underline transition">
          {t("legal.privacy_link")}
        </Link>
      </div>
    </div>
  );
}
