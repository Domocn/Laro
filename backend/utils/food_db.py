"""
Curated food composition DB for AI recipe ideas grounded in real macros.

A small hand-tuned table (per 100g) of high-protein foods, pantry staples and
plant-based / dairy-free specifics, backed by the full UK CoFID 2021 + USDA FDC
dataset (``utils.food_dataset``, bundled in ``data/foods/``) for everything else.
``find_food`` is UK-first by default (UK supermarket labels -> CoFID -> curated); see its
docstring for the order and ``region="us"``. Values are food-composition averages for meal planning / idea generation, not
medical advice.

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
    # Official UK Weetabix: 2 biscuits (37.5g) = 136 kcal / 4.5g protein / 26g carbs / 0.8g fat
    "weetabix": {
        "calories": 363, "protein": 12, "carbs": 69, "fat": 2.1, "fiber": 10,
        "tags": ["grain", "pantry", "vegan", "vegetarian", "breakfast"], "category": "grain",
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

    # --- Chocolate / cocoa ---
    "cocoa powder": {
        "calories": 228, "protein": 20, "carbs": 58, "fat": 14, "fiber": 37,
        "tags": ["pantry", "vegan", "vegetarian"], "category": "pantry",
    },
    "dark chocolate": {
        "calories": 570, "protein": 8, "carbs": 46, "fat": 42, "fiber": 11,
        "tags": ["pantry", "vegetarian"], "category": "pantry",
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

# ---------------------------------------------------------------------------
# Raw / as-sold basis. Recipes weigh ingredients raw (dry pasta, raw chicken), and
# labels + apps quote raw values, so the plain name is the raw figure. A "(cooked)"
# twin is used only when the recipe line says cooked / tinned / drained.
# Values: USDA FDC SR Legacy + UK CoFID typical, per 100 g.
# ---------------------------------------------------------------------------
_RAW_VALUES = {
    # name: (kcal, protein, carbs, fat, fibre)
    "chicken breast": (120, 22.5, 0, 2.6, 0),
    "chicken thigh": (121, 19.7, 0, 4.1, 0),
    "turkey breast": (114, 23.7, 0.1, 1.5, 0),
    "lean ground turkey": (150, 18.7, 0, 8.3, 0),
    "beef": (198, 19.4, 0, 12.7, 0),
    "pork": (211, 17, 0, 15.4, 0),
    "tuna": (109, 24.4, 0, 0.5, 0),
    "shrimp": (85, 20.1, 0, 0.5, 0),
    "egg": (143, 12.6, 0.7, 9.5, 0),
    "seitan": (120, 21, 4, 1.9, 0.6),
    "yogurt": (61, 3.5, 4.7, 3.3, 0),
    "yoghurt": (61, 3.5, 4.7, 3.3, 0),
    "milk": (46, 3.5, 4.8, 1.7, 0),
    "rice": (365, 7.1, 80, 0.7, 1.3),
    "brown rice": (370, 7.9, 77, 2.9, 3.5),
    "pasta": (371, 13, 75, 1.5, 3.2),
    "whole wheat pasta": (352, 14.6, 72, 2.5, 9.2),
    "quinoa": (368, 14.1, 64, 6.1, 7),
    "lentils": (352, 24.6, 63, 1.1, 10.7),
    "chickpeas": (378, 20.5, 63, 6, 12.2),
    "black beans": (341, 21.6, 62, 1.4, 15.5),
    "kidney beans": (333, 23.6, 60, 0.8, 24.9),
    "beans": (333, 23.6, 60, 0.8, 24.9),
}
for _name, (_kcal, _p, _c, _f, _fib) in _RAW_VALUES.items():
    FOOD_DATABASE[_name].update({"calories": _kcal, "protein": _p, "carbs": _c, "fat": _f, "fiber": _fib})

_COOKED_VALUES = {
    "chicken breast": (165, 31, 0, 3.6, 0),
    "chicken thigh": (209, 26, 0, 10.9, 0),
    "turkey breast": (135, 30, 0, 1, 0),
    "beef": (250, 26, 0, 15, 0),
    "pork": (242, 27, 0, 14, 0),
    "tuna": (132, 29, 0, 1, 0),
    "shrimp": (99, 24, 0.2, 0.3, 0),
    "egg": (155, 13, 1.1, 11, 0),
    "rice": (130, 2.7, 28, 0.3, 0.4),
    "brown rice": (112, 2.6, 24, 0.9, 1.8),
    "pasta": (131, 5, 25, 1.1, 1.8),
    "whole wheat pasta": (124, 5.3, 26, 0.5, 3.9),
    "quinoa": (120, 4.4, 21, 1.9, 2.8),
    "lentils": (116, 9, 20, 0.4, 7.9),
    "chickpeas": (139, 7.2, 16.1, 2.9, 4.1),  # tinned, drained (CoFID)
    "black beans": (132, 8.9, 24, 0.5, 8.7),
    "kidney beans": (127, 8.7, 23, 0.5, 6.4),
    "beans": (127, 8.7, 22, 0.5, 6.4),
}
for _name, (_kcal, _p, _c, _f, _fib) in _COOKED_VALUES.items():
    FOOD_DATABASE[f"{_name} (cooked)"] = {
        "calories": _kcal, "protein": _p, "carbs": _c, "fat": _f, "fiber": _fib,
        "tags": list(FOOD_DATABASE[_name].get("tags") or []), "category": FOOD_DATABASE[_name].get("category"),
    }

# Common recipe ingredients the table was missing (and specific names that used to
# fall through to a wrong generic match, e.g. "coconut milk" -> dairy milk).
_EXTRA_FOODS = {
    # name: (kcal, protein, carbs, fat, fibre, category)
    "vital wheat gluten": (370, 75, 14, 1.9, 0.6, "protein"),
    "impossible mince": (212, 16.8, 8, 12.4, 2.7, "protein"),
    "plant-based mince": (212, 16.8, 8, 12.4, 2.7, "protein"),
    "vegetarian sausages": (220, 15, 10, 13, 3, "protein"),
    "nutritional yeast": (380, 45, 37, 4, 20, "pantry"),
    "aquafaba": (18, 1, 3, 0.3, 0, "pantry"),
    "salt": (0, 0, 0, 0, 0, "seasoning"),
    "black salt": (0, 0, 0, 0, 0, "seasoning"),
    "black pepper": (251, 10.4, 64, 3.3, 25.3, "seasoning"),
    "water": (0, 0, 0, 0, 0, "pantry"),
    "baking powder": (53, 0, 28, 0, 0.2, "baking"),
    "bicarbonate of soda": (0, 0, 0, 0, 0, "baking"),
    "baking soda": (0, 0, 0, 0, 0, "baking"),
    "instant dried yeast": (325, 40, 41, 7.6, 27, "baking"),
    "yeast": (325, 40, 41, 7.6, 27, "baking"),
    "psyllium husk": (180, 2, 4, 0.6, 80, "baking"),
    "xanthan gum": (330, 0, 78, 0, 77, "baking"),
    "vanilla extract": (288, 0.1, 12.7, 0.1, 0, "baking"),
    "almond extract": (288, 0, 12.7, 0, 0, "baking"),
    "cornflour": (381, 0.3, 91, 0.1, 0.9, "baking"),
    "cornstarch": (381, 0.3, 91, 0.1, 0.9, "baking"),
    "potato starch": (333, 0.1, 83, 0.1, 0, "baking"),
    "tapioca starch": (358, 0.2, 89, 0, 0.9, "baking"),
    "gluten-free flour": (345, 6, 78, 1.5, 3, "baking"),
    "almond flour": (579, 21, 22, 50, 12.5, "baking"),
    "almond meal": (579, 21, 22, 50, 12.5, "baking"),
    "buckwheat flour": (335, 12.6, 70.6, 3.1, 10, "baking"),
    "brown rice flour": (363, 7.2, 76.5, 2.8, 4.6, "baking"),
    "rice flour": (366, 6, 80, 1.4, 2.4, "baking"),
    "millet flour": (382, 10.8, 75, 4.2, 3.5, "baking"),
    "icing sugar": (398, 0, 99.8, 0, 0, "baking"),
    "custard powder": (354, 0.6, 88, 0.1, 0, "baking"),
    "desiccated coconut": (660, 6.9, 24, 65, 16.3, "baking"),
    "cocoa nibs": (600, 13, 35, 46, 33, "baking"),
    "milk chocolate": (535, 7.6, 59, 30, 3.4, "sweet"),
    "white chocolate": (539, 5.9, 59, 32, 0.2, "sweet"),
    "chocolate chips": (480, 4.2, 64, 24, 6, "sweet"),
    "marshmallows": (318, 1.8, 81, 0.2, 0.1, "sweet"),
    "jam": (250, 0.4, 61, 0.1, 1, "sweet"),
    "biscuits": (480, 6, 68, 21, 2, "sweet"),
    "coconut milk": (197, 2, 2.8, 21, 0, "dairy-alt"),
    "light coconut milk": (73, 0.7, 1.6, 7, 0, "dairy-alt"),
    "condensed milk": (321, 7.9, 54, 8.7, 0, "dairy"),
    "condensed coconut milk": (330, 2.5, 55, 11, 0, "dairy-alt"),
    "coconut cream": (330, 3.6, 6.7, 34.7, 2.2, "dairy-alt"),
    "dairy-free milk": (33, 3, 0.5, 1.8, 0.5, "dairy-alt"),
    "oat milk": (45, 1, 6.6, 1.5, 0.8, "dairy-alt"),
    "almond milk": (13, 0.4, 0, 1.1, 0.2, "dairy-alt"),
    "soy milk": (33, 3.3, 0.2, 1.8, 0.5, "dairy-alt"),
    "dairy-free butter": (720, 0.2, 0.5, 80, 0, "dairy-alt"),
    "dairy-free cheese": (300, 0.5, 20, 24, 0, "dairy-alt"),
    "dairy-free feta": (280, 0.5, 20, 23, 0, "dairy-alt"),
    "dairy-free cream cheese": (260, 1, 6, 25, 0, "dairy-alt"),
    "dairy-free parmesan": (330, 1, 15, 29, 0, "dairy-alt"),
    "dairy-free cream": (180, 2, 4, 17, 0.5, "dairy-alt"),
    "dairy-free whipping cream": (250, 0.5, 4, 25, 0, "dairy-alt"),
    "coconut yoghurt": (128, 0.8, 5, 11.5, 0.5, "dairy-alt"),
    "coconut yogurt": (128, 0.8, 5, 11.5, 0.5, "dairy-alt"),
    "dairy-free yoghurt": (128, 0.8, 5, 11.5, 0.5, "dairy-alt"),
    "dairy-free yogurt": (128, 0.8, 5, 11.5, 0.5, "dairy-alt"),
    "dairy-free mayonnaise": (650, 0.5, 2, 71, 0, "condiment"),
    "dairy-free chocolate": (550, 5, 50, 36, 6, "sweet"),
    "dairy-free white chocolate": (560, 3, 55, 36, 0, "sweet"),
    "dairy-free milk chocolate": (550, 5, 55, 34, 3, "sweet"),
    "sesame oil": (884, 0, 0, 100, 0, "oil"),
    "tahini": (595, 17, 21, 54, 9.3, "pantry"),
    "sesame paste": (595, 17, 21, 54, 9.3, "pantry"),
    "sesame seeds": (573, 17.7, 23, 49.7, 11.8, "nuts-seeds"),
    "poppy seeds": (525, 18, 28, 42, 19.5, "nuts-seeds"),
    "poppyseeds": (525, 18, 28, 42, 19.5, "nuts-seeds"),
    "fennel seeds": (345, 15.8, 52, 14.9, 39.8, "seasoning"),
    "hazelnuts": (628, 15, 17, 61, 9.7, "nuts-seeds"),
    "pistachios": (562, 20, 28, 45, 10.6, "nuts-seeds"),
    "tamari": (60, 10.5, 5.6, 0.1, 0.8, "condiment"),
    "coconut aminos": (100, 0, 25, 0, 0, "condiment"),
    "miso": (198, 12.8, 26, 6, 5.4, "condiment"),
    "miso paste": (198, 12.8, 26, 6, 5.4, "condiment"),
    "vinegar": (19, 0, 0.9, 0, 0, "condiment"),
    "rice wine vinegar": (18, 0, 0, 0, 0, "condiment"),
    "apple cider vinegar": (21, 0, 0.9, 0, 0, "condiment"),
    "red wine vinegar": (19, 0, 0.3, 0, 0, "condiment"),
    "fish sauce": (35, 5, 3.6, 0, 0, "condiment"),
    "vegetarian fish sauce": (50, 2, 10, 0, 0, "condiment"),
    "oyster sauce": (51, 1.4, 11, 0.3, 0.3, "condiment"),
    "hoisin sauce": (220, 3.3, 44, 3.4, 2.8, "condiment"),
    "sriracha": (93, 1.9, 19, 0.9, 2.2, "condiment"),
    "gochujang": (230, 4.5, 48, 2, 2, "condiment"),
    "chilli crisp": (650, 5, 10, 65, 4, "condiment"),
    "dijon mustard": (151, 7.4, 3.5, 11.5, 2, "condiment"),  # Dijon is far richer than US yellow mustard
    "curry paste": (120, 2.5, 13, 6.5, 4, "condiment"),
    "satay sauce": (250, 7, 14, 19, 2, "condiment"),
    "pesto": (430, 5, 6, 43, 2, "condiment"),
    "hummus": (166, 7.9, 14.3, 9.6, 6, "condiment"),
    "stock powder": (243, 10, 27, 10.8, 1, "pantry"),
    "stock": (5, 0.3, 0.6, 0.2, 0, "pantry"),
    "kimchi": (15, 1.1, 2.4, 0.5, 1.6, "vegetable"),
    "olives": (115, 0.8, 6, 10.7, 3.2, "vegetable"),
    "capers": (23, 2.4, 4.9, 0.9, 3.2, "condiment"),
    "pickles": (11, 0.3, 2.3, 0.2, 1, "vegetable"),
    "artichoke hearts": (100, 2, 6, 8, 3, "vegetable"),
    "spring onion": (32, 1.8, 7.3, 0.2, 2.6, "vegetable"),
    "spring onions": (32, 1.8, 7.3, 0.2, 2.6, "vegetable"),
    "ginger": (80, 1.8, 18, 0.8, 2, "vegetable"),
    "red chilli": (40, 1.9, 8.8, 0.4, 1.5, "vegetable"),
    "chilli": (40, 1.9, 8.8, 0.4, 1.5, "vegetable"),
    "chilli flakes": (314, 12, 50, 17, 27, "seasoning"),
    "beetroot": (43, 1.6, 9.6, 0.2, 2.8, "vegetable"),
    "rocket": (25, 2.6, 3.7, 0.7, 1.6, "vegetable"),
    "bean sprouts": (30, 3, 5.9, 0.2, 1.8, "vegetable"),
    "pumpkin": (26, 1, 6.5, 0.1, 0.5, "vegetable"),
    "squash": (45, 1, 11.7, 0.1, 2, "vegetable"),
    "fennel": (31, 1.2, 7.3, 0.2, 3.1, "vegetable"),
    "french fries": (150, 2.5, 25, 4.5, 2.5, "vegetable"),
    "breadcrumbs": (380, 6, 80, 3, 3, "grain"),
    "dried mixed herbs": (270, 9, 60, 5, 38, "seasoning"),
    "bay leaves": (313, 7.6, 75, 8.4, 26.3, "seasoning"),
    "lemongrass": (99, 1.8, 25, 0.5, 0, "herb"),
    "jalapenos": (29, 0.9, 6.5, 0.4, 2.8, "vegetable"),
    "cranberry sauce": (159, 0.2, 40, 0.2, 1.1, "condiment"),
    "raspberries": (52, 1.2, 12, 0.7, 6.5, "fruit"),
    "passionfruit": (97, 2.2, 23, 0.7, 10.4, "fruit"),
    "dried apricots": (241, 3.4, 63, 0.5, 7.3, "fruit"),
    "currants": (283, 4.1, 74, 0.3, 6.8, "fruit"),
    "lime juice": (25, 0.4, 8.4, 0.1, 0.4, "fruit"),
    "lemon juice": (22, 0.4, 6.9, 0.2, 0.3, "fruit"),
    "parsley": (36, 3, 6.3, 0.8, 3.3, "herb"),
    "mint": (70, 3.8, 15, 0.9, 8, "herb"),
    "coriander": (23, 2.1, 3.7, 0.5, 2.8, "herb"),
    "basil": (23, 3.2, 2.7, 0.6, 1.6, "herb"),
    "dill": (43, 3.5, 7, 1.1, 2.1, "herb"),
    "chives": (30, 3.3, 4.4, 0.7, 2.5, "herb"),
    "rosemary": (131, 3.3, 21, 5.9, 14, "herb"),
    "cinnamon": (247, 4, 81, 1.2, 53, "seasoning"),
    "ground cumin": (375, 17.8, 44, 22, 10.5, "seasoning"),
    "ground coriander": (298, 12.4, 55, 17.8, 41.9, "seasoning"),
    "dried oregano": (265, 9, 69, 4.3, 42.5, "seasoning"),
    "smoked paprika": (282, 14, 54, 13, 35, "seasoning"),
    "nutmeg": (525, 5.8, 49, 36, 21, "seasoning"),
    "five spice": (350, 10, 60, 10, 30, "seasoning"),
    "instant coffee": (241, 12, 41, 0.5, 0, "drink"),
    "rice paper": (333, 5.9, 83.5, 0.6, 1, "grain"),
    "rice noodles": (364, 6, 80, 0.6, 1.6, "grain"),
    "rice vermicelli": (364, 6, 80, 0.6, 1.6, "grain"),
    "noodles": (360, 11, 72, 2, 3, "grain"),
    "instant noodles": (450, 9, 60, 19, 2.5, "grain"),
    "puff pastry": (400, 4, 38, 26, 1.5, "grain"),
    "wrap": (300, 5, 50, 8, 3, "grain"),
    "tortilla": (300, 5, 50, 8, 3, "grain"),
}
for _name, (_kcal, _p, _c, _f, _fib, _cat) in _EXTRA_FOODS.items():
    FOOD_DATABASE.setdefault(_name, {
        "calories": _kcal, "protein": _p, "carbs": _c, "fat": _f, "fiber": _fib,
        "tags": [], "category": _cat,
    })

# ---------------------------------------------------------------------------
# Carbohydrate basis. UK labels and CoFID (the bundled dataset) state *available*
# carbohydrate, fibre listed separately; USDA and most US tables state *total*
# carbohydrate "by difference", fibre included (chia: 42 g total vs 7.8 g on a UK label).
# The curated values above came mostly from USDA, so their carbs are converted once here:
#   carbs       = available carbohydrate (UK basis, the default everywhere)
#   carbs_total = total carbohydrate incl. fibre (US basis)
# kcal are left exactly as sourced. Entries listed below were already on the UK basis.
# ---------------------------------------------------------------------------
_CARBS_ALREADY_AVAILABLE = frozenset({
    "weetabix",            # official UK Weetabix label
    "chickpeas (cooked)",  # CoFID, tinned + drained
    "psyllium husk",       # label value already excludes the ~80 g fibre
})
for _name, _entry in FOOD_DATABASE.items():
    _carbs = float(_entry.get("carbs") or 0)
    _fib = float(_entry.get("fiber") or 0)
    if _name in _CARBS_ALREADY_AVAILABLE:
        _entry["carbs_total"] = round(_carbs + _fib, 1)
    else:
        _entry["carbs_total"] = _carbs
        _entry["carbs"] = round(max(0.0, _carbs - _fib), 1)

# Exact-name redirects: "pepper" alone is the seasoning; the vegetable needs a qualifier.
FOOD_ALIASES = {
    "pepper": "black pepper",
    "ground pepper": "black pepper",
    "capsicum": "bell pepper",
    "red pepper": "bell pepper",
    "green pepper": "bell pepper",
    "yellow pepper": "bell pepper",
    "courgette": "zucchini",
}

# Words in a recipe line that mean the weight is cooked / tinned, not raw.
_COOKED_MARKERS = re.compile(r"\b(cooked|canned|tinned|drained|leftover|boiled|steamed)\b|\btin\b|\bcan of\b", re.I)

# Back-compat alias for nutrition router flat macros (no tags)
NUTRITION_PER_100G: Dict[str, Dict[str, float]] = {
    name: {
        "calories": entry["calories"],
        "protein": entry["protein"],
        "carbs": entry["carbs"],
        "fat": entry["fat"],
        "fiber": entry.get("fiber", 0) or 0,
        "carbs_total": entry["carbs_total"],
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


def _curated_result(db_name: str) -> Tuple[str, FoodEntry]:
    entry = dict(FOOD_DATABASE[db_name])
    entry.setdefault("source", "curated")
    entry.setdefault("source_id", db_name)
    entry.setdefault("state", "cooked" if db_name.endswith(" (cooked)") else "raw")
    return db_name, entry


_WHOLE_FOOD_CATEGORIES = frozenset({"vegetable", "fruit", "legume", "protein", "grain"})

_DATASET_COOKED_STATES = frozenset({"boiled", "steamed", "cooked", "canned", "fried", "roasted", "grilled", "baked", "toasted"})


def _dataset_label(name: str) -> str:
    """Plain display name for a dataset hit: the recipe's own words, minus prep notes."""
    text = re.sub(r"\([^)]*\)", " ", (name or "").lower())
    text = re.split(r"\s+or\s+|\s*/\s*|,", text)[0]
    return re.sub(r"\s+", " ", _normalize_name(text)).strip() or (name or "").strip().lower()


def find_food_in_dataset(
    name: str, *, cooked: Optional[bool] = None, sources: Optional[frozenset] = None
) -> Optional[Tuple[str, FoodEntry, Any]]:
    """Look an ingredient up in the bundled CoFID + USDA dataset only.

    Returns (label, entry, match) or None when there is no confident match. ``sources``
    limits the rows considered (``food_dataset.COFID_SOURCES`` / ``USDA_SOURCES``).
    """
    from utils import food_dataset

    if cooked is None:
        cooked = bool(_COOKED_MARKERS.search(name or ""))
    match = food_dataset.search(name or "", cooked=cooked, sources=sources)
    if match is None:
        return None
    label = _dataset_label(name)
    if cooked and match.state in _DATASET_COOKED_STATES and not _COOKED_MARKERS.search(label):
        label = f"{label} (cooked)"
    return label, match.entry(), match


# ---------------------------------------------------------------------------
# Regions. UK is the default everywhere: UK supermarket labels for processed foods, then UK
# CoFID for plain foods, then the curated table. "us" uses USDA FoodData Central first.
# Every entry carries both carb figures (``carbs`` available, ``carbs_total`` incl. fibre);
# callers pick the one their region displays.
# ---------------------------------------------------------------------------
DEFAULT_REGION = "uk"
REGIONS = ("uk", "us")


def normalize_region(region: Any) -> str:
    """"us" for US-style nutrition, otherwise "uk" (the default)."""
    text = str(region or "").strip().lower().replace("_", "-")
    return "us" if text in ("us", "usa", "u.s.", "u.s.a.", "en-us", "united states", "america") else DEFAULT_REGION


# Curated entries that keep their own value over the region's primary dataset (CoFID for
# "uk", USDA for "us"): the dataset's nearest row is a different food, or the curated value
# encodes something the dataset lacks / gets wrong for recipes. Plant-based / dairy-free
# names always use the curated (or UK label) entry - the datasets don't describe them.
_CURATED_OVERRIDES: Dict[str, str] = {
    "milk": "CoFID's nearest plain row is sheep's milk; curated is UK semi-skimmed",
    "yogurt": "dataset picks Greek-style; curated is plain whole-milk yoghurt",
    "yoghurt": "dataset picks Greek-style; curated is plain whole-milk yoghurt",
    "cream": "CoFID match is salad cream",
    "corn": "CoFID match is corn oil",
    "olives": "CoFID match is olive oil",
    "pickles": "CoFID match is sweet pickle (chutney)",
    "beans": "CoFID match is cluster beans; curated is generic dried beans",
    "biscuits": "CoFID match is iced biscuits",
    "apple": "CoFID match is cooking apples; recipes mean eating apples",
    "rice": "CoFID's plain-rice match is red rice; curated is white rice, raw",
    "quinoa": "CoFID quinoa (309 kcal) is ~15% under UK labels (360-375 kcal)",
    "brown rice (cooked)": "CoFID match is brown rice salad",
    "pasta (cooked)": "CoFID match is fresh pasta, boiled; curated is dried pasta, boiled",
    "pork (cooked)": "CoFID match is pork crackling",
    "chicken thigh (cooked)": "USDA match is chicken skin",
    "orange": "USDA match is orange peel",
    "lemon": "USDA match is lemon peel",
    "seitan": "neither dataset has seitan",
    "nutritional yeast": "neither dataset has it ('yeast' is baker's yeast)",
    "vegetable oil": "USDA match is palm kernel oil",
    "coconut aminos": "dataset match is coconut flesh",
    "artichoke hearts": "dataset match is ox heart",
    "bean sprouts": "dataset match is alfalfa sprouts",
    "chilli": "dataset match is chili powder; curated is fresh chilli",
    "ground coriander": "dataset match is fresh coriander leaves",
    "rice paper": "dataset match is raw rice",
    "cocoa nibs": "dataset match is cocoa powder",
    "xanthan gum": "dataset match is chewing gum",
    "poppyseeds": "dataset match is poppyseed oil",
    "low-fat cottage cheese": "dataset match is low-fat Monterey cheese",
    "skim milk": "dataset match is part-skim mozzarella",
    "flour": "CoFID's plain 'flour' match is gram flour; curated is plain wheat flour",
}

# Extra overrides for the US region (USDA's nearest row is a different food).
_US_CURATED_OVERRIDES: Dict[str, str] = {
    "tuna": "USDA match is tuna salad",
    "canned tuna": "USDA match is tuna canned in oil; curated is in water / brine",
    "tuna (cooked)": "USDA match is tuna canned in oil",
    "beef (cooked)": "USDA match is canned corned beef",
    "bread": "USDA match is cheese bread",
    "butter": "USDA match is anhydrous butter oil",
    "walnuts": "USDA match is walnut oil",
    "hazelnuts": "USDA match is hazelnut oil",
    "mozzarella": "USDA match is nonfat mozzarella",
    "lean beef mince": "USDA match is 80% lean (not lean) ground beef",
    "greek yogurt": "USDA match is nonfat Greek yogurt",
    "greek yoghurt": "USDA match is nonfat Greek yogurt",
}

# Description words that mean a cooked dish, for a line that asks for the raw food
# ("Chicken, breast, casseroled" is not raw chicken breast).
_COOKED_DESC_RE = re.compile(
    r"\b(casseroled|stewed|roasted|roast|grilled|fried|baked|boiled|cooked|microwaved|poached|braised|steamed)\b",
    re.I,
)

# A dataset value more than this factor away from the curated one is taken as a different
# food (e.g. "pork, cooked" -> crackling), and the curated entry is kept.
_MAX_PRIMARY_RATIO = 2.0


def _primary_sources(region: str) -> frozenset:
    from utils import food_dataset

    return food_dataset.USDA_SOURCES if region == "us" else food_dataset.COFID_SOURCES


def _region_dataset_hit(name: str, cooked: bool, region: str) -> Optional[Tuple[str, FoodEntry, Any]]:
    """Dataset lookup for a line nothing curated answers: the region's own source first."""
    hit = find_food_in_dataset(name, cooked=cooked, sources=_primary_sources(region))
    if hit is not None and (region == "us" or hit[2].score >= 0.9):
        return hit  # UK: a confident CoFID row beats a slightly better-scored USDA one
    return find_food_in_dataset(name, cooked=cooked)


def find_food(
    name: str, *, remote: bool = False, region: str = DEFAULT_REGION
) -> Optional[Tuple[str, FoodEntry]]:
    """Find best matching food entry. Returns (canonical_name, entry) or None.

    ``region="uk"`` (default):
      1. UK supermarket label medians (``utils.uk_labels``) for processed / branded foods
         (houmous, plant drinks, vegan cheese, pastes, tofu, tinned beans drained ...);
      2. UK CoFID 2021 for plain foods the curated table names, unless the curated entry is
         in ``_CURATED_OVERRIDES`` (dataset row is a different food / curated knows better)
         or the name is plant-based / dairy-free;
      3. the curated table (hand-tuned names, aliases, plant-based specifics);
      4. the bundled CoFID + USDA dataset for everything else;
      5. when remote=True, live Open Food Facts / USDA FDC lookups (no AI).
    ``region="us"``: USDA FDC (Foundation / SR Legacy) in place of 1-2, then the same fallbacks.

    Raw / as sold by default; cooked / tinned / drained in the line picks cooked values.
    Entries carry ``source`` / ``source_id`` / ``state`` and both carb figures: ``carbs``
    (available carbohydrate, UK basis) and ``carbs_total`` (incl. fibre, US basis).
    """
    region = normalize_region(region)
    cooked = bool(_COOKED_MARKERS.search(name or ""))
    cleaned = _normalize_name(name)
    if not cleaned:
        return None
    if region == "uk":
        from utils import uk_labels

        # The words as written first: "fresh breadcrumbs" is not "breadcrumbs".
        label_hit = uk_labels.find(name, cooked=cooked) or uk_labels.find(cleaned, cooked=cooked)
        if label_hit is not None:
            return label_hit
    cleaned = FOOD_ALIASES.get(cleaned, cleaned)
    plant_based = bool(re.search(r"\b(dairy-free|vegan|plant-based|non-dairy)\b", cleaned))

    def _primary(db_name: str, query: str) -> Optional[Tuple[str, FoodEntry]]:
        """The region's dataset (CoFID / USDA) for a plain food the curated table names."""
        overrides = {**_CURATED_OVERRIDES, **_US_CURATED_OVERRIDES} if region == "us" else _CURATED_OVERRIDES
        if plant_based or db_name in overrides:
            return None
        twin = f"{db_name} (cooked)"
        curated_name = twin if cooked and twin in FOOD_DATABASE else db_name
        if curated_name in overrides:
            return None
        hit = find_food_in_dataset(query, cooked=cooked, sources=_primary_sources(region))
        if hit is None:
            return None
        from utils import food_dataset

        match = hit[2]
        if match.score < 0.9:
            return None
        if cooked != (match.state in _DATASET_COOKED_STATES):
            return None  # raw line -> raw / as-sold row; cooked line -> cooked / tinned row
        if not cooked and _COOKED_DESC_RE.search(match.description):
            return None
        ident, _states = food_dataset._query_parts(query)
        covered = set(food_dataset.tokens(match.description))
        if not ident or not all((food_dataset._SYNONYMS.get(t, frozenset((t,))) & covered) for t in ident):
            return None
        mine = float(FOOD_DATABASE[curated_name].get("calories") or 0)
        theirs = float(match.values.get("calories") or 0)
        if (mine <= 0) != (theirs <= 0):
            return None
        if mine > 0 and max(mine, theirs) / min(mine, theirs) > _MAX_PRIMARY_RATIO:
            return None
        return curated_name, hit[1]  # stable canonical name ("egg", "rice (cooked)"), dataset values

    def _pick(db_name: str, aliased: bool = False) -> Tuple[str, FoodEntry]:
        if plant_based and not db_name.startswith("dairy-free") and f"dairy-free {db_name}" in FOOD_DATABASE:
            db_name = f"dairy-free {db_name}"  # "dairy-free unsweetened milk" is plant milk, not cow's
        primary = _primary(db_name, db_name if aliased else (name or db_name))
        if primary is not None:
            return primary
        twin = f"{db_name} (cooked)"
        if cooked and twin in FOOD_DATABASE:
            return _curated_result(twin)
        if cooked and not plant_based and FOOD_DATABASE[db_name].get("category") in _WHOLE_FOOD_CATEGORIES:
            # Curated values are raw; "tinned tomatoes" wants the canned figure if the
            # dataset has a confident one. (Not for products that are only sold tinned,
            # like coconut cream - their curated value already is the tinned one.)
            hit = _region_dataset_hit(name, True, region)
            if hit is not None and hit[2].score >= 0.9 and hit[2].state in _DATASET_COOKED_STATES:
                return hit[0], hit[1]
        return _curated_result(db_name)

    def _partial_or_dataset(db_name: str) -> Tuple[str, FoodEntry]:
        """Curated partial hit vs. a dataset match that explains the whole line."""
        if plant_based:
            return _pick(db_name)
        from utils import food_dataset

        ident, _states = food_dataset._query_parts(name or "")
        curated_words = set(food_dataset.tokens(db_name))
        if not ident or set(ident) <= curated_words:
            return _pick(db_name)
        hit = _region_dataset_hit(name, cooked, region)
        if hit is not None:
            match = hit[2]
            covered = set(food_dataset.tokens(match.description))
            explained = all(
                (food_dataset._SYNONYMS.get(t, frozenset((t,))) & covered) for t in ident
            )
            if explained and match.score >= 0.9:
                return hit[0], hit[1]
        return _pick(db_name)

    def _longest_match(text: str) -> Optional[str]:
        # Longest whole-word match: "coconut milk" beats "milk", "rice wine vinegar" beats
        # "rice", and "egg" never matches inside "eggplant".
        best: Optional[str] = None
        for db_name in FOOD_DATABASE:
            if db_name.endswith(" (cooked)"):
                continue
            if re.search(rf"(?<![\w-]){re.escape(db_name)}(?![\w-])", text) and (
                best is None or len(db_name) > len(best)
            ):
                best = db_name
        return best

    if cleaned in FOOD_DATABASE:
        return _pick(cleaned, aliased=cleaned != _normalize_name(name))
    # "nutritional yeast or dairy-free parmesan": the recipe's first choice counts.
    # ...and "tomatoes, diced": the prep note after a comma isn't the food.
    first_choice = re.split(r"\s+or\s+|\s*/\s*|\s*,", cleaned)[0].strip()
    def _singular(w: str) -> str:
        if len(w) > 4 and w.endswith("oes"):
            return w[:-2]  # potatoes, tomatoes
        if len(w) > 4 and w.endswith("ies"):
            return w[:-3] + "y"  # berries
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            return w[:-1]
        return w

    singular = " ".join(_singular(w) for w in first_choice.split())
    # The unstripped line too, so "dried oregano" / "dried apricots" find their own entries.
    original = re.split(r"\s+or\s+|\s*/\s*", (name or "").lower().strip())[0].strip()
    for text in (original, first_choice, singular, cleaned):
        if text in FOOD_ALIASES:
            return _pick(FOOD_ALIASES[text], aliased=True)
        best_name = _longest_match(text)
        if best_name:
            if best_name in (text, first_choice, singular):
                return _pick(best_name)
            return _partial_or_dataset(best_name)

    hit = _region_dataset_hit(name, cooked, region)
    if hit is not None:
        return hit[0], hit[1]

    if not remote:
        return None
    try:
        from services.nutrition_lookup import lookup_remote_nutrition

        remote_entry = lookup_remote_nutrition(cleaned, prefer_uk=region == "uk")
        if remote_entry:
            label = _normalize_name(str(remote_entry.get("label") or cleaned)) or cleaned
            carbs = float(remote_entry.get("carbs", 0) or 0)
            fiber = float(remote_entry.get("fiber", 0) or 0)
            if str(remote_entry.get("source") or "").startswith("usda"):
                carbs, carbs_total = max(0.0, carbs - fiber), carbs  # FDC: carbohydrate by difference
            else:
                carbs_total = carbs + fiber  # Open Food Facts: EU / UK labels state available carbs
            entry: FoodEntry = {
                "calories": remote_entry.get("calories", 0),
                "protein": remote_entry.get("protein", 0),
                "carbs": round(carbs, 1),
                "carbs_total": round(carbs_total, 1),
                "fat": remote_entry.get("fat", 0),
                "fiber": remote_entry.get("fiber", 0),
                "salt": remote_entry.get("salt", 0),
                "sugars": remote_entry.get("sugars", 0),
                "saturates": remote_entry.get("saturates", 0),
                "tags": list(remote_entry.get("tags") or ["remote"]),
                "category": remote_entry.get("category") or "remote",
                "source": remote_entry.get("source"),
                "source_id": remote_entry.get("source_id") or remote_entry.get("label"),
                "state": "raw",
            }
            return label, entry
    except Exception:
        return None
    return None


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
    # Count units — grams resolved via PIECE_WEIGHTS_G / COUNT_UNIT_DEFAULT_G.
    # Placeholder 1 keeps parse_ingredient_amount able to strip these tokens.
    "biscuit": 1,
    "biscuits": 1,
    "piece": 1,
    "pieces": 1,
    "slice": 1,
    "slices": 1,
    "clove": 1,
    "cloves": 1,
    "item": 1,
    "items": 1,
    "serving": 1,
    "servings": 1,
    "egg": 1,
    "eggs": 1,
    "can": 1,
    "cans": 1,
    "jar": 1,
    "jars": 1,
    "pack": 1,
    "packs": 1,
    "package": 1,
    "packages": 1,
    "bag": 1,
    "bags": 1,
    "box": 1,
    "boxes": 1,
    "stick": 1,
    "sticks": 1,
    "stalk": 1,
    "stalks": 1,
    "head": 1,
    "heads": 1,
    "ear": 1,
    "ears": 1,
    "sheet": 1,
    "sheets": 1,
    "leaf": 1,
    "leaves": 1,
    "sprig": 1,
    "sprigs": 1,
    "bunch": 1,
    "bunches": 1,
    "pinch": 1,
    "pinches": 1,
    "dash": 1,
    "dashes": 1,
    "drop": 1,
    "drops": 1,
    "fillet": 1,
    "fillets": 1,
    "breast": 1,
    "breasts": 1,
    "thigh": 1,
    "thighs": 1,
}

# Count / discrete items → grams each (longest-key match wins).
# Without this, "2 Weetabix" / "4 eggs" were treated as qty × 100g.
PIECE_WEIGHTS_G = {
    # Breakfast cereals / bakery
    "weetabix": 18.75,  # 2 biscuits = 37.5g (official)
    "shredded wheat": 22.0,
    "rice cake": 9.0,
    "cracker": 5.0,
    "digestive": 15.0,
    "biscuit": 12.0,
    "cookie": 15.0,
    "slice bread": 30.0,
    "bread": 30.0,
    "bagel": 95.0,
    "tortilla": 45.0,
    "wrap": 45.0,
    "pita": 60.0,
    "english muffin": 57.0,
    "croissant": 58.0,
    # Eggs / dairy pieces
    "egg white": 33.0,
    "egg": 50.0,
    "stick butter": 113.0,  # US stick
    "butter": 10.0,  # knobs when counted without "stick"
    # Fruit (edible portion averages)
    "banana": 118.0,
    "apple": 182.0,
    "orange": 131.0,
    "lemon": 58.0,
    "lime": 67.0,
    "strawberry": 12.0,
    "blueberry": 1.5,
    "avocado": 150.0,
    "pear": 178.0,
    "peach": 150.0,
    "mango": 200.0,
    "kiwi": 69.0,
    "grape": 5.0,
    "date": 7.5,
    "fig": 50.0,
    # Veg counted as pieces
    "clove garlic": 3.0,
    "garlic": 3.0,
    "onion": 110.0,
    "shallot": 25.0,
    "tomato": 123.0,
    "potato": 173.0,
    "sweet potato": 130.0,
    "carrot": 61.0,
    "bell pepper": 120.0,
    "pepper": 120.0,  # when counted (not ground spice with mass unit)
    "cucumber": 300.0,
    "zucchini": 200.0,
    "courgette": 200.0,
    "mushroom": 18.0,
    "broccoli": 150.0,  # small head / florets bunch approx when counted
    "cauliflower": 150.0,
    "corn": 90.0,  # ear
    "asparagus": 12.0,  # spear
    "celery": 40.0,  # stalk
    "spring onion": 15.0,
    "scallion": 15.0,
    "lettuce": 150.0,  # small head when counted
    "cabbage": 150.0,
    # Protein pieces / fillets (typical retail unit)
    "chicken breast": 175.0,
    "chicken thigh": 120.0,
    "turkey breast": 175.0,
    "salmon": 150.0,
    "cod": 150.0,
    "tuna steak": 150.0,
    "shrimp": 8.0,
    "prawn": 8.0,
    "fillet": 150.0,
    "tofu": 100.0,  # when counted as blocks/pieces without mass
    # Canned / packaged defaults keyed by food
    "canned tuna": 112.0,  # drained can approx
    "tuna": 112.0,
    "chickpeas": 240.0,  # drained can when "1 can"
    "black beans": 240.0,
    "kidney beans": 240.0,
    "beans": 240.0,
    "lentils": 240.0,
    # Nuts (per piece when counted)
    "almond": 1.2,
    "walnut": 4.0,
    "cashew": 1.6,
    "peanut": 1.0,
}

# When the unit is a count word but the food has no PIECE_WEIGHTS entry,
# use a conservative per-unit default instead of qty × 100g.
COUNT_UNIT_DEFAULT_G = {
    "biscuit": 12.0,
    "piece": 50.0,
    "slice": 30.0,
    "clove": 3.0,
    "item": 50.0,
    "serving": 100.0,
    "egg": 50.0,
    "can": 240.0,  # drained canned goods typical
    "jar": 200.0,
    "pack": 50.0,
    "package": 50.0,
    "bag": 100.0,
    "box": 100.0,
    "stick": 50.0,
    "stalk": 40.0,
    "head": 400.0,
    "ear": 90.0,
    "sheet": 20.0,
    "leaf": 1.0,
    "sprig": 2.0,
    "bunch": 60.0,
    "pinch": 0.3,
    "dash": 0.3,
    "drop": 0.05,
    "fillet": 150.0,
    "breast": 175.0,
    "thigh": 120.0,
}

COUNT_UNITS = frozenset(
    {
        "biscuit",
        "biscuits",
        "piece",
        "pieces",
        "slice",
        "slices",
        "clove",
        "cloves",
        "item",
        "items",
        "serving",
        "servings",
        "egg",
        "eggs",
        "can",
        "cans",
        "jar",
        "jars",
        "pack",
        "packs",
        "package",
        "packages",
        "bag",
        "bags",
        "box",
        "boxes",
        "stick",
        "sticks",
        "stalk",
        "stalks",
        "head",
        "heads",
        "ear",
        "ears",
        "sheet",
        "sheets",
        "leaf",
        "leaves",
        "sprig",
        "sprigs",
        "bunch",
        "bunches",
        "pinch",
        "pinches",
        "dash",
        "dashes",
        "drop",
        "drops",
        "fillet",
        "fillets",
        "breast",
        "breasts",
        "thigh",
        "thighs",
    }
)

# Size adjectives stripped so "1 large egg" → unit=egg, name=…
SIZE_WORDS = frozenset(
    {
        "large",
        "medium",
        "small",
        "whole",
        "extra-large",
        "extra large",
        "xl",
        "jumbo",
        "mini",
    }
)

MASS_VOLUME_UNITS = frozenset(
    {
        "g",
        "gram",
        "grams",
        "kg",
        "kilogram",
        "oz",
        "ounce",
        "ounces",
        "lb",
        "pound",
        "pounds",
        "cup",
        "cups",
        "tbsp",
        "tablespoon",
        "tablespoons",
        "tsp",
        "teaspoon",
        "teaspoons",
        "ml",
        "l",
        "liter",
        "liters",
    }
)


def piece_weight_grams(food_name: str) -> Optional[float]:
    """Return grams-per-item for known count foods, else None."""
    cleaned = _normalize_name(food_name or "")
    if not cleaned:
        return None
    best_key = ""
    best_g: Optional[float] = None
    for key, grams in PIECE_WEIGHTS_G.items():
        if key in cleaned and len(key) > len(best_key):
            best_key = key
            best_g = grams
    return best_g


def _normalize_count_unit(unit_key: str) -> str:
    u = (unit_key or "").strip().lower()
    if u.endswith("es") and u[:-2] + "e" in COUNT_UNIT_DEFAULT_G:
        # leaves → leaf handled below; boxes → box
        pass
    if u in COUNT_UNIT_DEFAULT_G:
        return u
    singular = u.rstrip("s")
    if singular in COUNT_UNIT_DEFAULT_G:
        return singular
    if u.endswith("ies"):
        alt = u[:-3] + "y"  # berries-like unused
        if alt in COUNT_UNIT_DEFAULT_G:
            return alt
    if u == "leaves":
        return "leaf"
    if u == "loaves":
        return "loaf"
    return singular or u


def grams_from_parsed(
    parsed: Dict[str, Any],
    *,
    food_name: Optional[str] = None,
) -> float:
    """Convert a parsed ingredient amount into grams for nutrition scaling.

    - Mass/volume units use UNIT_CONVERSIONS.
    - Count units (biscuit, piece, can, egg, …) and bare counts ("2 Weetabix",
      "4 eggs") use PIECE_WEIGHTS_G when the food is known.
    - Known count units without a food-specific weight use COUNT_UNIT_DEFAULT_G
      (never qty × 100g).
    - Bare counts for unknown foods still default to qty × 100g (legacy).
    """
    qty = parsed.get("quantity")
    unit_raw = (parsed.get("unit") or "").strip().lower()
    unit = unit_raw.rstrip("s") if unit_raw else ""
    unit_key = unit_raw or unit
    search_name = " ".join(
        p for p in (food_name or "", parsed.get("name") or "") if p
    )
    piece_g = piece_weight_grams(search_name)

    if qty is None:
        return float(piece_g) if piece_g is not None else 100.0

    if unit_key in MASS_VOLUME_UNITS or unit in MASS_VOLUME_UNITS:
        conv = UNIT_CONVERSIONS.get(unit_key) or UNIT_CONVERSIONS.get(unit) or 1
        return float(qty) * float(conv)

    is_count = (not unit_key) or unit_key in COUNT_UNITS or unit in COUNT_UNITS
    if is_count and piece_g is not None:
        return float(qty) * float(piece_g)

    if unit_key and (unit_key in COUNT_UNITS or unit in COUNT_UNITS):
        default_key = _normalize_count_unit(unit_key)
        default_g = COUNT_UNIT_DEFAULT_G.get(default_key) or COUNT_UNIT_DEFAULT_G.get(unit)
        if default_g is not None:
            return float(qty) * float(default_g)

    if unit_key and unit_key not in COUNT_UNITS and unit not in COUNT_UNITS:
        # Unknown non-count unit (rare) — prefer piece weight, else qty×100
        if piece_g is not None:
            return float(qty) * float(piece_g)
        return float(qty) * 100.0

    # Bare count without a known piece weight
    return float(qty) * 100.0


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
        # Drop size adjectives: "1 large egg" → "egg …"
        for size in sorted(SIZE_WORDS, key=len, reverse=True):
            if remaining == size or remaining.startswith(size + " "):
                remaining = remaining[len(size):].strip()
                break
        # Prefer longer unit tokens first (tablespoons before tbsp, biscuits before …)
        for unit_name in sorted(UNIT_CONVERSIONS.keys(), key=len, reverse=True):
            if remaining == unit_name or remaining.startswith(unit_name + " "):
                unit = unit_name
                remaining = remaining[len(unit_name):].strip()
                break
        # "4 eggs" with nothing after → unit=eggs, name=egg
        if unit in ("egg", "eggs") and not remaining:
            remaining = "egg"
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
    Count foods (e.g. Weetabix biscuits) use piece weights; mass/volume units
    scale normally. Unknown bare counts still default to qty × 100g.
    """
    results = []
    unknown = []
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0}

    for ingredient in ingredients:
        if isinstance(ingredient, dict):
            amount = ingredient.get("amount", "")
            unit = ingredient.get("unit", "")
            name = ingredient.get("name", "")
            amount_s = str(amount).strip().lower() if amount is not None else ""
            name_s = str(name).strip().lower() if name is not None else ""
            # Skip seasoning phrases with no measurable quantity
            if amount_s in ("to taste", "as needed", "optional", "pinch") or (
                not amount_s and re.search(r"\b(to taste|as needed|optional)\b", name_s)
            ):
                continue
            ingredient_str = f"{amount} {unit} {name}".strip()
        else:
            ingredient_str = str(ingredient)
            if re.search(r"\b(to taste|as needed|optional)\b", ingredient_str.lower()) and not re.match(
                r"^\d", ingredient_str.strip()
            ):
                continue

        parsed = parse_ingredient_amount(ingredient_str)
        match = find_food(parsed["name"], remote=True)
        if not match:
            unknown.append(ingredient_str)
            continue
        canonical, entry = match
        macros = macros_only(entry)

        grams = grams_from_parsed(parsed, food_name=canonical)
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
