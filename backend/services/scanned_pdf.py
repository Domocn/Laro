"""
Scanned (image-only) PDF → page images for vision OCR.

Used when pypdf finds almost no extractable text. Caps pages to keep free-tier
AI quota predictable; callers should meter with require_ai_quota / consume.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Match photo extract UI (up to 5 images) — one vision call for the batch.
DEFAULT_MAX_SCANNED_PAGES = 5
# Soft floor: below this many chars of text-layer content → treat as scanned.
MIN_TEXT_LAYER_CHARS = 40


def pdf_text_layer(raw: bytes) -> str:
    """Extract text layer only (no OCR). Empty/short for image-only PDFs."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    parts: List[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def is_scanned_pdf_text(text: str, *, min_chars: int = MIN_TEXT_LAYER_CHARS) -> bool:
    return len((text or "").strip()) < min_chars


def pdf_page_count(raw: bytes) -> int:
    try:
        import pymupdf

        doc = pymupdf.open(stream=raw, filetype="pdf")
        try:
            return int(doc.page_count)
        finally:
            doc.close()
    except Exception:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(raw)).pages)


def render_pdf_pages_to_jpeg_base64(
    raw: bytes,
    *,
    max_pages: int = DEFAULT_MAX_SCANNED_PAGES,
    scale: float = 1.5,
    jpeg_quality: int = 85,
) -> Tuple[List[str], int]:
    """
    Rasterize PDF pages to JPEG base64 strings (no data-URL prefix).

    Returns (images, total_page_count). Only the first max_pages are rendered.
    """
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    try:
        import pymupdf
    except ImportError as e:
        raise ValueError(
            "Scanned PDF support requires pymupdf on the server. "
            "Photograph pages instead (Quick Add → Photos), or use a text-layer PDF."
        ) from e

    doc = pymupdf.open(stream=raw, filetype="pdf")
    try:
        total = int(doc.page_count)
        if total < 1:
            raise ValueError("PDF has no pages")
        limit = min(total, max_pages)
        matrix = pymupdf.Matrix(scale, scale)
        images: List[str] = []
        for i in range(limit):
            page = doc[i]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            # Prefer JPEG to keep vision payloads smaller
            try:
                jpeg_bytes = pix.tobytes("jpeg")
            except Exception:
                # Older/odd builds: PNG then re-encode via Pillow
                from PIL import Image

                png_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
                jpeg_bytes = buf.getvalue()
            images.append(base64.b64encode(jpeg_bytes).decode("ascii"))
        return images, total
    finally:
        doc.close()


def extract_text_or_scan_meta(
    raw: bytes,
    *,
    min_chars: int = MIN_TEXT_LAYER_CHARS,
) -> Tuple[Optional[str], bool]:
    """
    Returns (text, is_scanned).
    text is None when the PDF should go through vision OCR instead.

    Prefer PyMuPDF (via meal_plan_import.extract_text_from_pdf_bytes) so
    word-per-line pypdf layouts still look like real meal-plan headings.
    """
    text = ""
    try:
        from services.meal_plan_import import extract_text_from_pdf_bytes

        text = extract_text_from_pdf_bytes(raw)
    except Exception as e:
        logger.info("Preferred PDF extract failed (%s); falling back to pypdf layer", e)
        try:
            text = pdf_text_layer(raw)
        except ImportError as ie:
            raise ValueError(
                "PDF support is not installed on the server (pypdf). Paste the plan text instead."
            ) from ie
        except Exception as e2:
            logger.info("PDF text extract failed (%s); treating as scanned", e2)
            return None, True

    if is_scanned_pdf_text(text, min_chars=min_chars):
        return None, True
    return text, False
