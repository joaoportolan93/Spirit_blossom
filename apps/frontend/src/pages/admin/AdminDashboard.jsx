import { useEffect, useState } from "react";
import { Users, AlertTriangle, Ban, FileText, EyeOff } from "lucide-react";
import { getAdminStats } from "../../services/api";

export function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await getAdminStats();
        if (active) setStats(data);
      } catch {
        if (active) setError("Não foi possível carregar as estatísticas.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pink-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-rose-950/30 border border-rose-800/50 text-rose-300 rounded-xl p-6 text-sm">
        {error}
      </div>
    );
  }

  const kpis = stats?.kpis || {};
  const daily = stats?.daily_stats || [];
  const maxVal = Math.max(
    1,
    ...daily.flatMap((d) => [d.signups || 0, d.reports || 0, d.posts || 0])
  );

  const cards = [
    { label: "Total de usuários", value: kpis.total_users ?? 0, icon: Users, accent: "text-sky-400 bg-sky-500/10" },
    {
      label: "Denúncias pendentes",
      value: kpis.pending_reports ?? 0,
      icon: AlertTriangle,
      accent: "text-amber-400 bg-amber-500/10",
      alert: (kpis.pending_reports ?? 0) > 0,
    },
    { label: "Usuários banidos", value: kpis.banned_users ?? 0, icon: Ban, accent: "text-rose-400 bg-rose-500/10" },
    { label: "Publicações", value: kpis.total_posts ?? 0, icon: FileText, accent: "text-pink-400 bg-pink-500/10" },
    { label: "Posts ocultados", value: kpis.hidden_posts ?? 0, icon: EyeOff, accent: "text-purple-400 bg-purple-500/10" },
  ];

  const banRate =
    (kpis.total_users ?? 0) > 0
      ? (((kpis.banned_users ?? 0) / kpis.total_users) * 100).toFixed(2)
      : "0.00";
  const postsPerUser =
    (kpis.total_users ?? 0) > 0
      ? ((kpis.total_posts ?? 0) / kpis.total_users).toFixed(1)
      : "0.0";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white">Painel Administrativo</h1>
        <p className="text-zinc-400 mt-1 text-sm">Visão geral de segurança, moderação e atividade da rede.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {cards.map((card) => (
          <div
            key={card.label}
            className={`bg-zinc-900 border rounded-2xl p-5 flex items-start justify-between ${
              card.alert ? "border-amber-500/50" : "border-zinc-800"
            }`}
          >
            <div>
              <p className="text-xs text-zinc-400 font-medium">{card.label}</p>
              <p className="text-2xl font-bold text-white font-mono mt-2">
                {Number(card.value).toLocaleString()}
              </p>
            </div>
            <div className={`p-2.5 rounded-xl ${card.accent}`}>
              <card.icon size={18} />
            </div>
          </div>
        ))}
      </div>

      {/* Atividade dos últimos 7 dias */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-bold text-white">Atividade dos últimos 7 dias</h2>
          <div className="flex items-center gap-4 text-xs text-zinc-400">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500 inline-block" /> Novos usuários
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" /> Denúncias
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-pink-500 inline-block" /> Publicações
            </span>
          </div>
        </div>

        <div className="grid grid-cols-7 gap-3 items-end h-48 pt-4">
          {daily.map((day) => {
            const signupsH = Math.round(((day.signups || 0) / maxVal) * 100);
            const reportsH = Math.round(((day.reports || 0) / maxVal) * 100);
            const postsH = Math.round(((day.posts || 0) / maxVal) * 100);
            const label = new Date(`${day.date}T12:00:00`).toLocaleDateString("pt-BR", {
              day: "2-digit",
              month: "2-digit",
            });
            return (
              <div key={day.date} className="flex flex-col items-center gap-2 h-full justify-end">
                <div className="flex items-end gap-1 w-full justify-center h-36">
                  <div
                    className="w-2.5 bg-sky-500/80 rounded-t"
                    style={{ height: `${Math.max(4, signupsH)}%` }}
                    title={`Cadastros: ${day.signups}`}
                  />
                  <div
                    className="w-2.5 bg-amber-500/80 rounded-t"
                    style={{ height: `${Math.max(4, reportsH)}%` }}
                    title={`Denúncias: ${day.reports}`}
                  />
                  <div
                    className="w-2.5 bg-pink-500/80 rounded-t"
                    style={{ height: `${Math.max(4, postsH)}%` }}
                    title={`Posts: ${day.posts}`}
                  />
                </div>
                <span className="text-[11px] font-mono text-zinc-500">{label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Taxa de banimento</p>
          <p className="text-2xl font-bold text-white font-mono mt-2">{banRate}%</p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Posts por usuário</p>
          <p className="text-2xl font-bold text-white font-mono mt-2">{postsPerUser}</p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Novos usuários hoje</p>
          <p className="text-2xl font-bold text-white font-mono mt-2">{kpis.new_users_today ?? 0}</p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Posts publicados hoje</p>
          <p className="text-2xl font-bold text-white font-mono mt-2">{kpis.new_posts_today ?? 0}</p>
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;
