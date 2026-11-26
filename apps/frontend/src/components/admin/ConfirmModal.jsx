import { AlertTriangle, X } from "lucide-react";

const VARIANT_STYLES = {
  danger: {
    icon: "text-rose-400",
    iconBg: "bg-rose-500/15",
    btn: "bg-rose-600 hover:bg-rose-500 text-white",
    border: "border-rose-500/30",
  },
  warning: {
    icon: "text-amber-400",
    iconBg: "bg-amber-500/15",
    btn: "bg-amber-500 hover:bg-amber-400 text-zinc-950 font-semibold",
    border: "border-amber-500/30",
  },
  default: {
    icon: "text-zinc-300",
    iconBg: "bg-zinc-800",
    btn: "bg-pink-600 hover:bg-pink-500 text-white",
    border: "border-zinc-700",
  },
};

export function ConfirmModal({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  variant = "danger",
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
}) {
  if (!isOpen) return null;

  const style = VARIANT_STYLES[variant] || VARIANT_STYLES.default;

  return (
    <div
      data-testid="admin-confirm-modal"
      className="fixed inset-0 z-[100] bg-black/75 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className={`bg-zinc-900 rounded-2xl border ${style.border} p-6 w-full max-w-md shadow-2xl`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl ${style.iconBg}`}>
              <AlertTriangle size={18} className={style.icon} />
            </div>
            <h2 className="text-lg font-bold text-white">{title}</h2>
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

        <p className="text-zinc-300 text-sm leading-relaxed mb-6 pl-12">{message}</p>

        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl transition text-sm font-medium"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            data-testid="admin-confirm-btn"
            onClick={onConfirm}
            className={`flex-1 px-4 py-2.5 rounded-xl transition text-sm font-medium ${style.btn}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmModal;
