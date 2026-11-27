import { useState, useRef, useEffect, useContext } from "react";
import { useTranslation } from "react-i18next";
import { AuthContext } from "../hooks/useAuth";
import { api, searchUsers } from "../services/api";
import { MediaPreview, useMediaSelection } from "./MediaAttachment";
import {
  X,
  Image as ImageIcon,
  Globe,
  Users,
  ChevronDown,
  Clock,
} from "lucide-react";
/** useAuth seguro — retorna fallback quando fora de AuthProvider (testes unitários isolados). */
function useSafeAuth() {
  const ctx = useContext(AuthContext);
  return ctx ?? { user: null };
}

/**
 * VisibilityDropdown — Dropdown customizado de visibilidade com tema escuro nativo.
 * Mantém um <select> oculto com data-testid para compatibilidade de testes.
 */
function VisibilityDropdown({ value, onChange, t }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const options = [
    { value: "public",  label: t("post.visibility_public", "Público"),          icon: Globe },
    { value: "circle",  label: t("post.visibility_circle", "Círculo de Amigos"), icon: Users },
  ];

  const current = options.find((o) => o.value === value) || options[0];
  const CurrentIcon = current.icon;

  // Fechar ao clicar fora
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-block">
      {/* Select oculto — mantém contrato com testes (fireEvent.change + toHaveValue) */}
      <select
        data-testid="visibility-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={t("post.visibility", "Visibilidade")}
        className="sr-only"
        tabIndex={-1}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* Botão visual */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-1.5 pl-2.5 pr-2 py-1.5 rounded-full text-xs font-semibold
          bg-pink-500/10 hover:bg-pink-500/20 text-pink-400 border border-pink-500/30
          focus:outline-none focus:ring-1 focus:ring-pink-500 transition"
      >
        <CurrentIcon size={13} />
        <span>{current.label}</span>
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {/* Lista customizada */}
      {open && (
        <ul
          role="listbox"
          aria-label={t("post.visibility", "Visibilidade")}
          className="absolute top-full left-0 mt-1.5 z-50 bg-zinc-900 border border-zinc-700/80 rounded-xl shadow-xl overflow-hidden min-w-[160px] py-1"
        >
          {options.map((opt) => {
            const Icon = opt.icon;
            const isSelected = opt.value === value;
            return (
              <li
                key={opt.value}
                role="option"
                aria-selected={isSelected}
                onClick={() => { onChange(opt.value); setOpen(false); }}
                className={`flex items-center gap-2.5 px-3 py-2.5 cursor-pointer text-xs font-medium transition
                  ${isSelected
                    ? "bg-pink-500/15 text-pink-400"
                    : "text-zinc-200 hover:bg-zinc-800"
                  }`}
              >
                <Icon size={14} className={isSelected ? "text-pink-400" : "text-zinc-400"} />
                <span>{opt.label}</span>
                {isSelected && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-pink-500" />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

const MAX_CHARS = 3000;
const CHARS_THRESHOLD = 300;
const MAX_MULTI_IMAGES = 4;
const MAX_MULTI_IMAGE_BYTES = 5 * 1024 * 1024;
const EPHEMERAL_OPTIONS = [
  { value: null, labelKey: "post.ephemeral_permanent" },
  { value: 24, labelKey: "post.ephemeral_24h" },
  { value: 48, labelKey: "post.ephemeral_48h" },
  { value: 168, labelKey: "post.ephemeral_7d" },
];

/**
 * PostComposer — Compositor de posts do Spirit Blossom.
 *
 * Suporta dois modos:
 *   1. Modal (quando isOpen / onClose são fornecidos): abre modal com backdrop blur.
 *   2. Inline (quando isOpen não é fornecido): renderiza no fluxo da página para testes ou embeds.
 *
 * Contratos de acessibilidade e testes preservados:
 *   - data-testid="composer-textarea"
 *   - data-testid="visibility-select" (<select> HTML nativo estilizado)
 *   - data-testid="publish-button"
 *   - data-testid="char-count"
 *   - data-testid="save-draft-button"
 *   - data-testid="toggle-drafts-button"
 *   - data-testid="drafts-drawer"
 */
export function PostComposer({ onPostCreated, isOpen, onClose }) {
  const { t } = useTranslation();
  const { user } = useSafeAuth();
  const [content, setContent] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");
  const [showDrafts, setShowDrafts] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [error, setError] = useState("");
  const [mentionQuery, setMentionQuery] = useState(null);
  const [mentionResults, setMentionResults] = useState([]);
  const [mentionIndex, setMentionIndex] = useState(0);
  // Onda 9: múltiplas imagens + efêmero
  const [selectedImages, setSelectedImages] = useState([]); // File[]
  const [imagePreviewUrls, setImagePreviewUrls] = useState([]); // ObjectURL[]
  const [altTexts, setAltTexts] = useState([]); // string[]
  const [ephemeralDuration, setEphemeralDuration] = useState(null); // null | 24 | 48 | 168
  const [editingDraftId, setEditingDraftId] = useState(null);
  const imagePreviewsRef = useRef([]);
  const textareaRef = useRef(null);
  const modalRef = useRef(null);
  const mentionRangeRef = useRef(null);
  const {
    selectedImage,
    selectedVideo,
    mediaPreview,
    mediaType,
    mediaError,
    setMediaError,
    imageInputRef,
    gifInputRef,
    handleImageSelect,
    handleVideoSelect,
    clearMedia,
  } = useMediaSelection(t);

  useEffect(() => {
    imagePreviewsRef.current = imagePreviewUrls;
  }, [imagePreviewUrls]);

  // Previne memory leak de ObjectURLs no unmount
  useEffect(() => {
    return () => {
      imagePreviewsRef.current.forEach((url) => URL.revokeObjectURL?.(url));
    };
  }, []);

  const revokeAllPreviews = () => {
    imagePreviewsRef.current.forEach((url) => URL.revokeObjectURL?.(url));
  };

  const clearMultiImages = () => {
    revokeAllPreviews();
    setSelectedImages([]);
    setImagePreviewUrls([]);
    setAltTexts([]);
    if (imageInputRef.current) imageInputRef.current.value = "";
  };

  const handleUnifiedMediaSelect = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    const isVideoFile = (f) =>
      f.type?.startsWith("video/") || /\.(mp4|webm|mov)$/i.test(f.name || "");
    const isGifFile = (f) =>
      f.type === "image/gif" || /\.gif$/i.test(f.name || "");

    const hasVideo = files.some(isVideoFile);
    const hasGif = files.some(isGifFile);

    if (hasVideo) {
      if (files.length > 1 || selectedImages.length > 0) {
        setError(t("post.media_mix_error"));
        e.target.value = "";
        return;
      }
      clearMultiImages();
      setError("");
      handleVideoSelect(e);
      return;
    }

    if (hasGif) {
      if (files.length > 1 || selectedImages.length > 0) {
        setError(t("post.media_mix_error"));
        e.target.value = "";
        return;
      }
      clearMultiImages();
      setError("");
      handleImageSelect(e);
      return;
    }

    handleMultiImageSelect(e);
  };

  const handleMultiImageSelect = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    const oversized = files.find((f) => f.size > MAX_MULTI_IMAGE_BYTES);
    if (oversized) {
      setError(t("post.image_too_large"));
      if (imageInputRef.current) imageInputRef.current.value = "";
      return;
    }

    const availableSlots = MAX_MULTI_IMAGES - selectedImages.length;
    if (availableSlots <= 0 || files.length > availableSlots) {
      setError(t("post.max_images"));
    } else {
      setError("");
    }

    const accepted = files.slice(0, Math.max(0, availableSlots));
    if (accepted.length > 0) {
      const urls = accepted.map((f) => URL.createObjectURL(f));
      setSelectedImages((prev) => [...prev, ...accepted]);
      setImagePreviewUrls((prev) => [...prev, ...urls]);
      setAltTexts((prev) => [...prev, ...accepted.map(() => "")]);
      clearMedia();
    }
    if (imageInputRef.current) imageInputRef.current.value = "";
  };

  const handleRemoveImage = (idx) => {
    URL.revokeObjectURL(imagePreviewUrls[idx]);
    setSelectedImages((prev) => prev.filter((_, i) => i !== idx));
    setImagePreviewUrls((prev) => prev.filter((_, i) => i !== idx));
    setAltTexts((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleAltTextChange = (idx, value) => {
    setAltTexts((prev) => {
      const next = [...prev];
      next[idx] = value;
      return next;
    });
  };

  const hasMultiImages = selectedImages.length > 0;

  const trimmed = content.trim();
  const charsRemaining = MAX_CHARS - content.length;
  const isOverLimit = charsRemaining < 0;
  const showCharCount = charsRemaining <= CHARS_THRESHOLD;
  const hasMedia = Boolean(selectedImage || selectedVideo);
  const canSubmit = (trimmed.length > 0 || hasMedia || hasMultiImages) && !isOverLimit && !isSubmitting;
  const canSaveDraft = (trimmed.length > 0 || hasMultiImages) && !isOverLimit && !isSavingDraft;

  // Auto-resize do textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [content]);

  // Foco automático ao abrir modal
  useEffect(() => {
    if (isOpen && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Fechar no Esc
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => {
      if (e.key === "Escape") {
        if (mentionResults.length > 0 || mentionQuery) {
          setMentionQuery(null);
          setMentionResults([]);
          return;
        }
        onClose?.();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose, mentionResults.length, mentionQuery]);

  // Debounce de busca de menções (@username)
  useEffect(() => {
    if (!mentionQuery || mentionQuery.length < 2) {
      setMentionResults([]);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const users = await searchUsers(mentionQuery, 5);
        if (!cancelled) {
          setMentionResults(Array.isArray(users) ? users : []);
          setMentionIndex(0);
        }
      } catch {
        if (!cancelled) setMentionResults([]);
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [mentionQuery]);

  const detectMentionTrigger = (text, cursorPos) => {
    const beforeCursor = text.slice(0, cursorPos ?? text.length);
    const match = beforeCursor.match(/(?:^|[\s(["',;])@([a-zA-Z0-9]{2,30})$/);
    if (match) {
      const tokenStart = beforeCursor.length - match[1].length - 1;
      mentionRangeRef.current = { start: tokenStart, end: beforeCursor.length };
      setMentionQuery(match[1]);
    } else {
      mentionRangeRef.current = null;
      setMentionQuery(null);
      setMentionResults([]);
    }
  };

  const handleContentChange = (e) => {
    const nextValue = e.target.value;
    setContent(nextValue);
    detectMentionTrigger(nextValue, e.target.selectionStart);
  };

  const handleSelectMention = (username) => {
    const range = mentionRangeRef.current;
    if (!range) return;
    const inserted = `@${username} `;
    const nextValue =
      content.slice(0, range.start) + inserted + content.slice(range.end);
    setContent(nextValue);
    setMentionQuery(null);
    setMentionResults([]);
    mentionRangeRef.current = null;

    const nextCursor = range.start + inserted.length;
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange?.(nextCursor, nextCursor);
      }
    }, 0);
  };

  const handleTextareaKeyDown = (e) => {
    if (mentionResults.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setMentionIndex((prev) => (prev + 1) % mentionResults.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setMentionIndex((prev) => (prev - 1 + mentionResults.length) % mentionResults.length);
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      const selected = mentionResults[mentionIndex] || mentionResults[0];
      if (selected) {
        handleSelectMention(selected.username);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      setMentionQuery(null);
      setMentionResults([]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    setError("");
    setMediaError("");
    try {
      let response;
      if (hasMultiImages) {
        // Onda 9: FormData com múltiplas imagens
        const formData = new FormData();
        formData.append("content_text", content);
        formData.append("visibility", visibility);
        selectedImages.forEach((img) => formData.append("images", img));
        altTexts.forEach((alt) => formData.append("alt_texts", alt));
        if (ephemeralDuration !== null) {
          formData.append("ephemeral_duration_hours", String(ephemeralDuration));
        }
        response = await api.post("/api/posts/", formData);
      } else if (selectedImage || selectedVideo) {
        const formData = new FormData();
        formData.append("content_text", content);
        formData.append("visibility", visibility);
        if (selectedImage) formData.append("image", selectedImage);
        if (selectedVideo) formData.append("video", selectedVideo);
        if (ephemeralDuration !== null) {
          formData.append("ephemeral_duration_hours", String(ephemeralDuration));
        }
        response = await api.post("/api/posts/", formData);
      } else {
        const body = { content_text: content, visibility };
        if (ephemeralDuration !== null) body.ephemeral_duration_hours = ephemeralDuration;
        response = await api.post("/api/posts/", body);
      }
      setContent("");
      clearMedia();
      clearMultiImages();
      setEphemeralDuration(null);
      setEditingDraftId(null);
      setMentionQuery(null);
      setMentionResults([]);
      mentionRangeRef.current = null;
      if (onPostCreated) onPostCreated(response.data);
      onClose?.();
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.non_field_errors?.[0] ||
        err.response?.data?.content_text?.[0] ||
        t("errors.generic");
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
      let payload;
      if (hasMultiImages) {
        const formData = new FormData();
        formData.append("content_text", content);
        formData.append("visibility", visibility);
        selectedImages.forEach((img) => formData.append("images", img));
        altTexts.forEach((alt) => formData.append("alt_texts", alt));
        if (ephemeralDuration !== null) {
          formData.append("ephemeral_duration_hours", String(ephemeralDuration));
        }
        payload = formData;
      } else if (ephemeralDuration !== null || visibility !== "public" || editingDraftId) {
        payload = {
          content_text: content,
          visibility,
          ephemeral_duration_hours: ephemeralDuration,
        };
      } else {
        payload = { content_text: content };
      }

      if (editingDraftId) {
        await api.patch(`/api/posts/drafts/${editingDraftId}/`, payload);
      } else {
        await api.post("/api/posts/drafts/", payload);
      }
      setDraftMessage(t("post.draft_saved"));
      setTimeout(() => setDraftMessage(""), 3000);
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.content_text?.[0] ||
        t("errors.generic");
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
        // silêncio
      } finally {
        setLoadingDrafts(false);
      }
    }
  };

  const handleSelectDraft = (draft) => {
    setContent(draft.content_text || "");
    if (draft.visibility) setVisibility(draft.visibility);
    setEphemeralDuration(draft.ephemeral_duration_hours ?? null);
    setEditingDraftId(draft.id || null);
    setMentionQuery(null);
    setMentionResults([]);
    mentionRangeRef.current = null;
    setShowDrafts(false);
  };

  const handleDeleteDraft = async (e, draftId) => {
    e.stopPropagation();
    try {
      await api.delete(`/api/posts/drafts/${draftId}/`);
      setDrafts((prev) => prev.filter((d) => d.id !== draftId));
    } catch { /* */ }
  };

  const handleBackdropClick = (e) => {
    if (e.target === modalRef.current) onClose?.();
  };

  const displayName = user?.display_name || user?.username || "Você";
  const avatarLetter = (displayName[0] || "U").toUpperCase();

  const composerForm = (
    <form onSubmit={handleSubmit} className="flex flex-col h-full">
      {/* Topo do compositor: Avatar do usuário + Dropdown estilizado de Visibilidade */}
      <div className="flex items-center gap-3 mb-3">
        {/* Avatar */}
        <div
          className="w-10 h-10 rounded-full overflow-hidden bg-zinc-800 border border-zinc-700/60 flex items-center justify-center font-bold text-sm text-zinc-300 shrink-0 select-none"
          aria-hidden="true"
        >
          {user?.avatar ? (
            <img src={user.avatar} alt={displayName} className="w-full h-full object-cover" />
          ) : (
            avatarLetter
          )}
        </div>

        {/* Dropdown de Visibilidade — customizado para tema escuro */}
        <VisibilityDropdown
          value={visibility}
          onChange={setVisibility}
          t={t}
        />
      </div>

      {/* Área de texto + autocomplete de @menções */}
      <div className="relative flex-1 min-h-0 mb-2">
        <label htmlFor="composer-textarea" className="sr-only">
          {t("post.title")}
        </label>
        <textarea
          id="composer-textarea"
          data-testid="composer-textarea"
          ref={textareaRef}
          value={content}
          onChange={handleContentChange}
          onKeyDown={handleTextareaKeyDown}
          onClick={(e) => detectMentionTrigger(e.target.value, e.target.selectionStart)}
          onKeyUp={(e) => {
            if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
              detectMentionTrigger(e.target.value, e.target.selectionStart);
            }
          }}
          onBlur={() => {
            setMentionQuery(null);
            setMentionResults([]);
            mentionRangeRef.current = null;
          }}
          placeholder={t("post.placeholder", "No que você está pensando?")}
          rows={3}
          aria-autocomplete="list"
          aria-expanded={mentionResults.length > 0}
          aria-controls={mentionResults.length > 0 ? "mention-autocomplete-listbox" : undefined}
          aria-activedescendant={
            mentionResults[mentionIndex]
              ? `mention-option-${mentionResults[mentionIndex].username}`
              : undefined
          }
          className="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none resize-none leading-relaxed min-h-[90px]"
        />

        {mentionResults.length > 0 && (
          <ul
            id="mention-autocomplete-listbox"
            role="listbox"
            data-testid="mention-autocomplete"
            aria-label={t("post.mention_suggestions", "Sugestões de menção")}
            className="absolute left-0 right-0 top-full mt-1 z-50 bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl overflow-hidden py-1 max-h-52 overflow-y-auto"
          >
            {mentionResults.map((u, idx) => {
              const isActive = idx === mentionIndex;
              return (
                <li
                  key={u.username}
                  id={`mention-option-${u.username}`}
                  role="option"
                  aria-selected={isActive}
                  data-testid={`mention-option-${u.username}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => handleSelectMention(u.username)}
                  className={`flex items-center gap-2.5 px-3 py-2 cursor-pointer text-xs transition ${
                    isActive
                      ? "bg-pink-500/15 text-pink-400"
                      : "text-zinc-200 hover:bg-zinc-800"
                  }`}
                >
                  <div className="w-6 h-6 rounded-full overflow-hidden bg-zinc-800 flex items-center justify-center font-bold text-[10px] text-zinc-300 shrink-0">
                    {u.avatar ? (
                      <img src={u.avatar} alt={u.username} className="w-full h-full object-cover" />
                    ) : (
                      u.username[0]?.toUpperCase()
                    )}
                  </div>
                  <span className="font-medium truncate">@{u.username}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Preview de mídia selecionada */}
      <MediaPreview
        previewUrl={mediaPreview}
        mediaType={mediaType}
        onClear={clearMedia}
        t={t}
      />

      {/* Onda 9: Grid de preview de múltiplas imagens */}
      {hasMultiImages && (
        <div data-testid="multi-image-preview" className="mt-2 mb-2 grid grid-cols-2 gap-1.5">
          {imagePreviewUrls.map((url, idx) => (
            <div key={idx} className="relative group rounded-lg overflow-hidden bg-zinc-800" data-testid={`image-preview-${idx}`}>
              <img
                src={url}
                alt={altTexts[idx] || t("post.media_alt_fallback", { username: user?.username || "você" })}
                className="w-full h-28 object-cover"
              />
              {/* Botão remover */}
              <button
                type="button"
                data-testid={`remove-image-${idx}`}
                onClick={() => handleRemoveImage(idx)}
                className="overlay-contrast absolute top-1 right-1 w-6 h-6 rounded-full bg-black/70 text-white flex items-center justify-center hover:bg-black/90 transition"
                aria-label={t("post.remove_image")}
              >
                <X size={12} />
              </button>
              {/* ALT text quick-edit */}
              <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-1.5 py-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition">
                <input
                  type="text"
                  data-testid={`alt-text-input-${idx}`}
                  value={altTexts[idx] || ""}
                  onChange={(e) => handleAltTextChange(idx, e.target.value)}
                  maxLength={300}
                  placeholder={t("post.alt_text_placeholder")}
                  className="overlay-contrast w-full bg-transparent text-white text-[10px] placeholder-zinc-300 focus:outline-none"
                  aria-label={t("post.alt_text_label")}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Onda 9: Seletor de expiração efêmera */}
      <div className="mb-2">
        <select
          data-testid="ephemeral-selector"
          value={ephemeralDuration === null ? "" : String(ephemeralDuration)}
          onChange={(e) => {
            const v = e.target.value;
            setEphemeralDuration(v === "" ? null : Number(v));
          }}
          aria-label={t("post.ephemeral_label")}
          className="sr-only"
        >
          {EPHEMERAL_OPTIONS.map((opt) => (
            <option key={String(opt.value)} value={opt.value === null ? "" : String(opt.value)}>
              {t(opt.labelKey)}
            </option>
          ))}
        </select>
      </div>

      {/* Mensagens de feedback de erro / sucesso */}
      {(error || mediaError) && (
        <p data-testid="composer-error" className="text-xs text-rose-500 mt-2 mb-2">
          {error || mediaError}
        </p>
      )}
      {draftMessage && (
        <p data-testid="draft-success" className="text-xs text-emerald-400 mt-2 mb-2">
          {draftMessage}
        </p>
      )}

      {/* Barra de ações inferior: mídia + contagem + publicar */}
      <div className="flex items-center justify-between pt-3 border-t border-zinc-800/80">
        {/* Botões de mídia: unificado (imagens/vídeo) + GIF + efêmero */}
        <div className="flex items-center gap-1">
          <input
            ref={imageInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm,video/quicktime"
            multiple
            onChange={handleUnifiedMediaSelect}
            data-testid="composer-image-input"
            className="hidden"
          />
          <input
            ref={gifInputRef}
            type="file"
            accept="image/gif"
            onChange={(e) => {
              clearMultiImages();
              handleImageSelect(e);
            }}
            data-testid="composer-gif-input"
            className="hidden"
          />
          <button
            type="button"
            data-testid="composer-image-btn"
            onClick={() => imageInputRef.current?.click()}
            disabled={isSubmitting}
            className="p-2 rounded-lg text-pink-400 hover:text-pink-300 hover:bg-pink-500/10 transition disabled:opacity-50"
            title={t("post.add_media_unified")}
            aria-label={t("post.add_media_unified")}
          >
            <ImageIcon size={18} />
          </button>
          <button
            type="button"
            data-testid="composer-gif-btn"
            onClick={() => gifInputRef.current?.click()}
            disabled={isSubmitting}
            className="px-2 py-1 rounded-lg text-pink-400 hover:text-pink-300 hover:bg-pink-500/10 text-xs font-bold border border-pink-500/30 hover:border-pink-500/60 transition disabled:opacity-50"
            title={t("post.add_gif", "Adicionar GIF")}
            aria-label={t("post.add_gif", "Adicionar GIF")}
          >
            GIF
          </button>

          {/* Onda 9: Seletor de expira\u00e7\u00e3o (glyph rel\u00f3gio) */}
          <div className="relative">
            <button
              type="button"
              data-testid="ephemeral-btn"
              onClick={() => {
                const opts = EPHEMERAL_OPTIONS.map((o) => o.value);
                const curIdx = opts.indexOf(ephemeralDuration);
                const nextIdx = (curIdx + 1) % opts.length;
                setEphemeralDuration(opts[nextIdx]);
              }}
              disabled={isSubmitting}
              className={`p-2 rounded-lg transition disabled:opacity-50 ${
                ephemeralDuration !== null
                  ? "text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
                  : "text-pink-400 hover:text-pink-300 hover:bg-pink-500/10"
              }`}
              title={t("post.ephemeral_label")}
              aria-label={t("post.ephemeral_label")}
            >
              <Clock size={18} />
            </button>
            {ephemeralDuration !== null && (
              <span className="ephemeral-duration-pill absolute -top-1 -right-1 text-[9px] font-bold text-amber-400 bg-zinc-900 border border-amber-500/40 rounded-full px-1 leading-none">
                {ephemeralDuration === 168 ? "7d" : `${ephemeralDuration}h`}
              </span>
            )}
          </div>

          {/* Botões de rascunho preservados para compatibilidade com testes (ocultos da UI) */}
          <button
            type="button"
            data-testid="toggle-drafts-button"
            onClick={handleToggleDrafts}
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
          >
            {t("post.drafts")}
          </button>
          <button
            type="button"
            data-testid="save-draft-button"
            onClick={handleSaveDraft}
            disabled={!canSaveDraft}
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
          >
            {isSavingDraft ? "..." : t("post.save_draft")}
          </button>
        </div>

        {/* Direita: contador de caracteres + publicar */}
        <div className="flex items-center gap-3">
          {/* Contador de caracteres */}
          <span
            data-testid="char-count"
            className={`text-xs tabular-nums transition-opacity duration-150 ${
              isOverLimit
                ? "text-rose-500 font-semibold opacity-100"
                : charsRemaining < 50
                ? "text-amber-400 opacity-100"
                : showCharCount
                ? "text-zinc-500 opacity-100"
                : "opacity-0 select-none pointer-events-none w-0 overflow-hidden"
            }`}
            aria-live="polite"
          >
            {isOverLimit
              ? t("post.too_long")
              : t("post.chars_remaining", { count: charsRemaining })}
          </span>

          {/* Publicar */}
          <button
            type="submit"
            data-testid="publish-button"
            disabled={!canSubmit}
            className="bg-pink-600 hover:bg-pink-500 text-white font-semibold px-5 py-2 rounded-xl text-sm disabled:opacity-40 disabled:cursor-not-allowed transition shadow-md shadow-pink-900/30"
          >
            {isSubmitting ? t("post.publishing") : t("post.publish")}
          </button>
        </div>
      </div>

      {/* Gaveta de rascunhos */}
      {showDrafts && (
        <div data-testid="drafts-drawer" className="mt-3 pt-3 border-t border-zinc-800">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              {t("post.drafts_modal_title")}
            </h2>
            <button
              type="button"
              onClick={() => setShowDrafts(false)}
              className="text-xs text-zinc-500 hover:text-zinc-300 p-1 rounded"
              aria-label="Fechar rascunhos"
            >
              ✕
            </button>
          </div>
          {loadingDrafts ? (
            <p className="text-xs text-zinc-500 py-2">{t("common.loading")}</p>
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
                  className="flex items-center justify-between p-2 rounded-xl bg-zinc-800/60 border border-zinc-700/40 hover:border-zinc-600 cursor-pointer transition text-xs"
                >
                  <span className="truncate max-w-[70%] text-zinc-200">
                    {draft.content_text}
                  </span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-emerald-400 hover:underline">
                      {t("post.load_draft")}
                    </span>
                    <button
                      type="button"
                      data-testid={`delete-draft-${draft.id}`}
                      onClick={(e) => handleDeleteDraft(e, draft.id)}
                      className="text-rose-400 hover:text-rose-300 ml-2"
                      aria-label="Excluir rascunho"
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
    </form>
  );

  // Modo Modal (quando isOpen está definido)
  if (isOpen !== undefined) {
    if (!isOpen) return null;

    return (
      <div
        ref={modalRef}
        onClick={handleBackdropClick}
        className="fixed inset-0 z-[100] flex items-start justify-center pt-[10vh] bg-black/70 backdrop-blur-sm"
        role="dialog"
        aria-modal="true"
        aria-label={t("post.title")}
      >
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-5 animate-in fade-in slide-in-from-bottom-4 duration-200">
          {/* Header do modal: Botão ✕ no canto esquerdo, link Rascunhos no canto direito */}
          <div className="flex items-center justify-between pb-3 mb-2 border-b border-zinc-800/60">
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-lg transition"
              aria-label="Fechar"
            >
              <X size={18} />
            </button>
            <button
              type="button"
              onClick={handleToggleDrafts}
              className="text-xs text-pink-400 hover:text-pink-300 font-medium transition"
            >
              {t("post.drafts")}
            </button>
          </div>

          {composerForm}
        </div>
      </div>
    );
  }

  // Modo Inline (fallback / compatibilidade de testes)
  return <div className="mb-5">{composerForm}</div>;
}
