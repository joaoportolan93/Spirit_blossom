import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  EyeOff,
  Trash2,
  Ban,
  Skull,
  AlertTriangle,
  FileText,
  MessageSquare,
  User,
  List,
  History,
} from "lucide-react";
import { executeReportAction, getAdminReports } from "../../services/api";
import { ConfirmModal } from "../../components/admin/ConfirmModal";

const TARGET_FILTERS = [
  { value: "all", label: "Todos" },
  { value: "post", label: "Publicações" },
  { value: "comment", label: "Comentários" },
  { value: "user", label: "Usuários" },
];

export function ModerationQueue() {
  const [activeTab, setActiveTab] = useState("pending");
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [targetFilter, setTargetFilter] = useState("all");
  const [confirmState, setConfirmState] = useState({
    open: false,
    title: "",
    message: "",
    onConfirm: null,
    variant: "danger",
  });

  const fetchReports = useCallback(async (tabStatus) => {
    setLoading(true);
    try {
      const apiStatus = tabStatus === "pending" ? "pending" : "resolved";
      const data = await getAdminReports({ status: apiStatus });
      const list = Array.isArray(data) ? data : data?.results || [];
      setReports(list);
      setSelectedReport(list.length > 0 ? list[0] : null);
    } catch (err) {
      console.error("Erro ao buscar denúncias:", err);
      setReports([]);
      setSelectedReport(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReports(activeTab);
  }, [activeTab, fetchReports]);

  const filteredReports = useMemo(() => {
    if (targetFilter === "all") return reports;
    return reports.filter((r) => r.target_type === targetFilter);
  }, [reports, targetFilter]);

  const performAction = async (action) => {
    if (!selectedReport) return;
    setActionLoading(true);
    try {
      await executeReportAction(selectedReport.id, { action });
      const remaining = reports.filter((r) => r.id !== selectedReport.id);
      setReports(remaining);
      setSelectedReport(remaining.length > 0 ? remaining[0] : null);
    } catch (err) {
      console.error("Erro ao executar ação de moderação:", err);
    } finally {
      setActionLoading(false);
    }
  };

  const requestAction = (action) => {
    if (!selectedReport) return;
    if (action === "ignore") {
      performAction(action);
      return;
    }

    const configs = {
      hide: {
        title: "Ocultar conteúdo",
        message: "O conteúdo denunciado ficará oculto de todos os feeds e listagens públicas.",
        variant: "warning",
      },
      remove: {
        title: "Remover conteúdo",
        message: "O conteúdo será removido permanentemente (ou anonimizado se possuir respostas).",
        variant: "danger",
      },
      ban: {
        title: "Banir usuário",
        message: "A conta do autor será suspensa imediatamente e terá seus tokens revogados.",
        variant: "danger",
      },
      ban_remove: {
        title: "Banir usuário e remover conteúdo",
        message: "O conteúdo será removido e a conta do autor será suspensa imediatamente.",
        variant: "danger",
      },
    };

    const cfg = configs[action];
    setConfirmState({
      open: true,
      title: cfg.title,
      message: cfg.message,
      variant: cfg.variant,
      onConfirm: () => {
        setConfirmState((s) => ({ ...s, open: false }));
        performAction(action);
      },
    });
  };

  const getTypeIcon = (type) => {
    if (type === "post") return <FileText size={15} className="text-pink-400" />;
    if (type === "comment") return <MessageSquare size={15} className="text-sky-400" />;
    if (type === "user") return <User size={15} className="text-emerald-400" />;
    return <AlertTriangle size={15} className="text-amber-400" />;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Fila de Moderação</h1>
          <p className="text-zinc-400 mt-1 text-sm">
            {filteredReports.length} {activeTab === "pending" ? "denúncia(s) pendente(s)" : "denúncia(s) no histórico"}
          </p>
        </div>

        <div className="flex gap-1 bg-zinc-900 rounded-xl p-1 border border-zinc-800 w-fit">
          {[
            { id: "pending", label: "Pendentes", icon: List },
            { id: "history", label: "Histórico", icon: History },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                setActiveTab(tab.id);
                setTargetFilter("all");
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === tab.id
                  ? "bg-pink-600 text-white"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-800"
              }`}
            >
              <tab.icon size={14} /> {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        {TARGET_FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => {
              setTargetFilter(f.value);
              setSelectedReport(null);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition border ${
              targetFilter === f.value
                ? "bg-pink-600/20 text-pink-400 border-pink-500/40"
                : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:border-zinc-700 hover:text-zinc-200"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pink-500" />
        </div>
      ) : filteredReports.length === 0 ? (
        <div className="bg-zinc-900 rounded-2xl p-12 text-center border border-zinc-800">
          <Check className="text-emerald-400 mx-auto mb-3" size={40} />
          <h2 className="text-lg font-bold text-white">
            {activeTab === "pending" ? "Nenhuma denúncia pendente" : "Histórico vazio"}
          </h2>
          <p className="text-zinc-400 text-sm mt-1">
            {activeTab === "pending"
              ? "Todas as denúncias da fila foram analisadas."
              : "Nenhuma denúncia resolvida encontrada."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Lista esquerda */}
          <div className="lg:col-span-4 bg-zinc-900 rounded-2xl border border-zinc-800 overflow-hidden flex flex-col max-h-[650px]">
            <div className="p-4 border-b border-zinc-800 text-sm font-bold text-white">
              {activeTab === "pending" ? "Denúncias pendentes" : "Denúncias resolvidas"}
            </div>
            <div className="overflow-y-auto divide-y divide-zinc-800/70">
              {filteredReports.map((report) => (
                <button
                  key={report.id}
                  type="button"
                  onClick={() => setSelectedReport(report)}
                  className={`w-full text-left p-4 transition ${
                    selectedReport?.id === report.id
                      ? "bg-pink-600/10 border-l-4 border-l-pink-500"
                      : "hover:bg-zinc-800/50"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">{getTypeIcon(report.target_type)}</div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-white truncate">
                        {report.content?.content_text ||
                          (report.content?.username ? `@${report.content.username}` : null) ||
                          report.target_type_display}
                      </p>
                      <p className="text-xs text-amber-400 mt-0.5">{report.reason_display}</p>
                      <p className="text-[11px] text-zinc-500 font-mono mt-1">
                        {new Date(report.created_at).toLocaleString("pt-BR")}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Detalhe direita */}
          {selectedReport && (
            <div className="lg:col-span-8 bg-zinc-900 rounded-2xl border border-zinc-800 overflow-hidden flex flex-col">
              <div className="p-4 border-b border-zinc-800 bg-amber-500/5 flex items-center justify-between">
                <div className="flex items-center gap-2 text-amber-400 text-sm font-bold">
                  <AlertTriangle size={15} />
                  <span>Motivo: {selectedReport.reason_display}</span>
                </div>
                {selectedReport.action_taken_display && (
                  <span className="text-xs px-2.5 py-1 rounded-full bg-zinc-800 text-zinc-300">
                    {selectedReport.action_taken_display}
                  </span>
                )}
              </div>

              <div className="p-6 space-y-5 flex-1">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-zinc-950 rounded-xl p-4 border border-zinc-800 text-xs">
                  <div>
                    <span className="block text-[10px] uppercase text-zinc-500">Denunciante</span>
                    <span className="text-white font-semibold">@{selectedReport.reporter?.username}</span>
                  </div>
                  <div>
                    <span className="block text-[10px] uppercase text-zinc-500">Tipo</span>
                    <span className="text-white font-semibold">{selectedReport.target_type_display}</span>
                  </div>
                  <div className="sm:col-span-2">
                    <span className="block text-[10px] uppercase text-zinc-500">ID do Alvo</span>
                    <span className="text-zinc-300 font-mono truncate block">{selectedReport.target_id}</span>
                  </div>
                </div>

                {selectedReport.description && (
                  <div>
                    <h4 className="text-xs uppercase tracking-wide text-zinc-400 mb-2">
                      Descrição do denunciante
                    </h4>
                    <p className="bg-zinc-950 rounded-xl p-4 text-sm text-zinc-200 border border-zinc-800">
                      {selectedReport.description}
                    </p>
                  </div>
                )}

                <div>
                  <h4 className="text-xs uppercase tracking-wide text-zinc-400 mb-2">
                    Conteúdo denunciado
                  </h4>
                  <div className="bg-zinc-950 rounded-xl p-5 border border-rose-500/20">
                    {!selectedReport.content ? (
                      <p className="text-sm text-zinc-500 italic">Conteúdo não encontrado ou já removido.</p>
                    ) : selectedReport.content.type === "user" ? (
                      <div className="flex items-center gap-3">
                        <User size={20} className="text-zinc-400" />
                        <div>
                          <p className="text-white font-semibold">@{selectedReport.content.username}</p>
                          {selectedReport.content.bio && (
                            <p className="text-xs text-zinc-400 mt-0.5">{selectedReport.content.bio}</p>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div>
                        <p className="text-sm text-zinc-100 whitespace-pre-wrap">
                          {selectedReport.content.content_text || "[Sem texto]"}
                        </p>
                        {selectedReport.content.author && (
                          <p className="text-xs text-zinc-500 mt-3">
                            Autor: @{selectedReport.content.author.username}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {activeTab === "pending" && (
                <div className="p-4 border-t border-zinc-800 bg-zinc-950/60">
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                    <button
                      type="button"
                      data-testid="report-action-ignore"
                      onClick={() => requestAction("ignore")}
                      disabled={actionLoading}
                      className="flex items-center justify-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white py-2.5 px-3 rounded-xl text-xs font-semibold transition disabled:opacity-50"
                    >
                      <Check size={14} /> Ignorar
                    </button>
                    {selectedReport.target_type !== "user" && (
                      <>
                        <button
                          type="button"
                          data-testid="report-action-hide"
                          onClick={() => requestAction("hide")}
                          disabled={actionLoading}
                          className="flex items-center justify-center gap-1.5 bg-amber-600 hover:bg-amber-500 text-white py-2.5 px-3 rounded-xl text-xs font-semibold transition disabled:opacity-50"
                        >
                          <EyeOff size={14} /> Ocultar
                        </button>
                        <button
                          type="button"
                          data-testid="report-action-remove"
                          onClick={() => requestAction("remove")}
                          disabled={actionLoading}
                          className="flex items-center justify-center gap-1.5 bg-rose-600 hover:bg-rose-500 text-white py-2.5 px-3 rounded-xl text-xs font-semibold transition disabled:opacity-50"
                        >
                          <Trash2 size={14} /> Remover
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      data-testid="report-action-ban"
                      onClick={() => requestAction("ban")}
                      disabled={actionLoading}
                      className="flex items-center justify-center gap-1.5 bg-orange-600 hover:bg-orange-500 text-white py-2.5 px-3 rounded-xl text-xs font-semibold transition disabled:opacity-50"
                    >
                      <Ban size={14} /> Banir
                    </button>
                    <button
                      type="button"
                      data-testid="report-action-ban-remove"
                      onClick={() => requestAction("ban_remove")}
                      disabled={actionLoading}
                      className="flex items-center justify-center gap-1.5 bg-rose-800 hover:bg-rose-700 text-white py-2.5 px-3 rounded-xl text-xs font-semibold transition disabled:opacity-50"
                    >
                      <Skull size={14} /> Ban + Remover
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <ConfirmModal
        variant={confirmState.variant}
        isOpen={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState((s) => ({ ...s, open: false }))}
      />
    </div>
  );
}

export default ModerationQueue;
