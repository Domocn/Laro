"""
Helpers for mapping recipe API fields to/from the PostgreSQL schema.

The API exposes a nested `nutrition` object; the DB stores flat
`nutrition_*` columns. `dietary_tags` is JSON text in the DB.
"""
from __future__ import annotations

import json
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


def normalize_ingredient(item: Any) -> Dict[str, str]:
    """Coerce import/OCR ingredient shapes into Ingredient-safe dicts.

    Imported PDFs sometimes emit ``{"name": "...", "amount": null, "unit": null}``.
    RecipeResponse requires strings, and a single bad row used to 500 the
    entire GET /recipes list so "All" looked empty.
    """
    if isinstance(item, str):
        return {"name": item, "amount": "", "unit": ""}
    if not isinstance(item, dict):
        return {"name": "", "amount": "", "unit": ""}

    name = item.get("name")
    if name is None:
        name = item.get("item") or item.get("ingredient") or ""
    amount = item.get("amount")
    if amount is None and item.get("quantity") is not None:
        amount = item.get("quantity")
    unit = item.get("unit")

    return {
        "name": "" if name is None else str(name),
        "amount": "" if amount is None else str(amount),
        "unit": "" if unit is None else str(unit),
    }


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
    data["nutrition"] = nutrition

    # Drop raw columns that are not part of the API model
    for col in NUTRITION_COLUMN_MAP.values():
        data.pop(col, None)
    # Sign local upload URLs for <img> without Bearer headers
    ttl = SHARE_TTL_SECONDS if share_mode else DEFAULT_TTL_SECONDS
    if data.get("image_url"):
        data["image_url"] = sign_upload_path(data["image_url"], ttl_seconds=ttl)
    return data
