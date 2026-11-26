import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getFollowSuggestions } from "../services/api";
import { FollowButton } from "./FollowButton";

/**
 * FollowSuggestions — Sugestões éticas e transparentes para seguir.
 * Oculta-se completamente quando não há sugestões reais (zero widgets vazios).
 */
export function FollowSuggestions({ limit = 5 }) {
  const { t } = useTranslation();
  const [suggestions, setSuggestions] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let isMounted = true;
    getFollowSuggestions(limit)
      .then((items) => {
        if (isMounted) {
          setSuggestions(Array.isArray(items) ? items : []);
        }
      })
      .catch(() => {
        if (isMounted) setSuggestions([]);
      })
      .finally(() => {
        if (isMounted) setLoaded(true);
      });

    return () => {
      isMounted = false;
    };
  }, [limit]);

  if (!loaded || suggestions.length === 0) {
    return null;
  }

  return (
    <section
      data-testid="follow-suggestions"
      aria-label={t("suggestions.title")}
      className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 space-y-3"
    >
      <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
        {t("suggestions.title")}
      </h2>

      <ul className="space-y-3">
        {suggestions.map((user) => {
          const displayName = user.display_name || user.username;
          const initial = (displayName[0] || "U").toUpperCase();

          let reasonLabel = t("suggestions.active_community");
          if (user.mutual_sample_username && user.mutual_count > 1) {
            reasonLabel = t("suggestions.followed_by_and_more", {
              username: user.mutual_sample_username,
              count: user.mutual_count - 1,
            });
          } else if (user.mutual_sample_username) {
            reasonLabel = t("suggestions.followed_by", {
              username: user.mutual_sample_username,
            });
          }

          return (
            <li
              key={user.username}
              data-testid={`suggestion-item-${user.username}`}
              className="flex items-center justify-between gap-2.5"
            >
              <Link
                to={`/profile/${user.username}`}
                className="flex items-center gap-2.5 min-w-0 flex-1 group"
              >
                <div className="w-9 h-9 rounded-full overflow-hidden bg-zinc-800 border border-zinc-700/60 flex items-center justify-center font-bold text-xs text-zinc-300 shrink-0">
                  {user.avatar ? (
                    <img
                      src={user.avatar}
                      alt={displayName}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    initial
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-zinc-100 truncate group-hover:underline">
                    {displayName}
                  </p>
                  <p className="text-xs text-zinc-400 truncate">
                    @{user.username}
                  </p>
                  <p className="text-[11px] text-zinc-500 truncate">
                    {reasonLabel}
                  </p>
                </div>
              </Link>

              <div className="shrink-0">
                <FollowButton username={user.username} isFollowing={false} />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default FollowSuggestions;
