"""Enrich cook steps with ingredient amounts for display / speech.

Matching is fuzzy so list names like "White potatoes" still match step text
that says "the potatoes".
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

_NOISE_WORDS = {
    "fresh",
    "dried",
    "ground",
    "chopped",
    "minced",
    "sliced",
    "diced",
    "large",
    "small",
    "medium",
    "extra",
    "virgin",
    "organic",
    "raw",
    "cooked",
    "boneless",
    "skinless",
    "white",
    "black",
    "red",
    "green",
    "yellow",
    "brown",
    "whole",
    "plain",
    "unsalted",
    "salted",
    "light",
    "dark",
    "sweet",
    "hot",
    "cold",
    "warm",
    "olive",
    "vegetable",
    "canola",
    "coconut",
    "free",
    "range",
    "low",
    "fat",
    "lean",
    "thick",
    "thin",
    "fine",
    "coarse",
    "baby",
    "ripe",
    "frozen",
    "canned",
    "jarred",
    "packed",
    "of",
    "and",
    "or",
    "the",
    "a",
    "an",
    "to",
    "for",
    "with",
}


def _quantity_label(ing: Dict[str, Any]) -> str:
    amount = str(ing.get("amount") or "").strip()
    unit = str(ing.get("unit") or "").strip()
    return f"{amount} {unit}".strip()


def _singularize(token: str) -> str:
    w = (token or "").lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes") and len(w) > 4:
        return w[:-2]
    if w.endswith("ves") and len(w) > 4:
        stem = w[:-3]
        if stem.endswith(("l", "r", "a")):
            return stem + "f"
        return stem + "fe"
    if w.endswith(("ses", "xes", "zes", "ches", "shes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _pluralize(token: str) -> str:
    w = (token or "").lower()
    # Already plural / ends with s — leave alone
    if w.endswith("s"):
        return w
    if w.endswith("y") and len(w) > 2 and not re.search(r"[aeiou]y$", w):
        return w[:-1] + "ies"
    if w.endswith("o") and not w.endswith("oo"):
        return w + "es"
    if w.endswith(("x", "z", "ch", "sh")):
        return w + "es"
    if w.endswith("f"):
        return w[:-1] + "ves"
    if w.endswith("fe"):
        return w[:-2] + "ves"
    return w + "s"


def _significant_tokens(name: str) -> List[str]:
    cleaned = re.sub(r"[()]", " ", (name or "").lower())
    return [
        t
        for t in re.split(r"[\s,/]+", cleaned)
        if t and len(t) > 1 and t not in _NOISE_WORDS
    ]


def name_variants(name: str, unit: str = "") -> List[str]:
    """Candidate phrases to look for in step text, longest first."""
    raw = (name or "").strip().lower()
    if not raw:
        return []

    variants: Set[str] = {raw}

    if "," in raw:
        for part in raw.split(","):
            cleaned = part.strip()
            if cleaned and cleaned != raw:
                variants.update(name_variants(cleaned, unit))

    tokens = _significant_tokens(raw)
    if tokens:
        variants.add(" ".join(tokens))
        last = tokens[-1]
        first = tokens[0]
        last_sing = _singularize(last)
        last_plur = _pluralize(last_sing)
        first_sing = _singularize(first)
        variants.update(
            {
                last,
                first,
                last_sing,
                last_plur,
                first_sing,
                _pluralize(first_sing),
            }
        )
        unit_lower = (unit or "").lower()
        if re.search(r"leaves?", unit_lower) or re.search(r"leaves?", raw):
            variants.update(
                {
                    f"{last} leaves",
                    f"{last_sing} leaves",
                    f"{last_plur} leaves",
                }
            )
        if len(tokens) >= 2:
            variants.add(" ".join(tokens[-2:]))

    return sorted(
        (v.strip() for v in variants if len(v.strip()) >= 3),
        key=len,
        reverse=True,
    )


def enrich_step_with_amounts(step: str, ingredients: Optional[List[Any]]) -> str:
    """
    Insert quantities into a step when an ingredient name appears without
    a nearby amount. Example: "chop the potatoes" + 500g → "chop the 500 g potatoes".
    """
    if not step or not ingredients:
        return step or ""

    usable: List[Dict[str, Any]] = []
    for ing in ingredients:
        if isinstance(ing, dict) and ing.get("name") and (ing.get("amount") or ing.get("unit")):
            usable.append(ing)

    needles: List[Dict[str, str]] = []
    for ing in usable:
        name = str(ing.get("name") or "").strip()
        qty = _quantity_label(ing)
        if not name or not qty:
            continue
        for variant in name_variants(name, str(ing.get("unit") or "")):
            needles.append({"variant": variant, "qty": qty, "full_name": name})

    needles.sort(key=lambda n: len(n["variant"]), reverse=True)

    result = step
    injected: Set[str] = set()

    for needle in needles:
        full_name = needle["full_name"]
        if full_name in injected:
            continue

        variant = needle["variant"]
        qty = needle["qty"]
        escaped_variant = re.escape(variant)
        escaped_qty = re.escape(qty)

        if re.search(rf"(?i){escaped_qty}\s+{escaped_variant}\b", result):
            injected.add(full_name)
            continue

        match = re.search(rf"(?i)\b({escaped_variant})\b", result)
        if not match:
            continue

        before = result[max(0, match.start() - 28) : match.start()]
        if re.search(
            r"\d[\d./]*\s*(?:g|kg|ml|l|oz|lb|tsp|tbsp|cups?|cloves?|leaves?)?\s*$",
            before,
            re.IGNORECASE,
        ):
            injected.add(full_name)
            continue

        # Avoid "8 leaves sage leaves" when qty unit already ends the matched phrase
        insert_qty = qty
        qty_parts = qty.strip().split()
        matched_parts = match.group(1).strip().split()
        if (
            len(qty_parts) >= 2
            and len(matched_parts) >= 2
            and qty_parts[-1].lower() == matched_parts[-1].lower()
        ):
            insert_qty = " ".join(qty_parts[:-1])

        result = f"{result[: match.start()]}{insert_qty} {match.group(1)}{result[match.end() :]}"
        injected.add(full_name)

    return re.sub(r"\s+", " ", result).strip()


def enrich_steps(steps: List[str], ingredients: Optional[List[Any]]) -> List[str]:
    return [enrich_step_with_amounts(s, ingredients) for s in steps]
