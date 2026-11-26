import { useState } from "react";
import { AlertTriangle, Trash2, X } from "lucide-react";

export function PermanentDeleteModal({ isOpen, user, onConfirm, onCancel }) {
  const [confirmUsername, setConfirmUsername] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen || !user) return null;

  const normalized = confirmUsername.trim().toLowerCase().replace(/^@/, "");
  const isMatch = normalized === user.username.toLowerCase();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isMatch) {
      setError(`Digite exatamente @${user.username} para confirmar.`);
      return;
    }
    setError("");
    setLoading(true);
    try {
      await onConfirm(user.id, user.username);
      setConfirmUsername("");
    } catch (err) {
      setError(err?.response?.data?.detail || "Erro ao excluir usuário definitivamente.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      data-testid="permanent-delete-modal"
      className="fixed inset-0 z-[100] bg-black/85 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className="bg-zinc-900 rounded-2xl border border-rose-600/40 p-6 w-full max-w-lg shadow-2xl space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-rose-500/20 pb-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-rose-600/20 text-rose-500">
              <AlertTriangle size={20} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-rose-400">Excluir Conta Definitivamente</h2>
              <p className="text-xs text-zinc-400">Esta ação é irreversível (Estágio 2)</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="text-zinc-500 hover:text-white transition"
            aria-label="Fechar"
          >
            <X size={18} />
          </button>
        </div>

        <div className="bg-rose-950/30 border border-rose-800/40 rounded-xl p-3.5 text-xs text-rose-200 space-y-2">
          <p className="font-semibold text-rose-300">O que será apagado imediatamente:</p>
          <ul className="list-disc list-inside space-y-1 text-zinc-300 pl-1">
            <li>Todas as publicações, mídias, rascunhos e curtidas</li>
            <li>Comentários sem respostas (comentários com respostas viram tombstone)</li>
            <li>Relações de seguidores, bloqueios, silenciamentos e perfil</li>
          </ul>
          <p className="text-[11px] text-zinc-400 pt-1 border-t border-rose-800/30">
            * Registros de acesso (Marco Civil Art. 15) e logs de moderação são preservados. O
            e-mail terá um HMAC retido para impedir recadastro.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">
              Para confirmar, digite{" "}
              <span className="font-mono text-rose-400 font-bold">@{user.username}</span> abaixo:
            </label>
            <input
              type="text"
              data-testid="permanent-delete-username-input"
              value={confirmUsername}
              onChange={(e) => {
                setConfirmUsername(e.target.value);
                if (error) setError("");
              }}
              placeholder={`@${user.username}`}
              className="w-full bg-zinc-950 border border-rose-500/30 rounded-xl p-3 text-sm text-white placeholder-zinc-600 font-mono focus:outline-none focus:border-rose-500"
              autoFocus
            />
          </div>

          {error && (
            <p className="text-xs text-rose-400 bg-rose-950/40 p-2.5 rounded-lg border border-rose-800/60">
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => {
                setConfirmUsername("");
                onCancel();
              }}
              disabled={loading}
              className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 py-2.5 rounded-xl text-sm transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              data-testid="confirm-permanent-delete-btn"
              disabled={!isMatch || loading}
              className="flex-1 bg-rose-600 hover:bg-rose-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-xl text-sm transition flex items-center justify-center gap-2"
            >
              <Trash2 size={14} /> {loading ? "Excluindo..." : "Excluir Definitivamente"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default PermanentDeleteModal;
