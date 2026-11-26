import { Link } from "react-router-dom";

// Tokeniza URLs, e-mails, @menções ([a-zA-Z0-9]{3,30}) e #hashtags (Unicode alfanumérico + _, 2..50).
const ENTITY_REGEX =
  /((?:https?|ftp):\/\/(?:[^\s<>()]|\([^\s<>()]*\))+|www\.(?:[^\s<>()]|\([^\s<>()]*\))+)|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})|(@[a-zA-Z0-9]{3,30})(?![a-zA-Z0-9_])|(#[\p{L}\p{N}_]{2,50})(?![\p{L}\p{N}_])/gu;

const HAS_LETTER_REGEX = /\p{L}/u;
const INVALID_MENTION_PREFIX = /[\p{L}\p{N}._%+\-/]/u;
const INVALID_HASHTAG_PREFIX = /[\p{L}\p{N}_&/]/u;

function stopEvent(e) {
  e.stopPropagation();
}

/**
 * RichText — Renderiza texto puro com links seguros para @username e #hashtag.
 * Zero dangerouslySetInnerHTML (100% elementos React — imune a XSS).
 */
export function RichText({ text }) {
  if (!text) return null;
  const normalizedText = text.normalize("NFC");

  const nodes = [];
  let lastIndex = 0;
  ENTITY_REGEX.lastIndex = 0;

  let match;
  while ((match = ENTITY_REGEX.exec(normalizedText)) !== null) {
    const start = match.index;
    const full = match[0];
    const isUrl = Boolean(match[1]);
    const isEmail = Boolean(match[2]);
    const mentionToken = match[3];
    const hashtagToken = match[4];

    if (start > lastIndex) {
      nodes.push(normalizedText.slice(lastIndex, start));
    }

    if (isUrl || isEmail) {
      nodes.push(full);
    } else if (mentionToken) {
      const prevChar = start > 0 ? normalizedText[start - 1] : "";
      if (prevChar && INVALID_MENTION_PREFIX.test(prevChar)) {
        nodes.push(full);
      } else {
        const username = mentionToken.slice(1).toLowerCase();
        nodes.push(
          <Link
            key={`m-${start}`}
            to={`/profile/${username}`}
            onClick={stopEvent}
            className="text-pink-400 hover:underline font-medium"
          >
            {mentionToken}
          </Link>
        );
      }
    } else if (hashtagToken) {
      const prevChar = start > 0 ? normalizedText[start - 1] : "";
      const tag = hashtagToken.slice(1);
      const normalized = tag.toLowerCase().normalize("NFC");
      if (
        (prevChar && INVALID_HASHTAG_PREFIX.test(prevChar)) ||
        normalized.length < 2 ||
        normalized.length > 50 ||
        !HAS_LETTER_REGEX.test(normalized)
      ) {
        nodes.push(full);
      } else {
        nodes.push(
          <Link
            key={`h-${start}`}
            to={`/explore?hashtag=${encodeURIComponent(normalized)}`}
            onClick={stopEvent}
            className="text-pink-400 hover:underline font-medium"
          >
            {hashtagToken}
          </Link>
        );
      }
    }

    lastIndex = start + full.length;
  }

  if (lastIndex < normalizedText.length) {
    nodes.push(normalizedText.slice(lastIndex));
  }

  return <>{nodes}</>;
}

export default RichText;
