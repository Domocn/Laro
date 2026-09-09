"""
HMAC-signed upload URLs so private recipe images work in <img> tags
without Bearer headers, while remaining unguessable without a valid signature.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from config import settings

DEFAULT_TTL_SECONDS = 3600 * 6  # 6 hours for authenticated recipe views
SHARE_TTL_SECONDS = 3600 * 24 * 7  # 7 days for public share pages


def _secret() -> bytes:
    return (settings.jwt_secret or "dev").encode("utf-8")


def sign_upload_filename(filename: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> tuple[int, str]:
    """Return (exp, sig) for a filename."""
    # Normalize to basename only
    name = filename.split("/")[-1].split("?")[0]
    exp = int(time.time()) + int(ttl_seconds)
    msg = f"{name}:{exp}".encode("utf-8")
    sig = hmac.new(_secret(), msg, hashlib.sha256).hexdigest()
    return exp, sig


def verify_upload_signature(filename: str, exp: Optional[str], sig: Optional[str]) -> bool:
    """True if exp/sig are valid for filename and not expired."""
    if not exp or not sig:
        return False
    try:
        exp_i = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_i < int(time.time()):
        return False
    name = filename.split("/")[-1].split("?")[0]
    msg = f"{name}:{exp_i}".encode("utf-8")
    expected = hmac.new(_secret(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def sign_upload_path(path_or_url: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """
    If path is a local /api/uploads/... URL, append ?exp=&sig=.
    External http(s) URLs and empty values are returned unchanged.
    """
    if not path_or_url:
        return path_or_url
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        # Only sign our own upload paths if they appear as absolute same-host URLs
        parsed = urlparse(path_or_url)
        if "/api/uploads/" not in parsed.path and "/api/v1/uploads/" not in parsed.path:
            return path_or_url
        path = parsed.path
        filename = path.rstrip("/").split("/")[-1]
        exp, sig = sign_upload_filename(filename, ttl_seconds)
        qs = parse_qs(parsed.query)
        qs["exp"] = [str(exp)]
        qs["sig"] = [sig]
        flat = [(k, v[0]) for k, v in qs.items()]
        return urlunparse(parsed._replace(query=urlencode(flat)))

    if "/uploads/" not in path_or_url:
        return path_or_url

    # Relative /api/uploads/foo.jpg
    base, _, _old_q = path_or_url.partition("?")
    filename = base.rstrip("/").split("/")[-1]
    exp, sig = sign_upload_filename(filename, ttl_seconds)
    return f"{base}?exp={exp}&sig={sig}"
