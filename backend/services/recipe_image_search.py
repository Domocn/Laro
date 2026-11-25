"""
Find a relevant cover image for an imported recipe.

Order:
  1. TheMealDB title search (classic dish photos)
  2. Wikimedia Commons file search (food photos; skip logos/icons)
  3. Wikipedia page thumbnail (skip logos)
  4. Curated Unsplash keyword map (better than random category)

Never invent URLs via the LLM — only return real HTTP(S) image URLs.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_USER_AGENT = "LaroRecipeBot/1.0 (https://laro.food; recipe cover matching)"
_TIMEOUT = 8.0

_STOPWORDS = frozenset(
    """
    a an the and or with without style styled original protein overnight optional
    high low fat free easy quick homemade recipe recipes servings serve serves
    minutes mins prep cook bake baking dish meal breakfast lunch dinner dessert
    snack appetizer beverage drink vegan vegetarian gluten dairy free gf df
    cheesecake-style -style version revised complete your both made
    ingredient ingredients healthy delicious tasty simple perfect best yummy
    classic ultimate amazing super extra packed
    """.split()
)

# "2 ingredient pizza" / "4-ingredient banana bread" — the count is not a dish.
_N_INGREDIENT_RE = re.compile(r"\b\d+\s*[- ]?ingredient[s]?\b", re.I)

# Keyword → Unsplash photo id (images.unsplash.com/{id}).
# Specific dishes first so "banana bread" is not fruit/oats and "meatballs" is not salmon.
_KEYWORD_UNSPLASH: list[tuple[tuple[str, ...], str]] = [
    (("weetabix", "weet-bix", "weet-a-bix", "wheat biscuit"), "photo-1664802460246-42deccecbc92"),
    (("overnight oats", "overnight oat", "bircher"), "photo-1517673400267-0251440c45dc"),
    (("banana bread", "banana loaf"), "photo-1632931057819-4eefffa8e007"),
    (("meatball", "meatballs", "meat ball", "meat balls", "kofta"), "photo-1529042410759-befb1204b468"),
    (("nut bar", "granola bar", "protein bar", "cereal bar", "energy bar", "snack bar"), "photo-1705868432559-211198009991"),
    (("cheesecake",), "photo-1533134242443-d4fd215305ad"),
    (("mango lassi", "lassi"), "photo-1600271886742-f049cd451bba"),
    (("mango",), "photo-1553279768-865429fa0078"),
    (("custard", "pudding"), "photo-1488477181946-6428a0291777"),
    (("yogurt", "yoghurt", "skyr", "greek yogurt"), "photo-1488477181946-6428a0291777"),
    (("pancake",), "photo-1528207776546-365bb710ee93"),
    (("waffle",), "photo-1562376552-0d160a2f238d"),
    (("smoothie", "shake"), "photo-1505252585461-04db1eb85825"),
    (("salad",), "photo-1512621776951-a57141f2eefd"),
    (("pasta", "spaghetti", "noodle"), "photo-1621996346565-e3dbc646d9a9"),
    (("pizza",), "photo-1565299624946-b28f40a0ae38"),
    (("burger", "hamburger"), "photo-1568901346375-23c9450c58cd"),
    (("chicken",), "photo-1598103442097-8b74394b95c6"),
    (("steak", "beef", "mince"), "photo-1544025162-d76694265947"),
    (("salmon", "fish"), "photo-1467003909585-2f8a72700288"),
    (("oatmeal", "porridge", "oats", "oat"), "photo-1517673400267-0251440c45dc"),
    (("soup", "stew", "chili", "chilli"), "photo-1547592166-23ac45744acd"),
    (("curry", "tikka", "masala"), "photo-1585937421612-70a008356fbe"),
    (("sushi", "ramen"), "photo-1579871494447-9811cf80d66c"),
    (("taco", "burrito", "quesadilla"), "photo-1565299585323-38d6b0865b47"),
    (("sandwich", "toast"), "photo-1528735602780-2552fd46c7af"),
    (("egg", "omelette", "omelet", "frittata"), "photo-1525351484163-7529414344d8"),
    (("avocado", "guac"), "photo-1523049673857-eb18f1d7b578"),
    (("cake", "brownie", "cookie", "biscuit"), "photo-1563729784474-d77dbb933a9e"),
    (("ice cream", "gelato"), "photo-1563805042-7684c019e1cb"),
    (("coffee", "latte", "espresso"), "photo-1495474472287-4d71bcdd2085"),
    (("tea",), "photo-1544787219-7f47ccb76574"),
    (("cereal", "granola", "cornflakes", "corn flakes", "cheerios", "muesli", "shredded wheat"), "photo-1572319216151-4fb52730dc68"),
    (("protein powder", "shake bowl"), "photo-1505252585461-04db1eb85825"),
    (("fruit", "berry", "berries", "strawberry", "pear"), "photo-1490474418585-ba9bad8fd0ea"),
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _has_keyword(blob: str, key: str) -> bool:
    """Whole-word / phrase match so 'oat' does not hit inside unrelated tokens."""
    k = (key or "").strip().lower()
    if not k:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", blob or "") is not None


def _keyword_row_for(text: str) -> Optional[tuple[tuple[str, ...], str]]:
    blob = _normalize(text)
    if not blob:
        return None
    for keys, photo_id in _KEYWORD_UNSPLASH:
        if any(_has_keyword(blob, k) for k in keys):
            return keys, photo_id
    return None


def extract_search_terms(title: str, *, category: str | None = None, limit: int = 6) -> list[str]:
    """Build ordered search queries from a recipe title."""
    raw = (title or "").strip()
    if not raw:
        return []

    queries: list[str] = []
    # Parenthetical flavour: "Weetabix (Cheesecake-Style)" → also try "cheesecake"
    paren = re.findall(r"\(([^)]+)\)", raw)
    stripped = _N_INGREDIENT_RE.sub(" ", raw)
    cleaned = re.sub(r"[()\[\]{}\-_/]", " ", stripped)
    cleaned = re.sub(r"[^a-zA-Z0-9\s&']", " ", cleaned)
    tokens = [t for t in cleaned.split() if t and _normalize(t) not in _STOPWORDS and len(t) > 1]

    if tokens:
        queries.append(" ".join(tokens[:8]))
    if len(tokens) >= 2:
        # Dish is usually the tail: "Healthy Banana Bread" → "Banana Bread"
        queries.append(" ".join(tokens[-2:]))
        queries.append(" ".join(tokens[:4]))
        if len(tokens[0]) >= 4:
            queries.append(tokens[0])
    elif tokens:
        queries.append(tokens[0])
    for p in paren:
        p_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", p)
        p_tokens = [t for t in p_clean.split() if _normalize(t) not in _STOPWORDS and len(t) > 2]
        if p_tokens:
            queries.append(" ".join(p_tokens[:4]))

    # Brand / distinctive single tokens last (Weetabix, mango, …)
    for t in tokens:
        if len(t) >= 5 and t.lower() not in {q.lower() for q in queries}:
            queries.append(t)

    if category and category.lower() not in {"other", "meal pack"}:
        queries.append(f"{tokens[0]} {category}" if tokens else category)

    # Dedupe preserving order
    seen = set()
    out: list[str] = []
    for q in queries:
        key = _normalize(q)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(q.strip())
        if len(out) >= limit:
            break
    return out


def _score_label(label: str, terms: Iterable[str]) -> int:
    label_n = _normalize(label)
    score = 0
    for term in terms:
        for part in _normalize(term).split():
            if len(part) < 3:
                continue
            if part in label_n:
                score += 2 if len(part) >= 5 else 1
    # Prefer food photos; demote logos/icons/packaging wordmarks
    bad = ("logo", "icon", "wordmark", "svg", "packaging artwork", "emblem")
    if any(b in label_n for b in bad):
        score -= 10
    good = ("food", "dish", "recipe", "dessert", "cake", "meal", "breakfast", "bowl")
    if any(g in label_n for g in good):
        score += 1
    return score


def _is_usable_image_url(url: str, *, mime: str | None = None, label: str = "") -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    lower = url.lower()
    label_n = _normalize(label)
    if any(x in lower for x in (".svg", ".gif", "logo", "wordmark", "icon")):
        return False
    if any(x in label_n for x in ("logo", "icon", "wordmark", "svg")):
        return False
    if mime and not mime.startswith("image/"):
        return False
    if mime in {"image/svg+xml", "image/gif"}:
        return False
    return True


def _unsplash(photo_id: str, width: int = 1200) -> str:
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w={width}&q=80"


def curated_unsplash_for_title(title: str, category: str | None = None) -> Optional[str]:
    row = _keyword_row_for(title) or _keyword_row_for(f"{title} {category or ''}")
    if row:
        return _unsplash(row[1])
    return None


async def _themealdb(client: httpx.AsyncClient, query: str) -> Optional[tuple[str, int, str]]:
    url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={quote(query)}"
    try:
        r = await client.get(url)
        r.raise_for_status()
        meals = (r.json() or {}).get("meals") or []
    except Exception as e:
        logger.debug("TheMealDB search failed for %r: %s", query, e)
        return None
    best = None
    for meal in meals[:8]:
        img = (meal.get("strMealThumb") or "").strip()
        name = meal.get("strMeal") or ""
        if not _is_usable_image_url(img, label=name):
            continue
        score = _score_label(name, [query])
        if best is None or score > best[1]:
            best = (img, score, f"themealdb:{name}")
    return best


async def _wikimedia_commons(client: httpx.AsyncClient, query: str) -> Optional[tuple[str, int, str]]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": f"{query} food OR dish OR recipe OR dessert OR breakfast",
        "gsrlimit": "8",
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": "1280",
        "format": "json",
    }
    try:
        r = await client.get("https://commons.wikimedia.org/w/api.php", params=params)
        r.raise_for_status()
        pages = ((r.json() or {}).get("query") or {}).get("pages") or {}
    except Exception as e:
        logger.debug("Commons search failed for %r: %s", query, e)
        return None

    best = None
    for page in pages.values():
        title = page.get("title") or ""
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = info.get("mime") or ""
        # Prefer scaled thumb when present
        img = (info.get("thumburl") or info.get("url") or "").strip()
        if not _is_usable_image_url(img, mime=mime, label=title):
            continue
        score = _score_label(title, [query])
        if best is None or score > best[1]:
            best = (img, score, f"commons:{title}")
    return best


async def _wikipedia_thumb(client: httpx.AsyncClient, query: str) -> Optional[tuple[str, int, str]]:
    # Try the query as a page title directly
    slug = quote(query.replace(" ", "_"), safe="")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    try:
        r = await client.get(url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json() or {}
    except Exception as e:
        logger.debug("Wikipedia summary failed for %r: %s", query, e)
        return None
    thumb = ((data.get("thumbnail") or {}).get("source") or "").strip()
    title = data.get("title") or query
    if not _is_usable_image_url(thumb, label=title):
        return None
    # Reject tiny logos
    width = (data.get("thumbnail") or {}).get("width") or 0
    if width and width < 120:
        return None
    score = _score_label(title, [query])
    return (thumb, score, f"wikipedia:{title}")


async def find_matching_recipe_image(
    title: str,
    *,
    category: str | None = None,
    ingredients: list[Any] | None = None,
    client: httpx.AsyncClient | None = None,
) -> Optional[str]:
    """
    Return a relevant HTTPS image URL for this recipe, or None.
    Best-effort — never raises to callers.
    """
    title = (title or "").strip()
    if not title:
        return None

    queries = extract_search_terms(title, category=category)
    if not queries:
        return curated_unsplash_for_title(title, category)

    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )
    best: Optional[tuple[str, int, str]] = None
    try:
        for query in queries[:4]:
            for finder in (_themealdb, _wikimedia_commons, _wikipedia_thumb):
                try:
                    hit = await finder(client, query)
                except Exception:
                    hit = None
                if not hit:
                    continue
                url, score, src = hit
                if score < 1 and finder is not _themealdb:
                    # Weak commons/wiki hits are often unrelated
                    continue
                if best is None or score > best[1]:
                    best = (url, score, src)
                if best and best[1] >= 4:
                    break
            if best and best[1] >= 4:
                break

        if best and best[1] >= 1:
            row = _keyword_row_for(title)
            curated = _unsplash(row[1]) if row else curated_unsplash_for_title(title, category)
            # Prefer the dish keyword photo when the web hit is a different food
            # (e.g. "2 ingredient pizza" matching strawberries, meatballs → salmon).
            if row and curated:
                keys, _photo = row
                hit_blob = _normalize(f"{best[2]} {best[0]}")
                if not any(_has_keyword(hit_blob, k) for k in keys):
                    logger.info(
                        "Preferring curated Unsplash for %r over unrelated %s",
                        title[:80],
                        best[2],
                    )
                    return curated
            logger.info("Matched recipe image for %r via %s (score=%s)", title[:80], best[2], best[1])
            return best[0]

        curated = curated_unsplash_for_title(title, category)
        if curated:
            logger.info("Using curated Unsplash match for %r", title[:80])
            return curated
        return None
    except Exception as e:
        logger.warning("Recipe image search failed for %r: %s", title[:80], e)
        return None
    finally:
        if owns_client:
            await client.aclose()


async def enrich_recipe_with_image(recipe: dict) -> dict:
    """Mutate recipe dict: set image_url when missing. Returns the same dict."""
    if not isinstance(recipe, dict):
        return recipe
    existing = (recipe.get("image_url") or recipe.get("image") or "").strip()
    if existing.startswith(("http://", "https://")):
        recipe["image_url"] = existing
        return recipe

    ings = recipe.get("ingredients") or []
    url = await find_matching_recipe_image(
        recipe.get("title") or "",
        category=recipe.get("category") or recipe.get("course"),
        ingredients=ings if isinstance(ings, list) else None,
    )
    if url:
        recipe["image_url"] = url
        recipe["image_source"] = "matched"
    return recipe
