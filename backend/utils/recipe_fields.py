"""
Helpers for mapping recipe API fields to/from the PostgreSQL schema.

The API exposes a nested `nutrition` object; the DB stores flat
`nutrition_*` columns. `dietary_tags` is JSON text in the DB.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

NUTRITION_COLUMN_MAP = {
    "calories": "nutrition_calories",
    "protein": "nutrition_protein",
    "carbs": "nutrition_carbs",
    "fat": "nutrition_fat",
    "fiber": "nutrition_fiber",
    "sugar": "nutrition_sugar",
    "sodium": "nutrition_sodium",
}


def nutrition_to_columns(nutrition: Optional[Any]) -> Dict[str, Optional[int]]:
    """Flatten API nutrition (model or dict) into DB column values."""
    if nutrition is None:
        return {col: None for col in NUTRITION_COLUMN_MAP.values()}

    if hasattr(nutrition, "model_dump"):
        data = nutrition.model_dump()
    elif isinstance(nutrition, dict):
        # Prefer per-serving values when saving calculated nutrition
        data = nutrition.get("per_serving") or nutrition
    else:
        return {col: None for col in NUTRITION_COLUMN_MAP.values()}

    columns: Dict[str, Optional[int]] = {}
    for api_key, col in NUTRITION_COLUMN_MAP.items():
        value = data.get(api_key)
        if value is None:
            columns[col] = None
        else:
            try:
                columns[col] = int(round(float(value)))
            except (TypeError, ValueError):
                columns[col] = None
    return columns


def columns_to_nutrition(row: Dict[str, Any]) -> Optional[Dict[str, Optional[int]]]:
    """Rebuild nested nutrition object from flat DB columns."""
    if not row:
        return None

    # Already hydrated
    existing = row.get("nutrition")
    if isinstance(existing, dict) and any(v is not None for v in existing.values()):
        return existing

    nutrition = {
        api_key: row.get(col)
        for api_key, col in NUTRITION_COLUMN_MAP.items()
    }
    if all(v is None for v in nutrition.values()):
        return None
    return nutrition


CORE_NUTRITION_KEYS = ("calories", "protein", "carbs", "fat")


def enrich_nutrition_from_ingredients(
    nutrition: Optional[Dict[str, Any]],
    ingredients: Any,
    *,
    servings: Any = 1,
) -> Dict[str, Any]:
    """
    Prefer author-provided macros; fill any missing core macros from the food DB.

    Returns a nutrition dict plus optional metadata:
      nutrition_estimated: True when any value came from the ingredient estimate
      nutrition_source: "recipe" | "estimated" | "mixed"
    """
    provided: Dict[str, Any] = dict(nutrition or {})
    missing = [k for k in CORE_NUTRITION_KEYS if provided.get(k) is None]
    if not missing:
        # Preserve prior estimate metadata when re-enriching an already-complete dict
        prior_est = bool(provided.get("nutrition_estimated"))
        prior_src = provided.get("nutrition_source")
        return {
            **provided,
            "nutrition_estimated": prior_est,
            "nutrition_source": prior_src or ("estimated" if prior_est else "recipe"),
        }

    try:
        from utils.food_db import estimate_nutrition_from_foods

        estimate = estimate_nutrition_from_foods(
            ingredients or [],
            servings=servings or 1,
        )
        per = estimate.get("per_serving") or {}
    except Exception:
        return {
            **provided,
            "nutrition_estimated": False,
            "nutrition_source": "recipe" if any(provided.get(k) is not None for k in CORE_NUTRITION_KEYS) else "none",
        }

    out = dict(provided)
    filled = False
    for key in CORE_NUTRITION_KEYS + ("fiber",):
        if out.get(key) is None and per.get(key) is not None:
            try:
                out[key] = round(float(per[key]))
            except (TypeError, ValueError):
                out[key] = per[key]
            if key in CORE_NUTRITION_KEYS:
                filled = True

    had_any = any(provided.get(k) is not None for k in CORE_NUTRITION_KEYS)
    source = "estimated" if filled and not had_any else ("mixed" if filled else "recipe")
    return {
        **out,
        "nutrition_estimated": filled,
        "nutrition_source": source,
    }


def ensure_list_field(value: Any) -> list:
    """Deserialize JSON list fields that may arrive as strings from Postgres."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def normalize_adaptations(value: Any) -> Optional[Dict[str, Any]]:
    """Clean the optional ``adaptations`` JSON (``low_fodmap`` swaps, named ``versions``, ``page_notes``).

    Shape: ``{"low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}],
    "notes": "..."}, "versions": [{"name": "...", "ingredients": [...], "instructions": [...],
    "notes": "..."}]}``. Accepts a JSON string (Postgres TEXT) or dict; drops blank swaps.
    Returns None when nothing useful is left so the column stays NULL.
    Computed macros are kept too: each version's ``nutrition`` / ``ingredient_macros`` /
    ``low_fodmap_macros`` / ``macros_sig`` and the top-level ``low_fodmap_macros``.
    """
    from utils.ingredient_groups import split_ingredient_group

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(value, dict):
        return None
    out: Dict[str, Any] = {}
    fodmap = value.get("low_fodmap")
    if isinstance(fodmap, dict):
        swaps = []
        for swap in fodmap.get("swaps") or []:
            if not isinstance(swap, dict):
                continue
            # "Sauce: garlic" -> "garlic": swaps match the clean ingredient name.
            src = split_ingredient_group(str(swap.get("from") or "").strip())[1].strip()[:200]
            dst = str(swap.get("to") or "").strip()[:200]
            if src and dst:
                swaps.append({"from": src, "to": dst})
        notes = str(fodmap.get("notes") or "").strip()[:2000]
        if swaps or notes:
            out["low_fodmap"] = {"swaps": swaps[:30], "notes": notes}
            # Original with the swaps applied (services/version_macros.py).
            lf_macros = _normalize_macro_variant(value.get("low_fodmap_macros"), 100) if swaps else None
            if lf_macros:
                out["low_fodmap_macros"] = lf_macros
    versions = _normalize_versions(value.get("versions"))
    if versions:
        out["versions"] = versions
    page_notes = normalize_page_notes(value.get("page_notes"))
    if page_notes:
        out["page_notes"] = page_notes
    # The user's choice of nutrition basis ("serving" / "100g"); absent = automatic
    # (services/nutrition_basis.py). Computed per-100 g numbers are never stored here.
    basis = str(value.get("nutrition_basis") or "").strip().lower()
    if basis in ("serving", "100g"):
        out["nutrition_basis"] = basis
    if value.get("confirmed_lines"):
        # User-checked line macros ("Check the numbers"): services/confirmed_lines.py.
        from services.confirmed_lines import normalize_confirmed

        confirmed = normalize_confirmed(value.get("confirmed_lines"))
        if confirmed:
            out["confirmed_lines"] = confirmed
    return out or None


def normalize_page_notes(value: Any) -> list:
    """Cookbook "Notes & tips" (intro extras, soak / timing, storage, to serve): trimmed strings, max 30."""
    if isinstance(value, str):
        value = [value]
    out: list = []
    for note in value if isinstance(value, list) else []:
        text = str(note or "").strip()[:2000] if not isinstance(note, (dict, list)) else ""
        if text and text not in out:
            out.append(text)
    return out[:30]


MAX_RECIPE_VERSIONS = 10

_MACRO_NUTRITION_KEYS = ("calories", "protein", "carbs", "fat", "fiber", "sugar", "sodium")
_BADGE_LIMITS = {"p": 1000, "c": 2000, "f": 1000, "cal": 10000}  # same caps as services/line_macros.py
_SIG_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _bounded_int(value: Any, hi: int) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n or n < 0:  # NaN / negative
        return None
    return int(round(min(n, hi)))


def normalize_macro_nutrition(value: Any) -> Optional[Dict[str, Any]]:
    """Per-serving nutrition stored on a version: numeric macros only (ints, like the recipe
    columns) plus the estimate flag. None unless at least one core macro is present."""
    if not isinstance(value, dict):
        return None
    out: Dict[str, Any] = {}
    for key in _MACRO_NUTRITION_KEYS:
        n = _bounded_int(value.get(key), 100000)
        if n is not None:
            out[key] = n
    if not any(k in out for k in CORE_NUTRITION_KEYS):
        return None
    if value.get("nutrition_estimated") is True:
        out["nutrition_estimated"] = True
    if value.get("nutrition_source") in ("estimated", "recipe", "mixed", "derived"):
        out["nutrition_source"] = value["nutrition_source"]
    return out


def _badge_provenance(item: Dict[str, Any]) -> Dict[str, Any]:
    """Where a line's macros came from (services/line_macros.py): ``src`` "db" / "ai", and for
    "db" the matched ``food``, grams ``g`` and dataset ``source``. Anything else is dropped."""
    src = item.get("src")
    if src not in ("db", "ai", "user", "barcode"):  # user / barcode: confirmed by the user
        return {}
    out: Dict[str, Any] = {"src": src}
    # Grams of the line as used (database lines always; AI lines estimate them, g_src "ai";
    # user / barcode lines carry what the user entered).
    g = item.get("g")
    if not isinstance(g, bool) and isinstance(g, (int, float)) and 0 <= g <= 100000:
        out["g"] = round(float(g), 1)
        out["g_src"] = "ai" if src == "ai" else ("db" if src == "db" else "user")
    if src != "ai":
        food = " ".join(str(item.get("food") or "").split())[:200]
        if food:
            out["food"] = food
        source = str(item.get("source") or "").strip()
        if re.fullmatch(r"[a-z0-9_]{1,40}", source):
            out["source"] = source
    return out


def normalize_ingredient_macros(value: Any, limit: int = 100) -> list:
    """[{p, c, f, cal[, c_total, src, food, g, source]}] per ingredient line (ints, clamped), at
    most ``limit`` entries. ``c`` is available carbohydrate (UK basis), optional ``c_total``
    total carbohydrate incl. fibre (US basis)."""
    out: list = []
    for item in value if isinstance(value, list) else []:
        if len(out) >= max(0, min(limit, 100)):
            break
        item = item if isinstance(item, dict) else {}
        badge = {k: _bounded_int(item.get(k), hi) or 0 for k, hi in _BADGE_LIMITS.items()}
        c_total = _bounded_int(item.get("c_total"), _BADGE_LIMITS["c"])  # US-basis carbs (incl. fibre)
        if c_total is not None:
            badge["c_total"] = c_total
        badge.update(_badge_provenance(item))
        out.append(badge)
    return out


def _normalize_macro_variant(value: Any, limit: int) -> Optional[Dict[str, Any]]:
    """{nutrition, ingredient_macros[, macros_sig]} for a Low FODMAP variant."""
    if not isinstance(value, dict):
        return None
    nutrition = normalize_macro_nutrition(value.get("nutrition"))
    if not nutrition:
        return None
    out: Dict[str, Any] = {
        "nutrition": nutrition,
        "ingredient_macros": normalize_ingredient_macros(value.get("ingredient_macros"), limit),
    }
    sig = _clean_sig(value.get("macros_sig"))
    if sig:
        out["macros_sig"] = sig
    return out


def _clean_sig(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text if _SIG_RE.match(text) else None


def _normalize_versions(value: Any) -> list:
    """Named versions of one dish ("Chicken Schnitzel", "Chocolate Orange").

    Each holds FULL ingredient + instruction lists; the recipe's own lists are the
    "Original". Drops unnamed / empty versions and repeated names; caps at 10.
    """
    out: list = []
    seen: set = set()
    for version in value if isinstance(value, list) else []:
        if not isinstance(version, dict):
            continue
        name = " ".join(str(version.get("name") or "").split())[:80]
        if not name or name.lower() in seen or name.lower() == "original":
            continue
        ingredients = [
            ing for ing in (normalize_ingredient(i) for i in ensure_list_field(version.get("ingredients")))
            if ing["name"].strip()
        ][:100]
        instructions = [
            str(s).strip()[:4000] for s in ensure_list_field(version.get("instructions")) if str(s or "").strip()
        ][:100]
        if not ingredients and not instructions:
            continue
        seen.add(name.lower())
        entry: Dict[str, Any] = {"name": name, "ingredients": ingredients, "instructions": instructions}
        notes = str(version.get("notes") or "").strip()[:2000]
        if notes:
            entry["notes"] = notes
        # Per-version macros (services/version_macros.py): numbers only, badges capped to the list.
        nutrition = normalize_macro_nutrition(version.get("nutrition"))
        if nutrition:
            entry["nutrition"] = nutrition
        badges = normalize_ingredient_macros(version.get("ingredient_macros"), len(ingredients))
        if badges:
            entry["ingredient_macros"] = badges
        lf = _normalize_macro_variant(version.get("low_fodmap_macros"), len(ingredients))
        if lf:
            entry["low_fodmap_macros"] = lf
        for sig_field in ("macros_sig", "ingredients_sig"):
            sig = _clean_sig(version.get(sig_field))
            if sig:
                entry[sig_field] = sig
        out.append(entry)
        if len(out) >= MAX_RECIPE_VERSIONS:
            break
    return out


CATEGORIES = ("Breakfast", "Lunch", "Dinner", "Dessert", "Appetizer", "Snack", "Beverage", "Sauce", "Meal Pack", "Other")
_CATEGORY_ALIASES = {
    "brunch": "Breakfast", "main course": "Dinner", "main": "Dinner", "mains": "Dinner", "main dish": "Dinner",
    "supper": "Dinner", "entree": "Dinner", "side": "Dinner", "side dish": "Dinner", "soup": "Lunch",
    "salad": "Lunch", "sandwich": "Lunch", "light meal": "Lunch", "baking": "Dessert", "cake": "Dessert",
    "pudding": "Dessert", "afternoon tea": "Dessert", "treat": "Dessert", "starter": "Appetizer",
    "starters": "Appetizer", "canape": "Appetizer", "canapes": "Appetizer", "appetiser": "Appetizer",
    "drink": "Beverage", "drinks": "Beverage", "cocktail": "Beverage", "smoothie": "Beverage",
    "condiment": "Sauce", "dip": "Sauce", "dressing": "Sauce", "snacks": "Snack", "desserts": "Dessert",
}


RECIPE_COLUMNS = frozenset({
    "id", "title", "description", "ingredients", "instructions", "prep_time", "cook_time", "servings",
    "category", "tags", "image_url", "video_url", "author_id", "household_id", "created_at", "updated_at",
    "source_url", "source_author", "source_type", "cookbook_id", "cookbook_page", "dietary_tags", "difficulty",
    "ingredient_macros", "last_cooked_at", "adaptations",
    "nutrition_calories", "nutrition_protein", "nutrition_carbs", "nutrition_fat",
    "nutrition_fiber", "nutrition_sugar", "nutrition_sodium",
})


def recipe_row_for_insert(recipe: Dict[str, Any]) -> Dict[str, Any]:
    """Shape an imported recipe dict for recipes.insert: flatten nutrition, coerce image_url to a
    string and drop keys that are not columns (old code sent is_favorite/times_cooked/
    current_version/imported_from, which made every save fail)."""
    row = dict(recipe)
    nutrition = row.pop("nutrition", None)
    if nutrition:
        row.update({k: v for k, v in nutrition_to_columns(nutrition).items() if v is not None})
    img = row.get("image_url")
    if isinstance(img, list):
        img = img[0] if img else ""
    if isinstance(img, dict):
        img = img.get("url") or img.get("contentUrl") or ""
    row["image_url"] = img if isinstance(img, str) else ""
    if row.get("category"):
        row["category"] = normalize_category(row["category"])
    if isinstance(row.get("ingredients"), list):
        row["ingredients"] = [normalize_ingredient(i) for i in row["ingredients"]]
    return {k: v for k, v in row.items() if k in RECIPE_COLUMNS}


def normalize_category(value: Any) -> str:
    """Website JSON-LD gives "Breakfast, Brunch, Main course"; Laro filters need one known category.
    Takes the first token that maps to a known category; unknown values become "Other"."""
    if isinstance(value, (list, tuple)):
        tokens = [str(v) for v in value]
    else:
        tokens = re.split(r"[,/|;]| & ", str(value or ""))
    for tok in tokens:
        t = tok.strip().lower()
        if not t:
            continue
        for c in CATEGORIES:
            if t == c.lower() or t == c.lower() + "s":
                return c
        if t in _CATEGORY_ALIASES:
            return _CATEGORY_ALIASES[t]
    return "Other"


def normalize_ingredient(item: Any) -> Dict[str, str]:
    """Coerce import/OCR ingredient shapes into Ingredient-safe dicts.

    Imported PDFs sometimes emit ``{"name": "...", "amount": null, "unit": null}``.
    RecipeResponse requires strings, and a single bad row used to 500 the
    entire GET /recipes list so "All" looked empty.
    """
    from utils.ingredient_groups import split_ingredient_group, with_group

    if isinstance(item, str):
        group, name = split_ingredient_group(item)
        out = {"name": name, "amount": "", "unit": ""}
        if group:
            out["group"] = group
        return out
    if not isinstance(item, dict):
        return {"name": "", "amount": "", "unit": ""}

    name = item.get("name")
    if name is None:
        name = item.get("item") or item.get("ingredient") or ""
    amount = item.get("amount")
    if amount is None and item.get("quantity") is not None:
        amount = item.get("quantity")
    unit = item.get("unit")

    # Section: an explicit ``group`` wins, else a legacy "Sauce: tahini" name prefix is split off.
    grouped = with_group({"name": name, "group": item.get("group"), "section": item.get("section")})
    group = grouped.get("group")
    out = _tidy_ingredient({
        "name": grouped["name"],
        "amount": "" if amount is None else str(amount),
        "unit": "" if unit is None else str(unit),
    })
    if group:
        out["group"] = group  # only when set: ungrouped lines keep their old shape
    return out


_PREP_UNITS = {
    "sliced", "chopped", "diced", "minced", "crushed", "grated", "peeled", "halved", "cubed",
    "shredded", "finely chopped", "roughly chopped", "thinly sliced", "beaten", "melted", "softened",
}
_METRIC_ALT = re.compile(r"^/\s*(\d+(?:\.\d+)?)\s*(g|kg|ml|l)\b\s*", re.I)


_FRACTION_LEAD = re.compile(r"^\s*([\u00bc-\u00be\u2150-\u215e]|\d+/\d+)\s+")
_SIMPLE_UNITS = {
    "lb", "lbs", "oz", "g", "kg", "ml", "l", "cup", "cups", "tbsp", "tsp", "tablespoon", "tablespoons",
    "teaspoon", "teaspoons", "pint", "pints", "can", "cans", "pound", "pounds", "ounce", "ounces",
}


def _tidy_ingredient(ing: Dict[str, str]) -> Dict[str, str]:
    """Cosmetic fixes for imported rows (safe, never drops words):
    - prep word used as the unit ("2", "sliced", "lemons") -> unit "" + name "lemons, sliced"
    - WPRM note artefacts: "garlic, (, minced)" -> "garlic, minced"; "onion (, chopped)" -> "onion (chopped)"
    - "1 lb / 500g beef mince": prefer the metric figure that's already there.
    """
    name, amount, unit = ing["name"], ing["amount"], ing["unit"]
    if unit.strip().lower() in _PREP_UNITS:
        name = f"{name.strip()}, {unit.strip().lower()}" if name.strip() else unit.strip()
        unit = ""
    if "(" in name:
        name = re.sub(r",\s*\(\s*,\s*([^()]*)\)", r", \1", name)
        name = re.sub(r"\(\s*,\s*", "(", name)
        name = re.sub(r"\(\s*\)", "", name)
    if unit.strip().lower() in ("lb", "lbs", "pound", "pounds", "oz", "ounce", "ounces"):
        m = _METRIC_ALT.match(name.strip())
        if m:
            amount, unit, name = m.group(1), m.group(2).lower(), name.strip()[m.end():]
    # "1" + "½ lb chicken": the fraction belongs to the amount, then the unit follows.
    m = _FRACTION_LEAD.match(name)
    if m and re.fullmatch(r"\d+", amount.strip()):
        amount = f"{amount.strip()} {m.group(1)}"
        name = name[m.end():]
        if not unit.strip():
            w = re.match(r"([A-Za-z]+)\.?\s+", name)
            if w and w.group(1).lower() in _SIMPLE_UNITS:
                unit, name = w.group(1), name[w.end():]
    # Some scrapers fill amount/unit but leave the whole line in name ("1", "", "1 large onion").
    amt = amount.strip()
    if amt and name.strip().startswith(amt + " "):
        rest = name.strip()[len(amt):].lstrip()
        u = unit.strip()
        if u and re.match(re.escape(u) + r"s?\b\.?\s+", rest, re.I):
            rest = re.sub(r"^" + re.escape(u) + r"s?\b\.?\s+", "", rest, flags=re.I)
        if rest:
            name = rest
    name = re.sub(r"\s{2,}", " ", name).strip()
    return {"name": name, "amount": amount, "unit": unit}


def prepare_recipe_for_response(
    row: Dict[str, Any],
    *,
    share_mode: bool = False,
    estimate_missing_nutrition: bool = True,
) -> Dict[str, Any]:
    """Shape a DB recipe row for RecipeResponse validation.

    When estimate_missing_nutrition is True (default), fill any missing core
    macros from the curated food DB so recipe detail / lists / share do not
    show blank nutrition for imported recipes.
    """
    from utils.upload_tokens import sign_upload_path, DEFAULT_TTL_SECONDS, SHARE_TTL_SECONDS

    data = dict(row)
    data["dietary_tags"] = ensure_list_field(data.get("dietary_tags"))
    data["tags"] = ensure_list_field(data.get("tags"))
    data["adaptations"] = normalize_adaptations(data.get("adaptations"))
    data["ingredients"] = [
        normalize_ingredient(item) for item in ensure_list_field(data.get("ingredients"))
    ]
    data["instructions"] = [
        "" if step is None else str(step)
        for step in ensure_list_field(data.get("instructions"))
    ]
    # Required string/int fields that imports sometimes leave null
    if data.get("description") is None:
        data["description"] = ""
    if data.get("image_url") is None:
        data["image_url"] = ""
    if data.get("category") is None:
        data["category"] = "Other"
    for int_field in ("prep_time", "cook_time", "servings"):
        if data.get(int_field) is None:
            data[int_field] = 0 if int_field != "servings" else 4

    nutrition = columns_to_nutrition(data)
    if estimate_missing_nutrition:
        nutrition = enrich_nutrition_from_ingredients(
            nutrition,
            data.get("ingredients") or [],
            servings=data.get("servings") or 1,
        )
        # Drop empty nutrition objects (all core macros still missing)
        if not any(nutrition.get(k) is not None for k in CORE_NUTRITION_KEYS):
            nutrition = None
        elif nutrition is not None:
            # Keep API payload tidy when nothing was estimated
            if not nutrition.get("nutrition_estimated"):
                nutrition.pop("nutrition_estimated", None)
                if nutrition.get("nutrition_source") in (None, "recipe"):
                    nutrition.pop("nutrition_source", None)
    if nutrition is not None and nutrition.get("carbs_total") is None:
        # US "Total carbs" (incl. fibre) from the stored line macros, when they all carry it.
        from utils.region import with_total_carbs

        badges = data.get("ingredient_macros")
        if isinstance(badges, str):
            try:
                badges = json.loads(badges)
            except (TypeError, ValueError):
                badges = None
        if isinstance(badges, list) and len(badges) == len(data.get("ingredients") or []):
            nutrition = with_total_carbs(nutrition, badges, data.get("servings") or 1)
    data["nutrition"] = nutrition

    # Per-100 g view for batch / base recipes (services/nutrition_basis.py): derived from the
    # stored line badges (grams) every time, inside ``adaptations`` so clients that cache the
    # adaptations JSON (Android Room) get it without a schema change.
    try:
        from services.nutrition_basis import attach_weight_fields

        badges = data.get("ingredient_macros")
        if isinstance(badges, str):
            try:
                badges = json.loads(badges)
            except (json.JSONDecodeError, TypeError):
                badges = None
        if not (isinstance(badges, list) and len(badges) == len(data["ingredients"]) and badges):
            badges = None
        data["adaptations"] = attach_weight_fields(data, data["adaptations"], badges)
    except Exception:  # never fail a recipe response over the per-100 g extras
        pass

    # Drop raw columns that are not part of the API model
    for col in NUTRITION_COLUMN_MAP.values():
        data.pop(col, None)
    # Sign local upload URLs for <img> without Bearer headers
    ttl = SHARE_TTL_SECONDS if share_mode else DEFAULT_TTL_SECONDS
    if data.get("image_url"):
        data["image_url"] = sign_upload_path(data["image_url"], ttl_seconds=ttl)
    return data
