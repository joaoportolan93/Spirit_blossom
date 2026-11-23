import { useContext } from "react";
import { Link } from "react-router-dom";
import { AuthContext } from "../hooks/useAuth";

/** useAuth seguro — não lança erro quando fora de AuthProvider. */
function useSafeAuth() {
  const ctx = useContext(AuthContext);
  return ctx ?? { user: null };
}

/**
 * UserMiniCard — Mini-card do usuário logado para a sidebar direita.
 * Exibe avatar, display_name, @username e link para o perfil.
 * Substitui os widgets vazios "Sugestões" e "Tendências".
 */
export function UserMiniCard() {
  const { user } = useSafeAuth();
  if (!user) return null;

  const displayName = user.display_name || user.username || "Você";
  const username = user.username || "";
  const avatarLetter = (displayName[0] || "U").toUpperCase();

  return (
    <Link
      to="/profile"
      className="flex items-center gap-3 p-3 rounded-2xl border border-zinc-800/60 bg-zinc-900 hover:border-zinc-700/80 hover:bg-zinc-800/50 transition-all group"
      aria-label={`Ver perfil de ${displayName}`}
    >
      {/* Avatar */}
      <div className="w-10 h-10 rounded-full overflow-hidden bg-zinc-800 border-2 border-zinc-700/50 flex items-center justify-center font-bold text-sm text-zinc-300 shrink-0">
        {user.avatar ? (
          <img
            src={user.avatar}
            alt={displayName}
            className="w-full h-full object-cover"
          />
        ) : (
          avatarLetter
        )}
      </div>

      {/* Info */}
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-semibold text-zinc-100 truncate group-hover:text-white transition">
          {displayName}
        </span>
        {username && (
          <span className="text-xs text-zinc-500 truncate">
            @{username}
          </span>
        )}
      </div>
    </Link>
  );
}
