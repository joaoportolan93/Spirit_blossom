"""
Utilitário de segurança e sanitização de imagens de avatar (Onda 5 / AppSec).

Proteções implementadas:
1. Rejeição de arquivos SVG (prevenção contra Stored XSS via XML).
2. Validação estrita de extensão e assinatura binária real (magic bytes via Pillow).
3. Formatos permitidos: JPEG, PNG e WEBP.
4. Limite de tamanho de arquivo: 5 MB.
5. Limite de descompressão (decompression bomb protection): 25 Megapixels.
6. Correção de orientação EXIF (exif_transpose).
7. Redimensionamento seguro para até 512x512 pixels.
8. Recriação do buffer de pixels do zero (destrói payloads em EOF, metadados EXIF e dados polyglot).
9. Renomeação com UUIDv4 aleatório.
10. Limpeza/deleção segura de avatar antigo do disco ao atualizar ou remover.
"""

import io
import os
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_AVATAR_PIXELS = 25_000_000  # 25 MP
MAX_AVATAR_DIMENSIONS = (512, 512)

# Configura limite de segurança do Pillow globalmente para impedir Decompression Bombs
Image.MAX_IMAGE_PIXELS = MAX_AVATAR_PIXELS

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def sanitize_avatar_image(uploaded_file) -> ContentFile:
    """
    Valida e sanitiza um arquivo de imagem para uso seguro como avatar.

    Lança ValidationError se o arquivo for inválido, corrompido ou malicioso.
    Retorna ContentFile sanitizado pronto para salvar no UserProfile.avatar.
    """
    if not uploaded_file:
        raise ValidationError(_("Nenhum arquivo enviado."))

    # 1. Checagem de tamanho do arquivo
    file_size = getattr(uploaded_file, "size", 0)
    if file_size > MAX_AVATAR_SIZE_BYTES:
        raise ValidationError(_("O arquivo de imagem não pode exceder 5 MB."))

    # 2. Bloqueio prévio por extensão perigosa (ex: SVG, HTML, PHP, EXE)
    filename = getattr(uploaded_file, "name", "")
    base_name, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            _("Extensão de imagem inválida. Formatos permitidos: .jpg, .jpeg, .png, .webp.")
        )

    # 3. Leitura e identificação via Pillow
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        if len(file_bytes) > MAX_AVATAR_SIZE_BYTES:
            raise ValidationError(_("O arquivo de imagem não pode exceder 5 MB."))

        stream = io.BytesIO(file_bytes)
        img = Image.open(stream)
    except (UnidentifiedImageError, ValueError):
        raise ValidationError(_("Arquivo de imagem inválido ou corrompido."))
    except Image.DecompressionBombError:
        raise ValidationError(_("A resolução da imagem é muito alta (limite de 25 MP)."))
    except Exception as exc:
        raise ValidationError(_("Erro ao processar imagem: %(err)s") % {"err": str(exc)})

    # 4. Validação da assinatura real do formato
    real_format = img.format
    if real_format not in ALLOWED_FORMATS:
        raise ValidationError(
            _("Formato de imagem não suportado. Use JPEG, PNG ou WEBP.")
        )

    # 5. Validação de dimensões totais (proteção contra decompression bomb)
    width, height = img.size
    if width * height > MAX_AVATAR_PIXELS:
        raise ValidationError(_("A resolução da imagem é muito alta (limite de 25 MP)."))

    # 6. Normalização de orientação com base no EXIF
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # 7. Redimensionamento mantendo proporção para no máximo 512x512
    img.thumbnail(MAX_AVATAR_DIMENSIONS, Image.Resampling.LANCZOS)

    # 8. Recriação do buffer de pixels do zero descartando metadados e EOF payloads
    has_alpha = img.mode in ("RGBA", "LA", "P")
    target_mode = "RGBA" if has_alpha else "RGB"
    clean_img = Image.new(target_mode, img.size)

    if has_alpha:
        clean_img.paste(img.convert("RGBA"))
        save_format = "PNG"
        target_ext = "png"
    else:
        clean_img.paste(img.convert("RGB"))
        save_format = "JPEG"
        target_ext = "jpg"

    out_buffer = io.BytesIO()
    clean_img.save(
        out_buffer,
        format=save_format,
        quality=85 if save_format == "JPEG" else None,
        optimize=True,
    )
    out_buffer.seek(0)

    # 9. Geração de nome aleatório criptograficamente seguro
    random_filename = f"{uuid.uuid4().hex}.{target_ext}"
    return ContentFile(out_buffer.getvalue(), name=random_filename)


def delete_old_avatar(profile) -> None:
    """
    Remove fisicamente o arquivo de avatar anterior do disco/armazenamento.
    Evita acúmulo de arquivos órfãos no MEDIA_ROOT/avatars/.
    """
    if not profile or not getattr(profile, "avatar", None):
        return

    try:
        avatar_field = profile.avatar
        if avatar_field.name:
            avatar_field.storage.delete(avatar_field.name)
    except Exception:
        # Não bloqueia fluxo caso o arquivo já tenha sido removido do disco
        pass
