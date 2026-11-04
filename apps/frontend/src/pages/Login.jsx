import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../hooks/useAuth";
import { APP_NAME } from "../config/brand";

export function Login() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage(t("errors.required_field"));
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");

    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      if (err.response?.status === 429) {
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
          <label
            htmlFor="login-password"
            className="block text-xs font-medium text-zinc-300 mb-1"
          >
            {t("auth.password")}
          </label>
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
      </form>

      <div className="mt-6 text-center text-xs text-zinc-400">
        <Link to="/register" className="hover:text-zinc-200 transition">
          {t("auth.dont_have_account")}
        </Link>
      </div>
    </div>
  );
}
