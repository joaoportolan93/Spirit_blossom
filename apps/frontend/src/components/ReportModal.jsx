import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Flag, X, CheckCircle2 } from "lucide-react";
import { createReport } from "../services/api";

const REASON_KEYS = [
  "inappropriate",
  "harassment",
  "spam",
  "hate_speech",
  "illegal",
  "other",
];

export function ReportModal({ isOpen, targetType, targetId, targetLabel = "", onClose }) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("inappropriate");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen) return null;

  const handleClose = (e) => {
    if (e?.stopPropagation) e.stopPropagation();
    setError("");
    setSubmitted(false);
    setDescription("");
    setReason("inappropriate");
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (submitting) return;

    setError("");
    setSubmitting(true);
    try {
      await createReport({
        target_type: targetType,
        target_id: targetId,
        reason,
        description: description.trim(),
      });
      setSubmitted(true);
    } catch (err) {
      setError(
        err?.response?.data?.detail || t("report.error", "Não foi possível enviar a denúncia.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      data-testid="report-modal"
      className="fixed inset-0 z-[100] bg-black/75 flex items-center justify-center p-4"
      onClick={handleClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-rose-500/15 text-rose-400">
              <Flag size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">
                {t("report.title", "Enviar denúncia")}
              </h2>
              {targetLabel && <p className="text-xs text-zinc-400">{targetLabel}</p>}
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="text-zinc-400 hover:text-white transition"
            aria-label={t("report.close", "Fechar")}
          >
            <X size={18} />
          </button>
        </div>

        {submitted ? (
          <div className="py-4 text-center space-y-4" data-testid="report-success">
            <CheckCircle2 className="mx-auto text-emerald-400" size={40} />
            <p className="text-sm text-zinc-200">
              {t("report.success", "Denúncia enviada com sucesso.")}
            </p>
            <button
              type="button"
              onClick={handleClose}
              className="w-full py-2.5 rounded-xl bg-pink-600 hover:bg-pink-500 text-white text-sm font-semibold transition"
            >
              {t("report.close", "Fechar")}
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-xs text-zinc-400">
              {t("report.subtitle", "Ajude a manter a comunidade segura.")}
            </p>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                {t("report.reasonLabel", "Motivo da denúncia")}
              </label>
              <select
                data-testid="report-reason-select"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-xl px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-pink-500"
              >
                {REASON_KEYS.map((key) => (
                  <option key={key} value={key}>
                    {t(`report.reasons.${key}`, key)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                {t("report.descriptionLabel", "Detalhes adicionais (opcional)")}
              </label>
              <textarea
                data-testid="report-description-input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                maxLength={1000}
                placeholder={t(
                  "report.descriptionPlaceholder",
                  "Descreva o contexto para ajudar na análise..."
                )}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-xl p-3 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-pink-500 resize-none"
              />
            </div>

            {error && (
              <p
                data-testid="report-error"
                className="text-xs text-rose-400 bg-rose-950/40 border border-rose-800/60 rounded-lg p-2.5"
              >
                {error}
              </p>
            )}

            <div className="flex gap-3 pt-1">
              <button
                type="button"
                onClick={handleClose}
                className="flex-1 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-medium transition"
              >
                {t("report.cancel", "Cancelar")}
              </button>
              <button
                type="submit"
                disabled={submitting}
                data-testid="report-submit-btn"
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white text-sm font-semibold transition"
              >
                {submitting
                  ? t("report.submitting", "Enviando...")
                  : t("report.submit", "Enviar denúncia")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default ReportModal;
