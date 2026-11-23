import { useTranslation } from "react-i18next";

/**
 * EmptyFeedState — Estado vazio estilizado para o feed.
 *
 * @param {"following"|"explore"} tab
 */
export function EmptyFeedState({ tab = "following" }) {
  const { t } = useTranslation();

  const message =
    tab === "following"
      ? t("feed.empty_poetic", "Ainda quieto por aqui. Siga alguém para ver o que está florescendo. 🌸")
      : t("explore.empty", "Nenhuma publicação para explorar no momento.");

  return (
    <div
      data-testid={tab === "following" ? "feed-empty" : "empty-explore"}
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center py-16 px-6 text-center bg-zinc-900/40 border border-zinc-800/40 rounded-2xl"
    >
      <p className="text-zinc-400 text-sm leading-relaxed max-w-xs">{message}</p>
    </div>
  );
}
