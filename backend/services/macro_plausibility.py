"""
Sanity checks for line macros and per-serving totals (used by the backfill report).

Flags, never fixes: a flagged line still counts towards the total, it is just listed so a
person can look at it.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

MAX_KCAL_PER_GRAM = 9.5  # pure fat is ~9 kcal/g; anything above is impossible
VAGUE_MAX_KCAL = 200
SERVING_MAX_KCAL = 2000
SERVING_MIN_KCAL = 20

_VAGUE = re.compile(
    r"\b(drizzle|splash|dash|pinch|handful|sprinkle|knob|to taste|as needed|for serving|for garnish|optional|some|a little)\b",
    re.I,
)
_NUMBER = re.compile(r"(\d+(?:[.,]\d+)?|\d+\s*/\s*\d+|[½¼¾⅓⅔⅛])")
_MASS = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kg|kilograms?|g|grams?|gr|ml|millilit(?:er|re)s?|l|lit(?:er|re)s?)\b",
    re.I,
)
_TO_GRAMS = {"kg": 1000.0, "kilogram": 1000.0, "g": 1.0, "gram": 1.0, "gr": 1.0, "ml": 1.0,
             "milliliter": 1.0, "millilitre": 1.0, "l": 1000.0, "liter": 1000.0, "litre": 1000.0}

# Real foods with real calories: 0 kcal at a real quantity means the estimate went wrong.
CALORIC_FOODS = (
    "tofu", "tempeh", "rice", "pasta", "spaghetti", "noodle", "flour", "sugar", "honey", "syrup",
    "oil", "butter", "ghee", "nut", "almond", "cashew", "peanut", "walnut", "seed", "cheese",
    "parmesan", "feta", "cream", "milk", "yoghurt", "yogurt", "chocolate", "cocoa", "oat", "bread",
    "egg", "chicken", "beef", "pork", "lamb", "salmon", "fish", "bean", "lentil", "chickpea",
    "potato", "avocado", "coconut", "quinoa", "couscous", "tortilla", "mayonnaise", "pesto",
)
# Names that contain a caloric word but are ~0 kcal themselves.
_ZERO_OK = re.compile(r"\b(water|stock cube|spray|cooking spray|zest|extract|essence)\b", re.I)
# "Carrot Smoked Salmon: 1 tsp salt" - the words before the colon name a section, not the food.
_SECTION_PREFIX = re.compile(r"^\s*[^:\d]{1,60}:\s+")
# "vegetarian chicken stock powder", "vegan fish sauce": the animal word is not the food.
_NOT_THE_ANIMAL = re.compile(
    r"\b(?:vegetarian|vegan|plant[- ]based|meat[- ]free|meatless|dairy[- ]free|mock|faux)\s+"
    r"(?:chicken|beef|pork|lamb|salmon|fish|egg)\b",  # not "vegan butter": that is still fat
    re.I,
)
# "chicken stock powder", "beef flavour", "vegetable bouillon": a flavouring, ~0 at recipe amounts.
_FLAVOURING = re.compile(
    r"\b[\w-]+\s+(?:stock|broth|bouillon|flavou?r(?:ing)?|seasoning)(?:\s+(?:powder|cubes?|pots?|granules|paste))?\b"
    r"|\b(?:stock|bouillon)\s+(?:powder|cubes?|pots?|granules)\b",
    re.I,
)
SMALL_AMOUNT_G = 15.0  # <= 1 tbsp / 15 g / 15 ml: vinegar, salt, tamari, dried herbs round to ~0
_SPOON_ML = {"tsp": 5.0, "teaspoon": 5.0, "tbsp": 15.0, "tablespoon": 15.0, "cup": 240.0}
# A yield of one whole item ("Makes 1 loaf") saved as servings=1: word in the title -> item name.
_WHOLE_ITEMS = (
    (re.compile(r"\b(loaf|loaves|bread|shokupan|focaccia|brioche|babka|stollen)\b", re.I), "loaf"),
    (re.compile(r"\b(cake|cheesecake|gateau)\b", re.I), "cake"),
    (re.compile(r"\b(traybake|tray ?bake|tray|brownies?|blondies?|flapjacks?|slice tin)\b", re.I), "tray"),
    (re.compile(r"\b(tart|pie|quiche)\b", re.I), "tart / pie"),
    (re.compile(r"\b(batch)\b", re.I), "batch"),
)


def grams_in(line: str) -> Optional[float]:
    """Weight / volume written in the line, in grams (ml counted as g); None if not stated."""
    m = _MASS.search(line or "")
    if not m:
        return None
    unit = m.group(2).lower().rstrip("s")
    factor = _TO_GRAMS.get(unit) or _TO_GRAMS.get(unit.replace("re", "er"))
    if factor is None:
        return None
    try:
        return float(m.group(1).replace(",", ".")) * factor
    except ValueError:
        return None


def is_vague(line: str) -> bool:
    """A line whose amount is a word ('drizzle', 'to taste') rather than a number."""
    text = line or ""
    return bool(_VAGUE.search(text)) and not _NUMBER.search(text)


def _has_quantity(line: str) -> bool:
    return bool(_NUMBER.search(line or "")) and not _VAGUE.search(line or "")


def food_part(line: str) -> str:
    """The line without a 'Section:' prefix."""
    return _SECTION_PREFIX.sub("", line or "", count=1)


def amount_grams(line: str) -> Optional[float]:
    """Stated amount in grams-ish (g / ml / spoons / cups); None for counts or no amount."""
    from services.line_macros import _clean_text
    from utils.food_db import parse_ingredient_amount

    text = food_part(line)
    grams = grams_in(text)
    if grams is not None:
        return grams
    parsed = parse_ingredient_amount(_clean_text(text))
    qty, unit = parsed.get("quantity"), (parsed.get("unit") or "").lower()
    if qty is None:
        return None
    for key, ml in _SPOON_ML.items():
        if unit in (key, key + "s"):
            return float(qty) * ml
    return None


def _caloric_food(line: str) -> Optional[str]:
    low = food_part(line).lower()
    if _ZERO_OK.search(low):
        return None
    low = _FLAVOURING.sub(" ", _NOT_THE_ANIMAL.sub(" ", low))
    for food in CALORIC_FOODS:
        if re.search(rf"\b{re.escape(food)}", low):
            return food
    return None


def check_line(line: str, badge: Optional[Dict[str, Any]]) -> List[str]:
    """Reasons this line's macros look wrong (empty when plausible)."""
    if not badge:
        return []
    try:
        kcal = float(badge.get("cal") or 0)
    except (TypeError, ValueError):
        kcal = 0.0
    reasons: List[str] = []
    grams = grams_in(line)
    if grams and grams > 0 and kcal / grams > MAX_KCAL_PER_GRAM:
        reasons.append(f"{kcal:.0f} kcal for {grams:g} g is more than {MAX_KCAL_PER_GRAM} kcal/g")
    if is_vague(line) and kcal > VAGUE_MAX_KCAL:
        reasons.append(f"vague amount estimated at {kcal:.0f} kcal (over {VAGUE_MAX_KCAL})")
    food = _caloric_food(line)
    if kcal == 0 and food and _has_quantity(food_part(line)):
        amount = amount_grams(line)
        if amount is None or amount > SMALL_AMOUNT_G:
            reasons.append(f"0 kcal for a real quantity of {food}")
    return reasons


def whole_item_yield(recipe: Optional[Dict[str, Any]]) -> Optional[str]:
    """'loaf' / 'cake' / 'tray' ... when servings=1 looks like a yield of one whole item."""
    if not recipe:
        return None
    try:
        servings = int(recipe.get("servings") or 1)
    except (TypeError, ValueError):
        servings = 1
    if servings > 1:
        return None
    text = " ".join(str(recipe.get(k) or "") for k in ("yield", "recipe_yield", "title", "category"))
    for rx, item in _WHOLE_ITEMS:
        if rx.search(text):
            return item
    return None


def check_totals(per_serving: Optional[Dict[str, Any]], recipe: Optional[Dict[str, Any]] = None) -> List[str]:
    """Per-serving total sanity. Given the ``recipe``, an over-limit total on a servings=1 loaf /
    cake / tray says to set a slice count (servings is never changed here)."""
    if not per_serving or per_serving.get("calories") is None:
        return []
    kcal = float(per_serving["calories"])
    if kcal > SERVING_MAX_KCAL:
        item = whole_item_yield(recipe)
        if item:
            return [f"{kcal:.0f} kcal per serving: servings looks like a whole {item} - set a slice count"]
        return [f"{kcal:.0f} kcal per serving is over {SERVING_MAX_KCAL}"]
    if kcal < SERVING_MIN_KCAL:
        return [f"{kcal:.0f} kcal per serving is under {SERVING_MIN_KCAL}"]
    return []
