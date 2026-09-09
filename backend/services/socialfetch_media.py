"""
SocialFetch.dev media resolve for Instagram / TikTok / YouTube / Facebook.

Replaces SocialKit. Auth: x-api-key (sfk_…) via SOCIALFETCH_API_KEY.

  GET https://api.socialfetch.dev/v1/{platform}/…?url=

Returns the same meta shape as the old SocialKit/instagram resolvers:
  title, description, caption, uploader, thumbnail, video_url, page_url, source, platform
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.socialfetch.dev"
_resolve_cache: dict[str, tuple[float, Optional[dict]]] = {}
_RESOLVE_CACHE_SECS = 90.0

_PLATFORM_HOSTS = (
    ("instagram.com", "instagram"),
    ("instagr.am", "instagram"),
    ("tiktok.com", "tiktok"),
    ("vm.tiktok.com", "tiktok"),
    ("vt.tiktok.com", "tiktok"),
    ("youtube.com", "youtube"),
    ("youtu.be", "youtube"),
    ("facebook.com", "facebook"),
    ("fb.watch", "facebook"),
    ("fb.gg", "facebook"),
    ("fb.com", "facebook"),
    ("m.facebook.com", "facebook"),
    ("web.facebook.com", "facebook"),
)

# Tracking / share junk that breaks or confuses scrapers
_STRIP_QUERY_KEYS = {
    "igsh",
    "igshid",
    "img_index",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "fbclid",
    "si",
    "feature",
    "re",
    "stkn",  # Instagram share token — not needed for resolve
}

# Platform → (path, supports downloadMedia query)
_ENDPOINTS = {
    "tiktok": ("/v1/tiktok/videos", True),
    "instagram": ("/v1/instagram/posts", True),
    "youtube": ("/v1/youtube/videos", False),
    "facebook": ("/v1/facebook/posts", False),
}


def socialfetch_api_key() -> str:
    return (
        (os.getenv("SOCIALFETCH_API_KEY") or "").strip()
        or (os.getenv("SOCIAL_FETCH_API_KEY") or "").strip()
    )


def socialfetch_download_media() -> bool:
    """When true, ask SocialFetch to host media (+10 credits on TT/IG)."""
    return (os.getenv("SOCIALFETCH_DOWNLOAD_MEDIA") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def detect_social_platform(url: str) -> Optional[str]:
    if not url:
        return None
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    lower = url.lower()
    for needle, platform in _PLATFORM_HOSTS:
        if needle in host or needle in lower:
            if platform == "youtube" and "youtu.be" not in lower and "youtube.com" not in lower:
                continue
            return platform
    return None


def canonicalize_social_url(url: str) -> str:
    """
    Normalize share/short social URLs so SocialFetch / Cobalt / IG helpers agree.

    - Instagram /share/reel/<code> → /reel/<code>/
    - Instagram /share/<code> or /share/p/<code> → /p/<code>/
    - Strip tracking query params (igsh, utm_*, fbclid, …)
    """
    if not url or not isinstance(url, str):
        return url
    raw = url.strip()
    try:
        parsed = urlparse(raw)
    except Exception:
        return raw
    host = (parsed.hostname or "").lower()
    if not host:
        return raw

    path = parsed.path or ""
    if "instagram.com" in host or host.endswith("instagr.am"):
        m = re.search(r"/share/(?:reel|reels)/([A-Za-z0-9_-]+)/?", path, re.I)
        if m:
            path = f"/reel/{m.group(1)}/"
        else:
            m = re.search(r"/share/(?:p/)?([A-Za-z0-9_-]+)/?", path, re.I)
            if m and m.group(1).lower() not in ("reel", "reels", "p", "tv", "stories"):
                path = f"/p/{m.group(1)}/"
        path = re.sub(r"^/reels/", "/reel/", path, count=1, flags=re.I)
        host = "www.instagram.com"

    if host in ("m.facebook.com", "web.facebook.com", "fb.com", "www.fb.com"):
        host = "www.facebook.com"
    if host in ("tiktok.com", "m.tiktok.com"):
        host = "www.tiktok.com"

    q = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _STRIP_QUERY_KEYS
    ]
    scheme = parsed.scheme or "https"
    netloc = host
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{host}:{parsed.port}"
    return urlunparse((scheme, netloc, path or "/", "", urlencode(q), ""))


async def expand_short_social_url(url: str, client: httpx.AsyncClient) -> str:
    """Follow redirects for vm.tiktok / vt.tiktok / fb.watch / instagr.am short links."""
    host = (urlparse(url).hostname or "").lower()
    short_hosts = ("vm.tiktok.com", "vt.tiktok.com", "fb.watch", "instagr.am", "fb.gg")
    if host not in short_hosts:
        return url
    try:
        resp = await client.head(url, follow_redirects=True, timeout=15.0)
        final = str(resp.url) if resp.url else url
        if final and final != url:
            return canonicalize_social_url(final)
    except Exception as e:
        logger.info("short-link expand failed for %s: %s", host, e)
        try:
            resp = await client.get(url, follow_redirects=True, timeout=15.0)
            final = str(resp.url) if resp.url else url
            if final and final != url:
                return canonicalize_social_url(final)
        except Exception:
            pass
    return url


def _dig(obj, *keys, default=None):
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _first_str(*vals) -> str:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            inner = v.get("text") or v.get("content") or ""
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""


def _video_from_data(data: dict, platform: str) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    # Hosted downloads (downloadMedia=true)
    downloads = data.get("downloads") or []
    if isinstance(downloads, list):
        for item in downloads:
            if not isinstance(item, dict):
                continue
            if (item.get("type") or "").lower() in ("video", "") or item.get("cdnUrl"):
                cdn = item.get("cdnUrl") or item.get("originalUrl")
                if isinstance(cdn, str) and cdn.startswith("http"):
                    return cdn
    media = data.get("media") if isinstance(data.get("media"), dict) else {}
    for key in (
        "downloadWithoutWatermarkUrl",
        "downloadUrl",
        "videoHdUrl",  # Facebook HD
        "videoUrl",
        "video_url",
        "url",
        "playUrl",
    ):
        val = media.get(key)
        if isinstance(val, str) and val.startswith("http"):
            # skip Instagram page URLs mistaken for media
            if "instagram.com/" in val and ("/reel" in val or "/p/" in val or "/tv/" in val):
                continue
            if "facebook.com/" in val and "/reel/" not in val and "fbcdn" not in val and "video" not in val:
                # allow fbcdn video hosts; skip facebook.com page links
                if "fbcdn.net" not in val and "video-" not in val:
                    continue
            return val
    # Instagram carousel: first child with video
    children = media.get("carouselChildren") if isinstance(media, dict) else None
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict):
                continue
            v = child.get("videoUrl")
            if isinstance(v, str) and v.startswith("http"):
                return v
    # Nested fallbacks
    for path in (
        ("post", "media", "videoHdUrl"),
        ("post", "media", "videoUrl"),
        ("post", "videoUrl"),
        ("video", "media", "downloadUrl"),
        ("reel", "videoUrl"),
    ):
        val = _dig(data, *path)
        if isinstance(val, str) and val.startswith("http"):
            return val
    return None


def _thumb_from_data(data: dict) -> str:
    media = data.get("media") if isinstance(data.get("media"), dict) else {}
    for key in ("thumbnailUrl", "displayUrl", "imageUrl", "coverUrl", "thumbnail"):
        val = media.get(key) or data.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    return _first_str(
        _dig(data, "video", "thumbnailUrl"),
        _dig(data, "post", "displayUrl"),
        _dig(data, "post", "thumbnailUrl"),
    )


def _caption_from_data(data: dict, platform: str) -> str:
    if platform == "tiktok":
        return _first_str(
            _dig(data, "video", "caption"),
            data.get("caption"),
            data.get("description"),
        )
    if platform == "instagram":
        return _first_str(
            _dig(data, "post", "caption"),
            data.get("caption"),
            data.get("description"),
            _dig(data, "media", "caption"),
        )
    if platform == "youtube":
        return _first_str(
            _dig(data, "video", "description"),
            _dig(data, "video", "title"),
            data.get("description"),
            data.get("title"),
        )
    if platform == "facebook":
        return _first_str(
            _dig(data, "post", "description"),
            _dig(data, "post", "text"),
            _dig(data, "post", "message"),
            _dig(data, "post", "caption"),
            data.get("description"),
            data.get("text"),
            data.get("caption"),
            data.get("transcript"),
        )
    return _first_str(data.get("caption"), data.get("description"), data.get("title"))


def _author_from_data(data: dict, platform: str) -> str:
    author = data.get("author")
    if isinstance(author, dict):
        h = _first_str(
            author.get("handle"),
            author.get("username"),
            author.get("nickname"),
            author.get("name"),
        )
        if h:
            return h.lstrip("@")
        # Facebook sometimes only exposes profileUrl
        profile = author.get("profileUrl") or ""
        if isinstance(profile, str) and "facebook.com/" in profile:
            slug = profile.rstrip("/").rsplit("/", 1)[-1]
            if slug and slug not in ("profile.php", "people"):
                return slug.lstrip("@")
    if platform == "youtube":
        ch = data.get("channel") or _dig(data, "video", "channel") or {}
        if isinstance(ch, dict):
            h = _first_str(ch.get("handle"), ch.get("title"), ch.get("name"))
            if h:
                return h.lstrip("@")
    if platform == "facebook":
        page = data.get("page") or _dig(data, "post", "author") or {}
        if isinstance(page, dict):
            h = _first_str(page.get("name"), page.get("username"), page.get("handle"))
            if h:
                return h.lstrip("@")
    if platform == "instagram":
        owner = data.get("owner") or _dig(data, "post", "owner") or {}
        if isinstance(owner, dict):
            h = _first_str(owner.get("handle"), owner.get("username"), owner.get("fullName"))
            if h:
                return h.lstrip("@")
    return ""


def _title_from_caption(caption: str, author: str) -> str:
    if caption:
        return caption.split("\n", 1)[0][:120]
    if author:
        return f"Video by {author}"
    return ""


async def fetch_socialfetch_platform(
    url: str,
    platform: str,
    client: httpx.AsyncClient,
    *,
    download_media: Optional[bool] = None,
) -> Optional[dict]:
    key = socialfetch_api_key()
    if not key or platform not in _ENDPOINTS:
        return None

    path, supports_dl = _ENDPOINTS[platform]
    want_dl = socialfetch_download_media() if download_media is None else download_media
    params: dict = {"url": url}
    if supports_dl and want_dl:
        params["downloadMedia"] = "true"

    headers = {"Accept": "application/json", "x-api-key": key}
    try:
        resp = await client.get(
            f"{_BASE}{path}",
            params=params,
            headers=headers,
            timeout=60.0,
        )
    except Exception as e:
        logger.warning("SocialFetch %s request failed: %s", platform, e)
        return None

    if resp.status_code == 401:
        logger.info("SocialFetch auth failed — check SOCIALFETCH_API_KEY")
        return None
    if resp.status_code == 402:
        logger.info("SocialFetch insufficient credits")
        return None
    if resp.status_code >= 400:
        logger.info("SocialFetch %s HTTP %s: %s", platform, resp.status_code, (resp.text or "")[:180])
        return None

    try:
        payload = resp.json()
    except Exception:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None

    status = (data.get("lookupStatus") or "").lower()
    if status and status not in ("found",):
        logger.info("SocialFetch %s lookupStatus=%s", platform, status)
        return None

    caption = _caption_from_data(data, platform)
    author = _author_from_data(data, platform)
    thumb = _thumb_from_data(data)
    video = _video_from_data(data, platform)

    # Cheap path missed video — optional paid hosted download retry
    if not video and supports_dl and not want_dl and (os.getenv("SOCIALFETCH_AUTO_DOWNLOAD") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return await fetch_socialfetch_platform(
            url, platform, client, download_media=True
        )

    if not video and not caption:
        return None

    title = _title_from_caption(caption, author)
    # YouTube often has a better title field
    if platform == "youtube":
        yt_title = _first_str(_dig(data, "video", "title"), data.get("title"))
        if yt_title:
            title = yt_title[:120]

    credits = _dig(payload, "meta", "creditsCharged")
    logger.info(
        "SocialFetch %s OK video=%s caption=%s chars author=%s credits=%s",
        platform,
        bool(video),
        len(caption or ""),
        author,
        credits,
    )
    return {
        "title": title,
        "description": caption,
        "caption": caption,
        "uploader": author,
        "thumbnail": thumb or "",
        "video_url": video if isinstance(video, str) else None,
        "page_url": url,
        "source": f"socialfetch_{platform}",
        "platform": platform,
    }


async def resolve_social_media(url: str) -> Optional[dict]:
    """
    Resolve caption + optional video URL for a social cooking link.

    Order: SocialFetch → Instagram extras (IG only) → Cobalt (if COBALT_API_URL).
    yt-dlp remains the last resort in ai.py.
    """
    if not url:
        return None

    now = time.time()
    cached = _resolve_cache.get(url)
    if cached and cached[0] > now:
        return cached[1]

    meta: Optional[dict] = None
    async with httpx.AsyncClient(timeout=90.0) as client:
        resolved = canonicalize_social_url(url)
        resolved = await expand_short_social_url(resolved, client)
        resolved = canonicalize_social_url(resolved)

        platform = detect_social_platform(resolved) or detect_social_platform(url)
        if not platform:
            _resolve_cache[url] = (now + _RESOLVE_CACHE_SECS, None)
            return None

        # Prefer cache hit on canonical form too
        if resolved != url:
            cached2 = _resolve_cache.get(resolved)
            if cached2 and cached2[0] > now:
                _resolve_cache[url] = cached2
                return cached2[1]

        meta = await fetch_socialfetch_platform(resolved, platform, client)

        # Instagram: keep GraphQL / oEmbed / OG when SocialFetch misses text+video
        if platform == "instagram" and (
            not meta or (not meta.get("video_url") and not meta.get("caption"))
        ):
            from services.instagram_media import resolve_instagram_media

            ig = await resolve_instagram_media(resolved)
            if ig:
                if meta:
                    from services.cobalt_media import merge_social_meta

                    meta = merge_social_meta(meta, ig)
                else:
                    meta = ig

        # Cobalt fills missing video_url when configured
        needs_video = not meta or not meta.get("video_url")
        if needs_video:
            try:
                from services.cobalt_media import (
                    cobalt_enabled,
                    fetch_via_cobalt,
                    merge_social_meta,
                )

                if cobalt_enabled():
                    cobalt = await fetch_via_cobalt(resolved, client, platform=platform)
                    meta = merge_social_meta(meta, cobalt)
            except Exception as e:
                logger.warning("Cobalt fallback failed: %s", e)

        if meta and not meta.get("page_url"):
            meta["page_url"] = resolved
        elif meta and resolved != url:
            meta["page_url"] = resolved

    expires = now + _RESOLVE_CACHE_SECS
    _resolve_cache[url] = (expires, meta)
    if resolved != url:
        _resolve_cache[resolved] = (expires, meta)
    if len(_resolve_cache) > 64:
        # Drop expired / oldest entries
        for key in list(_resolve_cache.keys()):
            if _resolve_cache[key][0] <= now:
                _resolve_cache.pop(key, None)
        while len(_resolve_cache) > 64:
            oldest = min(_resolve_cache.items(), key=lambda kv: kv[1][0])[0]
            _resolve_cache.pop(oldest, None)
    return meta


_TRANSCRIPT_PATHS = {
    "instagram": "/v1/instagram/posts/transcript",
    "tiktok": "/v1/tiktok/videos/transcript",
    "youtube": "/v1/youtube/videos/transcript",
    "facebook": "/v1/facebook/posts/transcript",
}


async def fetch_socialfetch_transcript(
    url: str,
    platform: Optional[str] = None,
    *,
    client: Optional[httpx.AsyncClient] = None,
    use_ai_fallback: bool = False,
) -> Optional[str]:
    """
    Pull spoken transcript from SocialFetch (1 credit typical; TikTok AI = up to 11).

    Returns plain text or None. Does not raise on miss — callers fall back to Whisper.
    """
    key = socialfetch_api_key()
    if not key:
        return None
    resolved = canonicalize_social_url(url) or url
    plat = platform or detect_social_platform(resolved)
    path = _TRANSCRIPT_PATHS.get(plat or "")
    if not path:
        return None

    params: dict = {"url": resolved}
    if plat == "tiktok" and use_ai_fallback:
        params["useAiFallback"] = "true"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=90.0)
    try:
        resp = await client.get(
            f"{_BASE}{path}",
            params=params,
            headers={"x-api-key": key, "Accept": "application/json"},
        )
    except Exception as e:
        logger.warning("SocialFetch transcript request failed: %s", e)
        return None
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code == 401:
        logger.info("SocialFetch transcript auth failed")
        return None
    if resp.status_code == 402:
        logger.info("SocialFetch insufficient credits for transcript")
        return None
    if resp.status_code >= 400:
        logger.info(
            "SocialFetch transcript HTTP %s: %s",
            resp.status_code,
            (resp.text or "")[:180],
        )
        return None

    try:
        payload = resp.json()
    except Exception:
        return None

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None
    status = (data.get("lookupStatus") or "").lower()
    credits = _dig(payload, "meta", "creditsCharged")
    logger.info(
        "SocialFetch transcript platform=%s status=%s credits=%s",
        plat,
        status or "?",
        credits,
    )

    # Instagram: data.transcripts[] with {text}
    rows = data.get("transcripts")
    if isinstance(rows, list):
        parts = []
        for row in rows:
            if isinstance(row, dict) and row.get("text"):
                parts.append(str(row["text"]).strip())
            elif isinstance(row, str) and row.strip():
                parts.append(row.strip())
        if parts:
            return " ".join(parts)

    # YouTube / generic: data.transcript.plainText or string
    tr = data.get("transcript")
    if isinstance(tr, dict):
        plain = tr.get("plainText") or tr.get("content") or tr.get("text")
        if plain:
            return str(plain).strip()
    if isinstance(tr, str) and tr.strip():
        return tr.strip()

    # Some payloads put text at top level
    if data.get("text"):
        return str(data["text"]).strip()
    return None
