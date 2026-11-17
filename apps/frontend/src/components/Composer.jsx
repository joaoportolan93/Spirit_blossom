import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";

const MAX_CHARS = 3000;

export function Composer({ onPostCreated }) {
  const { t } = useTranslation();
  const [content, setContent] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");
  const [showDrafts, setShowDrafts] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [error, setError] = useState("");

  const trimmed = content.trim();
  const charsRemaining = MAX_CHARS - content.length;
  const isOverLimit = charsRemaining < 0;
  const canSubmit = trimmed.length > 0 && !isOverLimit && !isSubmitting;
  const canSaveDraft = trimmed.length > 0 && !isOverLimit && !isSavingDraft;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;

    setIsSubmitting(true);
    setError("");

    try {
      const response = await api.post("/api/posts/", {
        content_text: content,
        visibility: visibility,
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

  const handleSaveDraft = async () => {
    if (!canSaveDraft) return;
    setIsSavingDraft(true);
    setError("");
    setDraftMessage("");

    try {
      await api.post("/api/posts/drafts/", {
        content_text: content,
      });
      setDraftMessage(t("post.draft_saved"));
      setTimeout(() => setDraftMessage(""), 3000);
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.content_text?.[0] || t("errors.generic");
      setError(msg);
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleToggleDrafts = async () => {
    const nextState = !showDrafts;
    setShowDrafts(nextState);
    if (nextState) {
      setLoadingDrafts(true);
      try {
        const res = await api.get("/api/posts/drafts/");
        setDrafts(Array.isArray(res.data) ? res.data : []);
      } catch {
        // Silêncio em caso de falha transitória
      } finally {
        setLoadingDrafts(false);
      }
    }
  };

  const handleSelectDraft = (draft) => {
    setContent(draft.content_text);
    setShowDrafts(false);
  };

  const handleDeleteDraft = async (e, draftId) => {
    e.stopPropagation();
    try {
      await api.delete(`/api/posts/drafts/${draftId}/`);
      setDrafts((prev) => prev.filter((d) => d.id !== draftId));
    } catch {
      // Ignora erro
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-sm mb-5">
      <form onSubmit={handleSubmit}>
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
            className="w-full bg-zinc-950/70 border border-zinc-800/80 rounded-xl p-3 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-violet-500/60 focus:border-violet-500/50 resize-none transition"
          />
        </div>

        {error && (
          <div data-testid="composer-error" className="text-xs text-rose-500 mb-2">
            {error}
          </div>
        )}

        {draftMessage && (
          <div data-testid="draft-success" className="text-xs text-emerald-400 mb-2">
            {draftMessage}
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
          <div className="flex items-center gap-3">
            <span
              data-testid="char-count"
              className={`text-xs ${isOverLimit ? "text-rose-500 font-semibold" : "text-zinc-500"}`}
            >
              {isOverLimit
                ? t("post.too_long")
                : t("post.chars_remaining", { count: charsRemaining })}
            </span>

            <label htmlFor="composer-visibility" className="sr-only">
              {t("post.visibility")}
            </label>
            <select
              id="composer-visibility"
              data-testid="visibility-select"
              value={visibility}
              onChange={(e) => setVisibility(e.target.value)}
              className="bg-zinc-950 text-xs text-zinc-300 border border-zinc-800 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            >
              <option value="public">{t("post.visibility_public")}</option>
              <option value="circle">{t("post.visibility_circle")}</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="toggle-drafts-button"
              onClick={handleToggleDrafts}
              className="text-xs text-zinc-400 hover:text-zinc-200 px-2 py-1.5 rounded transition"
            >
              {t("post.drafts")}
            </button>

            <button
              type="button"
              data-testid="save-draft-button"
              onClick={handleSaveDraft}
              disabled={!canSaveDraft}
              className="text-xs bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed px-3 py-1.5 rounded transition"
            >
              {isSavingDraft ? "..." : t("post.save_draft")}
            </button>

            <button
              type="submit"
              data-testid="publish-button"
              disabled={!canSubmit}
              className="bg-violet-600 hover:bg-violet-500 text-white font-semibold px-5 py-1.5 rounded-xl text-sm disabled:opacity-40 disabled:cursor-not-allowed transition shadow-lg shadow-violet-900/30"
            >
              {isSubmitting ? t("post.publishing") : t("post.publish")}
            </button>
          </div>
        </div>
      </form>

      {/* Seção / Modal de Rascunhos */}
      {showDrafts && (
        <div
          data-testid="drafts-drawer"
          className="mt-4 pt-3 border-t border-zinc-800/80"
        >
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              {t("post.drafts_modal_title")}
            </h2>
            <button
              type="button"
              onClick={() => setShowDrafts(false)}
              className="text-xs text-zinc-500 hover:text-zinc-300"
            >
              ✕
            </button>
          </div>

          {loadingDrafts ? (
            <p className="text-xs text-zinc-500 py-2">Carregando rascunhos...</p>
          ) : drafts.length === 0 ? (
            <p data-testid="empty-drafts-msg" className="text-xs text-zinc-500 py-2">
              {t("post.empty_drafts")}
            </p>
          ) : (
            <div data-testid="drafts-list" className="space-y-2 max-h-48 overflow-y-auto">
              {drafts.map((draft) => (
                <div
                  key={draft.id}
                  data-testid={`draft-item-${draft.id}`}
                  onClick={() => handleSelectDraft(draft)}
                  className="flex items-center justify-between p-2 rounded bg-zinc-950/70 border border-zinc-800/60 hover:border-zinc-700 cursor-pointer transition text-xs"
                >
                  <span className="truncate max-w-[70%] text-zinc-200">
                    {draft.content_text}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-400 hover:underline">
                      {t("post.load_draft")}
                    </span>
                    <button
                      type="button"
                      data-testid={`delete-draft-${draft.id}`}
                      onClick={(e) => handleDeleteDraft(e, draft.id)}
                      className="text-rose-400 hover:text-rose-300 ml-2"
                    >
                      {t("post.delete_draft")}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
