"""
Utilitário de segurança e sanitização de mídia (imagens, GIFs animados e vídeos)
para publicações e comentários (adaptado do Lumem para Spirit Blossom).

Proteções implementadas:
1. Imagens estáticas (JPEG, PNG, WEBP):
   - Bloqueio de extensões perigosas (SVG, HTML, scripts).
   - Limite de tamanho (5 MB) e de pixels (25 MP — anti-Decompression Bomb).
   - Recodificação completa via Pillow (destrói payloads polyglot em EOF e metadados EXIF/GPS).
   - Limite de dimensões máximas (2048x2048) preservando proporção.
2. GIFs animados:
   - Reconstrução frame a frame via Pillow ImageSequence.Iterator (preserva animação).
   - Limite máximo de frames (300) e dimensões (1024x1024) contra GIF bombs.
   - Remoção de metadados e comentários embutidos em frames.
3. Vídeos (MP4, WEBM, MOV):
   - Limite de tamanho (50 MB) e extensão estrita.
   - Verificação real de magic bytes (`ftyp` para MP4/MOV e EBML+webm para WEBM).
   - Bloqueio de assinaturas HTML/SVG/script nos bytes iniciais (anti-polyglot XSS).
   - Renomeação segura com UUIDv4 aleatório para prevenir path traversal.
"""

import io
import logging
import os
import uuid
from typing import Optional

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

logger = logging.getLogger(__name__)

MAX_MEDIA_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_MEDIA_VIDEO_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_IMAGE_PIXELS = 25_000_000  # 25 MP
MAX_POST_IMAGE_DIMENSIONS = (2048, 2048)
MAX_GIF_DIMENSIONS = (1024, 1024)
MAX_GIF_FRAMES = 300

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

SAFE_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
FORMAT_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "gif": "GIF",
}

SAFE_VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}
VIDEO_MIME_MAP = {
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
}
MP4_MOV_BRANDS = {
    b"isom",
    b"iso2",
    b"iso4",
    b"iso5",
    b"iso6",
    b"mp41",
    b"mp42",
    b"avc1",
    b"hvc1",
    b"hev1",
    b"qt  ",
    b"M4V ",
    b"M4A ",
    b"mmp4",
    b"3gp4",
    b"3gp5",
}
DANGEROUS_HEADER_SNIPPETS = (
    b"<html",
    b"<!doctype",
    b"<svg",
    b"<script",
    b"<?xml",
    b"<?php",
)


class MediaSanitizationError(ValueError):
    """Levantado quando um arquivo de mídia falha na validação ou sanitização."""


def _rebuild_static_image(img: Image.Image, target_format: str, quality: int = 85) -> bytes:
    """Recria imagem estática do zero descartando EXIF e dados appended."""
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    img.thumbnail(MAX_POST_IMAGE_DIMENSIONS, Image.Resampling.LANCZOS)

    if target_format == "JPEG":
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
            background.paste(img, mask=mask)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
    elif target_format in ("PNG", "WEBP") and img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")

    buf = io.BytesIO()
    save_kwargs = {"format": target_format}
    if target_format == "JPEG":
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    elif target_format == "PNG":
        save_kwargs["optimize"] = True
    elif target_format == "WEBP":
        save_kwargs["quality"] = quality

    img.save(buf, **save_kwargs)
    return buf.getvalue()


def _rebuild_gif(img: Image.Image) -> bytes:
    """Processa GIF animado frame a frame, preservando animação e removendo metadados."""
    frames = []
    durations = []

    for idx, frame in enumerate(ImageSequence.Iterator(img)):
        if idx >= MAX_GIF_FRAMES:
            break
        rgba_frame = frame.convert("RGBA")
        rgba_frame.thumbnail(MAX_GIF_DIMENSIONS, Image.Resampling.LANCZOS)
        # Cria nova Image sem copiar `frame.info` (remove comment/extensões/metadados)
        clean_frame = Image.new("RGBA", rgba_frame.size)
        clean_frame.paste(rgba_frame)
        frames.append(clean_frame)
        durations.append(max(20, int(frame.info.get("duration", 100))))

    if not frames:
        raise MediaSanitizationError(_("GIF não contém frames válidos."))

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        loop=img.info.get("loop", 0),
        duration=durations,
        comment=b"",
        optimize=False,
    )
    return buf.getvalue()


def sanitize_media_image(
    uploaded_file,
    *,
    allowed_extensions: Optional[set[str]] = None,
    max_bytes: int = MAX_MEDIA_IMAGE_BYTES,
) -> InMemoryUploadedFile:
    """
    Valida e higieniza imagem (JPEG/PNG/WEBP) ou GIF animado para posts/comentários.
    Levanta MediaSanitizationError em qualquer violação.
    """
    if not uploaded_file:
        raise MediaSanitizationError(_("Nenhum arquivo de imagem enviado."))

    if allowed_extensions is None:
        allowed_extensions = SAFE_IMAGE_EXTENSIONS

    file_size = getattr(uploaded_file, "size", 0) or 0
    if file_size > max_bytes:
        raise MediaSanitizationError(_("A imagem ou GIF não pode exceder 5 MB."))

    original_name = getattr(uploaded_file, "name", "") or ""
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in allowed_extensions:
        safe_list = ", ".join(sorted(allowed_extensions))
        raise MediaSanitizationError(
            _('Formato "%(ext)s" não é permitido. Use: %(safe)s')
            % {"ext": ext or "?", "safe": safe_list}
        )

    uploaded_file.seek(0)
    raw_bytes = uploaded_file.read(max_bytes + 1)
    uploaded_file.seek(0)

    if len(raw_bytes) > max_bytes:
        raise MediaSanitizationError(_("A imagem ou GIF não pode exceder 5 MB."))

    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.load()
    except Image.DecompressionBombError as exc:
        raise MediaSanitizationError(
            _("A resolução da imagem é muito alta (limite de 25 MP).")
        ) from exc
    except (UnidentifiedImageError, Exception) as exc:
        logger.warning("Imagem/GIF inválido rejeitado: %s | %s", original_name, exc)
        raise MediaSanitizationError(_("Arquivo de imagem inválido ou corrompido.")) from exc

    width, height = img.size
    if width * height > MAX_IMAGE_PIXELS:
        raise MediaSanitizationError(_("A resolução da imagem é muito alta (limite de 25 MP)."))

    real_format = (img.format or "").upper()
    if real_format not in {"JPEG", "PNG", "WEBP", "GIF"}:
        raise MediaSanitizationError(_("Formato binário de imagem não suportado."))

    is_gif = ext == "gif" or real_format == "GIF"
    if ext == "gif" and real_format != "GIF":
        raise MediaSanitizationError(
            _("Arquivo com extensão .gif não possui assinatura GIF válida.")
        )

    target_format = "GIF" if is_gif else FORMAT_MAP.get(ext, real_format)
    try:
        if target_format == "GIF":
            clean_bytes = _rebuild_gif(img)
            output_ext = "gif"
            content_type = "image/gif"
        else:
            clean_bytes = _rebuild_static_image(img, target_format)
            output_ext = "jpg" if target_format == "JPEG" else target_format.lower()
            content_type = "image/jpeg" if output_ext == "jpg" else f"image/{output_ext}"
    except MediaSanitizationError:
        raise
    except Exception as exc:
        logger.error("Erro ao higienizar mídia %s: %s", original_name, exc, exc_info=True)
        raise MediaSanitizationError(
            _("Não foi possível processar a imagem. Tente outro arquivo.")
        ) from exc

    clean_name = f"{uuid.uuid4().hex}.{output_ext}"
    field_name = getattr(uploaded_file, "field_name", None)
    return InMemoryUploadedFile(
        file=io.BytesIO(clean_bytes),
        field_name=field_name,
        name=clean_name,
        content_type=content_type,
        size=len(clean_bytes),
        charset=None,
    )


def _has_valid_mp4_or_mov_signature(header: bytes) -> bool:
    """Verifica assinatura ISO Base Media File Format (`ftyp` box nos bytes 4..8)."""
    if len(header) < 12 or header[4:8] != b"ftyp":
        return False
    major_brand = header[8:12]
    return major_brand in MP4_MOV_BRANDS


def _has_valid_webm_signature(header: bytes) -> bool:
    """Verifica assinatura EBML (`0x1A45DFA3`) e DocType `webm` no cabeçalho."""
    if len(header) < 16 or not header.startswith(b"\x1a\x45\xdf\xa3"):
        return False
    return b"webm" in header[:128].lower()


def sanitize_media_video(uploaded_file, *, max_bytes: int = MAX_MEDIA_VIDEO_BYTES):
    """
    Valida vídeo (MP4, WEBM, MOV) quanto a tamanho, extensão, assinatura binária real
    e proteção anti-polyglot/path-traversal, gerando nome aleatório UUIDv4.
    """
    if not uploaded_file:
        raise MediaSanitizationError(_("Nenhum arquivo de vídeo enviado."))

    file_size = getattr(uploaded_file, "size", 0) or 0
    if file_size <= 0:
        raise MediaSanitizationError(_("Arquivo de vídeo vazio."))
    if file_size > max_bytes:
        raise MediaSanitizationError(_("O vídeo não pode exceder 50 MB."))

    original_name = getattr(uploaded_file, "name", "") or ""
    _stem, ext_dot = os.path.splitext(original_name.lower())
    ext = ext_dot.lstrip(".")
    if ext not in SAFE_VIDEO_EXTENSIONS:
        safe_list = ", ".join(sorted(SAFE_VIDEO_EXTENSIONS))
        raise MediaSanitizationError(
            _('Formato de vídeo "%(ext)s" não é permitido. Use: %(safe)s')
            % {"ext": ext or "?", "safe": safe_list}
        )

    uploaded_file.seek(0)
    header = uploaded_file.read(256)
    uploaded_file.seek(0)

    header_lower = header.lstrip().lower()
    if any(
        header_lower.startswith(sig) or sig in header_lower[:128]
        for sig in DANGEROUS_HEADER_SNIPPETS
    ):
        raise MediaSanitizationError(_("Arquivo de vídeo inválido ou potencialmente malicioso."))

    if ext in ("mp4", "mov") and not _has_valid_mp4_or_mov_signature(header):
        raise MediaSanitizationError(_("Arquivo não possui assinatura binária MP4/MOV válida."))
    if ext == "webm" and not _has_valid_webm_signature(header):
        raise MediaSanitizationError(_("Arquivo não possui assinatura binária WEBM válida."))

    clean_name = f"{uuid.uuid4().hex}.{ext}"
    uploaded_file.name = clean_name
    if hasattr(uploaded_file, "content_type"):
        uploaded_file.content_type = VIDEO_MIME_MAP[ext]
    return uploaded_file


def delete_media_file(file_field) -> None:
    """Remove arquivo físico do storage com segurança sem falhar se já ausente."""
    if not file_field:
        return
    try:
        if getattr(file_field, "name", None):
            file_field.storage.delete(file_field.name)
    except Exception:
        logger.warning("Falha ao remover arquivo de mídia do storage.", exc_info=True)
