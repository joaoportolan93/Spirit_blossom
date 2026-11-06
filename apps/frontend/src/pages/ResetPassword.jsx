import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { APP_NAME } from "../config/brand";

export function ResetPassword() {
  const navigate = useNavigate();
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusSuccess, setStatusSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Garante Referrer-Policy: no-referrer nesta tela para não vazar o fragmento
  useEffect(() => {
    let meta = document.querySelector('meta[name="referrer"]');
    let created = false;
    if (!meta) {
      meta = document.createElement("meta");
      meta.name = "referrer";
      meta.content = "no-referrer";
      document.head.appendChild(meta);
      created = true;
    } else {
      meta.content = "no-referrer";
    }

    // Extrai o token do fragmento da URL (#token=...)
    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const tokenFromHash = params.get("token") || hash;

    if (!tokenFromHash) {
      setErrorMessage("Token de recuperação ausente ou link incompleto.");
    } else {
      setToken(tokenFromHash);
    }

    return () => {
      if (created && meta && meta.parentNode) {
        meta.parentNode.removeChild(meta);
      }
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");

    if (!token) {
      setErrorMessage("Token inválido ou ausente.");
      return;
    }

    if (!newPassword || !newPasswordConfirm) {
      setErrorMessage("Preencha todos os campos.");
      return;
    }

    if (newPassword !== newPasswordConfirm) {
      setErrorMessage("As senhas não conferem.");
      return;
    }

    if (newPassword.length < 8) {
      setErrorMessage("A senha deve ter no mínimo 8 caracteres.");
      return;
    }

    setIsSubmitting(true);

    try {
      await api.post("/api/auth/password-reset/confirm/", {
        token,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
      });
      setStatusSuccess(true);
      // Limpa fragmento da URL por segurança
      window.history.replaceState(null, "", window.location.pathname);
    } catch (err) {
      if (err.response?.status === 429) {
        setErrorMessage("Muitas tentativas. Aguarde um instante.");
      } else {
        const detail =
          err.response?.data?.detail ||
          err.response?.data?.token?.[0] ||
          err.response?.data?.new_password?.[0] ||
          "Token de recuperação inválido ou expirado.";
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
        <p className="text-xs text-zinc-400">Criar Nova Senha</p>
      </div>

      {statusSuccess ? (
        <div className="space-y-4">
          <div
            data-testid="reset-password-success"
            className="p-3 bg-emerald-950/50 border border-emerald-800/80 rounded-lg text-xs text-emerald-300"
          >
            Sua senha foi redefinida com sucesso! Você já pode entrar com a nova senha.
          </div>
          <button
            type="button"
            data-testid="reset-password-go-login"
            onClick={() => navigate("/login")}
            className="w-full bg-white text-zinc-950 font-semibold py-2 rounded-lg text-sm hover:bg-zinc-200 transition"
          >
            Ir para o Login
          </button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} data-testid="reset-password-form" className="space-y-4">
          {errorMessage && (
            <div
              data-testid="reset-password-error"
              className="p-3 bg-rose-950/50 border border-rose-800/80 rounded-lg text-xs text-rose-300"
            >
              {errorMessage}
            </div>
          )}

          <div>
            <label
              htmlFor="reset-new-password"
              className="block text-xs font-medium text-zinc-300 mb-1"
            >
              Nova Senha (mínimo 8 caracteres)
            </label>
            <input
              id="reset-new-password"
              type="password"
              data-testid="reset-new-password-input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              required
            />
          </div>

          <div>
            <label
              htmlFor="reset-new-password-confirm"
              className="block text-xs font-medium text-zinc-300 mb-1"
            >
              Confirmar Nova Senha
            </label>
            <input
              id="reset-new-password-confirm"
              type="password"
              data-testid="reset-new-password-confirm-input"
              value={newPasswordConfirm}
              onChange={(e) => setNewPasswordConfirm(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              required
            />
          </div>

          <button
            type="submit"
            data-testid="reset-password-submit"
            disabled={isSubmitting || !token}
            className="w-full bg-white text-zinc-950 font-semibold py-2 rounded-lg text-sm hover:bg-zinc-200 transition disabled:opacity-50"
          >
            {isSubmitting ? "Redefinindo..." : "Salvar Nova Senha"}
          </button>

          <div className="text-center text-xs text-zinc-400 pt-2">
            <Link to="/login" className="hover:text-zinc-200 transition">
              Cancelar e voltar ao login
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}

