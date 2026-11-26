import { useState } from "react";
import { Ban, ShieldAlert, X } from "lucide-react";

export function BanUserModal({ isOpen, user, onConfirm, onCancel }) {
  const [reason, setReason] = useState("");
  const [durationDays, setDurationDays] = useState("");
  const [preserveForAuthorities, setPreserveForAuthorities] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen || !user) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!reason.trim()) {
      setError("O motivo do banimento é obrigatório.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const parsedDuration = durationDays ? Number(durationDays) : null;
      await onConfirm(user.id, reason.trim(), parsedDuration, preserveForAuthorities);
      setReason("");
      setDurationDays("");
      setPreserveForAuthorities(false);
    } catch (err) {
      setError(err?.response?.data?.detail || "Erro ao banir usuário.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      data-testid="ban-user-modal"
      className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className="bg-zinc-900 rounded-2xl border border-rose-500/30 p-6 w-full max-w-lg shadow-2xl space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-rose-500/15 text-rose-400">
              <Ban size={18} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Suspender / Banir Usuário</h2>
              <p className="text-xs text-zinc-400">
                @{user.username} ({user.email})
              </p>
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

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1">
              Duração da suspensão
            </label>
            <select
              data-testid="ban-duration-select"
              value={durationDays}
              onChange={(e) => setDurationDays(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-rose-500"
            >
              <option value="">Banimento (Estágio 1 — prazo de recurso de 30 dias)</option>
              <option value="1">Suspensão temporária — 1 dia</option>
              <option value="7">Suspensão temporária — 7 dias</option>
              <option value="30">Suspensão temporária — 30 dias</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1">
              Motivo do banimento <span className="text-rose-400">*</span>
            </label>
            <textarea
              data-testid="ban-reason-input"
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (error) setError("");
              }}
              rows={3}
              placeholder="Descreva a violação das diretrizes da plataforma..."
              className="w-full bg-zinc-950 border border-zinc-700 rounded-xl p-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-rose-500 resize-none"
              required
            />
          </div>

          <div className="bg-zinc-950/60 rounded-xl p-3 border border-zinc-800 flex items-start gap-3">
            <input
              type="checkbox"
              id="preserve_for_authorities"
              checked={preserveForAuthorities}
              onChange={(e) => setPreserveForAuthorities(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-rose-600 focus:ring-rose-500"
            />
            <label htmlFor="preserve_for_authorities" className="text-xs text-zinc-300 cursor-pointer">
              <strong className="text-amber-400 flex items-center gap-1">
                <ShieldAlert size={12} /> Preservar dados para autoridades
              </strong>
              <span>
                Marque caso a conta envolva ordem judicial ou investigação formal. Esta conta{" "}
                <strong>NÃO</strong> será excluída automaticamente após o prazo de recurso.
              </span>
            </label>
          </div>

          {error && (
            <p className="text-xs text-rose-400 bg-rose-950/40 p-2.5 rounded-lg border border-rose-800/60">
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={loading}
              className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 py-2.5 rounded-xl text-sm transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              data-testid="confirm-ban-btn"
              className="flex-1 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded-xl text-sm transition flex items-center justify-center gap-2"
            >
              <Ban size={14} /> {loading ? "Aplicando..." : "Confirmar Banimento"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default BanUserModal;
