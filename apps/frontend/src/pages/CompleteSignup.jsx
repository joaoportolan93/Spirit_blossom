import { useState } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";
import { APP_NAME } from "../config/brand";

export function CompleteSignup() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { setUser } = useAuth();

  const onboardingToken =
    location.state?.onboarding_token ||
    new URLSearchParams(location.search).get("token") ||
    "";
  const email =
    location.state?.email ||
    new URLSearchParams(location.search).get("email") ||
    "";

  const [username, setUsername] = useState("");
  const [birthDate, setBirthDate] = useState("");
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

    if (!onboardingToken) {
      setErrorMessage("Sessão de cadastro do Google expirada ou inválida. Inicie novamente.");
      return;
    }

    if (!username || !birthDate) {
      setErrorMessage("Preencha todos os campos obrigatórios.");
      return;
    }

    // Apenas alfanuméricos
    if (!/^[a-zA-Z0-9]+$/.test(username)) {
      setErrorMessage("O nome de usuário deve conter apenas letras e números.");
      return;
    }

    const age = calculateAge(birthDate);
    if (isNaN(age) || age < 18) {
      setErrorMessage("É necessário ter pelo menos 18 anos para utilizar a plataforma.");
      return;
    }

    if (!termsAccepted) {
      setErrorMessage("Você deve aceitar os Termos de Uso e Política de Privacidade.");
      return;
    }

    setIsSubmitting(true);

    try {
      const resp = await api.post("/api/auth/google/complete/", {
        onboarding_token: onboardingToken,
        username,
        birth_date: birthDate,
        terms_accepted: termsAccepted,
      });

      setUser({
        email: resp.data.email || email,
        username,
        birth_date: birthDate,
        is_authenticated: true,
      });
      navigate("/");
    } catch (err) {
      if (err.response?.status === 429) {
        setErrorMessage("Muitas tentativas. Aguarde um instante.");
      } else {
        const errorData = err.response?.data;
        const msg =
          errorData?.username?.[0] ||
          errorData?.birth_date?.[0] ||
          errorData?.terms_accepted?.[0] ||
          errorData?.detail ||
          "Erro ao concluir cadastro.";
        setErrorMessage(msg);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!onboardingToken) {
    return (
      <div className="max-w-md mx-auto mt-12 p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-lg text-center">
        <h1 className="text-xl font-bold text-white mb-2">Sessão Expirada</h1>
        <p className="text-xs text-zinc-400 mb-4">
          Não identificamos uma sessão ativa de cadastro via Google.
        </p>
        <Link
          to="/login"
          className="inline-block bg-white text-zinc-950 font-semibold px-4 py-2 rounded-lg text-xs hover:bg-zinc-200 transition"
        >
          Voltar ao Login
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto mt-8 p-6 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-lg">
      <div className="text-center mb-6">
        <h1 className="text-2xl font-bold text-white mb-1">{APP_NAME}</h1>
        <p className="text-xs text-zinc-400">Complete seu cadastro Google</p>
        {email && (
          <p className="text-xs text-zinc-500 mt-1">Conectado como: {email}</p>
        )}
        <div className="inline-block bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs px-2.5 py-1 rounded-full font-medium mt-2">
          Acesso Restrito 18+
        </div>
      </div>

      <form onSubmit={handleSubmit} data-testid="complete-signup-form" className="space-y-4">
        {errorMessage && (
          <div
            data-testid="complete-signup-error"
            className="p-3 bg-rose-950/50 border border-rose-800/80 rounded-lg text-xs text-rose-300"
          >
            {errorMessage}
          </div>
        )}

        <div>
          <label htmlFor="google-username" className="block text-xs font-medium text-zinc-300 mb-1">
            Nome de Usuário (apenas letras e números)
          </label>
          <input
            id="google-username"
            type="text"
            data-testid="complete-username-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            required
          />
        </div>

        <div>
          <label htmlFor="google-birth-date" className="block text-xs font-medium text-zinc-300 mb-1">
            Data de Nascimento (18+)
          </label>
          <input
            id="google-birth-date"
            type="date"
            data-testid="complete-birth-date-input"
            value={birthDate}
            onChange={(e) => setBirthDate(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            required
          />
        </div>

        <div className="flex items-start gap-2 pt-2">
          <input
            id="google-terms"
            type="checkbox"
            data-testid="complete-terms-checkbox"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
            className="mt-0.5 rounded border-zinc-700 bg-zinc-950 text-white focus:ring-zinc-600"
            required
          />
          <label htmlFor="google-terms" className="text-xs text-zinc-300">
            {t("legal.consent_prefix")}
            <Link
              to="/terms"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="complete-terms-link"
              className="text-pink-400 hover:underline font-medium"
            >
              {t("legal.terms_link")}
            </Link>
            {t("legal.consent_and")}
            <Link
              to="/privacy"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="complete-privacy-link"
              className="text-pink-400 hover:underline font-medium"
            >
              {t("legal.privacy_link")}
            </Link>
            .
          </label>
        </div>

        <button
          type="submit"
          data-testid="complete-signup-submit"
          disabled={isSubmitting}
          className="w-full bg-white text-zinc-950 font-semibold py-2 rounded-lg text-sm hover:bg-zinc-200 transition disabled:opacity-50"
        >
          {isSubmitting ? "Finalizando..." : "Concluir Cadastro"}
        </button>
      </form>
    </div>
  );
}

