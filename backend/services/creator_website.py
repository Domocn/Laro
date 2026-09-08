"""
Discover a social creator's recipe website (link-in-bio style) so imports can
offer the full written recipe when a reel only has spoken / on-screen amounts.

Uses DuckDuckGo HTML search + handle→domain heuristics. Never hits Instagram
profile pages (often blocked). Best-effort only — failures return None.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, Optional[dict]]] = {}
_CACHE_SECS = 6 * 60 * 60.0

_SOCIAL_HOST_FRAGMENTS = (
    "instagram.com",
    "instagr.am",
    "tiktok.com",
    "facebook.com",
    "fb.watch",
    "fb.com",
    "youtube.com",
    "youtu.be",
    "twitter.com",
    "x.com",
    "threads.net",
    "linktr.ee",
    "linktree.com",
    "beacons.ai",
    "bio.site",
    "carrd.co",
    "duckduckgo.com",
)

_SKIP_PATH_HINTS = (
    "/category/",
    "/tag/",
    "/author/",
    "/page/",
    "/shop",
    "/product",
    "/cart",
    "/account",
    "/login",
    "/search",
    "/?",
)

# Plain browser UA — DuckDuckGo HTML often returns an empty 202 shell to bot-like agents.
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _norm_handle(handle: Optional[str]) -> str:
    h = (handle or "").strip().lstrip("@").strip()
    h = re.sub(r"\s+", "", h)
    return h.lower()


def is_social_or_linkpage_host(host: str) -> bool:
    host = (host or "").lower().removeprefix("www.")
    return any(frag in host for frag in _SOCIAL_HOST_FRAGMENTS)


def handle_domain_candidates(handle: str) -> list[str]:
    """eliya.eats → eliyaeats.com, eliya-eats.com, …"""
    h = _norm_handle(handle)
    if not h or len(h) < 3:
        return []
    compact = re.sub(r"[^a-z0-9]", "", h)
    dashed = re.sub(r"[^a-z0-9]+", "-", h).strip("-")
    underscored = h.replace(".", "_").replace("-", "_")
    bases = []
    for b in (compact, dashed, underscored, h.replace(".", "")):
        if b and b not in bases and len(b) >= 3:
            bases.append(b)
    out: list[str] = []
    for b in bases:
        for tld in ("com", "co", "net", "food", "kitchen"):
            host = f"{b}.{tld}"
            if host not in out:
                out.append(host)
    return out[:12]


def _extract_ddg_urls(html: str) -> list[str]:
    urls: list[str] = []
    for m in re.finditer(r"uddg=([^&\"'>\s]+)", html or ""):
        try:
            u = unquote(m.group(1))
        except Exception:
            continue
        if not u.startswith("http"):
            continue
        if u not in urls:
            urls.append(u)
    # Fallback: plain result links
    for m in re.finditer(r'href="(https?://[^"]+)"', html or ""):
        u = m.group(1)
        if "duckduckgo.com" in u:
            if "uddg=" in u:
                qs = parse_qs(urlparse(u).query)
                if qs.get("uddg"):
                    u = unquote(qs["uddg"][0])
                else:
                    continue
            else:
                continue
        if u.startswith("http") and u not in urls:
            urls.append(u)
    return urls


async def _ddg_search(query: str, client: httpx.AsyncClient, limit: int = 12) -> list[str]:
    # Prefer GET — POST often returns a challenge/empty result shell without uddg= links.
    try:
        resp = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={
                "User-Agent": _UA,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=20.0,
            follow_redirects=True,
        )
        if resp.status_code >= 400:
            logger.info("DDG search HTTP %s for %r", resp.status_code, query[:80])
            return []
        urls = _extract_ddg_urls(resp.text)
        if not urls:
            # One POST retry for environments that prefer form search
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={
                    "User-Agent": _UA,
                    "Accept": "text/html",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=20.0,
                follow_redirects=True,
            )
            urls = _extract_ddg_urls(resp.text)
        return urls[:limit]
    except Exception as e:
        logger.warning("DDG search failed for %r: %s", query[:80], e)
        return []


def _website_home(url: str) -> Optional[str]:
    try:
        p = urlparse(url)
    except Exception:
        return None
    host = (p.hostname or "").lower()
    if not host or is_social_or_linkpage_host(host):
        return None
    # Prefer apex site home
    return f"https://{host}/"


def _looks_like_recipe_page(url: str) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    host = (p.hostname or "").lower()
    if not host or is_social_or_linkpage_host(host):
        return False
    path = (p.path or "/").lower()
    if path in ("", "/"):
        return False
    if any(h in path for h in _SKIP_PATH_HINTS):
        return False
    # Recipe slugs are usually multi-segment or long kebab titles
    slug = path.strip("/").split("/")[-1]
    if len(slug) < 8:
        return False
    if "-" not in slug and "_" not in slug:
        return False
    return True


def caption_mentions_full_recipe(text: str) -> bool:
    t = (text or "").lower()
    markers = (
        "link in bio",
        "linked in my bio",
        "link in my bio",
        "full recipe",
        "written recipe",
        "recipe is linked",
        "recipes in bio",
        "all my latest recipes",
        "on my website",
        "on my site",
    )
    return any(m in t for m in markers)


def _search_terms_from_caption(caption: str, title: str = "") -> list[str]:
    """Build short search queries from reel title/caption."""
    terms: list[str] = []
    if title and len(title.strip()) > 4:
        terms.append(re.sub(r"\s+", " ", title.strip())[:80])
    first = ""
    for line in (caption or "").splitlines():
        clean = re.sub(r"[^\w\s\-']+", " ", line, flags=re.UNICODE)
        clean = re.sub(r"\s+", " ", clean).strip()
        if len(clean) < 12:
            continue
        # Skip pure macro lines
        if re.search(r"\b(calories?|protein|carbs?|macros?)\b", clean, re.I) and len(clean) < 40:
            continue
        first = clean[:90]
        break
    if first:
        terms.append(first)
    # Drop filler words for a tighter site: query
    for base in list(terms):
        words = [
            w
            for w in re.findall(r"[A-Za-z0-9']+", base)
            if w.lower()
            not in {
                "i",
                "am",
                "the",
                "a",
                "an",
                "and",
                "or",
                "to",
                "for",
                "my",
                "this",
                "that",
                "with",
                "from",
                "just",
                "about",
                "obsessed",
                "recipe",
                "recipes",
            }
        ]
        if len(words) >= 3:
            terms.append(" ".join(words[:8]))
    # Dedupe preserve order
    out: list[str] = []
    for t in terms:
        if t and t not in out:
            out.append(t)
    return out[:4]


def _normalize_recipe_url(url: str) -> str:
    u = (url or "").split("#")[0].split("?")[0].rstrip("/") + "/"
    return u


def _score_recipe_url(url: str, tokens: set[str]) -> int:
    path = (urlparse(url).path or "").lower()
    score = 0
    for tok in tokens:
        if len(tok) >= 4 and tok in path:
            score += 2 if len(tok) >= 6 else 1
    if "recipe" in path or "pancake" in path or "bowl" in path:
        score += 1
    return score


async def _find_matching_recipe_url(
    website: str,
    host: str,
    caption: str,
    recipe_title: str,
    client: httpx.AsyncClient,
) -> Optional[str]:
    """
    Prefer an on-site search page (WordPress ?s=) via Jina — DDG site: queries are
    flaky / rate-limited. Fall back to a couple of DDG queries when available.
    """
    terms = _search_terms_from_caption(caption, recipe_title)
    if not terms:
        return None

    token_set: set[str] = set()
    for term in terms:
        for w in re.findall(r"[a-z0-9]{3,}", term.lower()):
            if w not in {"the", "and", "for", "with", "from", "this", "that", "bowl", "recipe"}:
                token_set.add(w)

    candidates: list[str] = []

    # On-site search (works for most recipe blogs even behind Cloudflare when via Jina)
    for term in terms[:2]:
        q = quote_plus(term.strip()[:80])
        search_url = f"https://{host}/?s={q}"
        try:
            jr = await client.get(
                f"https://r.jina.ai/{search_url}",
                headers={"Accept": "text/plain", "User-Agent": _UA},
                timeout=35.0,
                follow_redirects=True,
            )
            body = jr.text or ""
            # Jina occasionally surfaces Cloudflare HTML with a non-200; still scrape links.
            if "Just a moment" in body and host not in body.lower():
                body = ""
            if body:
                for m in re.finditer(
                    rf"https?://(?:www\.)?{re.escape(host)}/[^\s\)\]\>\"']+",
                    body,
                    flags=re.I,
                ):
                    u = m.group(0).rstrip(".,;)")
                    if _looks_like_recipe_page(u):
                        candidates.append(_normalize_recipe_url(u))
        except Exception as e:
            logger.info("On-site search via Jina failed for %s: %s", host, e)

        if candidates:
            break

    # Light DDG fallback (may be empty under rate limits)
    if not candidates:
        for term in terms[:2]:
            for q in (f"{host} {term}", f"site:{host} {term}"):
                for u in await _ddg_search(q, client, limit=8):
                    try:
                        uh = (urlparse(u).hostname or "").lower().removeprefix("www.")
                    except Exception:
                        continue
                    if uh == host and _looks_like_recipe_page(u):
                        candidates.append(_normalize_recipe_url(u))
            if candidates:
                break

    if not candidates:
        return None

    # Dedup + score
    ranked: list[tuple[int, str]] = []
    seen = set()
    for u in candidates:
        if u in seen:
            continue
        seen.add(u)
        ranked.append((_score_recipe_url(u, token_set), u))
    ranked.sort(key=lambda x: x[0], reverse=True)
    best_score, best = ranked[0]
    if best_score <= 0 and recipe_title:
        # Still offer the top hit when title tokens don't overlap (variant reels)
        return best
    return best if best_score > 0 else ranked[0][1]


async def resolve_creator_website(
    handle: Optional[str],
    *,
    caption: str = "",
    recipe_title: str = "",
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[dict]:
    """
    Find a creator recipe website and optionally a matching recipe page.

    Returns:
      {
        "creator_website": "https://eliyaeats.com/",
        "suggested_recipe_url": "https://eliyaeats.com/…/" | None,
        "creator_website_hint": "…",
        "via": "ddg"|"handle-heuristic",
      }
    """
    h = _norm_handle(handle)
    if not h:
        return None

    cache_key = h
    now = time.time()
    cached = _cache.get(cache_key)
    # Cache only the website home; recipe suggestion depends on caption.
    cached_site: Optional[str] = None
    cached_via = ""
    if cached and now - cached[0] < _CACHE_SECS:
        payload = cached[1]
        if payload is None:
            return None
        cached_site = payload.get("creator_website")
        cached_via = payload.get("via") or "cache"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient()

    try:
        website = cached_site
        via = cached_via

        if not website:
            # 1) Web search for the handle's recipe site
            queries = [
                f"{h} recipes",
                f"@{h} recipe blog",
                f"{h.replace('.', ' ')} recipes website",
            ]
            compact = re.sub(r"[^a-z0-9]", "", h)
            if compact and compact != h:
                queries.append(f"{compact} recipes")

            ranked: list[str] = []
            for q in queries:
                ranked.extend(await _ddg_search(q, client, limit=10))

            for u in ranked:
                home = _website_home(u)
                if home:
                    website = home
                    via = "ddg"
                    break

            # 2) Handle → domain heuristic (eliya.eats → eliyaeats.com)
            if not website:
                for host in handle_domain_candidates(h):
                    # DDG already failed — accept candidates that appear in any ranked URL host
                    # or that return something other than NXDOMAIN-style failures via GET.
                    probe = f"https://{host}/"
                    try:
                        resp = await client.get(
                            probe,
                            headers={"User-Agent": _UA, "Accept": "text/html"},
                            timeout=12.0,
                            follow_redirects=True,
                        )
                        # Cloudflare 403 still means the site exists
                        if resp.status_code in (200, 301, 302, 303, 307, 308, 403, 401, 429):
                            final_host = (urlparse(str(resp.url)).hostname or host).lower()
                            if not is_social_or_linkpage_host(final_host):
                                website = f"https://{final_host}/"
                                via = "handle-heuristic"
                                break
                    except Exception:
                        continue

            if not website:
                # Brief negative cache — search is flaky under rate limits.
                _cache[cache_key] = (now - _CACHE_SECS + 120.0, None)
                return None

            _cache[cache_key] = (
                now,
                {"creator_website": website, "via": via},
            )

        host = (urlparse(website).hostname or "").lower().removeprefix("www.")
        suggested = await _find_matching_recipe_url(
            website, host, caption, recipe_title, client
        )

        handle_disp = f"@{h}"
        if suggested:
            hint = (
                f"{handle_disp} has a recipe website — for exact amounts and steps, "
                f"try importing from their written recipe."
            )
        else:
            hint = (
                f"{handle_disp} looks like they have a recipe website "
                f"({host}). Check it for the full written recipe."
            )

        return {
            "creator_website": website,
            "suggested_recipe_url": suggested,
            "creator_website_hint": hint,
            "via": via or "ddg",
        }
    finally:
        if owns_client and client is not None:
            await client.aclose()
