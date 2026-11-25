"""
Which ingredients a planned meal actually needs: the chosen named version of a recipe
(``adaptations.versions``) with Low FODMAP swaps applied when asked.

Mirrors ``src/lib/recipeVersions.js`` + ``src/lib/fodmap.js`` so the shopping list matches
what the recipe page shows.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from utils.recipe_fields import ensure_list_field, normalize_adaptations


def clean_version_name(name: Any) -> Optional[str]:
    """Trimmed version name, or None for Original / blank."""
    text = " ".join(str(name or "").split())[:80]
    if not text or text.lower() == "original":
        return None
    return text


def find_version(recipe: Dict[str, Any], name: Any) -> Optional[Dict[str, Any]]:
    key = (clean_version_name(name) or "").lower()
    if not key:
        return None
    adaptations = normalize_adaptations((recipe or {}).get("adaptations")) or {}
    return next((v for v in adaptations.get("versions") or [] if v["name"].lower() == key), None)


def find_swap(name: Any, swaps: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """First swap whose ``from`` appears in the ingredient name (longest match wins)."""
    n = str(name or "").lower()
    if not n:
        return None
    best = None
    for swap in swaps or []:
        src = str(swap.get("from") or "").strip().lower()
        if src and src in n and (best is None or len(src) > len(best["from"].strip())):
            best = swap
    return best


def ingredients_for_choice(
    recipe: Dict[str, Any], version: Any = None, low_fodmap: bool = False
) -> List[Any]:
    """The recipe's ingredients for a version (unknown names fall back to Original),
    with Low FODMAP swaps applied (swapped name replaces the original) when ``low_fodmap``."""
    chosen = find_version(recipe, version)
    ingredients = list(chosen["ingredients"] if chosen else ensure_list_field((recipe or {}).get("ingredients")))
    if not low_fodmap:
        return ingredients
    adaptations = normalize_adaptations((recipe or {}).get("adaptations")) or {}
    swaps = (adaptations.get("low_fodmap") or {}).get("swaps") or []
    if not swaps:
        return ingredients
    out: List[Any] = []
    for ing in ingredients:
        name = ing if isinstance(ing, str) else (ing or {}).get("name")
        swap = find_swap(name, swaps)
        if not swap:
            out.append(ing)
        elif isinstance(ing, str):
            out.append(swap["to"])
        else:
            out.append({**ing, "name": swap["to"]})
    return out


def choice_label(title: str, version: Any = None, low_fodmap: bool = False) -> str:
    """"Pesto Pasta · Pomegranate · Low FODMAP" (just the title for Original)."""
    parts = [title or "Recipe"]
    name = clean_version_name(version)
    if name:
        parts.append(name)
    if low_fodmap:
        parts.append("Low FODMAP")
    return " · ".join(parts)
