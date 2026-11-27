"""
Utilitário de segurança e sanitização de imagens de avatar (Onda 5) e
mídia de posts (Onda 9 / AppSec).

Proteções implementadas:
1. Rejeição de arquivos SVG (prevenção contra Stored XSS via XML).
2. Validação estrita de extensão e assinatura binária real (magic bytes via Pillow).
3. Formatos permitidos: JPEG, PNG e WEBP.
4. Limite de tamanho de arquivo: 5 MB por arquivo, máx 4 imagens por post.
5. Limite de descompressão (decompression bomb protection): 25 Megapixels e
   dimensão máxima de 4096 px (proteção adicional por lado).
6. Correção de orientação EXIF (exif_transpose).
7. Redimensionamento seguro: avatar 512x512; post_media 2048x2048 (mantendo proporção).
8. Recriação do buffer de pixels do zero — remove 100% dos metadados EXIF/GPS.
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

# Onda 9 — post media
MAX_POST_MEDIA_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB por arquivo
MAX_POST_MEDIA_COUNT = 4  # máx. 4 imagens por post
MAX_POST_MEDIA_PIXELS = 25_000_000  # 25 MP — anti decompression bomb
MAX_POST_MEDIA_SIDE_PX = 4096  # px por lado — proteção extra
MAX_POST_MEDIA_DIMENSIONS = (2048, 2048)  # resize máximo (mantém proporção)

# Configura limite de segurança do Pillow globalmente para impedir Decompression Bombs
Image.MAX_IMAGE_PIXELS = MAX_POST_MEDIA_PIXELS  # aplica ao maior limite (post > avatar)

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
        raise ValidationError(_("Formato de imagem não suportado. Use JPEG, PNG ou WEBP."))

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


def _sanitize_post_image_internal(uploaded_file, max_side: int, max_dims: tuple) -> ContentFile:
    """
    Pipeline compartilhado de sanitização de imagem para posts (Onda 9).

    Garante:
    - Tamanho <= MAX_POST_MEDIA_SIZE_BYTES (5 MB)
    - Extensão e magic bytes JPEG/PNG/WEBP
    - Proteção contra decompression bomb via MAX_POST_MEDIA_PIXELS e max_side
    - Remoção 100% dos metadados EXIF/GPS via recriação de buffer do zero
    - Renomeação UUID4 aleatória
    """
    if not uploaded_file:
        raise ValidationError(_("Nenhum arquivo enviado."))

    file_size = getattr(uploaded_file, "size", 0)
    if file_size > MAX_POST_MEDIA_SIZE_BYTES:
        raise ValidationError(_("Cada imagem não pode exceder 5 MB."))

    filename = getattr(uploaded_file, "name", "")
    base_name, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            _("Extensão de imagem inválida. Formatos permitidos: .jpg, .jpeg, .png, .webp.")
        )

    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        if len(file_bytes) > MAX_POST_MEDIA_SIZE_BYTES:
            raise ValidationError(_("Cada imagem não pode exceder 5 MB."))

        stream = io.BytesIO(file_bytes)
        probe = Image.open(stream)
        probe.verify()
        real_format = probe.format

        # verify() consome o stream; reabre para extrair dimensões e decodificar pixels
        img = Image.open(io.BytesIO(file_bytes))
        img.load()
    except (UnidentifiedImageError, ValueError):
        raise ValidationError(_("Arquivo de imagem inválido ou corrompido."))
    except Image.DecompressionBombError:
        raise ValidationError(_("A resolução da imagem é muito alta (limite de 25 MP)."))
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(_("Erro ao processar imagem: %(err)s") % {"err": str(exc)})

    if real_format not in ALLOWED_FORMATS:
        raise ValidationError(_("Formato de imagem não suportado. Use JPEG, PNG ou WEBP."))

    width, height = img.size
    # Proteção extra por dimensão — anti decompression bomb independente de MP
    if width > max_side or height > max_side:
        raise ValidationError(
            _("Dimensões da imagem excedem o limite de %(px)d px por lado.") % {"px": max_side}
        )
    if width * height > MAX_POST_MEDIA_PIXELS:
        raise ValidationError(_("A resolução da imagem é muito alta (limite de 25 MP)."))

    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    img.thumbnail(max_dims, Image.Resampling.LANCZOS)

    # Recria buffer do zero — remove 100% dos metadados EXIF/GPS
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

    # Dimensões limpas após resize
    final_width, final_height = clean_img.size

    random_filename = f"{uuid.uuid4().hex}.{target_ext}"
    content = ContentFile(out_buffer.getvalue(), name=random_filename)
    # Anexa metadados de dimensão para uso pelo service sem re-abrir
    content._post_media_width = final_width
    content._post_media_height = final_height
    return content


def sanitize_post_media_image(uploaded_file) -> ContentFile:
    """
    Valida e sanitiza imagem para PostMedia (Onda 9).

    Lança ValidationError se inválido. Retorna ContentFile sanitizado sem EXIF.
    Use sanitize_post_media_images() para batch com contagem.
    """
    return _sanitize_post_image_internal(
        uploaded_file,
        max_side=MAX_POST_MEDIA_SIDE_PX,
        max_dims=MAX_POST_MEDIA_DIMENSIONS,
    )


def sanitize_post_media_images(uploaded_files: list) -> list:
    """
    Valida e sanitiza até 4 imagens para um post.

    uploaded_files: lista de InMemoryUploadedFile
    Retorna lista de ContentFile sanitizados.
    Lança ValidationError se houver mais de 4 ou qualquer arquivo inválido.
    """
    if len(uploaded_files) > MAX_POST_MEDIA_COUNT:
        raise ValidationError(
            _("Máximo de %(n)d imagens por publicação.") % {"n": MAX_POST_MEDIA_COUNT}
        )
    return [sanitize_post_media_image(f) for f in uploaded_files]


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
