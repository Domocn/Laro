"""Helpers for public recipe share links."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import secrets
import string


def parse_share_expiry(value: Any) -> Optional[datetime]:
    """
    Normalize recipe_shares.expires_at from Postgres (datetime) or JSON (str).

    Calling str.replace on a datetime hits datetime.replace() and raises:
    TypeError: 'str' object cannot be interpreted as an integer
    """
    if value is None or value is False:
        return None
    if isinstance(value, datetime):
        expires = value
    else:
        text = str(value).strip()
        if not text:
            return None
        expires = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires


def generate_share_code(length: int = 6) -> str:
    """Short URL-safe code for /recipe/{code} links (e.g. xgdghK)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def public_share_path(share_code: str) -> str:
    return f"/recipe/{share_code}"
