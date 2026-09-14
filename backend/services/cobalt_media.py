"""
Cobalt media resolve — optional self-hosted filler for video URLs.

Uses a Cobalt API instance (https://github.com/imputnet/cobalt):
  POST /  { "url": "...", "videoQuality": "720", ... }
  → status tunnel|redirect + url

Configure:
  COBALT_API_URL   e.g. http://cobalt:9000/  (required to enable)
  COBALT_API_KEY   optional Api-Key for protected instances

Returns the same meta shape as services.instagram_media / socialfetch_media:
  title, description, caption, uploader, thumbnail, video_url, page_url, source
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


def cobalt_api_url() -> str:
    return (os.getenv("COBALT_API_URL") or "").strip().rstrip("/") + (
        "/" if (os.getenv("COBALT_API_URL") or "").strip() else ""
    )


def cobalt_api_key() -> str:
    return (os.getenv("COBALT_API_KEY") or "").strip()


def cobalt_enabled() -> bool:
    return bool(cobalt_api_url())


def _author_from_url(url: str) -> str:
    if not url:
        return ""
    m = re.search(
        r"(?:tiktok\.com|instagram\.com|youtube\.com)/@([A-Za-z0-9._-]+)",
        url,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.search(r"tiktok\.com/@([^/?#]+)", url, re.I)
    if m:
        return m.group(1).lstrip("@")
    host = (urlparse(url).hostname or "").lower()
    if "youtu.be" in host or "youtube" in host:
        return ""
    m = re.search(r"facebook\.com/([^/?#]+)", url, re.I)
    if m and m.group(1) not in ("watch", "reel", "share", "story.php", "groups"):
        return m.group(1)
    return ""


def _pick_video_url(payload: dict) -> tuple[Optional[str], Optional[str]]:
    """Return (video_url, thumbnail) from a Cobalt response."""
    if not isinstance(payload, dict):
        return None, None
    status = (payload.get("status") or "").lower()
    thumb = None

    if status in ("tunnel", "redirect"):
        url = payload.get("url")
        return (url if isinstance(url, str) and url.startswith("http") else None), thumb

    if status == "picker":
        items = payload.get("picker") or []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                if (item.get("type") or "").lower() == "video" and item.get("url"):
                    thumb = item.get("thumb") or thumb
                    return item["url"], thumb if isinstance(thumb, str) else None
            for item in items:
                if isinstance(item, dict) and item.get("url"):
                    thumb = item.get("thumb") or thumb
                    return item["url"], thumb if isinstance(thumb, str) else None
        return None, None

    if status == "local-processing":
        tunnels = payload.get("tunnel") or []
        if isinstance(tunnels, list) and tunnels:
            u = tunnels[0]
            if isinstance(u, str) and u.startswith("http"):
                return u, None
    return None, None


def _title_from_payload(payload: dict, author: str) -> str:
    meta = ((payload.get("output") or {}) if isinstance(payload, dict) else {}).get("metadata") or {}
    if isinstance(meta, dict):
        title = (meta.get("title") or "").strip()
        if title:
            return title[:120]
        artist = (meta.get("artist") or "").strip()
        if artist:
            return f"Video by {artist}"[:120]
    if author:
        return f"Video by {author}"
    return ""


async def fetch_via_cobalt(
    url: str,
    client: Optional[httpx.AsyncClient] = None,
    *,
    platform: str = "",
) -> Optional[dict]:
    """
    Ask Cobalt for a downloadable media URL for the given social page.
    Caption/description are usually empty — callers should merge with SocialFetch/yt-dlp text.
    """
    base = cobalt_api_url()
    if not base or not url:
        return None

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    key = cobalt_api_key()
    if key:
        headers["Authorization"] = f"Api-Key {key}"

    body = {
        "url": url,
        "videoQuality": "720",
        "downloadMode": "auto",
        "filenameStyle": "basic",
        "disableMetadata": False,
        "alwaysProxy": True,  # keep URLs on our Cobalt host for datacenter fetch
    }
    if platform == "youtube" or "youtu" in url.lower():
        body["youtubeVideoCodec"] = "h264"
        body["youtubeVideoContainer"] = "mp4"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=90.0)
    assert client is not None

    try:
        resp = await client.post(base, headers=headers, json=body, timeout=90.0)
        if resp.status_code == 401 or resp.status_code == 403:
            logger.info("Cobalt auth failed HTTP %s — check COBALT_API_KEY", resp.status_code)
            return None
        if resp.status_code >= 400:
            logger.info("Cobalt HTTP %s: %s", resp.status_code, (resp.text or "")[:200])
            return None
        payload = resp.json() if resp.content else {}
        if not isinstance(payload, dict):
            return None
        if (payload.get("status") or "").lower() == "error":
            err = payload.get("error") or {}
            code = err.get("code") if isinstance(err, dict) else err
            logger.info("Cobalt error: %s", code)
            return None

        video, thumb = _pick_video_url(payload)
        if not video:
            logger.info("Cobalt returned no video (status=%s)", payload.get("status"))
            return None

        author = _author_from_url(url)
        # Prefer metadata artist when present
        meta = ((payload.get("output") or {}) if isinstance(payload, dict) else {}).get("metadata") or {}
        if isinstance(meta, dict):
            artist = (meta.get("artist") or meta.get("album_artist") or "").strip()
            if artist:
                author = artist.lstrip("@")

        title = _title_from_payload(payload, author)
        logger.info(
            "Cobalt OK platform=%s author=%s video=%s",
            platform or "?",
            author,
            True,
        )
        return {
            "title": title,
            "description": "",
            "caption": "",
            "uploader": author,
            "thumbnail": thumb or "",
            "video_url": video,
            "page_url": url,
            "source": "cobalt",
            "platform": platform or None,
        }
    except Exception as e:
        logger.warning("Cobalt request failed: %s", e)
        return None
    finally:
        if owns_client:
            await client.aclose()


def merge_social_meta(primary: Optional[dict], secondary: Optional[dict]) -> Optional[dict]:
    """
    Prefer primary for caption/author text; fill missing video_url/thumbnail from secondary.
    """
    if not primary and not secondary:
        return None
    if not primary:
        return secondary
    if not secondary:
        return primary
    out = dict(primary)
    for key in ("video_url", "thumbnail"):
        if not out.get(key) and secondary.get(key):
            out[key] = secondary[key]
    for key in ("caption", "description", "title", "uploader"):
        if not (out.get(key) or "").strip() and (secondary.get(key) or "").strip():
            out[key] = secondary[key]
    # Track combined source for logs
    if primary.get("source") and secondary.get("source") and primary.get("source") != secondary.get("source"):
        if out.get("video_url") and secondary.get("video_url") == out.get("video_url"):
            out["source"] = f"{primary.get('source')}+{secondary.get('source')}"
    return out
