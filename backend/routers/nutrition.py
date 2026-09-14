"""
Nutrition Router - Calculate and manage nutritional information for recipes
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
from dependencies import get_current_user, recipe_repository, custom_ingredient_repository
from utils.authorization import require_recipe_view, require_recipe_edit
from utils.recipe_fields import nutrition_to_columns
from datetime import datetime, timezone
import uuid
import re

router = APIRouter(prefix="/nutrition", tags=["Nutrition"])

# =============================================================================
# NUTRITION DATABASE — curated food DB (utils.food_db)
# =============================================================================

from utils.food_db import NUTRITION_PER_100G, UNIT_CONVERSIONS, find_food

NUTRITION_DATABASE = NUTRITION_PER_100G

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
    """Parse an ingredient string into quantity, unit, and name (OSS parser first)."""
    try:
        from utils.ingredient_parse import parse_ingredient_line

        parsed = parse_ingredient_line(ingredient_str)
        return {
            "quantity": parsed.get("quantity"),
            "unit": parsed.get("unit") or None,
            "name": (parsed.get("name") or ingredient_str).lower().strip(),
        }
    except Exception:
        pass

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
    """Find the best matching ingredient in the food database (remote OFF/USDA fallback)."""
    match = find_food(name, remote=True)
    if not match:
        return None
    _canonical, entry = match
    return {
        "calories": entry["calories"],
        "protein": entry["protein"],
        "carbs": entry["carbs"],
        "fat": entry["fat"],
        "fiber": entry.get("fiber", 0) or 0,
    }

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
    from services.nutrition_lookup import UK_REFERENCE_INTAKES, uk_percent_ri

    return {
        "ingredients": results,
        "unknown_ingredients": unknown_ingredients,
        "totals": totals,
        "per_serving": per_serving,
        "servings": data.servings,
        "uk_percent_ri_per_serving": uk_percent_ri(per_serving),
        "uk_reference_intakes": UK_REFERENCE_INTAKES,
    }

@router.get("/recipe/{recipe_id}")
async def get_recipe_nutrition(
    recipe_id: str,
    recalculate: bool = False,
    user: dict = Depends(get_current_user)
):
    """Get nutritional information for a recipe.

    Prefer macros already saved on the recipe (e.g. from a meal-plan PDF).
    Pass recalculate=true to force the ingredient-table estimate instead.
    """
    from utils.recipe_fields import columns_to_nutrition

    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    require_recipe_view(user, recipe)

    servings = recipe.get("servings", 1) or 1

    if not recalculate:
        saved = columns_to_nutrition(recipe)
        if saved and saved.get("calories") is not None:
            per_serving = {
                "calories": float(saved.get("calories") or 0),
                "protein": float(saved.get("protein") or 0),
                "carbs": float(saved.get("carbs") or 0),
                "fat": float(saved.get("fat") or 0),
                "fiber": float(saved.get("fiber") or 0),
            }
            totals = {k: round(v * servings, 1) for k, v in per_serving.items()}
            from services.nutrition_lookup import UK_REFERENCE_INTAKES, uk_percent_ri

            return {
                "recipe_id": recipe_id,
                "recipe_title": recipe.get("title"),
                "ingredients": [],
                "unknown_ingredients": [],
                "totals": totals,
                "per_serving": per_serving,
                "servings": servings,
                "source": "saved",
                "uk_percent_ri_per_serving": uk_percent_ri(per_serving),
                "uk_reference_intakes": UK_REFERENCE_INTAKES,
            }

    ingredients = recipe.get("ingredients", [])

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
    from services.nutrition_lookup import UK_REFERENCE_INTAKES, uk_percent_ri

    return {
        "recipe_id": recipe_id,
        "recipe_title": recipe.get("title"),
        "ingredients": results,
        "unknown_ingredients": unknown_ingredients,
        "totals": totals,
        "per_serving": per_serving,
        "servings": servings,
        "source": "estimated",
        "uk_percent_ri_per_serving": uk_percent_ri(per_serving),
        "uk_reference_intakes": UK_REFERENCE_INTAKES,
    }

@router.post("/recipe/{recipe_id}/save")
async def save_recipe_nutrition(
    recipe_id: str,
    user: dict = Depends(get_current_user)
):
    """Calculate and save nutrition info to a recipe"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    require_recipe_edit(user, recipe)

    # Force ingredient-table estimate when explicitly saving a recalculation
    nutrition_data = await get_recipe_nutrition(recipe_id, recalculate=True, user=user)

    # Persist per-serving values into flat nutrition_* columns
    await recipe_repository.update_recipe(
        recipe_id,
        nutrition_to_columns(nutrition_data.get("per_serving")),
    )

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

@router.get("/food-db")
async def list_food_db(
    high_protein: bool = False,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """
    List curated food-DB entries used for AI recipe ideas (macros per 100g).
    Approximate planning values — not medical advice.
    """
    from utils.food_db import FOOD_DATABASE, HIGH_PROTEIN_THRESHOLD, retrieve_foods_for_ai
    from dependencies import user_preferences_repository

    prefs = await user_preferences_repository.find_by_user(user["id"]) or {}
    if high_protein:
        foods = retrieve_foods_for_ai(prefs, limit=min(limit, 80), seed=user["id"])
        return {
            "foods": foods,
            "count": len(foods),
            "disclaimer": "Approximate food-composition averages for meal planning — not medical advice.",
        }

    items = []
    for name, entry in sorted(FOOD_DATABASE.items()):
        protein = float(entry.get("protein") or 0)
        if high_protein and protein < HIGH_PROTEIN_THRESHOLD and "high-protein" not in (entry.get("tags") or []):
            continue
        items.append({
            "name": name,
            "per_100g": {
                "calories": entry["calories"],
                "protein": entry["protein"],
                "carbs": entry["carbs"],
                "fat": entry["fat"],
                "fiber": entry.get("fiber", 0) or 0,
            },
            "tags": list(entry.get("tags") or []),
            "category": entry.get("category", "other"),
        })
        if len(items) >= min(limit, 200):
            break

    return {
        "foods": items,
        "count": len(items),
        "disclaimer": "Approximate food-composition averages for meal planning — not medical advice.",
    }

@router.get("/ingredient/{name}")
async def get_ingredient_nutrition(
    name: str,
    user: dict = Depends(get_current_user)
):
    """Get nutrition info for a specific ingredient (curated DB, then free OFF/USDA)."""
    match = find_food(name, remote=True)
    if match:
        db_name, entry = match
        per_100g = {
            "calories": entry["calories"],
            "energy_kcal": entry["calories"],
            "energy_kj": round(float(entry["calories"]) * 4.184, 1),
            "protein": entry["protein"],
            "carbs": entry["carbs"],
            "fat": entry["fat"],
            "fiber": entry.get("fiber", 0) or 0,
            "fibre": entry.get("fiber", 0) or 0,
            "salt": entry.get("salt", 0) or 0,
            "sugars": entry.get("sugars", 0) or 0,
            "saturates": entry.get("saturates", 0) or 0,
        }
        from services.nutrition_lookup import (
            UK_REFERENCE_INTAKES,
            uk_percent_ri,
            uk_traffic_lights_per_100g,
        )

        return {
            "name": db_name,
            "matched_from": name.lower().strip() if db_name != name.lower().strip() else None,
            "per_100g": per_100g,
            "uk_percent_ri_per_100g": uk_percent_ri(per_100g),
            "uk_traffic_lights_per_100g": uk_traffic_lights_per_100g(per_100g),
            "uk_reference_intakes": UK_REFERENCE_INTAKES,
            "allergens": list(entry.get("allergens") or []),
            "traces": list(entry.get("traces") or []),
            "categories": list(entry.get("categories") or []),
            "suggested_aisle": entry.get("suggested_aisle"),
            "tags": list(entry.get("tags") or []),
            "source": entry.get("source") or "food_db",
            "disclaimer": (
                "Approximate open-data / curated values for meal planning. "
                "%RI and traffic lights use UK FSA guidance — not personalised medical advice."
            ),
        }

    raise HTTPException(status_code=404, detail="Ingredient not found")


@router.get("/barcode/{code}")
async def get_barcode_nutrition(
    code: str,
    user: dict = Depends(get_current_user),
):
    """Lookup product nutrition by barcode via free Open Food Facts (UK first)."""
    from services.nutrition_lookup import (
        UK_REFERENCE_INTAKES,
        lookup_barcode_nutrition,
        uk_percent_ri,
        uk_traffic_lights_per_100g,
    )

    entry = lookup_barcode_nutrition(code, prefer_uk=True)
    if not entry:
        raise HTTPException(status_code=404, detail="Product not found in Open Food Facts")
    per_100g = {
        "calories": entry["calories"],
        "energy_kcal": entry.get("energy_kcal", entry["calories"]),
        "energy_kj": entry.get("energy_kj", round(float(entry["calories"]) * 4.184, 1)),
        "protein": entry["protein"],
        "carbs": entry["carbs"],
        "fat": entry["fat"],
        "fiber": entry.get("fiber", 0) or 0,
        "fibre": entry.get("fibre") or entry.get("fiber", 0) or 0,
        "salt": entry.get("salt", 0) or 0,
        "sugars": entry.get("sugars", 0) or 0,
        "saturates": entry.get("saturates", 0) or 0,
    }
    return {
        "barcode": re.sub(r"\D", "", code),
        "name": entry.get("label") or code,
        "brands": entry.get("brands"),
        "per_100g": per_100g,
        "uk_percent_ri_per_100g": entry.get("uk_percent_ri_per_100g") or uk_percent_ri(per_100g),
        "uk_traffic_lights_per_100g": entry.get("uk_traffic_lights_per_100g")
        or uk_traffic_lights_per_100g(per_100g),
        "uk_reference_intakes": UK_REFERENCE_INTAKES,
        "allergens": list(entry.get("allergens") or []),
        "traces": list(entry.get("traces") or []),
        "categories": list(entry.get("categories") or []),
        "suggested_aisle": entry.get("suggested_aisle"),
        "source": entry.get("source") or "openfoodfacts",
        "disclaimer": (
            "Open Food Facts open data. %RI and traffic lights use UK FSA guidance — "
            "not personalised medical advice."
        ),
    }


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
