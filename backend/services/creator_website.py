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


def _handle_host_score(handle: str, host: str) -> int:
    """
    How likely is this hostname the creator's own site?
    Rejects weak DDG hits like paleorunningmomma.com for @running.and.mumming.
    """
    h = _norm_handle(handle)
    base = (host or "").lower().removeprefix("www.").split(":")[0].split(".")[0]
    if not h or not base:
        return 0
    compact = re.sub(r"[^a-z0-9]", "", h)
    score = 0
    if compact and compact in base:
        score += 10
    if base and len(base) >= 5 and base in compact:
        score += 8
    tokens = [t for t in re.split(r"[^a-z0-9]+", h) if len(t) >= 4]
    matched = [t for t in tokens if t in base]
    score += len(matched) * 3
    if tokens and base.startswith(tokens[0]):
        score += 4
    # Prefer hosts that are basically the handle (joytothefood, cindafit, eliyaeats)
    for cand in handle_domain_candidates(h):
        if cand.split(".")[0] == base:
            score += 12
            break
    return score


def host_plausibly_matches_handle(host: str, handle: str, *, min_score: int = 6) -> bool:
    return _handle_host_score(handle, host) >= min_score


def _slugify_recipe_query(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[“”\"'’]", "", t)
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    # Drop lead-magnet / promo / review noise tokens
    drop = {
        "comment", "send", "follow", "following", "link", "bio", "recipe", "recipes",
        "the", "and", "for", "with", "from", "this", "that", "your", "you", "are",
        "these", "those", "best", "ever", "turned", "out", "just", "like", "picture",
        "fluffy", "great", "tasting", "thank", "thanks", "much", "telling", "everyone",
        "use", "them", "were", "huge", "win", "our", "house", "didnt", "have", "hand",
        "so", "used", "suggested", "they", "cooked", "beautifully", "really", "tasty",
        "perfect", "doubled", "ate", "breakfast", "then", "again", "dinner", "amazing",
        "amp", "amped", "when", "yall", "love", "stuff", "as", "we", "do", "weekend",
        "ya", "how", "to", "make", "also", "details", "linked", "ill", "over", "sure",
    }
    parts = [p for p in t.split("-") if p and p not in drop and len(p) > 1]
    return "-".join(parts[:10])


def _food_phrase_candidates(blob: str) -> list[str]:
    """Pull likely dish names out of review-quote captions."""
    out: list[str] = []
    low = (blob or "").lower()
    for m in re.finditer(
        r"\b((?:protein\s+)?pancakes?\s+without\s+protein\s+powder)\b",
        low,
    ):
        out.append(m.group(1).strip())
    for m in re.finditer(
        r"\b(pancake(?:s)?\s+recipe\s+without\s+protein\s+powder)\b",
        low,
    ):
        out.append("pancakes without protein powder")
    for m in re.finditer(
        r"\b((?:caramel\s+)?slice\s+weet-?bix|weet-?bix\s+caramel\s+slice)\b",
        low,
    ):
        out.append(re.sub(r"\s+", " ", m.group(1)).strip())
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq[:4]


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


def caption_mentions_dm_gate(text: str) -> bool:
    """
    True when the poster says to comment / DM them to receive the recipe
    (lead-magnet captions) — amounts are not public in the post.
    """
    t = (text or "").lower()
    if not t.strip():
        return False
    patterns = (
        r"\bcomment\b.{0,80}\b(send|dm|inbox|message)\b",
        r"\b(dm|message)\s+me\b.{0,60}\b(recipe|send|ingredients?)\b",
        r"\bi(?:'|’)?ll\s+(send|dm)\b",
        r"\bi\s+will\s+(send|dm)\b",
        r"\bsend\s+(it|the\s+recipe)\s+over\b",
        r"\bdrop\s+a\s+comment\b.{0,60}\b(send|dm)\b",
        r"\bcomment\b.{0,30}\band\s+i(?:'|’)?ll\b",
        r"\bsend\s+(you\s+)?(the\s+)?recipe\b.{0,40}\b(dm|inbox|comment)\b",
        # "comment the word ROLLS for the …" / "comment RECIPE for the full recipe"
        r"\bcomment\s+(?:the\s+word\s+)?[\"'“”]?\w+[\"'“”]?\s+for\b",
        r"\bcomment\b.{0,40}\bfor\s+the\s+(?:full\s+)?(?:recipe|ingredients?|method|details)\b",
    )
    return any(re.search(p, t, flags=re.I | re.S) for p in patterns)


_DM_COMMENT_STOP = frozenset(
    {
        "the",
        "word",
        "a",
        "an",
        "and",
        "or",
        "for",
        "below",
        "if",
        "you",
        "try",
        "this",
        "that",
        "me",
        "my",
        "your",
        "on",
        "to",
        "with",
        "from",
        "full",
        "details",
        "method",
        "ingredients",
        "inbox",
        "over",
        "send",
        "dm",
        "message",
        "how",
        "make",
        "them",
        "ya",
        "ill",
        "will",
        # Keep "recipe" allowed — creators often say Comment RECIPE
    }
)


def extract_dm_comment_keywords(text: str) -> list[str]:
    """
    Pull the word(s) the creator asks people to comment, e.g. ROLLS / SLICE / RECIPE.
    """
    raw = text or ""
    found: list[str] = []

    def _add(word: str | None):
        w = (word or "").strip().strip("\"'“”").upper()
        if not w or len(w) > 24:
            return
        if w.lower() in _DM_COMMENT_STOP:
            return
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*", w):
            return
        if w not in found:
            found.append(w)

    patterns = (
        # comment the word ROLLS
        r"\bcomment\s+the\s+word\s+[\"'“”]?([A-Za-z0-9_-]+)[\"'“”]?",
        # COMMENT "SLICE" …
        r"\bcomment\s+[\"'“”]([A-Za-z0-9_-]+)[\"'“”]",
        # Comment RECIPE or PANCAKE and I'll…
        r"\bcomment\s+([A-Za-z0-9_-]+)(?:\s+or\s+([A-Za-z0-9_-]+))?\s+and\s+i",
        # comment RECIPE for the…
        r"\bcomment\s+(?:the\s+word\s+)?[\"'“”]?([A-Za-z0-9_-]+)[\"'“”]?\s+for\b",
    )
    for pat in patterns:
        for m in re.finditer(pat, raw, flags=re.I):
            _add(m.group(1))
            if m.lastindex and m.lastindex >= 2:
                _add(m.group(2))
    return found[:4]


def instagram_profile_url(handle: Optional[str]) -> Optional[str]:
    h = _norm_handle(handle)
    if not h or len(h) < 2:
        return None
    return f"https://www.instagram.com/{h}/"


def dm_gate_user_message(
    *,
    keywords: Optional[list[str]] = None,
    handle: Optional[str] = None,
) -> str:
    words = [w for w in (keywords or []) if w]
    handle_disp = f"@{_norm_handle(handle)}" if _norm_handle(handle) else "their Instagram"

    if len(words) == 1:
        comment_bit = f'comment "{words[0]}"'
    elif len(words) == 2:
        comment_bit = f'comment "{words[0]}" or "{words[1]}"'
    elif len(words) > 2:
        quoted = ", ".join(f'"{w}"' for w in words[:-1]) + f', or "{words[-1]}"'
        comment_bit = f"comment {quoted}"
    else:
        comment_bit = "comment or DM them"

    return (
        f"This creator asks people to {comment_bit} on {handle_disp} for the recipe — "
        "the full written amounts usually aren’t in the caption or on a public page. "
        "Laro will still try to read the video (spoken + on-screen text). "
        f"For the exact written recipe, open {handle_disp} on Instagram and {comment_bit}."
    )


def build_dm_gate_meta(caption: str = "", handle: Optional[str] = None) -> dict:
    """Structured DM-gate payload for import clients (popup + IG link)."""
    if not caption_mentions_dm_gate(caption or ""):
        return {}
    keywords = extract_dm_comment_keywords(caption or "")
    ig_url = instagram_profile_url(handle)
    h = _norm_handle(handle)
    out: dict = {
        "dm_gated": True,
        "dm_gated_message": dm_gate_user_message(keywords=keywords, handle=h or None),
    }
    if keywords:
        out["dm_comment_words"] = keywords
    if h:
        out["dm_instagram_handle"] = h
    if ig_url:
        out["dm_instagram_url"] = ig_url
    return out


def _search_terms_from_caption(caption: str, title: str = "") -> list[str]:
    """Build short search queries from reel title/caption."""
    terms: list[str] = []

    def _clean(s: str) -> str:
        s = re.sub(r"[“”\"\'’]", "", s or "")
        s = re.sub(r"[^\w\s\-']+", " ", s, flags=re.UNICODE)
        s = re.sub(r"\s+", " ", s).strip()
        # Drop DM-funnel CTAs: COMMENT "SLICE" AND I'LL SEND IT OVER
        s = re.sub(r"\bcomment\b.{0,40}\b(send|dm|inbox)\b.*", " ", s, flags=re.I)
        return re.sub(r"\s+", " ", s).strip()

    combined = f"{title or ''}\n{caption or ''}"
    # Prefer dish phrases over review-quote fluff (common on IG).
    for phrase in _food_phrase_candidates(combined):
        terms.append(phrase)

    title_c = _clean(title)
    # Skip titles that are mostly a customer review quote
    if title_c and len(title_c) > 4:
        reviewish = bool(
            re.search(
                r"\b(thank you|turned out|huge win|amazing|telling everyone|love this)\b",
                title_c,
                flags=re.I,
            )
        )
        if not reviewish or not terms:
            terms.append(title_c[:80])

    first = ""
    for line in (caption or "").splitlines():
        clean = _clean(line)
        if len(clean) < 12:
            continue
        if re.match(r"^(comment|follow|link in bio|dm me)\b", clean, flags=re.I):
            continue
        if re.search(r"\b(calories?|protein|carbs?|macros?)\b", clean, re.I) and len(clean) < 40:
            continue
        if re.search(
            r"\b(thank you|turned out|huge win|amazing|telling everyone|doubled the recipe)\b",
            clean,
            flags=re.I,
        ):
            continue
        first = clean[:90]
        break
    if first:
        terms.append(first)

    filler = {
        "i", "am", "the", "a", "an", "and", "or", "to", "for", "my", "this", "that",
        "with", "from", "just", "about", "obsessed", "recipe", "recipes", "comment",
        "send", "follow", "following", "ill", "over", "make", "sure", "you", "are",
        "these", "best", "ever", "turned", "out", "like", "picture", "fluffy", "great",
        "tasting", "thank", "much", "telling", "everyone", "use",
    }
    for base in list(terms):
        words = [
            w
            for w in re.findall(r"[A-Za-z0-9']+", base)
            if w.lower() not in filler
        ]
        if len(words) >= 3:
            terms.append(" ".join(words[:8]))
    for t in list(terms):
        slug = _slugify_recipe_query(t)
        if slug and "-" in slug:
            terms.append(slug.replace("-", " "))
            parts = slug.split("-")
            if "pancake" in parts or "pancakes" in parts:
                # WP often uses protein-pancakes-without-protein-powder
                if "without" in parts and "protein" in parts:
                    terms.append("protein pancakes without protein powder")
    # Dedupe preserve order
    out: list[str] = []
    for t in terms:
        if t and t not in out:
            out.append(t)
    return out[:6]


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
    flaky / rate-limited. Also probe likely kebab slugs (cheap HEAD/Jina) when
    search pages omit absolute links.
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

    # Slug probe: many WP blogs use /protein-pancakes-without-protein-powder/
    # even when their search result pages omit absolute URLs in Jina markdown.
    if not candidates:
        slug_try: list[str] = []
        # Known dish reorderings when review quotes scramble the title.
        if {"pancake", "pancakes", "protein", "powder", "without"} & token_set:
            if "pancake" in token_set or "pancakes" in token_set:
                slug_try.append("protein-pancakes-without-protein-powder")
                slug_try.append("pancakes-without-protein-powder")
        for term in terms[:4]:
            slug = _slugify_recipe_query(term)
            if slug and "-" in slug and slug not in slug_try:
                slug_try.append(slug)
            parts = slug.split("-") if slug else []
            if len(parts) > 6:
                shorter = "-".join(parts[:6])
                if shorter not in slug_try:
                    slug_try.append(shorter)
        for slug in slug_try[:6]:
            probe = f"https://{host}/{slug}/"
            try:
                resp = await client.get(
                    probe,
                    headers={"User-Agent": _UA, "Accept": "text/html"},
                    timeout=12.0,
                    follow_redirects=True,
                )
                if resp.status_code == 200 and len(resp.text or "") > 800:
                    low = (resp.text or "").lower()
                    if (
                        "application/ld+json" in low
                        or "wprm-recipe" in low
                        or "recipeingredient" in low
                        or "ingredient" in low
                    ):
                        candidates.append(_normalize_recipe_url(str(resp.url)))
                        break
            except Exception:
                continue

    # Light DDG fallback (may be empty under rate limits)
    if not candidates:
        for term in terms[:2]:
            for q in (f"site:{host} {term}", f"{host} {term}"):
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
        # Drop stale false-positive homes (wrong creator domain).
        if cached_site and not host_plausibly_matches_handle(
            (urlparse(cached_site).hostname or ""), h
        ):
            cached_site = None
            cached_via = ""
            _cache.pop(cache_key, None)

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

            # Prefer DDG hits that actually look like this creator's domain.
            scored_homes: list[tuple[int, str]] = []
            for u in ranked:
                home = _website_home(u)
                if not home:
                    continue
                host0 = (urlparse(home).hostname or "").lower()
                scored_homes.append((_handle_host_score(h, host0), home))
            scored_homes.sort(key=lambda x: x[0], reverse=True)
            if scored_homes and scored_homes[0][0] >= 6:
                website = scored_homes[0][1]
                via = "ddg"

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

            # Reject cached/weak DDG false positives (e.g. paleorunningmomma for @running.and.mumming)
            if website and not host_plausibly_matches_handle(
                (urlparse(website).hostname or ""), h
            ):
                # Try heuristic before giving up
                website = None
                via = ""
                for host in handle_domain_candidates(h):
                    probe = f"https://{host}/"
                    try:
                        resp = await client.get(
                            probe,
                            headers={"User-Agent": _UA, "Accept": "text/html"},
                            timeout=12.0,
                            follow_redirects=True,
                        )
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
