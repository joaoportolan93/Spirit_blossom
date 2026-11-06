import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";
import { APP_NAME } from "../config/brand";

export function ForgotPassword() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) {
      setErrorMessage(t("errors.required_field") || "Campo obrigatório");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");
    setStatusMessage("");

    try {
      await api.post("/api/auth/password-reset/request/", { email });
      // Resposta uniforme anti-enumeração
      setStatusMessage(
        "Se o e-mail estiver cadastrado em nossa base, um link de recuperação foi enviado. Verifique sua caixa de entrada (e pasta de spam)."
      );
    } catch (err) {
      if (err.response?.status === 429) {
        setErrorMessage("Muitas tentativas. Aguarde um instante antes de tentar novamente.");
      } else {
        // Mesmo em falha não esperada, evitar confirmação de existência
        setStatusMessage(
          "Se o e-mail estiver cadastrado em nossa base, um link de recuperação foi enviado. Verifique sua caixa de entrada (e pasta de spam)."
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-12 p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-lg">
      <div className="text-center mb-6">
        <h1 className="text-2xl font-bold text-white mb-1">{APP_NAME}</h1>
        <p className="text-xs text-zinc-400">Recuperação de Acesso</p>
      </div>

      {statusMessage ? (
        <div className="space-y-4">
          <div
            data-testid="forgot-password-success"
            className="p-3 bg-emerald-950/50 border border-emerald-800/80 rounded-lg text-xs text-emerald-300"
          >
            {statusMessage}
          </div>
          <div className="text-center text-xs text-zinc-400">
            <Link to="/login" className="hover:text-zinc-200 transition underline">
              Voltar ao login
            </Link>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} data-testid="forgot-password-form" className="space-y-4">
          {errorMessage && (
            <div
              data-testid="forgot-password-error"
              className="p-3 bg-rose-950/50 border border-rose-800/80 rounded-lg text-xs text-rose-300"
            >
              {errorMessage}
            </div>
          )}

          <div>
            <label
              htmlFor="forgot-email"
              className="block text-xs font-medium text-zinc-300 mb-1"
            >
              {t("auth.email") || "E-mail"}
            </label>
            <input
              id="forgot-email"
              type="email"
              data-testid="forgot-email-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              required
            />
          </div>

          <button
            type="submit"
            data-testid="forgot-password-submit"
            disabled={isSubmitting}
            className="w-full bg-white text-zinc-950 font-semibold py-2 rounded-lg text-sm hover:bg-zinc-200 transition disabled:opacity-50"
          >
            {isSubmitting ? "Enviando..." : "Enviar link de recuperação"}
          </button>

          <div className="text-center text-xs text-zinc-400 pt-2">
            <Link to="/login" className="hover:text-zinc-200 transition">
              Lembrou sua senha? Entrar
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}

