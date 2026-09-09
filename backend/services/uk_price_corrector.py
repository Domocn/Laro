"""
Correct noisy Open Prices (GBP) observations before they hit the offline catalog.

Crowdsourced pack prices are often fine as pack prices but produce absurd £/kg
when quantity is a tiny sachet, or include typos (£99 milk). This module:

1. Sanitises each observation (pack size / per-kg bounds)
2. Aggregates by barcode (or normalised name) using medians + outlier drops
3. Optionally scrapes Open Prices *consensus* for staple OFF categories and
   clamps remaining wild £/kg values toward those references

No supermarket HTML scraping (blocked / ToS-fragile). Corrections come from
Open Prices itself + category-aware sanity bands.
"""
from __future__ import annotations

import logging
import re
import statistics
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "LaroFood/1.0 (https://laro.food; prices@laro.food)"
PRICES_API = "https://prices.openfoodfacts.org/api/v1/prices"
PRODUCTS_API = "https://prices.openfoodfacts.org/api/v1/products"

# High-concentration products where £/kg is naturally huge
_SPICE_HINT = re.compile(
    r"\b(spice|seasoning|rub|herb|mint|basil|oregano|cumin|paprika|chili|chilli|"
    r"pepper|salt|saffron|vanilla|yeast|gelatine|gelatin|baking powder|"
    r"stock cube|stock cubes|tea|coffee|matcha|supplement|vitamin|capsule|"
    r"tablet|nori|bay leaf|bay leaves|extract|essence|colouring|coloring)\b",
    re.I,
)

# Staple OFF categories → (min_per_kg, max_per_kg, max_pack_gbp)
STAPLE_CATEGORY_TAGS: Dict[str, Tuple[float, float, float]] = {
    "en:chicken-breasts": (3.0, 16.0, 20.0),
    "en:chicken-thighs": (2.5, 14.0, 18.0),
    "en:chicken-eggs": (1.5, 8.0, 8.0),
    "en:semi-skimmed-milks": (0.4, 2.5, 4.0),
    "en:whole-milks": (0.4, 2.5, 4.0),
    "en:bananas": (0.5, 3.5, 5.0),
    "en:onions": (0.4, 3.0, 4.0),
    "en:potatoes": (0.3, 3.0, 6.0),
    "en:rices": (0.5, 8.0, 10.0),
    "en:pasta": (0.5, 6.0, 8.0),
    "en:olive-oils": (3.0, 25.0, 30.0),
    "en:butters": (3.0, 16.0, 8.0),
    "en:cheeses": (3.0, 30.0, 15.0),
    "en:yogurts": (0.8, 8.0, 6.0),
    "en:salmons": (6.0, 35.0, 20.0),
    "en:ground-beef": (4.0, 18.0, 15.0),
    "en:beef-mince": (4.0, 18.0, 15.0),
}

_NAME_BANDS: List[Tuple[re.Pattern, Tuple[float, float, float]]] = [
    (re.compile(r"\bchicken breast", re.I), (3.0, 16.0, 20.0)),
    (re.compile(r"\bchicken thigh", re.I), (2.5, 14.0, 18.0)),
    (re.compile(r"\b(semi[- ]?skimmed|whole)\s+milk\b", re.I), (0.4, 2.5, 4.0)),
    (re.compile(r"\bbanana", re.I), (0.5, 3.5, 5.0)),
    (re.compile(r"\bonion", re.I), (0.4, 3.0, 4.0)),
    (re.compile(r"\bpotato", re.I), (0.3, 3.0, 6.0)),
    (re.compile(r"\brice\b", re.I), (0.5, 8.0, 10.0)),
    (re.compile(r"\bpasta\b|\bspaghetti\b|\bpenne\b", re.I), (0.5, 6.0, 8.0)),
    (re.compile(r"\bolive oil\b", re.I), (3.0, 25.0, 30.0)),
    (re.compile(r"\bbutter\b", re.I), (3.0, 16.0, 8.0)),
    (re.compile(r"\bsalmon\b", re.I), (6.0, 35.0, 20.0)),
    (re.compile(r"\b(beef mince|minced beef|ground beef)\b", re.I), (4.0, 18.0, 15.0)),
    (re.compile(r"\beggs?\b", re.I), (1.5, 8.0, 8.0)),
]

TAG_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "en:chicken-breasts": ("chicken breast",),
    "en:chicken-thighs": ("chicken thigh",),
    "en:semi-skimmed-milks": ("semi skimmed milk", "semi-skimmed milk"),
    "en:whole-milks": ("whole milk",),
    "en:bananas": ("banana",),
    "en:onions": ("onion",),
    "en:potatoes": ("potato",),
    "en:rices": ("rice", "basmati"),
    "en:pasta": ("pasta", "spaghetti", "penne"),
    "en:olive-oils": ("olive oil",),
    "en:butters": ("butter",),
    "en:salmons": ("salmon",),
    "en:ground-beef": ("beef mince", "minced beef", "ground beef"),
    "en:beef-mince": ("beef mince", "minced beef"),
    "en:chicken-eggs": ("egg", "eggs"),
    "en:yogurts": ("yogurt", "yoghurt"),
    "en:cheeses": ("cheddar", "cheese"),
}

DEFAULT_MAX_PER_KG = 40.0
DEFAULT_MAX_PACK = 50.0
MIN_GRAMS_FOR_PER_KG = 100.0


def _is_spice_like(name: str) -> bool:
    return bool(_SPICE_HINT.search(name or ""))


def _band_for_name(name: str) -> Optional[Tuple[float, float, float]]:
    for pattern, band in _NAME_BANDS:
        if pattern.search(name or ""):
            return band
    return None


def _pack_grams(entry: Dict[str, Any]) -> Optional[float]:
    qty = entry.get("quantity")
    unit = (entry.get("quantity_unit") or "").lower()
    if not qty or unit not in ("g", "kg", "ml", "l"):
        return None
    try:
        q = float(qty)
    except (TypeError, ValueError):
        return None
    return q * (1000.0 if unit in ("kg", "l") else 1.0)


def sanitize_price_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a cleaned copy, or None if the observation should be dropped."""
    if not entry:
        return None
    out = dict(entry)
    name = out.get("name") or ""
    try:
        price = float(out.get("price") or 0)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    band = _band_for_name(name)
    max_pack = band[2] if band else DEFAULT_MAX_PACK
    if price > max_pack * 2.5 and not _is_spice_like(name):
        return None
    if price > 120:
        return None

    per_kg = out.get("per_kg")
    try:
        per_kg_f = float(per_kg) if per_kg is not None else None
    except (TypeError, ValueError):
        per_kg_f = None

    grams = _pack_grams(out)
    spice = _is_spice_like(name)

    if per_kg_f is not None and not spice:
        if grams is not None and grams < MIN_GRAMS_FOR_PER_KG:
            per_kg_f = None
        elif per_kg_f > DEFAULT_MAX_PER_KG or per_kg_f < 0.15:
            per_kg_f = None

    if per_kg_f is not None and spice and per_kg_f > 800:
        per_kg_f = None

    if band and per_kg_f is not None:
        lo, hi, _ = band
        if per_kg_f < lo * 0.5 or per_kg_f > hi * 1.8:
            per_kg_f = None

    if band and price > band[2] * 1.5 and not spice:
        return None

    out["per_kg"] = round(per_kg_f, 2) if per_kg_f is not None else None
    out["price"] = round(price, 2)
    return out


def _group_key(entry: Dict[str, Any]) -> str:
    code = (entry.get("product_code") or "").strip()
    if code:
        return f"code:{code}"
    return f"name:{(entry.get('name_norm') or entry.get('name') or '').strip().lower()}"


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median(values))


def aggregate_price_entries(
    entries: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Collapse duplicates to median observations; drop outliers."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    stats = {
        "input": 0,
        "sanitized_out": 0,
        "groups": 0,
        "outliers_dropped": 0,
        "aggregated": 0,
    }

    for raw in entries:
        stats["input"] += 1
        clean = sanitize_price_entry(raw)
        if not clean:
            stats["sanitized_out"] += 1
            continue
        groups.setdefault(_group_key(clean), []).append(clean)

    stats["groups"] = len(groups)
    out: List[Dict[str, Any]] = []

    for key, rows in groups.items():
        prices = [float(r["price"]) for r in rows if r.get("price")]
        med_price = _median(prices)
        if med_price is None:
            continue

        kept: List[Dict[str, Any]] = []
        for r in rows:
            p = float(r["price"])
            if med_price > 0 and (p > med_price * 2.5 or p < med_price * 0.35):
                stats["outliers_dropped"] += 1
                continue
            kept.append(r)
        if not kept:
            kept = [min(rows, key=lambda r: abs(float(r["price"]) - med_price))]

        prices = [float(r["price"]) for r in kept]
        per_kgs = [float(r["per_kg"]) for r in kept if r.get("per_kg")]
        med_price = _median(prices) or med_price
        med_per_kg = _median(per_kgs)

        template = sorted(
            kept,
            key=lambda r: str(r.get("observed_date") or r.get("date") or ""),
            reverse=True,
        )[0]
        merged = dict(template)
        merged["price"] = round(med_price, 2)
        merged["per_kg"] = round(med_per_kg, 2) if med_per_kg is not None else None
        merged["id"] = f"agg:{key}:{merged['price']}:{merged.get('per_kg')}"
        merged["observation_count"] = len(kept)
        out.append(merged)
        stats["aggregated"] += 1

    return out, stats


async def scrape_category_reference_prices(
    *,
    category_tags: Optional[Dict[str, Tuple[float, float, float]]] = None,
    max_products_per_category: int = 25,
    timeout: float = 40.0,
) -> Dict[str, Dict[str, Any]]:
    """Scrape Open Prices consensus £/kg for staple OFF categories."""
    tags = category_tags or STAPLE_CATEGORY_TAGS
    refs: Dict[str, Dict[str, Any]] = {}

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=timeout) as client:
        for tag, band in tags.items():
            try:
                resp = await client.get(
                    PRODUCTS_API,
                    params={
                        "size": max_products_per_category,
                        "order_by": "-price_count",
                        "categories_tags__contains": tag,
                    },
                )
                resp.raise_for_status()
                products = resp.json().get("items") or []
            except Exception as e:
                logger.warning("Price scrape: products for %s failed: %s", tag, e)
                continue

            per_kgs: List[float] = []
            for product in products:
                code = product.get("code")
                if not code or not product.get("price_count"):
                    continue
                try:
                    pr = await client.get(
                        PRICES_API,
                        params={
                            "product__code": code,
                            "currency": "GBP",
                            "size": 40,
                            "order_by": "-date",
                        },
                    )
                    pr.raise_for_status()
                    price_items = pr.json().get("items") or []
                except Exception:
                    continue

                for item in price_items:
                    try:
                        price = float(item.get("price") or 0)
                    except (TypeError, ValueError):
                        continue
                    if price <= 0:
                        continue
                    prod = item.get("product") or product
                    qty = prod.get("product_quantity")
                    unit = (prod.get("product_quantity_unit") or "").lower()
                    price_per = (item.get("price_per") or "").upper()
                    pk = None
                    if price_per == "KILOGRAM":
                        pk = price
                    elif qty and unit in ("g", "kg", "ml", "l"):
                        try:
                            grams = float(qty) * (1000 if unit in ("kg", "l") else 1)
                        except (TypeError, ValueError):
                            grams = 0
                        if grams >= MIN_GRAMS_FOR_PER_KG:
                            pk = price / (grams / 1000.0)
                    if pk is None:
                        continue
                    lo, hi, _ = band
                    if lo * 0.4 <= pk <= hi * 2.0:
                        per_kgs.append(pk)

            if len(per_kgs) >= 3:
                med = float(statistics.median(per_kgs))
                refs[tag] = {
                    "median_per_kg": round(med, 2),
                    "n": len(per_kgs),
                    "band": band,
                }
                logger.info(
                    "Price scrape: %s median £%.2f/kg from %s observations",
                    tag,
                    med,
                    len(per_kgs),
                )

    return refs


def apply_reference_clamps(
    entries: Iterable[Dict[str, Any]],
    references: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Soft-clamp per_kg toward scraped category medians when outside the band."""
    clamped = 0
    out: List[Dict[str, Any]] = []
    for entry in entries:
        row: Optional[Dict[str, Any]] = dict(entry)
        name = (row.get("name") or "").lower()
        per_kg = row.get("per_kg")
        try:
            per_kg_f = float(per_kg) if per_kg is not None else None
        except (TypeError, ValueError):
            per_kg_f = None

        for tag, ref in references.items():
            keywords = TAG_KEYWORDS.get(tag) or ()
            if not any(k in name for k in keywords):
                continue
            band = ref.get("band") or STAPLE_CATEGORY_TAGS.get(tag)
            med = ref.get("median_per_kg")
            if not band or med is None:
                break
            lo, hi, max_pack = band
            try:
                price = float(row.get("price") or 0)
            except (TypeError, ValueError):
                price = 0
            if price > max_pack * 1.8:
                row = None
                break
            if per_kg_f is None:
                row["per_kg"] = round(float(med), 2)
                row["per_kg_source"] = "open_prices_consensus"
                clamped += 1
            elif per_kg_f < lo or per_kg_f > hi:
                row["per_kg"] = round(float(med), 2)
                row["per_kg_source"] = "open_prices_consensus"
                clamped += 1
            break

        if row is not None:
            out.append(row)

    return out, clamped


async def correct_open_prices_catalog(
    entries: List[Dict[str, Any]],
    *,
    scrape_references: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Full correction pipeline used by sync_uk_open_prices."""
    aggregated, agg_stats = aggregate_price_entries(entries)
    refs: Dict[str, Dict[str, Any]] = {}
    clamped = 0
    if scrape_references:
        try:
            refs = await scrape_category_reference_prices()
        except Exception as e:
            logger.warning("Reference price scrape failed: %s", e)
            refs = {}
        if refs:
            aggregated, clamped = apply_reference_clamps(aggregated, refs)

    stats = {
        **agg_stats,
        "reference_categories": len(refs),
        "clamped_to_consensus": clamped,
        "output": len(aggregated),
    }
    return aggregated, stats
