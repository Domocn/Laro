"""Shared PDF upload size limits for recipe / meal-plan imports."""
import os

DEFAULT_PDF_UPLOAD_MAX_MB = 50


def pdf_upload_max_bytes() -> int:
    """Max PDF upload size in bytes (env `LARO_PDF_UPLOAD_MAX_MB`, default 50)."""
    raw = os.getenv("LARO_PDF_UPLOAD_MAX_MB", str(DEFAULT_PDF_UPLOAD_MAX_MB))
    try:
        mb = int(raw)
    except ValueError:
        mb = DEFAULT_PDF_UPLOAD_MAX_MB
    mb = max(1, min(mb, 200))
    return mb * 1024 * 1024


def pdf_upload_max_mb_label() -> int:
    return pdf_upload_max_bytes() // (1024 * 1024)


def pdf_too_large_detail() -> str:
    return f"PDF too large (max {pdf_upload_max_mb_label()}MB)"
