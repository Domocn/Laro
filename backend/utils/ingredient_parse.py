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


_UNICODE_FRACTIONS = {
    "½": 0.5,
    "⅓": 1 / 3,
    "⅔": 2 / 3,
    "¼": 0.25,
    "¾": 0.75,
    "⅕": 0.2,
    "⅖": 0.4,
    "⅗": 0.6,
    "⅘": 0.8,
    "⅙": 1 / 6,
    "⅚": 5 / 6,
    "⅛": 0.125,
    "⅜": 0.375,
    "⅝": 0.625,
    "⅞": 0.875,
}


def parse_amount_to_float(amount: Any) -> Optional[float]:
    """Parse ingredient amount strings (1 1/2, ½, 0.5) to a float."""
    if amount is None:
        return None
    raw = str(amount).strip()
    if not raw:
        return None
    if raw in _UNICODE_FRACTIONS:
        return _UNICODE_FRACTIONS[raw]
    text = raw.replace(",", ".")
    for char, val in _UNICODE_FRACTIONS.items():
        if char in text:
            text = text.replace(char, f" {val} ")
    text = re.sub(r"\s+", " ", text).strip()

    mixed = re.match(r"^(\d+)\s+(\d+)\s*/\s*(\d+)$", text)
    if mixed:
        return float(mixed.group(1)) + float(mixed.group(2)) / float(mixed.group(3))

    frac = re.match(r"^(\d+)\s*/\s*(\d+)$", text)
    if frac:
        return float(frac.group(1)) / float(frac.group(2))

    parsed = _fraction_to_float(text)
    if parsed is not None:
        return parsed
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def format_scaled_amount(value: float) -> str:
    rounded = round(float(value) * 1000) / 1000
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    text = f"{rounded:.3f}".rstrip("0").rstrip(".")
    return text


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
    Convert quantity+unit to grams using food_db piece weights / unit table, then Pint.
    """
    if quantity is None:
        return None

    from utils.food_db import grams_from_parsed

    parsed = {
        "quantity": float(quantity),
        "unit": (unit or "").strip().lower() or None,
        "name": food_name or "",
    }
    grams = grams_from_parsed(parsed, food_name=food_name)
    if grams is not None and grams > 0:
        return float(grams)

    unit_l = (unit or "").strip().lower()
    if not unit_l:
        return float(quantity) * 100.0

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
