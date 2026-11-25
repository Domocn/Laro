"""Shrink recipe photos so the VPS uploads volume stays small."""
from __future__ import annotations

import io
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MAX_SIDE = 1280
JPEG_QUALITY = 78


def upload_dir() -> Path:
    path = Path(os.getenv("UPLOAD_DIR") or "uploads")
    path.mkdir(parents=True, exist_ok=True)
    return path


def compress_image_bytes(content: bytes, max_side: int = MAX_SIDE, quality: int = JPEG_QUALITY) -> bytes:
    """Return a JPEG under max_side. Falls back to the original bytes on failure."""
    if not content or len(content) < 32:
        return content
    try:
        from PIL import Image, ImageOps
    except Exception:
        return content
    try:
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_side:
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=quality, optimize=True)
        data = out.getvalue()
        if data and len(data) < len(content):
            return data
        if data and (w > max_side or h > max_side):
            return data
        return data or content
    except Exception as e:
        logger.debug("image compress skipped: %s", e)
        return content


def save_compressed_jpeg(content: bytes, prefix: str = "recipe") -> Optional[str]:
    data = compress_image_bytes(content)
    if not data:
        return None
    name = f"{prefix}-{uuid.uuid4().hex[:12]}.jpg"
    dest = upload_dir() / name
    dest.write_bytes(data)
    return f"/api/uploads/{name}"


async def stash_remote_cover(http_client, image_url: str, prefix: str = "migrate") -> Optional[str]:
    """Copy a remote Mealime (or other) cover onto the VPS so it survives the shutdown."""
    url = (image_url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return None
    from urllib.parse import urljoin
    from utils.security import is_safe_external_url
    try:
        # Follow redirects manually so every hop is SSRF-checked; the page URL
        # being safe says nothing about the image URL it embeds.
        resp = None
        for _ in range(5):
            is_safe, error = is_safe_external_url(url)
            if not is_safe:
                logger.warning("cover stash blocked for %s: %s", url[:80], error)
                return None
            resp = await http_client.get(
                url,
                headers={"User-Agent": "LaroFood/1.0 (+https://laro.food)"},
                timeout=20.0,
                follow_redirects=False,
            )
            if resp.is_redirect and resp.headers.get("location"):
                url = urljoin(url, resp.headers["location"])
                continue
            break
        else:
            return None
        resp.raise_for_status()
        content = resp.content or b""
        if len(content) < 64 or len(content) > 8 * 1024 * 1024:
            return None
        return save_compressed_jpeg(content, prefix=prefix)
    except Exception as e:
        logger.info("cover stash skipped for %s: %s", url[:80], e)
        return None
