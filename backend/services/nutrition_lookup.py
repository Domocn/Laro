"""
Remote nutrition lookups — free open-source / open-data only. No AI. No paid APIs.

Sources (in order for unknown foods):
  1. Curated food_db (caller)
  2. Open Food Facts UK (uk.openfoodfacts.org) — preferred for Laro's GB default
  3. Open Food Facts world
  4. USDA FoodData Central free DEMO_KEY / optional USDA_FDC_API_KEY

Also exposes UK Reference Intake (RI) helpers aligned with FSA / NHS labelling.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# name -> (expires_epoch, entry|None)
_CACHE: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}
_CACHE_TTL_SEC = 60 * 60 * 12
_CACHE_NEG_TTL_SEC = 60 * 30
_MAX_CACHE = 512

# UK adult Reference Intakes (labelling) — FSA / retained EU FIC style values
# Used for %RI display; not personalised medical advice.
UK_REFERENCE_INTAKES = {
    "energy_kj": 8400.0,
    "energy_kcal": 2000.0,
    "fat_g": 70.0,
    "saturates_g": 20.0,
    "carbs_g": 260.0,
    "sugars_g": 90.0,
    "protein_g": 50.0,
    "salt_g": 6.0,
    "fibre_g": 30.0,  # SACN / NHS fibre guideline (not always on RI panel)
}


def _cache_get(key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    item = _CACHE.get(key)
    if not item:
        return False, None
    expires, value = item
    if time.time() > expires:
        _CACHE.pop(key, None)
        return False, None
    return True, value


def _cache_set(key: str, value: Optional[Dict[str, Any]], negative: bool = False) -> None:
    if len(_CACHE) >= _MAX_CACHE:
        for old in list(_CACHE.keys())[: _MAX_CACHE // 2]:
            _CACHE.pop(old, None)
    ttl = _CACHE_NEG_TTL_SEC if negative or value is None else _CACHE_TTL_SEC
    _CACHE[key] = (time.time() + ttl, value)


def _normalize_query(name: str) -> str:
    text = (name or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:80]


def _macros_entry(
    *,
    calories: float,
    protein: float,
    carbs: float,
    fat: float,
    fiber: float = 0.0,
    source: str,
    label: str,
    salt: float = 0.0,
    sugars: float = 0.0,
    saturates: float = 0.0,
) -> Dict[str, Any]:
    kcal = round(float(calories or 0), 1)
    return {
        "calories": kcal,
        "energy_kcal": kcal,
        "energy_kj": round(kcal * 4.184, 1),  # UK labels show kJ + kcal
        "protein": round(float(protein or 0), 1),
        "carbs": round(float(carbs or 0), 1),
        "fat": round(float(fat or 0), 1),
        "fiber": round(float(fiber or 0), 1),
        "fibre": round(float(fiber or 0), 1),  # UK spelling alias
        "salt": round(float(salt or 0), 2),
        "sugars": round(float(sugars or 0), 1),
        "saturates": round(float(saturates or 0), 1),
        "tags": ["remote", source, "open-data"],
        "category": "remote",
        "source": source,
        "label": label,
    }


def uk_percent_ri(per_serving: Dict[str, Any]) -> Dict[str, float]:
    """Percent of UK adult Reference Intakes for a serving (free FSA RI values)."""
    kcal = float(per_serving.get("calories") or per_serving.get("energy_kcal") or 0)
    out = {
        "energy_kcal_pct": round(100.0 * kcal / UK_REFERENCE_INTAKES["energy_kcal"], 1),
        "energy_kj_pct": round(
            100.0 * (kcal * 4.184) / UK_REFERENCE_INTAKES["energy_kj"], 1
        ),
        "fat_pct": round(100.0 * float(per_serving.get("fat") or 0) / UK_REFERENCE_INTAKES["fat_g"], 1),
        "carbs_pct": round(
            100.0 * float(per_serving.get("carbs") or 0) / UK_REFERENCE_INTAKES["carbs_g"], 1
        ),
        "protein_pct": round(
            100.0 * float(per_serving.get("protein") or 0) / UK_REFERENCE_INTAKES["protein_g"], 1
        ),
        "fibre_pct": round(
            100.0
            * float(per_serving.get("fiber") or per_serving.get("fibre") or 0)
            / UK_REFERENCE_INTAKES["fibre_g"],
            1,
        ),
        "salt_pct": round(
            100.0 * float(per_serving.get("salt") or 0) / UK_REFERENCE_INTAKES["salt_g"], 1
        ),
        "sugars_pct": round(
            100.0 * float(per_serving.get("sugars") or 0) / UK_REFERENCE_INTAKES["sugars_g"], 1
        ),
        "saturates_pct": round(
            100.0 * float(per_serving.get("saturates") or 0) / UK_REFERENCE_INTAKES["saturates_g"], 1
        ),
    }
    return out


# FSA front-of-pack traffic light thresholds (per 100g) — public UK guidance
_FSA_PER_100G = {
    "fat": (3.0, 17.5),
    "saturates": (1.5, 5.0),
    "sugars": (5.0, 22.5),
    "salt": (0.3, 1.5),
}


def _traffic_band(value: float, low: float, high: float) -> str:
    if value <= low:
        return "green"
    if value <= high:
        return "amber"
    return "red"


def uk_traffic_lights_per_100g(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    UK FSA traffic-light colours for fat / saturates / sugars / salt per 100g.
    Returns colour + value for each nutrient (and None when value missing).
    """
    out: Dict[str, Any] = {}
    for key, (low, high) in _FSA_PER_100G.items():
        raw = entry.get(key)
        if raw is None or raw == "":
            out[key] = {"value": None, "color": None, "per": "100g"}
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            out[key] = {"value": None, "color": None, "per": "100g"}
            continue
        out[key] = {
            "value": round(value, 2),
            "color": _traffic_band(value, low, high),
            "per": "100g",
            "thresholds": {"green_max": low, "amber_max": high},
        }
    return out


def _clean_off_tags(tags: Any) -> list:
    if not tags:
        return []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.replace(",", "\n").split("\n") if t.strip()]
    out = []
    for tag in tags:
        text = str(tag).strip()
        if not text:
            continue
        # OFF tags often look like en:milk — keep readable tail
        if ":" in text:
            text = text.split(":", 1)[1]
        text = text.replace("-", " ").strip()
        if text and text not in out:
            out.append(text)
    return out[:40]


def _off_category_to_aisle(categories: list) -> Optional[str]:
    """Map OFF category strings to Laro grocery aisle names."""
    blob = " ".join(categories).lower()
    mapping = [
        ("Produce", ("fruit", "vegetable", "produce", "salad", "herb")),
        ("Dairy", ("dairy", "cheese", "milk", "yogurt", "egg")),
        ("Meat & Seafood", ("meat", "poultry", "fish", "seafood", "beef", "chicken")),
        ("Bakery", ("bread", "bakery", "pastries")),
        ("Frozen", ("frozen",)),
        ("Beverages", ("beverage", "drink", "juice", "soda", "water")),
        ("Snacks", ("snack", "chip", "crisp", "confection")),
        ("Breakfast", ("breakfast", "cereal")),
        ("Pasta & Grains", ("pasta", "rice", "grain", "noodle")),
        ("Canned Goods", ("canned", "tinned")),
        ("Condiments & Sauces", ("sauce", "condiment", "dressing")),
        ("Baking", ("baking", "flour", "sugar")),
        ("Spices & Seasonings", ("spice", "seasoning", "herb")),
        ("Household", ("household", "cleaning")),
    ]
    for aisle, keys in mapping:
        if any(k in blob for k in keys):
            return aisle
    return None


def _entry_from_off_product(product: Dict[str, Any], query: str, source: str) -> Optional[Dict[str, Any]]:
    nutriments = product.get("nutriments") or {}
    kcal = nutriments.get("energy-kcal_100g")
    if kcal is None:
        kj = nutriments.get("energy-kj_100g") or nutriments.get("energy_100g")
        if kj is not None:
            try:
                kcal = float(kj) / 4.184
            except Exception:
                kcal = None
    protein = nutriments.get("proteins_100g")
    carbs = nutriments.get("carbohydrates_100g")
    fat = nutriments.get("fat_100g")
    fiber = nutriments.get("fiber_100g") or nutriments.get("fibre_100g") or 0
    salt = nutriments.get("salt_100g") or 0
    sugars = nutriments.get("sugars_100g") or 0
    saturates = nutriments.get("saturated-fat_100g") or 0
    if kcal is None and protein is None:
        return None
    label = product.get("product_name") or product.get("generic_name") or query
    allergens = _clean_off_tags(
        product.get("allergens_tags") or product.get("allergens") or []
    )
    traces = _clean_off_tags(product.get("traces_tags") or product.get("traces") or [])
    categories = _clean_off_tags(
        product.get("categories_tags") or product.get("categories") or []
    )
    entry = _macros_entry(
        calories=float(kcal or 0),
        protein=float(protein or 0),
        carbs=float(carbs or 0),
        fat=float(fat or 0),
        fiber=float(fiber or 0),
        salt=float(salt or 0),
        sugars=float(sugars or 0),
        saturates=float(saturates or 0),
        source=source,
        label=str(label),
    )
    entry["allergens"] = allergens
    entry["traces"] = traces
    entry["categories"] = categories
    entry["suggested_aisle"] = _off_category_to_aisle(categories)
    entry["uk_traffic_lights_per_100g"] = uk_traffic_lights_per_100g(entry)
    entry["uk_percent_ri_per_100g"] = uk_percent_ri(entry)
    brands = product.get("brands") or ""
    if brands:
        entry["brands"] = str(brands)
    return entry


def _off_api(country: Any):
    from openfoodfacts import API, APIVersion, Environment, Flavor

    return API(
        user_agent="LaroFoodApp/1.0 (free-open-data nutrition; +https://laro.app)",
        country=country,
        flavor=Flavor.off,
        version=APIVersion.v2,
        environment=Environment.org,
    )


def lookup_open_food_facts(name: str, *, prefer_uk: bool = True) -> Optional[Dict[str, Any]]:
    """Free Open Food Facts search. UK catalogue first when prefer_uk=True."""
    query = _normalize_query(name)
    if len(query) < 2:
        return None
    try:
        from openfoodfacts import Country

        countries = []
        if prefer_uk:
            countries.append((Country.uk, "openfoodfacts-uk"))
        countries.append((Country.world, "openfoodfacts"))

        for country, source in countries:
            try:
                api = _off_api(country)
                result = api.product.text_search(query, page_size=5)
                products = (result or {}).get("products") or []
                for product in products:
                    entry = _entry_from_off_product(product, query, source)
                    if entry:
                        return entry
            except Exception as e:
                logger.info("OFF %s search failed for %r: %s", source, query, e)
    except Exception as e:
        logger.info("Open Food Facts lookup failed for %r: %s", query, e)
    return None


def lookup_open_food_facts_barcode(barcode: str, *, prefer_uk: bool = True) -> Optional[Dict[str, Any]]:
    code = re.sub(r"\D", "", barcode or "")
    if len(code) < 8:
        return None
    try:
        from openfoodfacts import Country

        countries = []
        if prefer_uk:
            countries.append((Country.uk, "openfoodfacts-uk-barcode"))
        countries.append((Country.world, "openfoodfacts-barcode"))

        for country, source in countries:
            try:
                api = _off_api(country)
                product = api.product.get(code)
                if not isinstance(product, dict) or product.get("status") == 0:
                    continue
                body = product.get("product") if isinstance(product.get("product"), dict) else product
                entry = _entry_from_off_product(body, code, source)
                if entry:
                    return entry
            except Exception as e:
                logger.info("OFF barcode %s failed for %s: %s", source, code, e)
    except Exception as e:
        logger.info("OFF barcode lookup failed for %s: %s", code, e)
    return None


def lookup_usda_fdc(name: str) -> Optional[Dict[str, Any]]:
    """Free USDA FoodData Central (DEMO_KEY). Last resort after OFF."""
    query = _normalize_query(name)
    if len(query) < 2:
        return None
    api_key = (
        os.getenv("USDA_FDC_API_KEY")
        or os.getenv("FDC_API_KEY")
        or "DEMO_KEY"
    )
    try:
        from usda_fdc import FdcClient

        client = FdcClient(api_key=api_key)
        result = client.search(
            query,
            data_type=["Foundation", "SR Legacy", "Survey (FNDDS)"],
            page_size=5,
        )
        foods = list(getattr(result, "foods", None) or [])
        if not foods:
            result = client.search(query, page_size=5)
            foods = list(getattr(result, "foods", None) or [])
        if not foods:
            return None

        def _rank(f: Any) -> int:
            dt = str(getattr(f, "data_type", "") or "")
            if "Foundation" in dt:
                return 0
            if "SR Legacy" in dt:
                return 1
            if "Survey" in dt:
                return 2
            return 3

        foods.sort(key=_rank)
        food = client.get_food(foods[0].fdc_id)
        nutrients = list(getattr(food, "nutrients", None) or [])

        def _amt(*names: str) -> float:
            wanted = {n.lower() for n in names}
            for nutrient in nutrients:
                nname = str(getattr(nutrient, "name", "") or "").lower()
                unit = str(getattr(nutrient, "unit_name", "") or "").lower()
                if nname in wanted:
                    if "energy" in nname and unit not in ("kcal",):
                        continue
                    try:
                        return float(getattr(nutrient, "amount", 0) or 0)
                    except Exception:
                        return 0.0
            for nutrient in nutrients:
                nname = str(getattr(nutrient, "name", "") or "").lower()
                unit = str(getattr(nutrient, "unit_name", "") or "").lower()
                for w in wanted:
                    if w in nname:
                        if "energy" in nname and unit not in ("kcal",):
                            continue
                        try:
                            return float(getattr(nutrient, "amount", 0) or 0)
                        except Exception:
                            return 0.0
            return 0.0

        calories = _amt("energy")
        protein = _amt("protein")
        carbs = _amt("carbohydrate, by difference", "carbohydrate")
        fat = _amt("total lipid (fat)", "total lipid", "fat")
        fiber = _amt("fiber, total dietary", "fiber")
        sugars = _amt("total sugars", "sugars")
        saturates = _amt("fatty acids, total saturated", "saturated")
        sodium_mg = _amt("sodium, na", "sodium")
        salt = round(sodium_mg / 400.0, 2) if sodium_mg else 0.0  # Na mg → salt g approx
        if not any((calories, protein, carbs, fat)):
            return None
        label = getattr(food, "description", None) or query
        return _macros_entry(
            calories=calories,
            protein=protein,
            carbs=carbs,
            fat=fat,
            fiber=fiber,
            salt=salt,
            sugars=sugars,
            saturates=saturates,
            source="usda-fdc",
            label=str(label),
        )
    except Exception as e:
        logger.info("USDA FDC lookup failed for %r: %s", query, e)
    return None


def lookup_remote_nutrition(name: str, *, prefer_uk: bool = True) -> Optional[Dict[str, Any]]:
    """
    Resolve per-100g macros via free open data (UK OFF → world OFF → USDA).
    Cached; never raises.
    """
    key = _normalize_query(name)
    if not key:
        return None
    cache_key = f"name:{'uk' if prefer_uk else 'world'}:{key}"
    hit, cached = _cache_get(cache_key)
    if hit:
        return cached

    entry = lookup_open_food_facts(key, prefer_uk=prefer_uk)
    if not entry:
        entry = lookup_usda_fdc(key)
    _cache_set(cache_key, entry, negative=entry is None)
    return entry


def lookup_barcode_nutrition(barcode: str, *, prefer_uk: bool = True) -> Optional[Dict[str, Any]]:
    code = re.sub(r"\D", "", barcode or "")
    if not code:
        return None
    cache_key = f"bc:{'uk' if prefer_uk else 'world'}:{code}"
    hit, cached = _cache_get(cache_key)
    if hit:
        return cached
    entry = lookup_open_food_facts_barcode(code, prefer_uk=prefer_uk)
    _cache_set(cache_key, entry, negative=entry is None)
    return entry
