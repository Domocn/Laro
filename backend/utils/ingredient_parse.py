"""
Structured ingredient-line parsing via ingredient-parser-nlp + Pint.

Falls back to the existing regex parser in food_db so callers stay safe
when the NLP model is unavailable.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_UNIT_ALIASES = {
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "cup": "cup",
    "cups": "cup",
    "ounce": "oz",
    "ounces": "oz",
    "pound": "lb",
    "pounds": "lb",
    "gram": "g",
    "grams": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "milliliter": "ml",
    "millilitre": "ml",
    "milliliters": "ml",
    "millilitres": "ml",
    "liter": "l",
    "litre": "l",
    "liters": "l",
    "litres": "l",
    "pinch": "pinch",
    "clove": "clove",
    "cloves": "clove",
    "can": "can",
    "cans": "can",
    "package": "package",
    "packages": "package",
}


def _fraction_to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        from fractions import Fraction

        return float(Fraction(value))
    except Exception:
        try:
            return float(value)
        except Exception:
            return None


def _normalize_unit(unit: Any) -> str:
    if unit is None:
        return ""
    text = str(unit).strip().lower()
    if not text:
        return ""
    # Pint Unit string often looks like "cup" / "teaspoon"
    text = text.replace(".", "")
    return _UNIT_ALIASES.get(text, text)


def _oss_parse(line: str) -> Optional[Dict[str, Any]]:
    try:
        from ingredient_parser import parse_ingredient
    except Exception as e:
        logger.debug("ingredient-parser unavailable: %s", e)
        return None

    try:
        parsed = parse_ingredient(line)
    except Exception as e:
        logger.debug("ingredient-parser failed for %r: %s", line[:80], e)
        return None

    name = ""
    names = getattr(parsed, "name", None) or []
    if names:
        name = getattr(names[0], "text", None) or str(names[0])
    name = (name or "").strip()

    amount = ""
    unit = ""
    amounts = getattr(parsed, "amount", None) or []
    if amounts:
        first = amounts[0]
        qty = _fraction_to_float(getattr(first, "quantity", None))
        if qty is not None:
            # Prefer compact display (2 vs 2.0)
            amount = str(int(qty)) if float(qty).is_integer() else str(round(qty, 3)).rstrip("0").rstrip(".")
        unit = _normalize_unit(getattr(first, "unit", None))

    preparation = getattr(parsed, "preparation", None)
    prep_text = ""
    if preparation is not None:
        prep_text = getattr(preparation, "text", None) or str(preparation)
        prep_text = prep_text.strip()
    if prep_text and name and prep_text.lower() not in name.lower():
        name = f"{name}, {prep_text}"

    if not name and not amount:
        return None
    return {
        "amount": amount,
        "unit": unit,
        "name": name or line.strip(),
        "quantity": _fraction_to_float(amount) if amount else None,
        "parser": "ingredient-parser-nlp",
    }


def _legacy_parse(line: str) -> Dict[str, Any]:
    from utils.food_db import parse_ingredient_amount

    legacy = parse_ingredient_amount(line)
    qty = legacy.get("quantity")
    unit = legacy.get("unit") or ""
    name = legacy.get("name") or line.strip()
    amount = ""
    if qty is not None:
        amount = str(int(qty)) if float(qty).is_integer() else str(qty)
    return {
        "amount": amount,
        "unit": unit,
        "name": name,
        "quantity": qty,
        "parser": "legacy",
    }


def parse_ingredient_line(line: str) -> Dict[str, Any]:
    """
    Parse a free-text ingredient line into amount / unit / name.

    Prefer ingredient-parser-nlp; fall back to food_db regex parser.
    """
    text = (line or "").strip()
    if not text:
        return {"amount": "", "unit": "", "name": "", "quantity": None, "parser": "empty"}

    # Skip obvious section headers
    if text.endswith(":") and len(text) < 40:
        return {"amount": "", "unit": "", "name": text, "quantity": None, "parser": "header"}

    oss = _oss_parse(text)
    if oss and oss.get("name"):
        return oss
    return _legacy_parse(text)


def grams_from_amount(quantity: Optional[float], unit: Optional[str], food_name: str = "") -> Optional[float]:
    """
    Convert quantity+unit to grams using food_db table first, then Pint.
    """
    if quantity is None:
        return None
    unit_l = (unit or "").strip().lower()
    if not unit_l:
        # Count-like: treat as 100g portions for nutrition estimates
        return float(quantity) * 100.0

    from utils.food_db import UNIT_CONVERSIONS

    if unit_l in UNIT_CONVERSIONS:
        return float(quantity) * float(UNIT_CONVERSIONS[unit_l])
    singular = unit_l.rstrip("s")
    if singular in UNIT_CONVERSIONS:
        return float(quantity) * float(UNIT_CONVERSIONS[singular])

    try:
        from pint import UnitRegistry

        ureg = UnitRegistry()
        q = quantity * ureg(unit_l)
        # Volume → assume water density when mass unknown (conservative pantry estimate)
        if q.dimensionality == ureg.gram.dimensionality:
            return float(q.to(ureg.gram).magnitude)
        if q.check("[volume]"):
            return float(q.to(ureg.milliliter).magnitude)  # ~1g/ml
    except Exception:
        pass
    return None
