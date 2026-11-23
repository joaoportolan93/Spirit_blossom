import {
  FaHeart,
  FaRegHeart,
  FaRegComment,
  FaComment,
  FaBookmark,
  FaRegBookmark,
} from "react-icons/fa";

/**
 * Componente centralizado para ícones de ações sociais (Coração, Balão de Fala e Marcador).
 */
export function HeartIcon({ size = 18, filled = false, className = "" }) {
  if (filled) {
    return (
      <FaHeart
        size={size}
        className={`text-rose-500 ${className}`}
        data-testid="heart-icon"
      />
    );
  }
  return (
    <FaRegHeart
      size={size}
      className={`text-zinc-400 group-hover:text-rose-500 ${className}`}
      data-testid="heart-icon"
    />
  );
}

export function SpeechBubbleIcon({ size = 18, filled = false, className = "" }) {
  if (filled) {
    return (
      <FaComment
        size={size}
        className={`text-sky-400 ${className}`}
        data-testid="speech-bubble-icon"
      />
    );
  }
  return (
    <FaRegComment
      size={size}
      className={`text-zinc-400 group-hover:text-sky-400 ${className}`}
      data-testid="speech-bubble-icon"
    />
  );
}

export function BookmarkIcon({ size = 16, filled = false, className = "" }) {
  if (filled) {
    return (
      <FaBookmark
        size={size}
        className={`text-pink-400 ${className}`}
        data-testid="bookmark-icon"
      />
    );
  }
  return (
    <FaRegBookmark
      size={size}
      className={`text-zinc-400 group-hover:text-pink-400 ${className}`}
      data-testid="bookmark-icon"
    />
  );
}

export function SocialActionIcon({ type, active = false, size = 18, className = "" }) {
  switch (type) {
    case "heart":
    case "like":
      return <HeartIcon size={size} filled={active} className={className} />;
    case "comment":
    case "reply":
      return <SpeechBubbleIcon size={size} filled={active} className={className} />;
    case "bookmark":
    case "save":
      return <BookmarkIcon size={size} filled={active} className={className} />;
    default:
      return null;
  }
}

// Aliases para compatibilidade reversa
export const SparkleIcon = HeartIcon;
export const CloudBubbleIcon = SpeechBubbleIcon;

export default {
  HeartIcon,
  SpeechBubbleIcon,
  BookmarkIcon,
  SocialActionIcon,
  SparkleIcon,
  CloudBubbleIcon,
};
