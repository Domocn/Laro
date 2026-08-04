"""
Cost Tracking Router - Track ingredient costs and recipe expenses
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from dependencies import get_current_user, recipe_repository, ingredient_cost_repository
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/costs", tags=["Cost Tracking"])

# =============================================================================
# MODELS
# =============================================================================

class IngredientPrice(BaseModel):
    name: str
    price: float
    unit: str  # per unit (e.g., "lb", "kg", "each")
    quantity: float = 1.0  # quantity for this price
    store: Optional[str] = None
    notes: Optional[str] = None

class UpdateIngredientPrice(BaseModel):
    price: Optional[float] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    store: Optional[str] = None
    notes: Optional[str] = None

class RecipeCostOverride(BaseModel):
    recipe_id: str
    total_cost: float
    notes: Optional[str] = None

class CostReport(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None

# =============================================================================
# DEFAULT PRICES (Common ingredients, USD)
# =============================================================================

DEFAULT_PRICES = {
    # Proteins
    "chicken breast": {"price": 3.99, "unit": "lb"},
    "chicken thigh": {"price": 2.99, "unit": "lb"},
    "ground beef": {"price": 5.99, "unit": "lb"},
    "beef": {"price": 8.99, "unit": "lb"},
    "pork": {"price": 3.99, "unit": "lb"},
    "salmon": {"price": 9.99, "unit": "lb"},
    "shrimp": {"price": 8.99, "unit": "lb"},
    "eggs": {"price": 4.99, "unit": "dozen"},
    "egg": {"price": 0.42, "unit": "each"},
    "tofu": {"price": 2.49, "unit": "block"},

    # Dairy
    "milk": {"price": 3.99, "unit": "gallon"},
    "butter": {"price": 4.99, "unit": "lb"},
    "cheese": {"price": 5.99, "unit": "lb"},
    "cream": {"price": 3.99, "unit": "pint"},
    "yogurt": {"price": 1.29, "unit": "cup"},
    "sour cream": {"price": 2.49, "unit": "cup"},

    # Grains
    "flour": {"price": 3.49, "unit": "5lb"},
    "rice": {"price": 2.99, "unit": "lb"},
    "pasta": {"price": 1.49, "unit": "lb"},
    "bread": {"price": 3.49, "unit": "loaf"},
    "tortillas": {"price": 3.49, "unit": "pack"},

    # Vegetables
    "onion": {"price": 1.29, "unit": "lb"},
    "garlic": {"price": 0.50, "unit": "head"},
    "tomato": {"price": 1.99, "unit": "lb"},
    "potato": {"price": 0.99, "unit": "lb"},
    "carrot": {"price": 1.29, "unit": "lb"},
    "celery": {"price": 1.99, "unit": "bunch"},
    "bell pepper": {"price": 1.49, "unit": "each"},
    "broccoli": {"price": 1.99, "unit": "lb"},
    "spinach": {"price": 2.99, "unit": "bag"},
    "lettuce": {"price": 1.99, "unit": "head"},

    # Oils & Condiments
    "olive oil": {"price": 8.99, "unit": "bottle"},
    "vegetable oil": {"price": 4.99, "unit": "bottle"},
    "soy sauce": {"price": 3.49, "unit": "bottle"},
    "honey": {"price": 7.99, "unit": "jar"},
    "sugar": {"price": 2.99, "unit": "bag"},
    "salt": {"price": 1.49, "unit": "container"},
    "pepper": {"price": 4.99, "unit": "jar"},

    # Spices
    "cumin": {"price": 4.99, "unit": "jar"},
    "paprika": {"price": 4.99, "unit": "jar"},
    "oregano": {"price": 3.99, "unit": "jar"},
    "basil": {"price": 2.99, "unit": "bunch"},
    "cilantro": {"price": 1.49, "unit": "bunch"},
    "parsley": {"price": 1.49, "unit": "bunch"},
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_ingredient_name(name: str) -> str:
    """Normalize ingredient name for matching"""
    name = name.lower().strip()
    # Remove common prefixes
    prefixes = ["fresh ", "dried ", "chopped ", "minced ", "diced ", "sliced ", "ground "]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name

async def get_ingredient_price(user_id: str, ingredient_name: str) -> dict:
    """Get price for an ingredient, checking user prices first, then defaults"""
    normalized = normalize_ingredient_name(ingredient_name)

    # Check user's custom prices using ingredient_cost_repository
    # Note: The ingredient_cost_repository uses household_id, but we can adapt for user_id
    from database.connection import get_db, dict_from_row

    pool = await get_db()
    async with pool.acquire() as conn:
        query = """
            SELECT * FROM ingredient_costs
            WHERE user_id = $1 AND name_normalized = $2
            LIMIT 1
        """
        row = await conn.fetchrow(query, user_id, normalized)

    if row:
        user_price = dict_from_row(row)
        return {
            "price": user_price["price"],
            "unit": user_price["unit"],
            "quantity": user_price.get("quantity", 1),
            "source": "custom"
        }

    # Check defaults
    for default_name, default_price in DEFAULT_PRICES.items():
        if default_name in normalized or normalized in default_name:
            return {
                "price": default_price["price"],
                "unit": default_price["unit"],
                "quantity": 1,
                "source": "default"
            }

    return None

async def calculate_recipe_cost(user_id: str, ingredients: list) -> dict:
    """Calculate total cost of a recipe"""
    total = 0.0
    breakdown = []
    unknown = []

    for ing in ingredients:
        if isinstance(ing, dict):
            name = ing.get("name", "")
            amount = ing.get("amount", "1")
        else:
            name = str(ing)
            amount = "1"

        # Try to parse amount
        try:
            amount_num = float(amount.replace("/", ".").split()[0]) if amount else 1
        except (ValueError, AttributeError, IndexError):
            amount_num = 1

        price_info = await get_ingredient_price(user_id, name)

        if price_info:
            # Estimate cost based on amount
            estimated_cost = (price_info["price"] / price_info["quantity"]) * (amount_num / 10)  # Rough estimate
            estimated_cost = round(max(0.10, min(estimated_cost, price_info["price"])), 2)

            total += estimated_cost
            breakdown.append({
                "ingredient": name,
                "amount": amount,
                "unit_price": price_info["price"],
                "estimated_cost": estimated_cost,
                "source": price_info["source"]
            })
        else:
            unknown.append(name)

    return {
        "total": round(total, 2),
        "breakdown": breakdown,
        "unknown_ingredients": unknown
    }

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/prices")
async def list_ingredient_prices(user: dict = Depends(get_current_user)):
    """List all ingredient prices (user's custom + defaults)"""
    # Get user's custom prices
    from database.connection import get_db, rows_to_dicts

    pool = await get_db()
    async with pool.acquire() as conn:
        query = "SELECT * FROM ingredient_costs WHERE user_id = $1"
        rows = await conn.fetch(query, user["id"])

    custom_prices = rows_to_dicts(rows)

    # Format defaults
    defaults = [
        {"name": name, **info, "source": "default"}
        for name, info in DEFAULT_PRICES.items()
    ]

    return {
        "custom_prices": custom_prices,
        "default_prices": defaults,
        "currency": "USD"
    }

@router.post("/prices")
async def add_ingredient_price(
    data: IngredientPrice,
    user: dict = Depends(get_current_user)
):
    """Add or update a custom ingredient price"""
    from database.connection import get_db

    pool = await get_db()
    normalized = normalize_ingredient_name(data.name)
    updated_at = datetime.now(timezone.utc).isoformat()

    async with pool.acquire() as conn:
        # Check if exists
        query = "SELECT id FROM ingredient_costs WHERE user_id = $1 AND name_normalized = $2"
        existing = await conn.fetchrow(query, user["id"], normalized)

        if existing:
            # Update
            await conn.execute(
                """
                UPDATE ingredient_costs
                SET price = $1, unit = $2, quantity = $3, store = $4, notes = $5, updated_at = $6
                WHERE user_id = $7 AND name_normalized = $8
                """,
                data.price, data.unit, data.quantity, data.store, data.notes, updated_at, user["id"], normalized
            )
        else:
            # Insert
            price_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO ingredient_costs (id, user_id, name, name_normalized, price, unit, quantity, store, notes, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                price_id, user["id"], data.name, normalized, data.price, data.unit, data.quantity, data.store, data.notes, updated_at
            )

    price_doc = {
        "user_id": user["id"],
        "name": data.name,
        "name_normalized": normalized,
        "price": data.price,
        "unit": data.unit,
        "quantity": data.quantity,
        "store": data.store,
        "notes": data.notes,
        "updated_at": updated_at
    }

    return {"message": "Price saved", "price": price_doc}

@router.delete("/prices/{price_id}")
async def delete_ingredient_price(
    price_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a custom ingredient price"""
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM ingredient_costs WHERE id = $1 AND user_id = $2",
            price_id, user["id"]
        )

    # Parse rowcount from result string (e.g., "DELETE 1")
    rowcount = int(result.split()[-1]) if result else 0
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Price not found")

    return {"message": "Price deleted"}

@router.get("/recipe/{recipe_id}")
async def get_recipe_cost(
    recipe_id: str,
    user: dict = Depends(get_current_user)
):
    """Calculate cost for a specific recipe"""
    recipe = await recipe_repository.find_by_id(recipe_id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ingredients = recipe.get("ingredients", [])
    servings = recipe.get("servings", 1)

    cost_data = await calculate_recipe_cost(user["id"], ingredients)

    return {
        "recipe_id": recipe_id,
        "recipe_title": recipe.get("title"),
        "total_cost": cost_data["total"],
        "cost_per_serving": round(cost_data["total"] / servings, 2),
        "servings": servings,
        "breakdown": cost_data["breakdown"],
        "unknown_ingredients": cost_data["unknown_ingredients"],
        "currency": "USD"
    }

@router.post("/recipe/{recipe_id}/save")
async def save_recipe_cost(
    recipe_id: str,
    user: dict = Depends(get_current_user)
):
    """Calculate and save cost to recipe"""
    recipe = await recipe_repository.find_by_id(recipe_id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    cost_data = await calculate_recipe_cost(user["id"], recipe.get("ingredients", []))
    servings = recipe.get("servings", 1)

    cost_info = {
        "cost_total": cost_data["total"],
        "cost_per_serving": round(cost_data["total"] / servings, 2),
        "cost_calculated_at": datetime.now(timezone.utc).isoformat(),
        "cost_currency": "USD"
    }

    await recipe_repository.update_recipe(recipe_id, cost_info)

    return {
        "message": "Cost saved to recipe",
        "cost": {
            "total": cost_info["cost_total"],
            "per_serving": cost_info["cost_per_serving"],
            "calculated_at": cost_info["cost_calculated_at"],
            "currency": cost_info["cost_currency"]
        }
    }

@router.get("/summary")
async def get_cost_summary(user: dict = Depends(get_current_user)):
    """Get cost summary across all recipes"""
    # Get all user's recipes with cost info
    from database.connection import get_db, rows_to_dicts

    pool = await get_db()
    async with pool.acquire() as conn:
        query = """
            SELECT id, title, cost_total, cost_per_serving, servings
            FROM recipes
            WHERE author_id = $1
        """
        rows = await conn.fetch(query, user["id"])

    recipes = rows_to_dicts(rows)

    recipes_with_cost = [r for r in recipes if r.get("cost_total")]

    if not recipes_with_cost:
        return {
            "total_recipes": len(recipes),
            "recipes_with_cost": 0,
            "average_cost": 0,
            "average_per_serving": 0,
            "cheapest_recipe": None,
            "most_expensive_recipe": None
        }

    costs = [r["cost_total"] for r in recipes_with_cost]
    per_servings = [r["cost_per_serving"] for r in recipes_with_cost]

    cheapest = min(recipes_with_cost, key=lambda x: x["cost_total"])
    expensive = max(recipes_with_cost, key=lambda x: x["cost_total"])

    return {
        "total_recipes": len(recipes),
        "recipes_with_cost": len(recipes_with_cost),
        "average_cost": round(sum(costs) / len(costs), 2),
        "average_per_serving": round(sum(per_servings) / len(per_servings), 2),
        "cheapest_recipe": {
            "id": cheapest["id"],
            "title": cheapest["title"],
            "cost": cheapest["cost_total"]
        },
        "most_expensive_recipe": {
            "id": expensive["id"],
            "title": expensive["title"],
            "cost": expensive["cost_total"]
        },
        "currency": "USD"
    }

@router.get("/budget")
async def get_budget_friendly_recipes(
    max_cost: float = 10.0,
    user: dict = Depends(get_current_user)
):
    """Get recipes under a certain cost"""
    from database.connection import get_db, rows_to_dicts

    pool = await get_db()
    async with pool.acquire() as conn:
        query = """
            SELECT id, title, cost_total, cost_per_serving, servings, image_url
            FROM recipes
            WHERE author_id = $1
            AND cost_total <= $2
            ORDER BY cost_total ASC
            LIMIT 50
        """
        rows = await conn.fetch(query, user["id"], max_cost)

    recipes = rows_to_dicts(rows)

    # Format cost info
    for r in recipes:
        r["cost"] = {
            "total": r.pop("cost_total", None),
            "per_serving": r.pop("cost_per_serving", None)
        }

    return {
        "max_cost": max_cost,
        "recipes": recipes,
        "count": len(recipes)
    }
