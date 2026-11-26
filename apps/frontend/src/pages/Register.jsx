import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../hooks/useAuth";
import { APP_NAME } from "../config/brand";

export function Register() {
  const { t } = useTranslation();
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const calculateAge = (dateString) => {
    const today = new Date();
    const birth = new Date(dateString);
    let age = today.getFullYear() - birth.getFullYear();
    const m = today.getMonth() - birth.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) {
      age--;
    }
    return age;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");

    if (!email || !username || !birthDate || !password || !passwordConfirm) {
      setErrorMessage(t("errors.required_field"));
      return;
    }

    if (password !== passwordConfirm) {
      setErrorMessage(t("auth.passwords_mismatch"));
      return;
    }

    // Validação estrita 18+ no frontend (hard gate)
    const age = calculateAge(birthDate);
    if (isNaN(age) || age < 18) {
      setErrorMessage(t("auth.underage_error"));
      return;
    }

    if (!termsAccepted) {
      setErrorMessage(t("legal.terms_required"));
      return;
    }

    setIsSubmitting(true);

    try {
      await register({
        email,
        username,
        birth_date: birthDate,
        password,
        password_confirm: passwordConfirm,
        terms_accepted: termsAccepted,
      });
      navigate("/");
    } catch (err) {
      if (err.response?.status === 429) {
        setErrorMessage(t("auth.throttle_error"));
      } else {
        const errorData = err.response?.data;
        const firstError =
          errorData?.birth_date?.[0] ||
          errorData?.email?.[0] ||
          errorData?.username?.[0] ||
          errorData?.password?.[0] ||
          errorData?.detail ||
          t("errors.generic");
        setErrorMessage(firstError);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-8 p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-lg">
      <div className="text-center mb-6">
        <h1 className="text-2xl font-bold text-white mb-1">{APP_NAME}</h1>
        <div className="inline-block bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs px-2.5 py-1 rounded-full font-medium mt-1">
          {t("auth.age_notice")}
        </div>
      </div>

      <form onSubmit={handleSubmit} data-testid="register-form" className="space-y-4">
        {errorMessage && (
          <div
            data-testid="register-error"
            className="p-3 bg-rose-950/50 border border-rose-800/80 rounded-lg text-xs text-rose-300"
          >
            {errorMessage}
          </div>
        )}

        <div>
          <label htmlFor="reg-email" className="block text-xs font-medium text-zinc-300 mb-1">
            {t("auth.email")}
          </label>
          <input
            id="reg-email"
            type="email"
            data-testid="register-email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            required
          />
        </div>

        <div>
          <label htmlFor="reg-username" className="block text-xs font-medium text-zinc-300 mb-1">
            {t("auth.username")}
          </label>
          <input
            id="reg-username"
            type="text"
            data-testid="register-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            required
          />
        </div>

        <div>
          <label htmlFor="reg-birth-date" className="block text-xs font-medium text-zinc-300 mb-1">
            {t("auth.birth_date")} (18+)
          </label>
          <input
            id="reg-birth-date"
            type="date"
            data-testid="register-birth-date"
            value={birthDate}
            onChange={(e) => setBirthDate(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            required
          />
        </div>

        <div>
          <label htmlFor="reg-password" className="block text-xs font-medium text-zinc-300 mb-1">
            {t("auth.password")}
          </label>
          <input
            id="reg-password"
            type="password"
            data-testid="register-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            required
          />
        </div>

        <div>
          <label htmlFor="reg-password-confirm" className="block text-xs font-medium text-zinc-300 mb-1">
            {t("auth.password_confirm")}
          </label>
          <input
            id="reg-password-confirm"
            type="password"
            data-testid="register-password-confirm"
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            required
          />
        </div>

        <div className="flex items-start gap-2 pt-2">
          <input
            id="reg-terms"
            type="checkbox"
            data-testid="register-terms"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
            className="mt-0.5 rounded border-zinc-700 bg-zinc-950 text-white focus:ring-zinc-600"
            required
          />
          <label htmlFor="reg-terms" className="text-xs text-zinc-300">
            {t("legal.consent_prefix")}
            <Link
              to="/terms"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="register-terms-link"
              className="text-pink-400 hover:underline font-medium"
            >
              {t("legal.terms_link")}
            </Link>
            {t("legal.consent_and")}
            <Link
              to="/privacy"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="register-privacy-link"
              className="text-pink-400 hover:underline font-medium"
            >
              {t("legal.privacy_link")}
            </Link>
            .
          </label>
        </div>

        <button
          type="submit"
          data-testid="register-submit"
          disabled={isSubmitting}
          className="w-full bg-white text-zinc-950 font-semibold py-2 rounded-lg text-sm hover:bg-zinc-200 transition disabled:opacity-50"
        >
          {isSubmitting ? t("auth.register_submitting") : t("auth.register")}
        </button>
      </form>

      <div className="mt-6 text-center text-xs text-zinc-400">
        <Link to="/login" className="hover:text-zinc-200 transition">
          {t("auth.already_have_account")}
        </Link>
      </div>
    </div>
  );
}
