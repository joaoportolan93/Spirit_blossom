import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";

const MAX_CHARS = 3000;

export function Composer({ onPostCreated }) {
  const { t } = useTranslation();
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const trimmed = content.trim();
  const charsRemaining = MAX_CHARS - content.length;
  const isOverLimit = charsRemaining < 0;
  const canSubmit = trimmed.length > 0 && !isOverLimit && !isSubmitting;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;

    setIsSubmitting(true);
    setError("");

    try {
      const response = await api.post("/api/posts/", {
        content_text: content,
        visibility: "public",
      });
      setContent("");
      if (onPostCreated) {
        onPostCreated(response.data);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.content_text?.[0] || t("errors.generic");
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 shadow-sm mb-6">
      <div className="mb-2">
        <label htmlFor="composer-textarea" className="sr-only">
          {t("post.title")}
        </label>
        <textarea
          id="composer-textarea"
          data-testid="composer-textarea"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={t("post.placeholder")}
          rows={3}
          className="w-full bg-zinc-950/60 border border-zinc-800 rounded-lg p-3 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600 resize-none"
        />
      </div>

      {error && (
        <div data-testid="composer-error" className="text-xs text-rose-500 mb-2">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
        <span
          data-testid="char-count"
          className={`text-xs ${isOverLimit ? "text-rose-500 font-semibold" : "text-zinc-500"}`}
        >
          {isOverLimit
            ? t("post.too_long")
            : t("post.chars_remaining", { count: charsRemaining })}
        </span>

        <button
          type="submit"
          data-testid="publish-button"
          disabled={!canSubmit}
          className="bg-white text-zinc-950 font-medium px-4 py-1.5 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-zinc-200 transition"
        >
          {isSubmitting ? t("post.publishing") : t("post.publish")}
        </button>
      </div>
    </form>
  );
}
