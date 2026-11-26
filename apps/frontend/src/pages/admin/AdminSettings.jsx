import { useCallback, useEffect, useState } from "react";
import {
  Flag,
  Plus,
  RefreshCw,
  Shield,
  Users,
  Trash2,
  Check,
  X,
} from "lucide-react";
import {
  createAdminFeatureFlag,
  deleteAdminFeatureFlag,
  getAdminFeatureFlags,
  updateAdminFeatureFlag,
} from "../../services/api";
import { ConfirmModal } from "../../components/admin/ConfirmModal";

function FlagRow({ flag, onToggle, onUpdate, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [pct, setPct] = useState(flag.rollout_percentage);
  const [saving, setSaving] = useState(false);

  const handleSavePct = async () => {
    setSaving(true);
    try {
      await onUpdate(flag.key, { rollout_percentage: Number(pct) });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-pink-400 font-mono text-sm bg-pink-500/10 px-2 py-0.5 rounded">
              {flag.key}
            </code>
            {flag.admin_only && (
              <span className="flex items-center gap-1 text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full">
                <Shield size={11} /> admin only
              </span>
            )}
            {!flag.admin_only && (
              <span className="flex items-center gap-1 text-xs text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded-full">
                <Users size={11} /> {flag.rollout_percentage}%
              </span>
            )}
          </div>
          {flag.description && <p className="text-zinc-400 text-sm mt-1.5">{flag.description}</p>}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            data-testid={`toggle-flag-${flag.key}`}
            onClick={() => onToggle(flag.key, !flag.is_enabled)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
              flag.is_enabled
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                : "bg-zinc-800 text-zinc-400 border border-zinc-700"
            }`}
          >
            {flag.is_enabled ? "Ativa" : "Inativa"}
          </button>
          <button
            type="button"
            data-testid={`delete-flag-${flag.key}`}
            onClick={() => onDelete(flag.key)}
            className="p-2 text-zinc-500 hover:text-rose-400 transition"
            title="Remover flag"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 pt-2 border-t border-zinc-800/70">
        <button
          type="button"
          onClick={() => onUpdate(flag.key, { admin_only: !flag.admin_only })}
          className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition ${
            flag.admin_only
              ? "border-purple-500/50 text-purple-400 bg-purple-500/10"
              : "border-zinc-700 text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Shield size={12} />
          {flag.admin_only ? "Admin Only: ON" : "Admin Only: OFF"}
        </button>

        {!flag.admin_only &&
          (editing ? (
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="0"
                max="100"
                value={pct}
                onChange={(e) => setPct(e.target.value)}
                className="w-16 bg-zinc-950 text-white text-xs rounded-lg px-2 py-1 border border-zinc-700 focus:outline-none focus:border-pink-500"
              />
              <span className="text-zinc-500 text-xs">%</span>
              <button
                type="button"
                onClick={handleSavePct}
                disabled={saving}
                className="text-emerald-400 hover:text-emerald-300 text-xs px-2 py-1 rounded border border-emerald-700 flex items-center gap-1"
              >
                <Check size={12} /> Salvar
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setPct(flag.rollout_percentage);
                }}
                className="text-zinc-500 hover:text-zinc-300 text-xs"
              >
                <X size={13} />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-200 transition"
            >
              <Users size={12} /> Rollout: {flag.rollout_percentage}%
            </button>
          ))}
      </div>
    </div>
  );
}

export function AdminSettings() {
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const fetchFlags = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getAdminFeatureFlags();
      setFlags(Array.isArray(data) ? data : []);
    } catch {
      setError("Erro ao carregar as feature flags.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFlags();
  }, [fetchFlags]);

  const handleToggle = async (key, isEnabled) => {
    const updated = await updateAdminFeatureFlag(key, { is_enabled: isEnabled });
    setFlags((prev) => prev.map((f) => (f.key === key ? updated : f)));
  };

  const handleUpdate = async (key, payload) => {
    const updated = await updateAdminFeatureFlag(key, payload);
    setFlags((prev) => prev.map((f) => (f.key === key ? updated : f)));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newKey.trim()) return;
    setCreating(true);
    try {
      const created = await createAdminFeatureFlag({
        key: newKey.trim(),
        description: newDesc.trim(),
        is_enabled: false,
        rollout_percentage: 100,
      });
      setFlags((prev) => [...prev, created]);
      setNewKey("");
      setNewDesc("");
      setShowCreate(false);
    } finally {
      setCreating(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    await deleteAdminFeatureFlag(deleteTarget);
    setFlags((prev) => prev.filter((f) => f.key !== deleteTarget));
    setDeleteTarget(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-2.5">
            <Flag className="text-pink-400" size={26} /> Feature Flags
          </h1>
          <p className="text-zinc-400 text-sm mt-1">
            Ative ou desative funcionalidades dinamicamente sem novo deploy.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={fetchFlags}
            className="flex items-center gap-1.5 text-xs text-zinc-300 border border-zinc-700 rounded-xl px-3 py-2 hover:bg-zinc-800 transition"
          >
            <RefreshCw size={13} /> Atualizar
          </button>
          <button
            type="button"
            data-testid="new-flag-btn"
            onClick={() => setShowCreate((v) => !v)}
            className="flex items-center gap-1.5 text-xs bg-pink-600 hover:bg-pink-500 text-white font-semibold rounded-xl px-3.5 py-2 transition"
          >
            <Plus size={14} /> Nova Flag
          </button>
        </div>
      </div>

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-3"
        >
          <h2 className="text-sm font-bold text-white">Criar Feature Flag</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input
              type="text"
              data-testid="new-flag-key-input"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="chave_em_snake_case"
              required
              className="bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-pink-500 font-mono"
            />
            <input
              type="text"
              data-testid="new-flag-desc-input"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Descrição da funcionalidade"
              className="bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-pink-500"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 text-xs text-zinc-400 hover:text-white"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={creating}
              data-testid="create-flag-submit"
              className="px-4 py-2 text-xs bg-pink-600 hover:bg-pink-500 text-white font-semibold rounded-xl"
            >
              {creating ? "Criando..." : "Criar Flag"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pink-500" />
        </div>
      ) : error ? (
        <div className="text-center py-8 text-rose-400 text-sm">{error}</div>
      ) : flags.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 text-center text-zinc-500 text-sm">
          Nenhuma feature flag cadastrada.
        </div>
      ) : (
        <div className="space-y-3">
          {flags.map((flag) => (
            <FlagRow
              key={flag.key}
              flag={flag}
              onToggle={handleToggle}
              onUpdate={handleUpdate}
              onDelete={(k) => setDeleteTarget(k)}
            />
          ))}
        </div>
      )}

      <ConfirmModal
        variant="danger"
        isOpen={!!deleteTarget}
        title="Remover Feature Flag"
        message={`Deseja excluir permanentemente a flag "${deleteTarget}"?`}
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

export default AdminSettings;
