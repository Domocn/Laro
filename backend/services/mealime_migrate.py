"""Resolve Mealime saved-recipe names/URLs to public mealime.com pages.

Mealime shuts on 21 October 2026 with no export. Public recipe pages still
expose JSON-LD. The /recipes listing embeds a name+id catalog we can match
against, then fetch each page like any other URL import.
"""
from __future__ import annotations

import html
import unicodedata
import logging
import re
import time
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MEALIME_CATALOG_URL = "https://www.mealime.com/recipes"
MEALIME_HOSTS = ("mealime.com",)
MEALIME_URL_RE = re.compile(
    r"https?://(?:www\.)?mealime\.com/recipes/[a-z0-9-]+/\d+",
    re.I,
)
ANY_URL_RE = re.compile(r"https?://[^\s,;<>\"')\]]+", re.I)
NUMBERED_PREFIX_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•–—])\s+")
JUNK_LINE_RE = re.compile(
    r"^(saved|cook now|start cooking|add to (?:list|grocery|meal plan|plan)|"
    r"grocery list|meal plan|minutes?|min\.?|\d+\s*(?:min|minutes|servings?)|"
    r"serves?\s*\d+|dinner|lunch|breakfast|snack|my recipes|mealime|"
    r"samsung food|whisk|pepperplate|yummly|search|share|print)$",
    re.I,
)
STOPWORDS = {
    "with", "and", "a", "an", "the", "of", "for", "to", "in",
}
_CATALOG_TTL_SEC = 6 * 60 * 60
_catalog_cache: dict[str, Any] = {"at": 0.0, "items": []}

RECIPE_SAVE_KEYS = (
    "title",
    "description",
    "ingredients",
    "instructions",
    "prep_time",
    "cook_time",
    "servings",
    "category",
    "tags",
    "image_url",
    "source_url",
    "source_type",
    "source_author",
    "dietary_tags",
    "difficulty",
)


def _fold_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def mealime_slug(name: str) -> str:
    # Mealime slugs fold accents ("Sautéed" -> "sauteed"); dropping é gave a 404 "saut-ed" link.
    s = _fold_accents(html.unescape(name or "")).lower().replace("&", " ")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    parts = [p for p in s.split("-") if p and p not in STOPWORDS]
    return "-".join(parts)


def normalize_name(name: str) -> str:
    s = html.unescape(name or "")
    # "Sautéed" must match a typed "Sauteed" (dropping é used to leave "saut ed").
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    parts = [p for p in s.split() if p and p not in STOPWORDS]
    return " ".join(parts)


def is_mealime_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host == "mealime.com" or host.endswith(".mealime.com")


def extract_mealime_url(text: str) -> Optional[str]:
    match = MEALIME_URL_RE.search(text or "")
    return match.group(0) if match else None


def extract_any_url(text: str) -> Optional[str]:
    mealime = extract_mealime_url(text)
    if mealime:
        return mealime
    match = ANY_URL_RE.search(text or "")
    if not match:
        return None
    return match.group(0).rstrip(").,;")


def source_type_for_url(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return "web"
    if host == "mealime.com" or host.endswith(".mealime.com"):
        return "mealime"
    if "samsungfood" in host or host.endswith("whisk.com") or host == "whisk.com":
        return "samsung_food"
    if "pepperplate" in host:
        return "pepperplate"
    if "yummly" in host:
        return "yummly"
    return "web"


def _clean_name(line: str) -> str:
    s = html.unescape(line or "").strip()
    s = NUMBERED_PREFIX_RE.sub("", s).strip().strip("-•").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _is_junk(line: str) -> bool:
    s = _clean_name(line)
    if not s or len(s) < 3:
        return True
    if JUNK_LINE_RE.match(s):
        return True
    if re.fullmatch(r"[\d\W]+", s):
        return True
    return False


def _dedupe_add(entries: list[str], seen: set[str], value: str) -> None:
    key = value.strip().lower()
    if not key or key in seen:
        return
    seen.add(key)
    entries.append(value.strip())


def split_paste(text: str) -> list[str]:
    """Turn a messy Saved-list paste into one name or URL per entry."""
    entries: list[str] = []
    seen: set[str] = set()
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    chunks = re.split(r"[\n\u2022•]+", raw)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        urls = ANY_URL_RE.findall(chunk)
        if urls:
            before = ANY_URL_RE.split(chunk)[0]
            before = _clean_name(before.strip(" -,;|"))
            if before and not _is_junk(before) and not extract_any_url(before):
                _dedupe_add(entries, seen, before)
            for url in urls:
                _dedupe_add(entries, seen, url.rstrip(").,;"))
            continue
        name = _clean_name(chunk)
        if name and not _is_junk(name):
            _dedupe_add(entries, seen, name)
    return entries


def split_lines(text: str) -> list[str]:
    return split_paste(text)


def leftover_paste(entries: list[str], processed: int) -> str:
    rest = entries[processed:]
    return "\n".join(rest)


def dinner_dates(start, days: int = 7) -> list[str]:
    from datetime import timedelta

    out = []
    for i in range(max(1, min(int(days or 7), 14))):
        out.append((start + timedelta(days=i)).isoformat())
    return out


def assign_week_dinners(
    recipe_ids: list[str],
    occupied_dates: set[str],
    start,
    days: int = 7,
) -> list[tuple[str, str]]:
    """Pair imported recipe ids with empty dinner days, skipping occupied slots."""
    slots: list[tuple[str, str]] = []
    idx = 0
    ids = [rid for rid in recipe_ids if rid]
    for day in dinner_dates(start, days):
        if idx >= len(ids):
            break
        if day in occupied_dates:
            continue
        slots.append((day, ids[idx]))
        idx += 1
    return slots


def mealime_url_for(item: dict) -> str:
    slug = mealime_slug(item.get("name") or "")
    variant_id = item.get("id")
    return f"https://www.mealime.com/recipes/{slug}/{variant_id}"


def _score_match(query_norm: str, item_norm: str) -> float:
    if not query_norm or not item_norm:
        return 0.0
    if query_norm == item_norm:
        return 1.0
    q = set(query_norm.split())
    n = set(item_norm.split())
    if not q:
        return 0.0
    if q <= n:
        return 0.85 + 0.1 * (len(q) / max(len(n), 1))
    overlap = len(q & n)
    if overlap >= 3 and overlap / len(q) >= 0.75:
        return overlap / max(len(q | n), 1)
    return 0.0


def resolve_name(name: str, catalog: list[dict]) -> Optional[dict]:
    query = normalize_name(name)
    if not query or not catalog:
        return None
    best = None
    best_score = 0.0
    for item in catalog:
        score = _score_match(query, item.get("norm") or "")
        if score > best_score:
            best_score = score
            best = item
    if best_score < 0.75:
        return None
    return best


def _index_catalog(raw_variants: list[dict]) -> list[dict]:
    items = []
    for row in raw_variants or []:
        name = (row.get("name") or "").strip()
        variant_id = row.get("id")
        if not name or variant_id is None:
            continue
        items.append({
            "id": variant_id,
            "recipeId": row.get("recipeId"),
            "name": name,
            "img": row.get("img") or "",
            "norm": normalize_name(name),
            "url": mealime_url_for({"name": name, "id": variant_id}),
        })
    return items


async def load_catalog(http_client, force: bool = False) -> list[dict]:
    now = time.time()
    if (
        not force
        and _catalog_cache["items"]
        and now - float(_catalog_cache["at"] or 0) < _CATALOG_TTL_SEC
    ):
        return _catalog_cache["items"]

    resp = await http_client.get(
        MEALIME_CATALOG_URL,
        headers={"User-Agent": "LaroFood/1.0 (Mealime migration; +https://laro.food)"},
        timeout=30.0,
        follow_redirects=True,
    )
    resp.raise_for_status()
    html_text = resp.text
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html_text,
        re.I | re.S,
    )
    if not match:
        logger.warning("Mealime catalog page missing __NEXT_DATA__")
        return list(_catalog_cache["items"] or [])

    import json

    payload = json.loads(match.group(1))
    variants = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("reducedVariants")
        or []
    )
    items = _index_catalog(variants)
    if items:
        _catalog_cache["at"] = now
        _catalog_cache["items"] = items
    return items


def recipe_payload_for_save(recipe_data: dict, source_url: str) -> dict:
    out = {}
    for key in RECIPE_SAVE_KEYS:
        if key in recipe_data and recipe_data[key] is not None:
            out[key] = recipe_data[key]
    title = html.unescape(str(out.get("title") or "Imported Recipe"))
    out["title"] = title
    if isinstance(out.get("description"), str):
        out["description"] = html.unescape(out["description"])
    if isinstance(out.get("instructions"), list):
        out["instructions"] = [
            html.unescape(step) if isinstance(step, str) else step
            for step in out["instructions"]
        ]
    out["source_url"] = source_url
    out["source_type"] = source_type_for_url(source_url)
    if not out.get("category"):
        out["category"] = "Other"
    if not isinstance(out.get("tags"), list):
        out["tags"] = []
    if not isinstance(out.get("ingredients"), list):
        out["ingredients"] = []
    if not isinstance(out.get("instructions"), list):
        out["instructions"] = []
    tags = list(out.get("tags") or [])
    if "closing-app" not in tags:
        tags.append("closing-app")
    cook = out.get("cook_time") or 0
    prep = out.get("prep_time") or 0
    try:
        total = int(cook or 0) + int(prep or 0)
    except (TypeError, ValueError):
        total = 0
    if 0 < total <= 30 and "30-min" not in tags:
        tags.append("30-min")
    out["tags"] = tags
    return out
