import { useTranslation } from "react-i18next";

/**
 * FeedTabs — Abas editoriais "Seguindo" e "Para você" com semântica ARIA padrão.
 *
 * @param {"following"|"for_you"} activeTab
 * @param {(tab: "following"|"for_you") => void} onTabChange
 */
export function FeedTabs({ activeTab, onTabChange }) {
  const { t } = useTranslation();

  const tabs = [
    { id: "following", label: t("feed.following", "Seguindo") },
    { id: "for_you", label: t("feed.for_you", "Para você") },
  ];

  return (
    <div
      role="tablist"
      aria-label={t("feed.title", "Feeds")}
      className="flex border-b border-zinc-800/80 mb-5"
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={isActive}
            aria-controls={`tabpanel-${tab.id}`}
            type="button"
            onClick={() => onTabChange(tab.id)}
            className={`
              relative px-5 py-3 text-sm font-medium transition-colors
              ${isActive
                ? "text-white font-semibold"
                : "text-zinc-500 hover:text-zinc-300"
              }
            `}
          >
            {tab.label}
            {isActive && (
              <span
                aria-hidden="true"
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-pink-500 rounded-full"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
