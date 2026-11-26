import { useEffect, useState } from "react";
import { History } from "lucide-react";
import { getAdminModerationLogs } from "../../services/api";

export function AdminModerationLogs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await getAdminModerationLogs();
        if (active) setLogs(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error("Erro ao carregar logs de moderação:", err);
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-2.5">
          <History className="text-pink-400" size={26} /> Auditoria de Moderação
        </h1>
        <p className="text-zinc-400 text-sm mt-1">
          Histórico imutável de decisões sobre contas, publicações e denúncias.
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pink-500" />
        </div>
      ) : logs.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-10 text-center text-zinc-500 text-sm">
          Nenhum registro de moderação encontrado.
        </div>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl divide-y divide-zinc-800/80">
          {logs.map((log) => (
            <div key={log.id} className="p-4 space-y-1.5 hover:bg-zinc-800/30 transition">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm">
                  <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-pink-500/15 text-pink-400">
                    {log.action_display || log.action}
                  </span>
                  <span className="text-zinc-400 text-xs font-mono">
                    {log.target_type}:{log.target_id}
                  </span>
                </div>
                <span className="text-xs text-zinc-500 font-mono">
                  {new Date(log.created_at).toLocaleString("pt-BR")}
                </span>
              </div>
              {log.reason && <p className="text-sm text-zinc-200">{log.reason}</p>}
              <div className="flex flex-wrap gap-4 text-xs text-zinc-500">
                <span>Moderador: {log.moderator_username ? `@${log.moderator_username}` : "Sistema"}</span>
                {log.affected_username && <span>Alvo: @{log.affected_username}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AdminModerationLogs;
