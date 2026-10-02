import os

from utils.pdf_upload_limits import (
    DEFAULT_PDF_UPLOAD_MAX_MB,
    pdf_too_large_detail,
    pdf_upload_max_bytes,
    pdf_upload_max_mb_label,
)


def test_default_pdf_limit_is_50mb():
    assert pdf_upload_max_bytes() == 50 * 1024 * 1024
    assert pdf_upload_max_mb_label() == 50
    assert "50MB" in pdf_too_large_detail()


def test_pdf_limit_from_env(monkeypatch):
    monkeypatch.setenv("LARO_PDF_UPLOAD_MAX_MB", "32")
    assert pdf_upload_max_bytes() == 32 * 1024 * 1024
    assert pdf_upload_max_mb_label() == 32


def test_pdf_limit_clamped(monkeypatch):
    monkeypatch.setenv("LARO_PDF_UPLOAD_MAX_MB", "999")
    assert pdf_upload_max_mb_label() == 200
    monkeypatch.delenv("LARO_PDF_UPLOAD_MAX_MB", raising=False)
    monkeypatch.setenv("LARO_PDF_UPLOAD_MAX_MB", "0")
    assert pdf_upload_max_mb_label() == 1
