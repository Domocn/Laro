"""Scale recipe ingredient rows for meal-plan / grocery generation."""
from __future__ import annotations

from typing import Any, Dict, List

from utils.ingredient_parse import format_scaled_amount, parse_amount_to_float


def scale_factor_for_servings(recipe_servings: int, target_servings: int) -> float:
    base = int(recipe_servings) if recipe_servings and int(recipe_servings) > 0 else 4
    target = int(target_servings) if target_servings and int(target_servings) > 0 else base
    return float(target) / float(base)


def scale_ingredient_row(ing: Any, factor: float) -> Dict[str, Any]:
    if isinstance(ing, str):
        return {"name": ing.strip(), "amount": "1", "unit": ""}
    row = dict(ing)
    parsed = parse_amount_to_float(row.get("amount", ""))
    if parsed is None or factor == 1.0:
        return row
    row["amount"] = format_scaled_amount(parsed * factor)
    return row


def ingredients_for_slot(recipe: dict, target_servings: int | None) -> List[Dict[str, Any]]:
    base = recipe.get("servings") or 4
    target = target_servings if target_servings else base
    factor = scale_factor_for_servings(base, target)
    out: List[Dict[str, Any]] = []
    for ing in recipe.get("ingredients") or []:
        if isinstance(ing, dict):
            name = (ing.get("name") or "").strip()
            if not name:
                continue
            scaled = scale_ingredient_row(ing, factor)
            out.append(scaled)
        elif isinstance(ing, str) and ing.strip():
            out.append(scale_ingredient_row(ing, factor))
    return out
