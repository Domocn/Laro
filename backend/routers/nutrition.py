"""
Nutrition Router - Calculate and manage nutritional information for recipes
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
from dependencies import get_current_user, recipe_repository, custom_ingredient_repository
from datetime import datetime, timezone
import uuid
import re

router = APIRouter(prefix="/nutrition", tags=["Nutrition"])

# =============================================================================
# NUTRITION DATABASE (Common ingredients per 100g)
# =============================================================================

NUTRITION_DATABASE = {
    # Proteins
    "chicken breast": {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6, "fiber": 0},
    "chicken thigh": {"calories": 209, "protein": 26, "carbs": 0, "fat": 10.9, "fiber": 0},
    "beef": {"calories": 250, "protein": 26, "carbs": 0, "fat": 15, "fiber": 0},
    "ground beef": {"calories": 254, "protein": 17, "carbs": 0, "fat": 20, "fiber": 0},
    "pork": {"calories": 242, "protein": 27, "carbs": 0, "fat": 14, "fiber": 0},
    "salmon": {"calories": 208, "protein": 20, "carbs": 0, "fat": 13, "fiber": 0},
    "tuna": {"calories": 132, "protein": 29, "carbs": 0, "fat": 1, "fiber": 0},
    "shrimp": {"calories": 99, "protein": 24, "carbs": 0.2, "fat": 0.3, "fiber": 0},
    "egg": {"calories": 155, "protein": 13, "carbs": 1.1, "fat": 11, "fiber": 0},
    "tofu": {"calories": 76, "protein": 8, "carbs": 1.9, "fat": 4.8, "fiber": 0.3},

    # Dairy
    "milk": {"calories": 42, "protein": 3.4, "carbs": 5, "fat": 1, "fiber": 0},
    "cheese": {"calories": 402, "protein": 25, "carbs": 1.3, "fat": 33, "fiber": 0},
    "butter": {"calories": 717, "protein": 0.9, "carbs": 0.1, "fat": 81, "fiber": 0},
    "cream": {"calories": 340, "protein": 2.1, "carbs": 2.8, "fat": 36, "fiber": 0},
    "yogurt": {"calories": 59, "protein": 10, "carbs": 3.6, "fat": 0.7, "fiber": 0},

    # Grains
    "rice": {"calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3, "fiber": 0.4},
    "pasta": {"calories": 131, "protein": 5, "carbs": 25, "fat": 1.1, "fiber": 1.8},
    "bread": {"calories": 265, "protein": 9, "carbs": 49, "fat": 3.2, "fiber": 2.7},
    "flour": {"calories": 364, "protein": 10, "carbs": 76, "fat": 1, "fiber": 2.7},
    "oats": {"calories": 389, "protein": 17, "carbs": 66, "fat": 7, "fiber": 11},
    "quinoa": {"calories": 120, "protein": 4.4, "carbs": 21, "fat": 1.9, "fiber": 2.8},

    # Vegetables
    "potato": {"calories": 77, "protein": 2, "carbs": 17, "fat": 0.1, "fiber": 2.2},
    "carrot": {"calories": 41, "protein": 0.9, "carbs": 10, "fat": 0.2, "fiber": 2.8},
    "broccoli": {"calories": 34, "protein": 2.8, "carbs": 7, "fat": 0.4, "fiber": 2.6},
    "spinach": {"calories": 23, "protein": 2.9, "carbs": 3.6, "fat": 0.4, "fiber": 2.2},
    "tomato": {"calories": 18, "protein": 0.9, "carbs": 3.9, "fat": 0.2, "fiber": 1.2},
    "onion": {"calories": 40, "protein": 1.1, "carbs": 9.3, "fat": 0.1, "fiber": 1.7},
    "garlic": {"calories": 149, "protein": 6.4, "carbs": 33, "fat": 0.5, "fiber": 2.1},
    "bell pepper": {"calories": 31, "protein": 1, "carbs": 6, "fat": 0.3, "fiber": 2.1},
    "mushroom": {"calories": 22, "protein": 3.1, "carbs": 3.3, "fat": 0.3, "fiber": 1},
    "zucchini": {"calories": 17, "protein": 1.2, "carbs": 3.1, "fat": 0.3, "fiber": 1},
    "cucumber": {"calories": 15, "protein": 0.7, "carbs": 3.6, "fat": 0.1, "fiber": 0.5},
    "lettuce": {"calories": 15, "protein": 1.4, "carbs": 2.9, "fat": 0.2, "fiber": 1.3},
    "cabbage": {"calories": 25, "protein": 1.3, "carbs": 5.8, "fat": 0.1, "fiber": 2.5},
    "corn": {"calories": 86, "protein": 3.2, "carbs": 19, "fat": 1.2, "fiber": 2.7},
    "peas": {"calories": 81, "protein": 5.4, "carbs": 14, "fat": 0.4, "fiber": 5.1},
    "beans": {"calories": 127, "protein": 8.7, "carbs": 22, "fat": 0.5, "fiber": 6.4},
    "lentils": {"calories": 116, "protein": 9, "carbs": 20, "fat": 0.4, "fiber": 7.9},

    # Fruits
    "apple": {"calories": 52, "protein": 0.3, "carbs": 14, "fat": 0.2, "fiber": 2.4},
    "banana": {"calories": 89, "protein": 1.1, "carbs": 23, "fat": 0.3, "fiber": 2.6},
    "orange": {"calories": 47, "protein": 0.9, "carbs": 12, "fat": 0.1, "fiber": 2.4},
    "lemon": {"calories": 29, "protein": 1.1, "carbs": 9.3, "fat": 0.3, "fiber": 2.8},
    "strawberry": {"calories": 32, "protein": 0.7, "carbs": 7.7, "fat": 0.3, "fiber": 2},
    "blueberry": {"calories": 57, "protein": 0.7, "carbs": 14, "fat": 0.3, "fiber": 2.4},
    "avocado": {"calories": 160, "protein": 2, "carbs": 8.5, "fat": 15, "fiber": 6.7},

    # Oils & Fats
    "olive oil": {"calories": 884, "protein": 0, "carbs": 0, "fat": 100, "fiber": 0},
    "vegetable oil": {"calories": 884, "protein": 0, "carbs": 0, "fat": 100, "fiber": 0},
    "coconut oil": {"calories": 862, "protein": 0, "carbs": 0, "fat": 100, "fiber": 0},

    # Nuts & Seeds
    "almonds": {"calories": 579, "protein": 21, "carbs": 22, "fat": 50, "fiber": 12},
    "walnuts": {"calories": 654, "protein": 15, "carbs": 14, "fat": 65, "fiber": 6.7},
    "peanuts": {"calories": 567, "protein": 26, "carbs": 16, "fat": 49, "fiber": 8.5},
    "cashews": {"calories": 553, "protein": 18, "carbs": 30, "fat": 44, "fiber": 3.3},

    # Sweeteners
    "sugar": {"calories": 387, "protein": 0, "carbs": 100, "fat": 0, "fiber": 0},
    "honey": {"calories": 304, "protein": 0.3, "carbs": 82, "fat": 0, "fiber": 0.2},
    "maple syrup": {"calories": 260, "protein": 0, "carbs": 67, "fat": 0, "fiber": 0},

    # Condiments
    "soy sauce": {"calories": 53, "protein": 8, "carbs": 4.9, "fat": 0, "fiber": 0.8},
    "mayonnaise": {"calories": 680, "protein": 1, "carbs": 0.6, "fat": 75, "fiber": 0},
    "ketchup": {"calories": 112, "protein": 1.7, "carbs": 26, "fat": 0.4, "fiber": 0.3},
    "mustard": {"calories": 66, "protein": 4.4, "carbs": 5.8, "fat": 4, "fiber": 3.3},
}

# Unit conversions to grams
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

# =============================================================================
# MODELS
# =============================================================================

class IngredientNutrition(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None

class RecipeNutritionRequest(BaseModel):
    ingredients: List[str]
    servings: Optional[int] = 1

class CustomIngredient(BaseModel):
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    fiber: Optional[float] = 0

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_ingredient(ingredient_str: str) -> Dict:
    """Parse an ingredient string into quantity, unit, and name"""
    ingredient_str = ingredient_str.lower().strip()

    quantity = None
    unit = None
    name = ingredient_str

    fraction_match = re.match(r'^(\d+/\d+|\d+\s+\d+/\d+|\d+\.?\d*)\s*', ingredient_str)
    if fraction_match:
        qty_str = fraction_match.group(1).strip()
        if ' ' in qty_str:
            parts = qty_str.split()
            whole = float(parts[0])
            frac_parts = parts[1].split('/')
            quantity = whole + float(frac_parts[0]) / float(frac_parts[1])
        elif '/' in qty_str:
            parts = qty_str.split('/')
            quantity = float(parts[0]) / float(parts[1])
        else:
            quantity = float(qty_str)

        remaining = ingredient_str[fraction_match.end():].strip()

        for unit_name, conversion in UNIT_CONVERSIONS.items():
            if remaining.startswith(unit_name + ' ') or remaining.startswith(unit_name + 's '):
                unit = unit_name.rstrip('s')
                remaining = remaining[len(unit_name):].strip()
                if remaining.startswith('s '):
                    remaining = remaining[2:]
                elif remaining.startswith(' '):
                    remaining = remaining[1:]
                break

        name = remaining

    return {
        "quantity": quantity,
        "unit": unit,
        "name": name
    }

def find_matching_ingredient(name: str) -> Optional[Dict]:
    """Find the best matching ingredient in the database"""
    name = name.lower().strip()

    prefixes_to_remove = ["fresh ", "dried ", "chopped ", "diced ", "minced ", "sliced ", "cooked ", "raw ", "frozen ", "canned "]
    for prefix in prefixes_to_remove:
        if name.startswith(prefix):
            name = name[len(prefix):]

    if name in NUTRITION_DATABASE:
        return NUTRITION_DATABASE[name]

    for db_name, nutrition in NUTRITION_DATABASE.items():
        if db_name in name or name in db_name:
            return nutrition

    return None

def calculate_nutrition(parsed: Dict) -> Optional[Dict]:
    """Calculate nutrition for a parsed ingredient"""
    nutrition = find_matching_ingredient(parsed["name"])
    if not nutrition:
        return None

    grams = 100

    if parsed["quantity"] is not None:
        if parsed["unit"]:
            unit_grams = UNIT_CONVERSIONS.get(parsed["unit"], 1)
            grams = parsed["quantity"] * unit_grams
        else:
            grams = parsed["quantity"] * 100

    scale = grams / 100

    return {
        "ingredient": parsed["name"],
        "amount_grams": round(grams, 1),
        "calories": round(nutrition["calories"] * scale, 1),
        "protein": round(nutrition["protein"] * scale, 1),
        "carbs": round(nutrition["carbs"] * scale, 1),
        "fat": round(nutrition["fat"] * scale, 1),
        "fiber": round(nutrition["fiber"] * scale, 1),
    }

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/calculate")
async def calculate_recipe_nutrition(
    data: RecipeNutritionRequest,
    user: dict = Depends(get_current_user)
):
    """Calculate nutrition for a list of ingredients"""
    results = []
    unknown_ingredients = []

    totals = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0}

    for ingredient in data.ingredients:
        parsed = parse_ingredient(ingredient)
        nutrition = calculate_nutrition(parsed)

        if nutrition:
            results.append(nutrition)
            totals["calories"] += nutrition["calories"]
            totals["protein"] += nutrition["protein"]
            totals["carbs"] += nutrition["carbs"]
            totals["fat"] += nutrition["fat"]
            totals["fiber"] += nutrition["fiber"]
        else:
            unknown_ingredients.append(ingredient)

    for key in totals:
        totals[key] = round(totals[key], 1)

    per_serving = {k: round(v / data.servings, 1) for k, v in totals.items()}

    return {
        "ingredients": results,
        "unknown_ingredients": unknown_ingredients,
        "totals": totals,
        "per_serving": per_serving,
        "servings": data.servings
    }

@router.get("/recipe/{recipe_id}")
async def get_recipe_nutrition(
    recipe_id: str,
    user: dict = Depends(get_current_user)
):
    """Get nutritional information for a recipe"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ingredients = recipe.get("ingredients", [])
    servings = recipe.get("servings", 1)

    results = []
    unknown_ingredients = []

    totals = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0}

    for ingredient in ingredients:
        if isinstance(ingredient, dict):
            ingredient_str = f"{ingredient.get('amount', '')} {ingredient.get('unit', '')} {ingredient.get('name', '')}".strip()
        else:
            ingredient_str = ingredient

        parsed = parse_ingredient(ingredient_str)
        nutrition = calculate_nutrition(parsed)

        if nutrition:
            results.append(nutrition)
            totals["calories"] += nutrition["calories"]
            totals["protein"] += nutrition["protein"]
            totals["carbs"] += nutrition["carbs"]
            totals["fat"] += nutrition["fat"]
            totals["fiber"] += nutrition["fiber"]
        else:
            unknown_ingredients.append(ingredient_str if isinstance(ingredient, dict) else ingredient)

    for key in totals:
        totals[key] = round(totals[key], 1)

    per_serving = {k: round(v / servings, 1) for k, v in totals.items()}

    return {
        "recipe_id": recipe_id,
        "recipe_title": recipe.get("title"),
        "ingredients": results,
        "unknown_ingredients": unknown_ingredients,
        "totals": totals,
        "per_serving": per_serving,
        "servings": servings
    }

@router.post("/recipe/{recipe_id}/save")
async def save_recipe_nutrition(
    recipe_id: str,
    user: dict = Depends(get_current_user)
):
    """Calculate and save nutrition info to a recipe"""
    nutrition_data = await get_recipe_nutrition(recipe_id, user)

    await recipe_repository.update(recipe_id, {
        "nutrition": {
            "per_serving": nutrition_data["per_serving"],
            "totals": nutrition_data["totals"],
            "calculated_at": datetime.now(timezone.utc).isoformat()
        }
    })

    return {
        "message": "Nutrition saved to recipe",
        "nutrition": nutrition_data
    }

@router.get("/ingredients")
async def list_known_ingredients(user: dict = Depends(get_current_user)):
    """List all ingredients in the nutrition database"""
    return {
        "ingredients": list(NUTRITION_DATABASE.keys()),
        "count": len(NUTRITION_DATABASE)
    }

@router.get("/ingredient/{name}")
async def get_ingredient_nutrition(
    name: str,
    user: dict = Depends(get_current_user)
):
    """Get nutrition info for a specific ingredient"""
    name = name.lower().strip()

    if name in NUTRITION_DATABASE:
        return {
            "name": name,
            "per_100g": NUTRITION_DATABASE[name]
        }

    for db_name, nutrition in NUTRITION_DATABASE.items():
        if db_name in name or name in db_name:
            return {
                "name": db_name,
                "matched_from": name,
                "per_100g": nutrition
            }

    raise HTTPException(status_code=404, detail="Ingredient not found")

@router.post("/custom-ingredient")
async def add_custom_ingredient(
    data: CustomIngredient,
    user: dict = Depends(get_current_user)
):
    """Add a custom ingredient to the user's personal database"""
    ingredient_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": data.name.lower().strip(),
        "calories": data.calories,
        "protein": data.protein,
        "carbs": data.carbs,
        "fat": data.fat,
        "fiber": data.fiber,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await custom_ingredient_repository.create(ingredient_doc)

    return {"message": "Custom ingredient added", "id": ingredient_doc["id"]}
