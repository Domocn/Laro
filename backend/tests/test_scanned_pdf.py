"""Tests for scanned PDF detection / page rasterization and multi-image wiring."""
from __future__ import annotations

import base64
import io

import pytest

from services.scanned_pdf import (
    DEFAULT_MAX_SCANNED_PAGES,
    extract_text_or_scan_meta,
    is_scanned_pdf_text,
    pdf_text_layer,
    render_pdf_pages_to_jpeg_base64,
)


def _image_only_pdf(pages: int = 2) -> bytes:
    """Build a PDF with embedded JPEG pages and no text layer."""
    import pymupdf
    from PIL import Image, ImageDraw

    doc = pymupdf.open()
    for i in range(pages):
        img = Image.new("RGB", (320, 480), "white")
        d = ImageDraw.Draw(img)
        d.text((24, 24), f"Recipe Page {i + 1}\nIngredients:\n1 cup flour\nInstructions:\nMix.", fill="black")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        page = doc.new_page(width=320, height=480)
        page.insert_image(page.rect, stream=buf.getvalue())
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def _text_pdf() -> bytes:
    """Minimal text-layer PDF via pypdf writer if available, else pymupdf text."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Recipe 1\nChocolate Cake\nIngredients:\n2 cups flour\nInstructions:\nBake.",
        fontsize=12,
    )
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def test_is_scanned_detects_short_text():
    assert is_scanned_pdf_text("")
    assert is_scanned_pdf_text("   hi  ")
    assert not is_scanned_pdf_text("x" * 80)


def test_image_only_pdf_marked_scanned():
    raw = _image_only_pdf(2)
    text, scanned = extract_text_or_scan_meta(raw)
    assert scanned is True
    assert text is None
    # pypdf text layer should be empty/short
    assert is_scanned_pdf_text(pdf_text_layer(raw))


def test_text_pdf_not_scanned():
    raw = _text_pdf()
    text, scanned = extract_text_or_scan_meta(raw)
    assert scanned is False
    assert text is not None
    assert "Chocolate" in text or "flour" in text.lower() or len(text.strip()) >= 40


def test_render_pages_respects_cap():
    raw = _image_only_pdf(4)
    images, total = render_pdf_pages_to_jpeg_base64(raw, max_pages=2)
    assert total == 4
    assert len(images) == 2
    for b64 in images:
        raw_bytes = base64.b64decode(b64)
        assert raw_bytes[:2] == b"\xff\xd8"  # JPEG SOI
    assert DEFAULT_MAX_SCANNED_PAGES == 5


def test_render_rejects_bad_max():
    raw = _image_only_pdf(1)
    with pytest.raises(ValueError):
        render_pdf_pages_to_jpeg_base64(raw, max_pages=0)
