"""
Curated food composition DB for AI recipe ideas grounded in real macros.

Pragmatic MVP: a small in-repo table (per 100g) focused on high-protein foods
plus common pantry staples — not a multi-GB USDA dump. Values are approximate
food-composition averages for meal planning / idea generation, not medical advice.

Used to:
- Retrieve allowed building blocks (high protein + pantry overlap + preferred)
- Inject macros into AI prompts
- Estimate recipe nutrition from DB foods when possible
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Defaults when high-protein is on but user has not set targets
# ---------------------------------------------------------------------------
DEFAULT_PROTEIN_G_HIGH_PROTEIN = 140
DEFAULT_CALORIES_HIGH_PROTEIN = 2200
DEFAULT_PROTEIN_G = 100
DEFAULT_CALORIES = 2000
DEFAULT_MEALS_PER_DAY = 4
MIN_PROTEIN_PER_MEAL_G = 25

# Protein density threshold (g per 100g) to flag "high protein" foods
HIGH_PROTEIN_THRESHOLD = 10.0

# ---------------------------------------------------------------------------
# Food table: name -> macros per 100g + metadata
# Source: typical food-composition averages (USDA FDC / common tables).
# ---------------------------------------------------------------------------

FoodEntry = Dict[str, Any]

FOOD_DATABASE: Dict[str, FoodEntry] = {
    # --- High-protein anchors ---
    "chicken breast": {
        "calories": 165, "protein": 31, "carbs": 0, "fat": 3.6, "fiber": 0,
        "tags": ["high-protein", "meat", "poultry"], "category": "protein",
    },
    "chicken thigh": {
        "calories": 209, "protein": 26, "carbs": 0, "fat": 10.9, "fiber": 0,
        "tags": ["high-protein", "meat", "poultry"], "category": "protein",
    },
    "turkey breast": {
        "calories": 135, "protein": 30, "carbs": 0, "fat": 1, "fiber": 0,
        "tags": ["high-protein", "meat", "poultry"], "category": "protein",
    },
    "lean ground turkey": {
        "calories": 176, "protein": 27, "carbs": 0, "fat": 8, "fiber": 0,
        "tags": ["high-protein", "meat", "poultry"], "category": "protein",
    },
    "beef": {
        "calories": 250, "protein": 26, "carbs": 0, "fat": 15, "fiber": 0,
        "tags": ["high-protein", "meat"], "category": "protein",
    },
    "lean beef mince": {
        "calories": 176, "protein": 26, "carbs": 0, "fat": 8, "fiber": 0,
        "tags": ["high-protein", "meat"], "category": "protein",
    },
    "ground beef": {
        "calories": 254, "protein": 17, "carbs": 0, "fat": 20, "fiber": 0,
        "tags": ["meat"], "category": "protein",
    },
    "pork loin": {
        "calories": 143, "protein": 26, "carbs": 0, "fat": 3.5, "fiber": 0,
        "tags": ["high-protein", "meat"], "category": "protein",
    },
    "pork": {
        "calories": 242, "protein": 27, "carbs": 0, "fat": 14, "fiber": 0,
        "tags": ["high-protein", "meat"], "category": "protein",
    },
    "salmon": {
        "calories": 208, "protein": 20, "carbs": 0, "fat": 13, "fiber": 0,
        "tags": ["high-protein", "fish"], "category": "protein",
    },
    "cod": {
        "calories": 82, "protein": 18, "carbs": 0, "fat": 0.7, "fiber": 0,
        "tags": ["high-protein", "fish"], "category": "protein",
    },
    "tuna": {
        "calories": 132, "protein": 29, "carbs": 0, "fat": 1, "fiber": 0,
        "tags": ["high-protein", "fish"], "category": "protein",
    },
    "canned tuna": {
        "calories": 116, "protein": 26, "carbs": 0, "fat": 1, "fiber": 0,
        "tags": ["high-protein", "fish", "pantry"], "category": "protein",
    },
    "shrimp": {
        "calories": 99, "protein": 24, "carbs": 0.2, "fat": 0.3, "fiber": 0,
        "tags": ["high-protein", "seafood"], "category": "protein",
    },
    "egg": {
        "calories": 155, "protein": 13, "carbs": 1.1, "fat": 11, "fiber": 0,
        "tags": ["high-protein", "egg"], "category": "protein",
    },
    "egg whites": {
        "calories": 52, "protein": 11, "carbs": 0.7, "fat": 0.2, "fiber": 0,
        "tags": ["high-protein", "egg"], "category": "protein",
    },
    "tofu": {
        "calories": 76, "protein": 8, "carbs": 1.9, "fat": 4.8, "fiber": 0.3,
        "tags": ["vegetarian", "vegan", "soy"], "category": "protein",
    },
    "firm tofu": {
        "calories": 144, "protein": 17, "carbs": 2.8, "fat": 8.7, "fiber": 2.3,
        "tags": ["high-protein", "vegetarian", "vegan", "soy"], "category": "protein",
    },
    "tempeh": {
        "calories": 193, "protein": 19, "carbs": 9, "fat": 11, "fiber": 0,
        "tags": ["high-protein", "vegetarian", "vegan", "soy"], "category": "protein",
    },
    "edamame": {
        "calories": 121, "protein": 12, "carbs": 9, "fat": 5, "fiber": 5,
        "tags": ["high-protein", "vegetarian", "vegan", "soy"], "category": "protein",
    },
    "seitan": {
        "calories": 370, "protein": 75, "carbs": 14, "fat": 1.9, "fiber": 0.6,
        "tags": ["high-protein", "vegetarian", "wheat"], "category": "protein",
    },
    "greek yogurt": {
        "calories": 97, "protein": 9, "carbs": 3.6, "fat": 5, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "greek yoghurt": {
        "calories": 97, "protein": 9, "carbs": 3.6, "fat": 5, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "nonfat greek yogurt": {
        "calories": 59, "protein": 10, "carbs": 3.6, "fat": 0.4, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "skyr": {
        "calories": 63, "protein": 11, "carbs": 4, "fat": 0.2, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "cottage cheese": {
        "calories": 98, "protein": 11, "carbs": 3.4, "fat": 4.3, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "low-fat cottage cheese": {
        "calories": 72, "protein": 12, "carbs": 2.7, "fat": 1, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "quark": {
        "calories": 71, "protein": 12, "carbs": 4, "fat": 0.3, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "whey protein powder": {
        "calories": 400, "protein": 80, "carbs": 8, "fat": 5, "fiber": 0,
        "tags": ["high-protein", "supplement", "dairy"], "category": "supplement",
    },
    "casein protein powder": {
        "calories": 370, "protein": 78, "carbs": 6, "fat": 1.5, "fiber": 0,
        "tags": ["high-protein", "supplement", "dairy"], "category": "supplement",
    },
    "pea protein powder": {
        "calories": 380, "protein": 75, "carbs": 6, "fat": 5, "fiber": 2,
        "tags": ["high-protein", "supplement", "vegan", "vegetarian"], "category": "supplement",
    },
    "lentils": {
        "calories": 116, "protein": 9, "carbs": 20, "fat": 0.4, "fiber": 7.9,
        "tags": ["vegetarian", "vegan", "legume", "pantry"], "category": "legume",
    },
    "chickpeas": {
        "calories": 164, "protein": 8.9, "carbs": 27, "fat": 2.6, "fiber": 7.6,
        "tags": ["vegetarian", "vegan", "legume", "pantry"], "category": "legume",
    },
    "black beans": {
        "calories": 132, "protein": 8.9, "carbs": 24, "fat": 0.5, "fiber": 8.7,
        "tags": ["vegetarian", "vegan", "legume", "pantry"], "category": "legume",
    },
    "kidney beans": {
        "calories": 127, "protein": 8.7, "carbs": 23, "fat": 0.5, "fiber": 6.4,
        "tags": ["vegetarian", "vegan", "legume", "pantry"], "category": "legume",
    },
    "beans": {
        "calories": 127, "protein": 8.7, "carbs": 22, "fat": 0.5, "fiber": 6.4,
        "tags": ["vegetarian", "vegan", "legume", "pantry"], "category": "legume",
    },
    "peas": {
        "calories": 81, "protein": 5.4, "carbs": 14, "fat": 0.4, "fiber": 5.1,
        "tags": ["vegetarian", "vegan", "legume"], "category": "vegetable",
    },

    # --- Dairy / staples ---
    "milk": {
        "calories": 42, "protein": 3.4, "carbs": 5, "fat": 1, "fiber": 0,
        "tags": ["dairy", "vegetarian"], "category": "dairy",
    },
    "skim milk": {
        "calories": 34, "protein": 3.4, "carbs": 5, "fat": 0.1, "fiber": 0,
        "tags": ["dairy", "vegetarian"], "category": "dairy",
    },
    "cheese": {
        "calories": 402, "protein": 25, "carbs": 1.3, "fat": 33, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "cheddar": {
        "calories": 403, "protein": 25, "carbs": 1.3, "fat": 33, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "mozzarella": {
        "calories": 280, "protein": 28, "carbs": 3.1, "fat": 17, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "feta": {
        "calories": 264, "protein": 14, "carbs": 4.1, "fat": 21, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "parmesan": {
        "calories": 431, "protein": 38, "carbs": 4.1, "fat": 29, "fiber": 0,
        "tags": ["high-protein", "dairy", "vegetarian"], "category": "dairy",
    },
    "yogurt": {
        "calories": 59, "protein": 10, "carbs": 3.6, "fat": 0.7, "fiber": 0,
        "tags": ["dairy", "vegetarian"], "category": "dairy",
    },
    "yoghurt": {
        "calories": 59, "protein": 10, "carbs": 3.6, "fat": 0.7, "fiber": 0,
        "tags": ["dairy", "vegetarian"], "category": "dairy",
    },
    "butter": {
        "calories": 717, "protein": 0.9, "carbs": 0.1, "fat": 81, "fiber": 0,
        "tags": ["dairy"], "category": "fat",
    },
    "cream": {
        "calories": 340, "protein": 2.1, "carbs": 2.8, "fat": 36, "fiber": 0,
        "tags": ["dairy"], "category": "dairy",
    },

    # --- Grains ---
    "rice": {
        "calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3, "fiber": 0.4,
        "tags": ["grain", "pantry", "vegan", "vegetarian"], "category": "grain",
    },
    "brown rice": {
        "calories": 112, "protein": 2.6, "carbs": 24, "fat": 0.9, "fiber": 1.8,
        "tags": ["grain", "pantry", "vegan", "vegetarian"], "category": "grain",
    },
    "pasta": {
        "calories": 131, "protein": 5, "carbs": 25, "fat": 1.1, "fiber": 1.8,
        "tags": ["grain", "pantry", "vegetarian"], "category": "grain",
    },
    "whole wheat pasta": {
        "calories": 124, "protein": 5.3, "carbs": 26, "fat": 0.5, "fiber": 3.9,
        "tags": ["grain", "pantry", "vegetarian"], "category": "grain",
    },
    "bread": {
        "calories": 265, "protein": 9, "carbs": 49, "fat": 3.2, "fiber": 2.7,
        "tags": ["grain", "vegetarian"], "category": "grain",
    },
    "flour": {
        "calories": 364, "protein": 10, "carbs": 76, "fat": 1, "fiber": 2.7,
        "tags": ["grain", "pantry", "vegetarian"], "category": "grain",
    },
    "oats": {
        "calories": 389, "protein": 17, "carbs": 66, "fat": 7, "fiber": 11,
        "tags": ["high-protein", "grain", "pantry", "vegan", "vegetarian"], "category": "grain",
    },
    "quinoa": {
        "calories": 120, "protein": 4.4, "carbs": 21, "fat": 1.9, "fiber": 2.8,
        "tags": ["grain", "pantry", "vegan", "vegetarian"], "category": "grain",
    },

    # --- Vegetables ---
    "potato": {
        "calories": 77, "protein": 2, "carbs": 17, "fat": 0.1, "fiber": 2.2,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "sweet potato": {
        "calories": 86, "protein": 1.6, "carbs": 20, "fat": 0.1, "fiber": 3,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "carrot": {
        "calories": 41, "protein": 0.9, "carbs": 10, "fat": 0.2, "fiber": 2.8,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "broccoli": {
        "calories": 34, "protein": 2.8, "carbs": 7, "fat": 0.4, "fiber": 2.6,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "spinach": {
        "calories": 23, "protein": 2.9, "carbs": 3.6, "fat": 0.4, "fiber": 2.2,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "kale": {
        "calories": 49, "protein": 4.3, "carbs": 9, "fat": 0.9, "fiber": 3.6,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "tomato": {
        "calories": 18, "protein": 0.9, "carbs": 3.9, "fat": 0.2, "fiber": 1.2,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "onion": {
        "calories": 40, "protein": 1.1, "carbs": 9.3, "fat": 0.1, "fiber": 1.7,
        "tags": ["vegetable", "vegan", "vegetarian", "pantry"], "category": "vegetable",
    },
    "garlic": {
        "calories": 149, "protein": 6.4, "carbs": 33, "fat": 0.5, "fiber": 2.1,
        "tags": ["vegetable", "vegan", "vegetarian", "pantry"], "category": "vegetable",
    },
    "bell pepper": {
        "calories": 31, "protein": 1, "carbs": 6, "fat": 0.3, "fiber": 2.1,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "mushroom": {
        "calories": 22, "protein": 3.1, "carbs": 3.3, "fat": 0.3, "fiber": 1,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "zucchini": {
        "calories": 17, "protein": 1.2, "carbs": 3.1, "fat": 0.3, "fiber": 1,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "cucumber": {
        "calories": 15, "protein": 0.7, "carbs": 3.6, "fat": 0.1, "fiber": 0.5,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "lettuce": {
        "calories": 15, "protein": 1.4, "carbs": 2.9, "fat": 0.2, "fiber": 1.3,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "cabbage": {
        "calories": 25, "protein": 1.3, "carbs": 5.8, "fat": 0.1, "fiber": 2.5,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "corn": {
        "calories": 86, "protein": 3.2, "carbs": 19, "fat": 1.2, "fiber": 2.7,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "asparagus": {
        "calories": 20, "protein": 2.2, "carbs": 3.9, "fat": 0.1, "fiber": 2.1,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },
    "cauliflower": {
        "calories": 25, "protein": 1.9, "carbs": 5, "fat": 0.3, "fiber": 2,
        "tags": ["vegetable", "vegan", "vegetarian"], "category": "vegetable",
    },

    # --- Fruits ---
    "apple": {
        "calories": 52, "protein": 0.3, "carbs": 14, "fat": 0.2, "fiber": 2.4,
        "tags": ["fruit", "vegan", "vegetarian"], "category": "fruit",
    },
    "banana": {
        "calories": 89, "protein": 1.1, "carbs": 23, "fat": 0.3, "fiber": 2.6,
        "tags": ["fruit", "vegan", "vegetarian"], "category": "fruit",
    },
    "orange": {
        "calories": 47, "protein": 0.9, "carbs": 12, "fat": 0.1, "fiber": 2.4,
        "tags": ["fruit", "vegan", "vegetarian"], "category": "fruit",
    },
    "lemon": {
        "calories": 29, "protein": 1.1, "carbs": 9.3, "fat": 0.3, "fiber": 2.8,
        "tags": ["fruit", "vegan", "vegetarian", "pantry"], "category": "fruit",
    },
    "strawberry": {
        "calories": 32, "protein": 0.7, "carbs": 7.7, "fat": 0.3, "fiber": 2,
        "tags": ["fruit", "vegan", "vegetarian"], "category": "fruit",
    },
    "blueberry": {
        "calories": 57, "protein": 0.7, "carbs": 14, "fat": 0.3, "fiber": 2.4,
        "tags": ["fruit", "vegan", "vegetarian"], "category": "fruit",
    },
    "avocado": {
        "calories": 160, "protein": 2, "carbs": 8.5, "fat": 15, "fiber": 6.7,
        "tags": ["fruit", "vegan", "vegetarian"], "category": "fruit",
    },

    # --- Oils & fats ---
    "olive oil": {
        "calories": 884, "protein": 0, "carbs": 0, "fat": 100, "fiber": 0,
        "tags": ["fat", "pantry", "vegan", "vegetarian"], "category": "fat",
    },
    "vegetable oil": {
        "calories": 884, "protein": 0, "carbs": 0, "fat": 100, "fiber": 0,
        "tags": ["fat", "pantry", "vegan", "vegetarian"], "category": "fat",
    },
    "coconut oil": {
        "calories": 862, "protein": 0, "carbs": 0, "fat": 100, "fiber": 0,
        "tags": ["fat", "pantry", "vegan", "vegetarian"], "category": "fat",
    },

    # --- Nuts & seeds ---
    "almonds": {
        "calories": 579, "protein": 21, "carbs": 22, "fat": 50, "fiber": 12,
        "tags": ["high-protein", "nuts", "vegan", "vegetarian"], "category": "nuts",
    },
    "walnuts": {
        "calories": 654, "protein": 15, "carbs": 14, "fat": 65, "fiber": 6.7,
        "tags": ["high-protein", "nuts", "vegan", "vegetarian"], "category": "nuts",
    },
    "peanuts": {
        "calories": 567, "protein": 26, "carbs": 16, "fat": 49, "fiber": 8.5,
        "tags": ["high-protein", "nuts", "vegan", "vegetarian"], "category": "nuts",
    },
    "peanut butter": {
        "calories": 588, "protein": 25, "carbs": 20, "fat": 50, "fiber": 6,
        "tags": ["high-protein", "nuts", "pantry", "vegan", "vegetarian"], "category": "nuts",
    },
    "cashews": {
        "calories": 553, "protein": 18, "carbs": 30, "fat": 44, "fiber": 3.3,
        "tags": ["high-protein", "nuts", "vegan", "vegetarian"], "category": "nuts",
    },
    "chia seeds": {
        "calories": 486, "protein": 17, "carbs": 42, "fat": 31, "fiber": 34,
        "tags": ["high-protein", "seeds", "vegan", "vegetarian", "pantry"], "category": "nuts",
    },
    "hemp seeds": {
        "calories": 553, "protein": 32, "carbs": 9, "fat": 49, "fiber": 4,
        "tags": ["high-protein", "seeds", "vegan", "vegetarian"], "category": "nuts",
    },
    "pumpkin seeds": {
        "calories": 559, "protein": 30, "carbs": 11, "fat": 49, "fiber": 6,
        "tags": ["high-protein", "seeds", "vegan", "vegetarian"], "category": "nuts",
    },

    # --- Sweeteners / condiments ---
    "sugar": {
        "calories": 387, "protein": 0, "carbs": 100, "fat": 0, "fiber": 0,
        "tags": ["pantry", "vegan", "vegetarian"], "category": "condiment",
    },
    "honey": {
        "calories": 304, "protein": 0.3, "carbs": 82, "fat": 0, "fiber": 0.2,
        "tags": ["pantry", "vegetarian"], "category": "condiment",
    },
    "maple syrup": {
        "calories": 260, "protein": 0, "carbs": 67, "fat": 0, "fiber": 0,
        "tags": ["pantry", "vegan", "vegetarian"], "category": "condiment",
    },
    "soy sauce": {
        "calories": 53, "protein": 8, "carbs": 4.9, "fat": 0, "fiber": 0.8,
        "tags": ["pantry", "soy", "vegan", "vegetarian"], "category": "condiment",
    },
    "mayonnaise": {
        "calories": 680, "protein": 1, "carbs": 0.6, "fat": 75, "fiber": 0,
        "tags": ["condiment"], "category": "condiment",
    },
    "ketchup": {
        "calories": 112, "protein": 1.7, "carbs": 26, "fat": 0.4, "fiber": 0.3,
        "tags": ["pantry", "vegan", "vegetarian"], "category": "condiment",
    },
    "mustard": {
        "calories": 66, "protein": 4.4, "carbs": 5.8, "fat": 4, "fiber": 3.3,
        "tags": ["pantry", "vegan", "vegetarian"], "category": "condiment",
    },
}

# Back-compat alias for nutrition router flat macros (no tags)
NUTRITION_PER_100G: Dict[str, Dict[str, float]] = {
    name: {
        "calories": entry["calories"],
        "protein": entry["protein"],
        "carbs": entry["carbs"],
        "fat": entry["fat"],
        "fiber": entry.get("fiber", 0) or 0,
    }
    for name, entry in FOOD_DATABASE.items()
}


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return []


def _normalize_name(name: str) -> str:
    name = (name or "").lower().strip()
    prefixes = (
        "fresh ", "dried ", "chopped ", "diced ", "minced ", "sliced ",
        "cooked ", "raw ", "frozen ", "canned ", "organic ", "boneless ",
        "skinless ",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
                changed = True
    return name.strip()


def _veto_match(name: str, veto: str) -> bool:
    """True if food name is blocked by a veto token (exact / plural / substring)."""
    if not name or not veto:
        return False
    if name == veto:
        return True
    # Prefer longer tokens to avoid tiny false positives ("oil", "egg")
    if len(veto) < 4 and len(name) < 4:
        return name == veto
    if len(veto) >= 4 and (veto in name or name in veto):
        return True
    # Simple plural strip
    v2 = veto[:-1] if veto.endswith("s") and len(veto) > 3 else veto
    n2 = name[:-1] if name.endswith("s") and len(name) > 3 else name
    if v2 and n2 and (v2 == n2 or (len(v2) >= 4 and (v2 in name or name in v2))):
        return True
    return False


def _is_vetoed(name: str, veto_set: set) -> bool:
    return any(_veto_match(name, v) for v in veto_set if v)


def _active_veto_set(prefs: Optional[dict]) -> set:
    """Adult veto always; kid veto only when kid-friendly meals apply."""
    prefs = prefs or {}
    veto = {_normalize_name(d) for d in _as_str_list(prefs.get("dislikedIngredients"))}
    explicit = prefs.get("kidFriendlyMeals")
    wants_kids = (
        True if explicit is True
        else False if explicit is False
        else bool(prefs.get("hasChildren"))
    )
    if wants_kids:
        veto |= {_normalize_name(d) for d in _as_str_list(prefs.get("kidVetoIngredients"))}
    return {v for v in veto if v}


def _dietary_flags(prefs: Optional[dict]) -> Dict[str, bool]:
    dietary = [d.lower().replace("_", "-") for d in _as_str_list(
        (prefs or {}).get("dietaryRestrictions") or (prefs or {}).get("dietary")
    )]
    return {
        "high_protein": any(d in ("high-protein", "high protein") for d in dietary),
        "vegan": "vegan" in dietary,
        "vegetarian": "vegetarian" in dietary or "vegan" in dietary,
        "dairy_free": "dairy-free" in dietary or "dairy free" in dietary or "vegan" in dietary,
        "gluten_free": "gluten-free" in dietary or "gluten free" in dietary,
        "nut_free": "nut-free" in dietary or "nut free" in dietary,
        "keto": "keto" in dietary,
        "halal": "halal" in dietary,
        "kosher": "kosher" in dietary,
    }


def resolve_nutrition_goals(
    prefs: Optional[dict],
    *,
    meals_per_day: int = DEFAULT_MEALS_PER_DAY,
) -> Dict[str, Any]:
    """
    Resolve daily + per-meal protein/calorie targets from preferences.

    When high-protein is selected and no explicit target is set, apply sensible defaults.
    """
    prefs = prefs or {}
    flags = _dietary_flags(prefs)
    high = flags["high_protein"]

    raw_protein = prefs.get("dailyProteinTarget")
    raw_calories = prefs.get("dailyCalorieTarget")

    protein_daily: Optional[float] = None
    calories_daily: Optional[float] = None

    try:
        if raw_protein is not None and str(raw_protein).strip() != "":
            protein_daily = float(raw_protein)
    except (TypeError, ValueError):
        protein_daily = None
    try:
        if raw_calories is not None and str(raw_calories).strip() != "":
            calories_daily = float(raw_calories)
    except (TypeError, ValueError):
        calories_daily = None

    if protein_daily is None and high:
        protein_daily = float(DEFAULT_PROTEIN_G_HIGH_PROTEIN)
    if calories_daily is None and high:
        calories_daily = float(DEFAULT_CALORIES_HIGH_PROTEIN)

    # Soft defaults only when goals are explicitly useful for AI (high-protein or set)
    if protein_daily is None and (raw_protein is not None or high):
        protein_daily = float(DEFAULT_PROTEIN_G)
    if calories_daily is None and (raw_calories is not None or high):
        calories_daily = float(DEFAULT_CALORIES)

    meals = max(1, int(meals_per_day or DEFAULT_MEALS_PER_DAY))
    protein_per_meal = None
    calories_per_meal = None
    if protein_daily is not None:
        protein_per_meal = max(MIN_PROTEIN_PER_MEAL_G, round(protein_daily / meals, 1))
    if calories_daily is not None:
        calories_per_meal = round(calories_daily / meals, 1)

    return {
        "daily_protein_g": protein_daily,
        "daily_calories": calories_daily,
        "protein_per_meal_g": protein_per_meal,
        "calories_per_meal": calories_per_meal,
        "meals_per_day": meals,
        "high_protein": high,
        "defaults_applied": high and (
            raw_protein is None or str(raw_protein).strip() == ""
            or raw_calories is None or str(raw_calories).strip() == ""
        ),
    }


def find_food(name: str) -> Optional[Tuple[str, FoodEntry]]:
    """Find best matching food entry. Returns (canonical_name, entry) or None."""
    cleaned = _normalize_name(name)
    if not cleaned:
        return None
    if cleaned in FOOD_DATABASE:
        return cleaned, FOOD_DATABASE[cleaned]

    # Prefer longest substring match to avoid "egg" matching "eggplant" wrongly —
    # we don't have eggplant; still prefer more specific names.
    best: Optional[Tuple[str, FoodEntry]] = None
    best_len = 0
    for db_name, entry in FOOD_DATABASE.items():
        if db_name in cleaned or cleaned in db_name:
            if len(db_name) > best_len:
                best = (db_name, entry)
                best_len = len(db_name)
    return best


def macros_only(entry: FoodEntry) -> Dict[str, float]:
    return {
        "calories": float(entry["calories"]),
        "protein": float(entry["protein"]),
        "carbs": float(entry["carbs"]),
        "fat": float(entry["fat"]),
        "fiber": float(entry.get("fiber", 0) or 0),
    }


def _passes_diet_filters(name: str, entry: FoodEntry, flags: Dict[str, bool]) -> bool:
    tags = set(entry.get("tags") or [])
    if flags["vegan"] and "vegan" not in tags:
        # Allow pantry oils/grains marked vegan
        return False
    if flags["vegetarian"] and not flags["vegan"]:
        if "meat" in tags or "fish" in tags or "seafood" in tags:
            return False
    if flags["dairy_free"] and "dairy" in tags:
        return False
    if flags["nut_free"] and ("nuts" in tags or "seeds" in tags):
        # Keep seeds? Prefer exclude both for safety on nut-free
        if "nuts" in tags:
            return False
    if flags["gluten_free"] and ("wheat" in tags or name in ("pasta", "bread", "flour", "seitan", "whole wheat pasta")):
        return False
    if flags["halal"] and name in ("pork", "pork loin"):
        return False
    return True


def _pantry_overlap_score(name: str, pantry_names: Sequence[str]) -> int:
    if not pantry_names:
        return 0
    score = 0
    for p in pantry_names:
        p_norm = _normalize_name(p if isinstance(p, str) else str(p))
        if not p_norm:
            continue
        if name == p_norm or name in p_norm or p_norm in name:
            score += 3
        else:
            # token overlap
            n_tokens = set(re.split(r"[\s,/]+", name))
            p_tokens = set(re.split(r"[\s,/]+", p_norm))
            score += len(n_tokens & p_tokens)
    return score


def retrieve_foods_for_ai(
    prefs: Optional[dict] = None,
    *,
    pantry_items: Optional[Sequence[str]] = None,
    query: Optional[str] = None,
    limit: int = 18,
    seed: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant food DB items for AI recipe-idea prompts.

    Prioritises: high-protein anchors (when goal), pantry overlap, diet filters,
    then rotates with a seed so successive ideas feel unique.
    """
    prefs = prefs or {}
    flags = _dietary_flags(prefs)
    pantry = [str(x) for x in (pantry_items or []) if x]
    query_l = (query or "").lower()

    disliked = _active_veto_set(prefs)
    allergens = {_normalize_name(a) for a in _as_str_list(prefs.get("allergens"))}

    scored: List[Tuple[float, str, FoodEntry]] = []
    for name, entry in FOOD_DATABASE.items():
        if _is_vetoed(name, disliked):
            continue
        # crude allergen skip
        if any(a and (a in name or name in a) for a in allergens):
            continue
        if not _passes_diet_filters(name, entry, flags):
            continue

        protein = float(entry.get("protein") or 0)
        tags = set(entry.get("tags") or [])
        score = 0.0

        if flags["high_protein"] or protein >= HIGH_PROTEIN_THRESHOLD:
            if "high-protein" in tags or protein >= HIGH_PROTEIN_THRESHOLD:
                score += 20 + protein * 0.4
            else:
                score += 2

        score += _pantry_overlap_score(name, pantry) * 5

        if query_l and (name in query_l or any(tok in query_l for tok in name.split() if len(tok) > 3)):
            score += 8

        # Prefer protein + vegetable + grain mix for recipe building
        if entry.get("category") == "protein":
            score += 4
        elif entry.get("category") == "vegetable":
            score += 1.5
        elif entry.get("category") == "grain":
            score += 1

        # Slight jitter from seed for uniqueness (stable per seed)
        h = hashlib.sha256(f"{seed or 'default'}:{name}".encode()).hexdigest()
        jitter = (int(h[:6], 16) % 1000) / 1000.0  # 0..1
        score += jitter

        scored.append((score, name, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Ensure mix: take top protein anchors + supporting foods
    selected: List[Dict[str, Any]] = []
    seen = set()

    def add_item(name: str, entry: FoodEntry, reason: str) -> None:
        if name in seen:
            return
        seen.add(name)
        selected.append({
            "name": name,
            "per_100g": macros_only(entry),
            "tags": list(entry.get("tags") or []),
            "category": entry.get("category", "other"),
            "reason": reason,
        })

    # First pass: high protein
    for score, name, entry in scored:
        if len(selected) >= max(8, limit // 2):
            break
        protein = float(entry.get("protein") or 0)
        if "high-protein" in (entry.get("tags") or []) or protein >= HIGH_PROTEIN_THRESHOLD:
            add_item(name, entry, "high-protein")

    # Second: fill with remaining top scores (veg, grains, pantry)
    for score, name, entry in scored:
        if len(selected) >= limit:
            break
        add_item(name, entry, "support")

    return selected


def format_food_db_prompt_block(
    foods: Sequence[Dict[str, Any]],
    goals: Optional[Dict[str, Any]] = None,
    *,
    invent_unique: bool = True,
) -> str:
    """Format retrieved foods + goals as an AI prompt injection block."""
    if not foods and not goals:
        return ""

    lines: List[str] = []
    lines.append(
        "Food database building blocks (approximate macros per 100g — estimates for planning, "
        "not medical/dietitian advice):"
    )
    for f in foods:
        m = f.get("per_100g") or {}
        lines.append(
            f"- {f['name']}: {m.get('protein', 0)}g protein, {m.get('calories', 0)} kcal, "
            f"{m.get('carbs', 0)}g carbs, {m.get('fat', 0)}g fat /100g"
            + (f" [{', '.join(f.get('tags') or [])}]" if f.get("tags") else "")
        )

    if goals and (goals.get("daily_protein_g") or goals.get("protein_per_meal_g")):
        lines.append("")
        lines.append("User nutrition goals:")
        if goals.get("daily_protein_g") is not None:
            lines.append(f"- Daily protein target: ~{goals['daily_protein_g']}g")
        if goals.get("daily_calories") is not None:
            lines.append(f"- Daily calorie target: ~{goals['daily_calories']} kcal")
        if goals.get("protein_per_meal_g") is not None:
            lines.append(
                f"- Aim for ~{goals['protein_per_meal_g']}g protein per meal/serving "
                f"(assuming ~{goals.get('meals_per_day', DEFAULT_MEALS_PER_DAY)} eating occasions/day)"
            )
        if goals.get("calories_per_meal") is not None:
            lines.append(f"- Rough calorie budget per meal: ~{goals['calories_per_meal']} kcal")

    lines.append("")
    lines.append(
        "Instructions: Invent practical recipes primarily from these building blocks. "
        "Prefer combining a protein anchor with vegetables/grains from the list. "
        "When stating nutrition, estimate from the listed per-100g values and portion sizes."
    )
    if invent_unique:
        lines.append(
            "Make the recipe idea UNIQUE — avoid generic defaults like plain grilled chicken and rice; "
            "vary cuisine, technique, sauces, and ingredient pairings while staying realistic."
        )
    if goals and goals.get("high_protein"):
        lines.append(
            "Prioritise high-protein outcomes that help the user hit their protein goal."
        )

    return "\n".join(lines)


def build_ai_food_context(
    prefs: Optional[dict] = None,
    *,
    pantry_items: Optional[Sequence[str]] = None,
    query: Optional[str] = None,
    limit: int = 18,
    seed: Optional[str] = None,
    meals_per_day: int = DEFAULT_MEALS_PER_DAY,
) -> str:
    """
    One-shot helper: resolve goals, retrieve foods, format prompt block.
    Empty string when neither goals nor useful foods apply (keeps prompts lean for non-goal users).
    """
    prefs = prefs or {}
    goals = resolve_nutrition_goals(prefs, meals_per_day=meals_per_day)
    flags = _dietary_flags(prefs)

    # Always retrieve when high-protein or explicit targets; otherwise skip to avoid prompt bloat
    has_targets = goals.get("daily_protein_g") is not None or goals.get("daily_calories") is not None
    if not flags["high_protein"] and not has_targets and not pantry_items:
        # Still inject a light food block if the query looks like a recipe-idea ask
        q = (query or "").lower()
        idea_hints = ("recipe", "idea", "high protein", "protein", "meal", "cook", "what can i")
        if not any(h in q for h in idea_hints):
            return ""

    foods = retrieve_foods_for_ai(
        prefs,
        pantry_items=pantry_items,
        query=query,
        limit=limit,
        seed=seed,
    )
    return format_food_db_prompt_block(foods, goals if has_targets or flags["high_protein"] else None)


async def load_ai_food_context(
    user_id: str,
    *,
    pantry_items: Optional[Sequence[str]] = None,
    query: Optional[str] = None,
    limit: int = 18,
    seed: Optional[str] = None,
) -> str:
    """Load user prefs and build food-DB prompt context."""
    from dependencies import user_preferences_repository

    prefs = await user_preferences_repository.find_by_user(user_id)
    if seed is None:
        seed = f"{user_id}:{query or ''}"
    return build_ai_food_context(
        prefs,
        pantry_items=pantry_items,
        query=query,
        limit=limit,
        seed=seed,
    )


# Unit conversions to grams (shared with nutrition router via import)
UNIT_CONVERSIONS = {
    "g": 1,
    "gram": 1,
    "grams": 1,
    "kg": 1000,
    "kilogram": 1000,
    "oz": 28.35,
    "ounce": 28.35,
    "ounces": 28.35,
    "lb": 453.6,
    "pound": 453.6,
    "pounds": 453.6,
    "cup": 240,
    "cups": 240,
    "tbsp": 15,
    "tablespoon": 15,
    "tablespoons": 15,
    "tsp": 5,
    "teaspoon": 5,
    "teaspoons": 5,
    "ml": 1,
    "l": 1000,
    "liter": 1000,
    "liters": 1000,
}


def parse_ingredient_amount(ingredient_str: str) -> Dict[str, Any]:
    """Parse an ingredient string into quantity, unit, and name."""
    ingredient_str = (ingredient_str or "").lower().strip()
    quantity = None
    unit = None
    name = ingredient_str

    fraction_match = re.match(r"^(\d+/\d+|\d+\s+\d+/\d+|\d+\.?\d*)\s*", ingredient_str)
    if fraction_match:
        qty_str = fraction_match.group(1).strip()
        if " " in qty_str:
            parts = qty_str.split()
            whole = float(parts[0])
            frac_parts = parts[1].split("/")
            quantity = whole + float(frac_parts[0]) / float(frac_parts[1])
        elif "/" in qty_str:
            parts = qty_str.split("/")
            quantity = float(parts[0]) / float(parts[1])
        else:
            quantity = float(qty_str)

        remaining = ingredient_str[fraction_match.end():].strip()
        for unit_name in UNIT_CONVERSIONS:
            if remaining.startswith(unit_name + " ") or remaining.startswith(unit_name + "s "):
                unit = unit_name.rstrip("s")
                remaining = remaining[len(unit_name):].strip()
                if remaining.startswith("s "):
                    remaining = remaining[2:]
                elif remaining.startswith(" "):
                    remaining = remaining[1:]
                break
        name = remaining

    return {"quantity": quantity, "unit": unit, "name": name}


def estimate_nutrition_from_foods(
    ingredients: Sequence[Any],
    *,
    servings: int = 1,
) -> Dict[str, Any]:
    """
    Estimate nutrition for ingredient list using the food DB.

    ingredients: strings or dicts with name/amount/unit.
    Amounts without units are treated as 100g portions.
    """
    results = []
    unknown = []
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0}

    for ingredient in ingredients:
        if isinstance(ingredient, dict):
            amount = ingredient.get("amount", "")
            unit = ingredient.get("unit", "")
            name = ingredient.get("name", "")
            ingredient_str = f"{amount} {unit} {name}".strip()
        else:
            ingredient_str = str(ingredient)

        parsed = parse_ingredient_amount(ingredient_str)
        match = find_food(parsed["name"])
        if not match:
            unknown.append(ingredient_str)
            continue
        canonical, entry = match
        macros = macros_only(entry)

        grams = 100.0
        if parsed["quantity"] is not None:
            if parsed["unit"]:
                unit_key = parsed["unit"]
                unit_grams = UNIT_CONVERSIONS.get(
                    unit_key, UNIT_CONVERSIONS.get(unit_key.rstrip("s"), 1)
                )
                grams = parsed["quantity"] * unit_grams
            else:
                grams = parsed["quantity"] * 100

        scale = grams / 100.0
        row = {
            "ingredient": canonical,
            "amount_grams": round(grams, 1),
            "calories": round(macros["calories"] * scale, 1),
            "protein": round(macros["protein"] * scale, 1),
            "carbs": round(macros["carbs"] * scale, 1),
            "fat": round(macros["fat"] * scale, 1),
            "fiber": round(macros["fiber"] * scale, 1),
        }
        results.append(row)
        for k in totals:
            totals[k] += row[k]

    for k in totals:
        totals[k] = round(totals[k], 1)
    servings = max(1, int(servings or 1))
    per_serving = {k: round(v / servings, 1) for k, v in totals.items()}

    return {
        "ingredients": results,
        "unknown_ingredients": unknown,
        "totals": totals,
        "per_serving": per_serving,
        "servings": servings,
        "source": "food_db",
        "disclaimer": "Approximate estimates from the curated food database — not medical advice.",
    }
