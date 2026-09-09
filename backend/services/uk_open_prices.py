"""
UK grocery prices from Open Food Facts — Open Prices (ODbL).

Syncs crowdsourced GBP prices into Postgres regularly so cost estimates work
offline (no live API call at request time). Celery Beat runs the sync; the
first cost lookup will also seed the catalog if empty.

API source: https://prices.openfoodfacts.org/api/docs
Data © Open Food Facts / Open Prices contributors (ODbL).
"""
from __future__ import annotations

import logging
import re
import statistics
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from config import settings

logger = logging.getLogger(__name__)

USER_AGENT = f"LaroFood/{settings.version} (https://laro.food; prices@laro.food)"
PRICES_API = "https://prices.openfoodfacts.org/api/v1/prices"
INDEX_PAGE_SIZE = 100
MAX_PAGES = 40

# Minimum score before we trust an Open Prices match (else fall through to defaults)
MIN_MATCH_SCORE = 12.0

_READY_MEAL = re.compile(
    r"\b(sandwich|burger|pie|quiche|nugget|tenders?|"
    r"filler|stir.?fry|fries|crumble|pouch|drink|soda|chocolate|focaccia|"
    r"grissini|marinade|en croute|smoothie|yoghurt? pouch|peri-?naise|"
    r"stock cubes?|chips|crisps|flavour|flavor|protein|wafers?|crackers?|"
    r"biscuits?|cookies?|mayo|sauce|dressing|seasoning|"
    r"crispy|pepper chicken|salt & pepper)\b",
    flags=re.I,
)

# Allowed extra tokens for single-word staples (e.g. "brown onions", "bananas")
_MILD_DESCRIPTORS = {
    "large", "small", "medium", "brown", "white", "red", "green", "yellow",
    "loose", "whole", "baby", "new", "sweet", "semi", "skimmed",
    "full", "fat", "class", "wonky",
}

_STOPWORDS = {
    "and", "or", "with", "the", "of", "a", "an", "in", "for", "to", "on",
    "style", "added", "extra", "virgin", "free", "range", "british",
}


def normalize_price_name(name: str) -> str:
    name = (name or "").lower().strip()
    name = re.sub(r"[^a-z0-9%\s\-/&]+", " ", name)
    # Strip repeated known prefixes
    changed = True
    while changed:
        changed = False
        for prefix in (
            "fresh ", "frozen ", "organic ", "british ", "free range ",
            "chopped ", "diced ", "minced ", "sliced ", "raw ", "cooked ",
            "0% ", "5% ", "lean ",
        ):
            if name.startswith(prefix):
                name = name[len(prefix):]
                changed = True
    return re.sub(r"\s+", " ", name).strip()


def _tokens(name: str) -> List[str]:
    return [
        t for t in normalize_price_name(name).split()
        if t and t not in _STOPWORDS and len(t) > 1
    ]


def _entry_from_price_item(item: dict) -> Optional[Dict[str, Any]]:
    if (item.get("currency") or "").upper() != "GBP":
        return None
    price = item.get("price")
    if price is None:
        return None
    try:
        price = float(price)
    except (TypeError, ValueError):
        return None
    if price <= 0 or price > 200:
        return None

    product = item.get("product") or {}
    location = item.get("location") or {}
    name = (
        product.get("product_name")
        or item.get("product_name")
        or item.get("category_tag")
        or ""
    )
    name = str(name).strip()
    if not name:
        return None
    if name.startswith("en:"):
        name = name.replace("en:", "").replace("-", " ")

    qty = product.get("product_quantity")
    qty_unit = (product.get("product_quantity_unit") or "").lower() or None
    try:
        qty = float(qty) if qty not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        qty = None

    price_per = (item.get("price_per") or "").upper() or None
    per_kg = None
    if price_per == "KILOGRAM":
        per_kg = price
    elif qty and qty_unit in ("g", "kg", "ml", "l") and qty > 0:
        grams = qty * (1000 if qty_unit in ("kg", "l") else 1)
        # Tiny sachets make absurd £/kg (e.g. 4g magnesium → £1400/kg).
        # Require a meaningful pack before deriving unit price.
        if grams >= 100:
            per_kg = round(price / (grams / 1000.0), 2)

    store = location.get("osm_brand") or location.get("osm_name") or "UK shop"
    code = product.get("code") or item.get("product_code") or ""
    date = item.get("date") or ""
    entry_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"gbp|{code}|{store}|{date}|{price}|{name}",
        )
    )
    return {
        "id": entry_id,
        "name": name,
        "name_norm": normalize_price_name(name),
        "price": round(price, 2),
        "currency": "GBP",
        "store": store,
        "date": date,
        "observed_date": date,
        "product_code": code or None,
        "quantity": qty,
        "quantity_unit": qty_unit,
        "price_per": price_per,
        "per_kg": per_kg,
        "type": item.get("type") or "PRODUCT",
        "entry_type": item.get("type") or "PRODUCT",
    }


async def download_gbp_prices_from_api() -> List[Dict[str, Any]]:
    """Fetch the full GBP Open Prices feed (live network)."""
    index: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=45.0) as client:
        page = 1
        while page <= MAX_PAGES:
            resp = await client.get(
                PRICES_API,
                params={
                    "currency": "GBP",
                    "size": INDEX_PAGE_SIZE,
                    "page": page,
                    "order_by": "-date",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            items = payload.get("items") or []
            if not items:
                break
            for item in items:
                entry = _entry_from_price_item(item)
                if entry:
                    index.append(entry)
            pages = int(payload.get("pages") or page)
            if page >= pages:
                break
            page += 1
    return index


async def sync_uk_open_prices(*, force: bool = False) -> Dict[str, Any]:
    """
    Download GBP Open Prices and replace the local offline catalog.

    Safe to call from Celery Beat or startup. Skips if recently synced unless force=True.
    Never wipes the catalog on an empty download.
    """
    if not getattr(settings, "open_prices_enabled", True):
        return {"status": "disabled", "count": 0}

    from database.repositories.uk_open_price_repository import uk_open_price_repository

    if not force:
        count = await uk_open_price_repository.count_all()
        latest = await uk_open_price_repository.latest_synced_at()
        if count > 0 and latest is not None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            age_hours = (now - latest).total_seconds() / 3600.0
            if age_hours < 10:
                return {
                    "status": "fresh",
                    "count": count,
                    "synced_at": latest.isoformat() if hasattr(latest, "isoformat") else str(latest),
                }

    try:
        entries = await download_gbp_prices_from_api()
    except Exception as e:
        logger.warning("Open Prices download failed: %s", e)
        count = await uk_open_price_repository.count_all()
        return {"status": "error", "error": str(e), "count": count}

    by_id: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        eid = e.get("id")
        if eid:
            by_id[eid] = e
    entries = list(by_id.values())

    if not entries:
        count = await uk_open_price_repository.count_all()
        logger.warning("Open Prices download returned 0 rows — keeping existing catalog (%s)", count)
        return {"status": "empty_skip", "count": count}

    # Drop typos / sachet £/kg, median-aggregate barcodes, scrape consensus clamps
    from services.uk_price_corrector import correct_open_prices_catalog

    scrape = bool(getattr(settings, "open_prices_scrape_corrections", True))
    corrected, correction_stats = await correct_open_prices_catalog(
        entries,
        scrape_references=scrape,
    )
    if not corrected:
        logger.warning(
            "Open Prices correction removed all rows — keeping existing catalog"
        )
        count = await uk_open_price_repository.count_all()
        return {
            "status": "correct_empty_skip",
            "count": count,
            "correction": correction_stats,
        }

    saved = await uk_open_price_repository.replace_catalog(corrected)
    logger.info(
        "Synced %s UK Open Prices rows (from %s raw) correction=%s",
        saved,
        correction_stats.get("input"),
        correction_stats,
    )
    return {
        "status": "synced",
        "count": saved,
        "correction": correction_stats,
    }


async def ensure_local_catalog() -> int:
    """Ensure the offline catalog exists (seed on first use)."""
    from database.repositories.uk_open_price_repository import uk_open_price_repository

    count = await uk_open_price_repository.count_all()
    if count > 0:
        return count
    result = await sync_uk_open_prices(force=True)
    return int(result.get("count") or 0)


def _token_in_name(token: str, name_tokens: List[str]) -> bool:
    """Whole-token match (allow plural -s)."""
    for n in name_tokens:
        if token == n:
            return True
        if len(token) >= 3 and (n.startswith(token) or token.startswith(n)):
            # Avoid "pea" matching "peach" via startswith of short stems — require close length
            if abs(len(n) - len(token)) <= 2:
                return True
    return False


def _score_match(query: str, entry: Dict[str, Any]) -> float:
    """
    Strict token-overlap scorer. Short queries must have every token present as a
    whole word; multi-word products are penalised when the query is a single staple.
    """
    q = normalize_price_name(query)
    name = entry.get("name_norm") or normalize_price_name(entry.get("name") or "")
    if not q or not name:
        return -1.0

    # Compound seasoning lists ("Paprika, garlic, salt…") are too ambiguous for OP
    if "," in (query or "") and len(_tokens(query)) >= 3:
        return -1.0

    qt = _tokens(q)
    nt = _tokens(name)
    if not qt or not nt:
        return -1.0

    hits = sum(1 for t in qt if _token_in_name(t, nt))
    coverage = hits / len(qt)

    # Require full coverage for short queries; 80% for longer ones
    need = 1.0 if len(qt) <= 3 else 0.8
    if coverage < need:
        return -1.0

    score = coverage * 10.0
    if q == name or qt == nt:
        score += 15.0
    elif nt[: len(qt)] == qt:
        score += 10.0
    elif " ".join(qt) in name:
        score += 6.0

    # Single-token staples must not latch onto flavoured / processed products
    if len(qt) == 1:
        extras = [t for t in nt if not _token_in_name(qt[0], [t]) and t not in _MILD_DESCRIPTORS]
        if extras:
            return -1.0
        extra = len(nt) - 1
        if extra > 0:
            score -= min(4.0, extra * 1.5)
        # Only penalise first-token mismatch when there is no mild-descriptor explanation
        # (e.g. "oat milk" vs "milk"); "brown onions" is fine.
        if (
            nt[0] != qt[0]
            and not nt[0].startswith(qt[0])
            and not _token_in_name(qt[0], [nt[0]])
            and nt[0] not in _MILD_DESCRIPTORS
        ):
            score -= 6.0
        elif len(nt) == 1 and _token_in_name(qt[0], nt):
            score += 8.0  # bananas / onions plural exact-ish
        elif nt[0] in _MILD_DESCRIPTORS and _token_in_name(qt[0], nt[1:]):
            score += 6.0  # brown onions, semi skimmed milk

    # Extra product words for multi-token queries
    if len(qt) > 1:
        extra = max(0, len(nt) - len(qt))
        score -= min(5.0, extra * 1.2)
        # Reject when product is clearly a different prepared food
        leftovers = [t for t in nt if t not in qt and t not in _MILD_DESCRIPTORS]
        junk = {
            "crackers", "cracker", "wafers", "wafer", "biscuits", "biscuit",
            "cookies", "cookie", "crisps", "chips", "mayo", "sauce", "dressing",
            "smoothie", "yoghurt", "yogurt", "pouch", "peri-naise", "perinaise",
            "basa", "fish", "salmon", "cod", "tuna", "haddock",
            "nuggets", "tenders", "burger", "sandwich",
        }
        # "chicken" leftover only when the query itself isn't a chicken product
        if "chicken" not in qt:
            junk.add("chicken")
        if leftovers and any(t in junk for t in leftovers):
            return -1.0

    display = entry.get("name") or name
    if _READY_MEAL.search(display):
        score -= 6.0

    # Recency boost relative to today (not hardcoded years)
    date = str(entry.get("observed_date") or entry.get("date") or "")
    m = re.match(r"^(\d{4})-(\d{2})", date)
    if m:
        try:
            observed = datetime(int(m.group(1)), int(m.group(2)), 1, tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - observed).days
            if age_days <= 90:
                score += 1.5
            elif age_days <= 365:
                score += 0.5
        except ValueError:
            pass

    return score


def _estimate_usage_cost(entry: Dict[str, Any], amount: Any, unit: Optional[str]) -> Tuple[float, str]:
    pack_price = float(entry["price"])
    try:
        amount_num = float(str(amount).replace(",", "").split()[0]) if amount not in (None, "") else None
    except (TypeError, ValueError):
        amount_num = None

    unit = (unit or "").lower().strip() or None
    if amount_num is None and isinstance(amount, str):
        m = re.match(r"^\s*([\d.]+)\s*([a-zA-Z%]+)?", amount)
        if m:
            try:
                amount_num = float(m.group(1))
                unit = unit or (m.group(2) or "").lower() or None
            except ValueError:
                pass

    grams = None
    if amount_num is not None:
        if unit in ("g", "gram", "grams", "ml"):
            grams = amount_num
        elif unit in ("kg", "l", "litre", "liter"):
            grams = amount_num * 1000
        elif unit is None and amount_num >= 20:
            # Bare numbers ≥20 are usually grams in recipes
            grams = amount_num

    if grams and entry.get("per_kg"):
        return round(max(0.05, float(entry["per_kg"]) * (grams / 1000.0)), 2), "per_kg"

    qty = entry.get("quantity")
    qty_unit = entry.get("quantity_unit")
    if grams and qty and qty_unit in ("g", "kg", "ml", "l"):
        pack_grams = float(qty) * (1000 if qty_unit in ("kg", "l") else 1)
        if pack_grams > 0:
            cost = pack_price * (grams / pack_grams)
            return round(max(0.05, min(cost, pack_price)), 2), "pack_fraction"

    # Count units (eggs, onions, …): share of pack, not /500
    if amount_num is not None and grams is None:
        pack_count = None
        if qty and (qty_unit in (None, "", "each", "pcs", "pieces", "pack") or qty_unit is None):
            if 1 <= float(qty) <= 24:
                pack_count = float(qty)
        if pack_count:
            cost = pack_price * min(1.0, amount_num / pack_count)
        elif amount_num <= 1:
            # One "unit" with unknown pack size → modest share of pack
            cost = pack_price * 0.35
        elif amount_num <= 12:
            cost = pack_price * min(1.0, amount_num / 6.0)
        else:
            cost = pack_price
        return round(max(0.10, cost), 2), "count_share"

    return round(max(0.10, pack_price * 0.35), 2), "pack_share"


async def lookup_uk_ingredient_price(
    ingredient_name: str,
    *,
    amount: Any = None,
    unit: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Best match from the local offline UK Open Prices catalog."""
    if not getattr(settings, "open_prices_enabled", True):
        return None

    from database.repositories.uk_open_price_repository import uk_open_price_repository

    await ensure_local_catalog()

    q = normalize_price_name(ingredient_name)
    if len(q) < 2:
        return None

    qt = _tokens(q)
    if not qt:
        return None

    # Candidate search: full query, then significant tokens (no reverse-LIKE garbage)
    candidates: List[Dict[str, Any]] = await uk_open_price_repository.search_by_name(q, limit=80)
    seen_ids = {c.get("id") for c in candidates}
    for token in qt:
        if len(token) < 3:
            continue
        for row in await uk_open_price_repository.search_by_name(token, limit=40):
            rid = row.get("id")
            if rid not in seen_ids:
                candidates.append(row)
                seen_ids.add(rid)

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for entry in candidates:
        s = _score_match(ingredient_name, entry)
        if s >= MIN_MATCH_SCORE:
            scored.append((s, entry))
    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    top_score = scored[0][0]
    # Only pool near-ties that look like the same product family
    top = [e for s, e in scored if s >= top_score - 1.0][:8]
    best = scored[0][1]
    matched = dict(best)

    # Median per-kg across near-ties is safe; do NOT median pack prices across
    # different pack sizes (that breaks pack_fraction estimates).
    per_kgs = [float(e["per_kg"]) for e in top if e.get("per_kg")]
    if per_kgs:
        matched["per_kg"] = round(statistics.median(per_kgs), 2)

    estimated, method = _estimate_usage_cost(matched, amount, unit)
    return {
        "price": matched["price"],
        "unit": matched.get("quantity_unit") or matched.get("price_per") or "pack",
        "quantity": 1,
        "source": "open_prices_uk",
        "provider": "Open Prices",
        "currency": "GBP",
        "store": matched.get("store"),
        "matched_product": matched.get("name"),
        "observed_date": matched.get("observed_date") or matched.get("date"),
        "product_code": matched.get("product_code"),
        "per_kg": matched.get("per_kg"),
        "estimated_cost": estimated,
        "estimate_method": method,
        "match_score": round(top_score, 2),
        "attribution": "Data © Open Food Facts Open Prices contributors (ODbL)",
        "attribution_url": "https://prices.openfoodfacts.org",
        "offline": True,
    }


async def get_offline_catalog(limit: int = 5000) -> Dict[str, Any]:
    """Export the local catalog for Android / self-hosted offline clients."""
    from database.repositories.uk_open_price_repository import uk_open_price_repository

    await ensure_local_catalog()
    rows = await uk_open_price_repository.find_all(limit=limit)
    latest = await uk_open_price_repository.latest_synced_at()
    return {
        "currency": "GBP",
        "provider": "Open Prices",
        "attribution": "Data © Open Food Facts Open Prices contributors (ODbL)",
        "attribution_url": "https://prices.openfoodfacts.org",
        "synced_at": latest.isoformat() if latest and hasattr(latest, "isoformat") else None,
        "count": len(rows),
        "items": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "name_norm": r.get("name_norm"),
                "price": r.get("price"),
                "store": r.get("store"),
                "observed_date": r.get("observed_date"),
                "product_code": r.get("product_code"),
                "quantity": r.get("quantity"),
                "quantity_unit": r.get("quantity_unit"),
                "per_kg": r.get("per_kg"),
            }
            for r in rows
        ],
    }
