"""
Fetch public Instagram reel/post media without requiring yt-dlp cookies.

Order (see resolve_instagram_media):
  1. Optional REEL_MEDIA_API_URL
  2. Public web GraphQL shortcode (caption + CDN mp4) — often blocked from
     datacenter IPs with HTTP 401 "Please wait a few minutes"
  3. Instagram oEmbed + OG page tags (caption / author; no video) — works from
     OVH when GraphQL is rate-limited; recipe then uses caption-only LLM path

Callers must still support shared video upload / caption paste / yt-dlp cookies.

Optional override:
  REEL_MEDIA_API_URL=https://your-downloader.example/  # GET ?url= → JSON
  Expected JSON keys (any of): download_link, video_url, url, media_url
  Optional: title, description, caption, author, username, thumbnail
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional
from urllib.parse import quote, urlparse

import httpx

logger = logging.getLogger(__name__)

# Web app id used by www.instagram.com (public).
_IG_APP_ID = "936619743392459"

# Polaris shortcode → v1 web_info (works anonymously for many public reels as of 2025–2026).
# Override with INSTAGRAM_GRAPHQL_DOC_ID when Instagram rotates this.
_DEFAULT_DOC_IDS = (
    "24368985919464652",
    "27128499623469141",
)

_SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)

# After Instagram returns require_login / rate-limit on GraphQL, skip GraphQL
# for a while and use oEmbed (avoids hammering the VPS IP into a longer ban).
_graphql_cooldown_until = 0.0
_GRAPHQL_COOLDOWN_SECS = 180.0

# Short in-process cache so import-url → metadata + download don't re-hit IG.
_resolve_cache: dict[str, tuple[float, Optional[dict]]] = {}
_RESOLVE_CACHE_SECS = 90.0


def instagram_shortcode(url: str) -> Optional[str]:
    if not url:
        return None
    m = _SHORTCODE_RE.search(url)
    return m.group(1) if m else None


def _doc_ids() -> list[str]:
    primary = (os.getenv("INSTAGRAM_GRAPHQL_DOC_ID") or "").strip()
    ids: list[str] = []
    if primary:
        ids.append(primary)
    for d in _DEFAULT_DOC_IDS:
        if d not in ids:
            ids.append(d)
    return ids


def _pick_best_video_url(versions: list) -> Optional[str]:
    if not isinstance(versions, list) or not versions:
        return None
    best = None
    best_area = -1
    for v in versions:
        if not isinstance(v, dict):
            continue
        u = v.get("url")
        if not u or not isinstance(u, str):
            continue
        area = int(v.get("width") or 0) * int(v.get("height") or 0)
        if area >= best_area:
            best_area = area
            best = u
    return best


def _dig_items(payload: dict) -> Optional[dict]:
    """Normalize GraphQL / web_info payload to a single media item dict."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None
    web = data.get("xdt_api__v1__media__shortcode__web_info")
    if isinstance(web, dict):
        items = web.get("items")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            return items[0]
    # Older xdt_shortcode_media shape
    node = data.get("xdt_shortcode_media") or data.get("shortcode_media")
    if isinstance(node, dict):
        return node
    return None


def _item_to_meta(item: dict, page_url: str) -> dict:
    caption = ""
    cap = item.get("caption")
    if isinstance(cap, dict):
        caption = (cap.get("text") or "").strip()
    elif isinstance(cap, str):
        caption = cap.strip()
    if not caption:
        edge = (
            (item.get("edge_media_to_caption") or {})
            .get("edges") or [{}]
        )
        if edge and isinstance(edge[0], dict):
            caption = ((edge[0].get("node") or {}).get("text") or "").strip()

    user = item.get("user") or item.get("owner") or {}
    username = ""
    if isinstance(user, dict):
        username = (user.get("username") or "").strip()

    video_url = _pick_best_video_url(item.get("video_versions") or [])
    if not video_url:
        video_url = item.get("video_url") or None

    thumb = item.get("thumbnail_url") or item.get("display_url") or ""
    if not thumb:
        thumbs = item.get("image_versions2") or {}
        candidates = thumbs.get("candidates") if isinstance(thumbs, dict) else None
        if isinstance(candidates, list) and candidates:
            thumb = candidates[0].get("url") or ""

    title = ""
    if caption:
        title = caption.split("\n", 1)[0][:120]
    if username and not title:
        title = f"Reel by {username}"

    return {
        "title": title,
        "description": caption,
        "caption": caption,
        "uploader": username,
        "thumbnail": thumb or "",
        "video_url": video_url,
        "page_url": page_url,
        "source": "instagram_graphql",
    }


async def fetch_via_reel_media_api(url: str, client: httpx.AsyncClient) -> Optional[dict]:
    """Optional external downloader (REEL_MEDIA_API_URL shape)."""
    base = (os.getenv("REEL_MEDIA_API_URL") or "").strip().rstrip("/")
    if not base:
        return None
    try:
        headers = {}
        api_key = (os.getenv("REEL_MEDIA_API_KEY") or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["x-access-key"] = api_key
        resp = await client.get(base, params={"url": url}, headers=headers, timeout=45.0)
        if resp.status_code != 200:
            logger.info("REEL_MEDIA_API_URL status %s for %s", resp.status_code, url)
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        # unwrap {data: {...}} shapes
        if isinstance(data.get("data"), dict) and not (
            data.get("download_link") or data.get("video_url") or data.get("downloadUrl")
        ):
            data = data["data"]
        video = (
            data.get("download_link")
            or data.get("downloadUrl")
            or data.get("download_url")
            or data.get("video_url")
            or data.get("videoUrl")
            or data.get("media_url")
            or data.get("url")
        )
        # Avoid treating the Instagram page URL as the media URL
        if isinstance(video, str) and "instagram.com/" in video and (
            "/reel" in video or "/p/" in video
        ):
            video = None
        caption = (
            data.get("description")
            or data.get("caption")
            or data.get("title")
            or data.get("text")
            or ""
        )
        if isinstance(caption, dict):
            caption = caption.get("text") or ""
        caption = (caption or "").strip()
        author = (
            data.get("author")
            or data.get("username")
            or data.get("owner")
            or data.get("uploader")
            or ""
        )
        if isinstance(author, dict):
            author = author.get("username") or author.get("name") or ""
        author = (author or "").strip().lstrip("@")
        thumb = data.get("thumbnail") or data.get("thumbnail_url") or data.get("cover") or ""
        if not video and not caption:
            return None
        title = (caption.split("\n", 1)[0][:120] if caption else "") or (
            f"Reel by {author}" if author else ""
        )
        return {
            "title": title,
            "description": caption,
            "caption": caption,
            "uploader": author,
            "thumbnail": thumb or "",
            "video_url": video if isinstance(video, str) else None,
            "page_url": url,
            "source": "reel_media_api",
        }
    except Exception as e:
        logger.warning("REEL_MEDIA_API_URL failed: %s", e)
        return None


def caption_looks_like_recipe(text: str) -> bool:
    """Heuristic: caption has enough cookable signal to try text-only extraction."""
    t = (text or "").lower()
    if len(t.strip()) < 40:
        return False
    markers = (
        "ingredient",
        "ingredients",
        "tbsp",
        "tsp",
        "tablespoon",
        "teaspoon",
        "cup ",
        "cups ",
        "gram",
        "grams",
        " g ",
        "ml ",
        "oz ",
        "preheat",
        "bake",
        "oven",
        "simmer",
        "saute",
        "sauté",
        "recipe",
        "serves",
        "serving",
        "minutes",
        "mins",
        "whisk",
        "chop",
        "dice",
        "mix until",
        "add the",
        "step 1",
        "1.",
        "2.",
    )
    hits = sum(1 for m in markers if m in t)
    # Numbers + unit-ish words often mean a recipe list
    has_qty = bool(re.search(r"\b\d+([./]\d+)?\s*(g|kg|ml|l|cup|cups|tbsp|tsp|oz)\b", t))
    return hits >= 2 or (hits >= 1 and has_qty)



def _mark_graphql_cooldown(reason: str) -> None:
    global _graphql_cooldown_until
    _graphql_cooldown_until = time.time() + _GRAPHQL_COOLDOWN_SECS
    logger.info(
        "Instagram GraphQL cooldown %ss (%s)",
        int(_GRAPHQL_COOLDOWN_SECS),
        reason,
    )


def _graphql_on_cooldown() -> bool:
    return time.time() < _graphql_cooldown_until


async def fetch_instagram_oembed_meta(url: str, client: httpx.AsyncClient) -> Optional[dict]:
    """
    Caption + author via Instagram's public oEmbed endpoint.
    Works from datacenter IPs when GraphQL returns require_login.
    Does not provide a downloadable video URL.
    """
    code = instagram_shortcode(url)
    page_url = f"https://www.instagram.com/reel/{code}/" if code else url
    endpoints = [
        f"https://www.instagram.com/api/v1/oembed/?url={quote(page_url, safe='')}",
        f"https://www.instagram.com/api/v1/oembed/?url={quote(url, safe='')}",
    ]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/",
    }
    for endpoint in endpoints:
        try:
            resp = await client.get(endpoint, headers=headers, timeout=20.0, follow_redirects=True)
        except Exception as e:
            logger.warning("Instagram oEmbed error: %s", e)
            continue
        if resp.status_code != 200:
            logger.info("Instagram oEmbed HTTP %s", resp.status_code)
            continue
        ctype = (resp.headers.get("content-type") or "").lower()
        if "json" not in ctype and not (resp.text or "").lstrip().startswith("{"):
            continue
        try:
            data = resp.json()
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        caption = (data.get("title") or "").strip()
        author = (data.get("author_name") or "").strip()
        if not caption and not author:
            continue
        title = caption.split("\n", 1)[0][:120] if caption else (f"Reel by {author}" if author else "")
        logger.info(
            "Instagram oEmbed OK author=%s caption=%s chars",
            author,
            len(caption),
        )
        return {
            "title": title,
            "description": caption,
            "caption": caption,
            "uploader": author,
            "thumbnail": data.get("thumbnail_url") or "",
            "video_url": None,
            "page_url": page_url,
            "source": "instagram_oembed",
        }
    return None


async def fetch_instagram_og_meta(url: str, client: httpx.AsyncClient) -> Optional[dict]:
    """OG title/description from the public reel HTML (login-wall pages still expose these)."""
    code = instagram_shortcode(url)
    page_url = f"https://www.instagram.com/reel/{code}/" if code else url
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        resp = await client.get(page_url, headers=headers, timeout=20.0, follow_redirects=True)
    except Exception as e:
        logger.warning("Instagram OG page fetch failed: %s", e)
        return None
    if resp.status_code != 200 or not resp.text:
        return None
    html = resp.text

    def _meta(prop: str) -> str:
        m = re.search(
            rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']*)["\']',
            html,
            re.IGNORECASE,
        )
        if not m:
            m = re.search(
                rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']{re.escape(prop)}["\']',
                html,
                re.IGNORECASE,
            )
        if not m:
            return ""
        # Unescape common HTML entities in OG strings
        return (
            m.group(1)
            .replace("&quot;", '"')
            .replace("&#039;", "'")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .strip()
        )

    title = _meta("og:title")
    desc = _meta("og:description")
    image = _meta("og:image")
    # og:description is often "N likes, M comments - user on DATE: \"caption...\""
    caption = desc
    m = re.search(r':\s*[\"“](.+)[\"”]\s*$', desc, re.DOTALL)
    if m:
        caption = m.group(1).strip()
    uploader = ""
    um = re.search(r"instagram\.com/([A-Za-z0-9._]+)", _meta("og:url") or "")
    if " on Instagram" in title:
        uploader = title.split(" on Instagram", 1)[0].strip()
    elif um:
        uploader = um.group(1)

    if not caption and not title:
        return None
    body = caption or title
    logger.info("Instagram OG OK caption=%s chars uploader=%s", len(body), uploader)
    return {
        "title": (caption or title).split("\n", 1)[0][:120],
        "description": body,
        "caption": body,
        "uploader": uploader,
        "thumbnail": image,
        "video_url": None,
        "page_url": page_url,
        "source": "instagram_og",
    }


async def fetch_instagram_graphql_meta(url: str, client: httpx.AsyncClient) -> Optional[dict]:
    """Public GraphQL shortcode lookup. Returns meta dict or None."""
    if _graphql_on_cooldown():
        logger.info("Instagram GraphQL skipped (cooldown)")
        return None

    code = instagram_shortcode(url)
    if not code:
        return None

    headers_nav = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    page_url = f"https://www.instagram.com/reel/{code}/"
    try:
        home = await client.get(
            "https://www.instagram.com/",
            headers=headers_nav,
            timeout=20.0,
            follow_redirects=True,
        )
        # Warm cookies / claim on the reel page before GraphQL (helps some IPs).
        await client.get(page_url, headers=headers_nav, timeout=20.0, follow_redirects=True)
    except Exception as e:
        logger.warning("Instagram homepage bootstrap failed: %s", e)
        return None

    csrf = client.cookies.get("csrftoken") or ""
    if not csrf:
        m = re.search(r'"csrf_token"\s*:\s*"([^"]+)"', home.text or "")
        csrf = m.group(1) if m else ""
    if not csrf:
        logger.info("No Instagram csrftoken — GraphQL shortcode lookup skipped")
        return None

    headers = {
        **headers_nav,
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.instagram.com",
        "Referer": page_url,
        "X-CSRFToken": csrf,
        "X-IG-App-ID": _IG_APP_ID,
        "X-ASBD-ID": "129477",
        "X-IG-WWW-Claim": "0",
        "X-Requested-With": "XMLHttpRequest",
    }
    variables = {
        "shortcode": code,
        "fetch_tagged_user_count": None,
        "hoisted_comment_id": None,
        "hoisted_reply_id": None,
    }

    for doc_id in _doc_ids():
        form = {
            "variables": json.dumps(variables, separators=(",", ":")),
            "doc_id": doc_id,
            "server_timestamps": "true",
        }
        try:
            resp = await client.post(
                "https://www.instagram.com/graphql/query",
                headers=headers,
                data=form,
                timeout=30.0,
            )
        except Exception as e:
            logger.warning("Instagram GraphQL doc_id=%s error: %s", doc_id, e)
            continue

        if resp.status_code in (401, 403):
            # Do not try other doc_ids — IP is rate-limited / login-walled.
            try:
                msg = (resp.json() or {}).get("message") or ""
            except Exception:
                msg = ""
            _mark_graphql_cooldown(f"HTTP {resp.status_code} {msg[:80]}")
            return None
        if resp.status_code != 200:
            logger.info("Instagram GraphQL HTTP %s doc_id=%s", resp.status_code, doc_id)
            continue

        try:
            payload = resp.json()
        except Exception:
            continue

        if payload.get("require_login") or (
            isinstance(payload.get("message"), str)
            and "wait a few minutes" in payload["message"].lower()
        ):
            _mark_graphql_cooldown(str(payload.get("message"))[:80])
            return None

        if payload.get("errors") and not payload.get("data"):
            logger.info(
                "Instagram GraphQL errors doc_id=%s: %s",
                doc_id,
                str(payload.get("errors"))[:180],
            )
            continue

        item = _dig_items(payload)
        if not item:
            continue
        meta = _item_to_meta(item, page_url)
        if meta.get("video_url") or meta.get("caption"):
            logger.info(
                "Instagram GraphQL OK shortcode=%s video=%s caption=%s chars",
                code,
                bool(meta.get("video_url")),
                len(meta.get("caption") or ""),
            )
            return meta

    return None


async def resolve_instagram_media(url: str) -> Optional[dict]:
    """
    Resolve caption + optional direct video URL for an Instagram reel/post.

    Prefers sources that yield video_url; always falls back to caption-only
    oEmbed/OG when GraphQL is rate-limited (common on VPS IPs).
    """
    if "instagram.com" not in (url or "").lower():
        return None

    now = time.time()
    cached = _resolve_cache.get(url)
    if cached and cached[0] > now:
        return cached[1]

    meta: Optional[dict] = None
    async with httpx.AsyncClient() as client:
        api_meta = await fetch_via_reel_media_api(url, client)
        if api_meta and (api_meta.get("video_url") or api_meta.get("caption")):
            meta = api_meta
        else:
            gql = await fetch_instagram_graphql_meta(url, client)
            if gql and (gql.get("video_url") or gql.get("caption")):
                meta = gql
            else:
                # Caption-only paths — enough for many recipe reels.
                oembed = await fetch_instagram_oembed_meta(url, client)
                if oembed and oembed.get("caption"):
                    meta = oembed
                else:
                    meta = await fetch_instagram_og_meta(url, client)

    _resolve_cache[url] = (now + _RESOLVE_CACHE_SECS, meta)
    # Bound cache size
    if len(_resolve_cache) > 64:
        oldest = min(_resolve_cache.items(), key=lambda kv: kv[1][0])[0]
        _resolve_cache.pop(oldest, None)
    return meta


async def download_url_bytes(
    media_url: str,
    max_bytes: int = 80 * 1024 * 1024,
    referer: str = "https://www.instagram.com/",
) -> Optional[tuple[bytes, str]]:
    """Download a CDN media URL. Returns (bytes, ext) or None."""
    if not media_url:
        return None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": referer,
        "Accept": "*/*",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            resp = await client.get(media_url, headers=headers)
            if resp.status_code != 200:
                logger.info("Media CDN HTTP %s", resp.status_code)
                return None
            data = resp.content
            if not data or len(data) > max_bytes:
                return None
            path = urlparse(media_url).path.lower()
            ext = ".mp4"
            for candidate in (".mp4", ".m4v", ".webm", ".mov", ".jpg", ".jpeg", ".png", ".webp"):
                if candidate in path:
                    ext = candidate if candidate != ".jpeg" else ".jpg"
                    break
            ct = (resp.headers.get("content-type") or "").lower()
            if "video" in ct and ext not in (".mp4", ".webm", ".mov", ".m4v"):
                ext = ".mp4"
            return data, ext
    except Exception as e:
        logger.warning("Media CDN download failed: %s", e)
        return None
