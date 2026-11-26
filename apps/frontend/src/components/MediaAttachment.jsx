import { useState, useRef, useEffect, useCallback } from "react";
import { X } from "lucide-react";

export const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;
export const MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024;

/**
 * Hook reutilizável para seleção, validação e preview de imagem, GIF ou vídeo.
 */
export function useMediaSelection(t) {
  const [selectedImage, setSelectedImage] = useState(null);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [mediaPreview, setMediaPreview] = useState(null);
  const [mediaType, setMediaType] = useState(null);
  const [mediaError, setMediaError] = useState("");

  const imageInputRef = useRef(null);
  const gifInputRef = useRef(null);
  const videoInputRef = useRef(null);
  const previewRef = useRef(null);

  useEffect(() => {
    previewRef.current = mediaPreview;
  }, [mediaPreview]);

  useEffect(() => {
    return () => {
      if (previewRef.current && typeof URL.revokeObjectURL === "function") {
        URL.revokeObjectURL(previewRef.current);
      }
    };
  }, []);

  const clearMedia = useCallback(() => {
    if (previewRef.current && typeof URL.revokeObjectURL === "function") {
      URL.revokeObjectURL(previewRef.current);
    }
    setSelectedImage(null);
    setSelectedVideo(null);
    setMediaPreview(null);
    setMediaType(null);
    setMediaError("");
    if (imageInputRef.current) imageInputRef.current.value = "";
    if (gifInputRef.current) gifInputRef.current.value = "";
    if (videoInputRef.current) videoInputRef.current.value = "";
  }, []);

  const handleImageSelect = useCallback(
    (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (file.size > MAX_IMAGE_SIZE_BYTES) {
        setMediaError(t("post.image_too_large", "Imagem ou GIF deve ter no máximo 5 MB."));
        e.target.value = "";
        return;
      }
      if (previewRef.current && typeof URL.revokeObjectURL === "function") {
        URL.revokeObjectURL(previewRef.current);
      }
      setMediaError("");
      setSelectedImage(file);
      setSelectedVideo(null);
      setMediaType("image");
      setMediaPreview(
        typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : ""
      );
    },
    [t]
  );

  const handleVideoSelect = useCallback(
    (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (file.size > MAX_VIDEO_SIZE_BYTES) {
        setMediaError(t("post.video_too_large", "Vídeo deve ter no máximo 50 MB."));
        e.target.value = "";
        return;
      }
      if (previewRef.current && typeof URL.revokeObjectURL === "function") {
        URL.revokeObjectURL(previewRef.current);
      }
      setMediaError("");
      setSelectedVideo(file);
      setSelectedImage(null);
      setMediaType("video");
      setMediaPreview(
        typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : ""
      );
    },
    [t]
  );

  return {
    selectedImage,
    selectedVideo,
    mediaPreview,
    mediaType,
    mediaError,
    setMediaError,
    imageInputRef,
    gifInputRef,
    videoInputRef,
    handleImageSelect,
    handleVideoSelect,
    clearMedia,
  };
}

/**
 * Preview local de imagem/GIF/vídeo antes de enviar post ou comentário.
 */
export function MediaPreview({ previewUrl, mediaType, onClear, t, compact = false }) {
  if (!previewUrl && !mediaType) return null;

  return (
    <div
      data-testid="media-preview-container"
      className={`relative rounded-xl overflow-hidden border border-zinc-800 bg-black/30 mt-2 ${
        compact ? "max-w-xs" : "max-w-full"
      }`}
    >
      {mediaType === "video" ? (
        <video
          src={previewUrl}
          controls
          data-testid="media-preview-video"
          className={`w-full object-contain bg-black ${compact ? "max-h-44" : "max-h-72"}`}
        />
      ) : (
        <img
          src={previewUrl}
          alt={t("post.media_alt", "Mídia da publicação")}
          data-testid="media-preview-image"
          className={`w-full object-contain ${compact ? "max-h-44" : "max-h-72"}`}
        />
      )}
      <button
        type="button"
        data-testid="remove-media-btn"
        onClick={onClear}
        aria-label={t("post.remove_media", "Remover mídia")}
        title={t("post.remove_media", "Remover mídia")}
        className="absolute top-2 right-2 p-1.5 rounded-full bg-black/75 hover:bg-black text-white transition"
      >
        <X size={14} />
      </button>
    </div>
  );
}

/**
 * Renderização segura de imagem/GIF ou vídeo salvo em posts e comentários.
 */
export function MediaViewer({ imageUrl, videoUrl, alt, compact = false }) {
  if (!imageUrl && !videoUrl) return null;

  return (
    <div
      data-testid="media-viewer"
      onClick={(e) => e.stopPropagation()}
      className={`mt-2.5 rounded-xl overflow-hidden border border-zinc-800/80 bg-black/20 ${
        compact ? "max-w-md" : "w-full"
      }`}
    >
      {imageUrl && (
        <img
          src={imageUrl}
          alt={alt}
          loading="lazy"
          data-testid="media-image"
          onClick={(e) => {
            e.stopPropagation();
            window.open(imageUrl, "_blank", "noopener,noreferrer");
          }}
          className={`w-full object-contain cursor-pointer hover:opacity-95 transition-opacity ${
            compact ? "max-h-80" : "max-h-[480px]"
          }`}
        />
      )}
      {videoUrl && (
        <video
          src={videoUrl}
          controls
          preload="metadata"
          data-testid="media-video"
          onClick={(e) => e.stopPropagation()}
          className={`w-full object-contain bg-black ${
            compact ? "max-h-80" : "max-h-[480px]"
          }`}
        />
      )}
    </div>
  );
}
