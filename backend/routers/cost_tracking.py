"""
Cost Tracking Router - Track ingredient costs and recipe expenses

Persists to `ingredient_costs` (household_id, ingredient_name, cost, unit, store)
and optional recipe cost columns (cost_total, cost_per_serving, ...).
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Any
from dependencies import get_current_user, recipe_repository, ingredient_cost_repository
from datetime import datetime, timezone

router = APIRouter(prefix="/costs", tags=["Cost Tracking"])

# =============================================================================
# MODELS
# =============================================================================

class IngredientPrice(BaseModel):
    name: str
    price: float
    unit: str  # per unit (e.g., "lb", "kg", "each")
    quantity: float = 1.0  # quantity for this price (API compat; stored as unit cost)
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
# DEFAULT PRICES (Common ingredients, rough UK supermarket GBP estimates)
# =============================================================================

DEFAULT_CURRENCY = "GBP"

DEFAULT_PRICES = {
    # Proteins
    "chicken breast": {"price": 3.50, "unit": "pack"},
    "chicken thigh": {"price": 2.80, "unit": "pack"},
    "ground beef": {"price": 3.50, "unit": "pack"},
    "beef": {"price": 5.50, "unit": "pack"},
    "beef mince": {"price": 3.50, "unit": "pack"},
    "pork": {"price": 3.20, "unit": "pack"},
    "salmon": {"price": 5.00, "unit": "pack"},
    "shrimp": {"price": 4.50, "unit": "pack"},
    "eggs": {"price": 2.50, "unit": "dozen"},
    "egg": {"price": 0.25, "unit": "each"},
    "tofu": {"price": 1.80, "unit": "pack"},

    # Dairy
    "milk": {"price": 1.25, "unit": "litre"},
    "butter": {"price": 2.20, "unit": "pack"},
    "cheese": {"price": 2.80, "unit": "pack"},
    "cream": {"price": 1.50, "unit": "pot"},
    "yogurt": {"price": 1.20, "unit": "pot"},
    "yoghurt": {"price": 1.20, "unit": "pot"},
    "greek yoghurt": {"price": 1.50, "unit": "pot"},
    "skyr": {"price": 1.80, "unit": "pot"},
    "sour cream": {"price": 1.20, "unit": "pot"},

    # Grains
    "flour": {"price": 1.20, "unit": "bag"},
    "rice": {"price": 1.50, "unit": "bag"},
    "pasta": {"price": 0.85, "unit": "pack"},
    "bread": {"price": 1.20, "unit": "loaf"},
    "tortillas": {"price": 1.50, "unit": "pack"},
    "potato": {"price": 1.20, "unit": "bag"},
    "potatoes": {"price": 1.20, "unit": "bag"},

    # Vegetables
    "onion": {"price": 0.80, "unit": "bag"},
    "garlic": {"price": 0.40, "unit": "bulb"},
    "tomato": {"price": 1.50, "unit": "pack"},
    "carrot": {"price": 0.60, "unit": "bag"},
    "carrots": {"price": 0.60, "unit": "bag"},
    "celery": {"price": 0.80, "unit": "pack"},
    "bell pepper": {"price": 1.00, "unit": "each"},
    "broccoli": {"price": 1.00, "unit": "head"},
    "cauliflower": {"price": 1.20, "unit": "head"},
    "spinach": {"price": 1.20, "unit": "bag"},
    "lettuce": {"price": 0.80, "unit": "head"},
    "peas": {"price": 0.75, "unit": "bag"},
    "sweetcorn": {"price": 0.65, "unit": "tin"},

    # Oils & Condiments
    "olive oil": {"price": 4.50, "unit": "bottle"},
    "vegetable oil": {"price": 2.00, "unit": "bottle"},
    "soy sauce": {"price": 1.80, "unit": "bottle"},
    "honey": {"price": 2.50, "unit": "jar"},
    "sugar": {"price": 1.00, "unit": "bag"},
    "salt": {"price": 0.60, "unit": "tub"},
    "pepper": {"price": 1.50, "unit": "jar"},
    "black pepper": {"price": 1.50, "unit": "jar"},

    # Fruit / nuts
    "banana": {"price": 0.90, "unit": "bunch"},
    "pear": {"price": 1.50, "unit": "pack"},
    "almonds": {"price": 2.50, "unit": "bag"},
    "banana chips": {"price": 1.50, "unit": "bag"},

    # Spices
    "cumin": {"price": 1.20, "unit": "jar"},
    "paprika": {"price": 1.20, "unit": "jar"},
    "garlic granules": {"price": 1.20, "unit": "jar"},
    "oregano": {"price": 1.00, "unit": "jar"},
    "basil": {"price": 0.80, "unit": "bunch"},
    "cilantro": {"price": 0.60, "unit": "bunch"},
    "parsley": {"price": 0.60, "unit": "bunch"},
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


def cost_scope_id(user: dict) -> str:
    """Household-scoped costs; solo users use their user id as the scope key."""
    return user.get("household_id") or user["id"]


def row_to_api_price(row: dict) -> dict:
    """Map DB ingredient_costs row to the API price shape the frontend expects."""
    return {
        "id": row.get("id"),
        "name": row.get("ingredient_name"),
        "name_normalized": normalize_ingredient_name(row.get("ingredient_name") or ""),
        "price": row.get("cost"),
        "unit": row.get("unit"),
        "quantity": 1.0,
        "store": row.get("store"),
        "updated_at": row.get("updated_at"),
        "source": "custom",
        "household_id": row.get("household_id"),
    }


async def get_ingredient_price(
    scope_id: str,
    ingredient_name: str,
    *,
    amount: Any = None,
    unit: Optional[str] = None,
) -> dict:
    """Get price for an ingredient: custom → Open Prices (UK) → local defaults."""
    normalized = normalize_ingredient_name(ingredient_name)

    custom = await ingredient_cost_repository.find_by_household(scope_id)
    for row in custom:
        row_name = normalize_ingredient_name(row.get("ingredient_name") or "")
        if row_name == normalized or normalized in row_name or row_name in normalized:
            return {
                "price": row["cost"],
                "unit": row.get("unit") or "each",
                "quantity": 1,
                "source": "custom",
                "store": row.get("store"),
                "currency": DEFAULT_CURRENCY,
            }

    # Crowdsourced UK supermarket prices (Open Food Facts — Open Prices)
    try:
        from services.uk_open_prices import lookup_uk_ingredient_price

        uk = await lookup_uk_ingredient_price(ingredient_name, amount=amount, unit=unit)
        if uk:
            return uk
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "Open Prices lookup failed for %r: %s", ingredient_name, e
        )

    # Check defaults
    for default_name, default_price in DEFAULT_PRICES.items():
        if default_name in normalized or normalized in default_name:
            return {
                "price": default_price["price"],
                "unit": default_price["unit"],
                "quantity": 1,
                "source": "default",
                "currency": DEFAULT_CURRENCY,
            }

    return None


async def calculate_recipe_cost(scope_id: str, ingredients: list) -> dict:
    """Calculate total cost of a recipe"""
    total = 0.0
    breakdown = []
    unknown = []
    sources_used = set()

    for ing in ingredients:
        if isinstance(ing, dict):
            name = ing.get("name", "")
            amount = ing.get("amount", "1")
            unit = ing.get("unit") or ""
        else:
            name = str(ing)
            amount = "1"
            unit = ""

        # Try to parse amount
        try:
            amount_num = float(str(amount).replace(",", "").replace("/", ".").split()[0]) if amount else 1
        except (ValueError, AttributeError, IndexError):
            amount_num = 1

        price_info = await get_ingredient_price(
            scope_id, name, amount=amount, unit=unit or None
        )

        if price_info:
            if price_info.get("estimated_cost") is not None:
                estimated_cost = float(price_info["estimated_cost"])
            else:
                # Estimate cost based on amount (rough heuristic — same as before)
                estimated_cost = (price_info["price"] / price_info["quantity"]) * (amount_num / 10)
                estimated_cost = round(max(0.10, min(estimated_cost, price_info["price"])), 2)

            total += estimated_cost
            sources_used.add(price_info.get("source") or "unknown")
            breakdown.append({
                "ingredient": name,
                "amount": amount,
                "unit_price": price_info["price"],
                "estimated_cost": estimated_cost,
                "source": price_info["source"],
                "store": price_info.get("store"),
                "matched_product": price_info.get("matched_product"),
                "observed_date": price_info.get("observed_date"),
                "currency": price_info.get("currency") or DEFAULT_CURRENCY,
            })
        else:
            unknown.append(name)

    provider = None
    attribution = None
    attribution_url = None
    if "open_prices_uk" in sources_used:
        provider = "Open Prices (UK)"
        attribution = "Data © Open Food Facts Open Prices contributors (ODbL)"
        attribution_url = "https://prices.openfoodfacts.org"

    return {
        "total": round(total, 2),
        "breakdown": breakdown,
        "unknown_ingredients": unknown,
        "currency": DEFAULT_CURRENCY,
        "provider": provider,
        "attribution": attribution,
        "attribution_url": attribution_url,
        "sources_used": sorted(sources_used),
    }

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/prices")
async def list_ingredient_prices(user: dict = Depends(get_current_user)):
    """List all ingredient prices (custom + defaults)"""
    scope_id = cost_scope_id(user)
    rows = await ingredient_cost_repository.find_by_household(scope_id)
    custom_prices = [row_to_api_price(r) for r in rows]

    defaults = [
        {"name": name, **info, "source": "default"}
        for name, info in DEFAULT_PRICES.items()
    ]

    return {
        "custom_prices": custom_prices,
        "default_prices": defaults,
        "currency": DEFAULT_CURRENCY
    }


@router.post("/prices")
async def add_ingredient_price(
    data: IngredientPrice,
    user: dict = Depends(get_current_user)
):
    """Add or update a custom ingredient price"""
    scope_id = cost_scope_id(user)
    normalized = normalize_ingredient_name(data.name)
    # asyncpg expects a datetime for TIMESTAMP columns (not ISO strings)
    updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Store unit cost; quantity is API-only (per-pack size). Divide if provided.
    unit_cost = data.price / data.quantity if data.quantity else data.price

    saved = await ingredient_cost_repository.upsert_cost(
        household_id=scope_id,
        ingredient_name=normalized,
        cost=unit_cost,
        unit=data.unit,
        store=data.store,
        updated_at=updated_at,
    )

    price_doc = {
        "name": data.name,
        "name_normalized": normalized,
        "price": unit_cost,
        "unit": data.unit,
        "quantity": 1.0,
        "store": data.store,
        "notes": data.notes,
        "updated_at": updated_at.isoformat(),
        "household_id": scope_id,
        **{k: saved.get(k) for k in ("ingredient_name", "cost") if k in saved},
    }

    return {"message": "Price saved", "price": price_doc}


@router.delete("/prices/{price_id}")
async def delete_ingredient_price(
    price_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a custom ingredient price"""
    scope_id = cost_scope_id(user)
    existing = await ingredient_cost_repository.find_one({"id": price_id})
    if not existing or existing.get("household_id") != scope_id:
        raise HTTPException(status_code=404, detail="Price not found")

    await ingredient_cost_repository.delete_cost(price_id)
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
    servings = recipe.get("servings", 1) or 1

    cost_data = await calculate_recipe_cost(cost_scope_id(user), ingredients)

    return {
        "recipe_id": recipe_id,
        "recipe_title": recipe.get("title"),
        "total_cost": cost_data["total"],
        "cost_per_serving": round(cost_data["total"] / servings, 2),
        "servings": servings,
        "breakdown": cost_data["breakdown"],
        "unknown_ingredients": cost_data["unknown_ingredients"],
        "currency": DEFAULT_CURRENCY,
        "provider": cost_data.get("provider"),
        "attribution": cost_data.get("attribution"),
        "attribution_url": cost_data.get("attribution_url"),
        "sources_used": cost_data.get("sources_used") or [],
    }


@router.post("/recipe/{recipe_id}")
async def calculate_recipe_cost_post(
    recipe_id: str,
    user: dict = Depends(get_current_user),
):
    """Android/legacy alias — same as GET /recipe/{id}."""
    return await get_recipe_cost(recipe_id, user)


@router.get("/uk-catalog")
async def get_uk_open_prices_catalog(
    user: dict = Depends(get_current_user),
    limit: int = 5000,
):
    """
    Export the synced UK Open Prices catalog for offline clients (Android).
    Data is served from the local DB — no live Open Prices call.
    """
    from services.uk_open_prices import get_offline_catalog

    return await get_offline_catalog(limit=min(max(limit, 1), 10000))


@router.post("/uk-catalog/sync")
async def sync_uk_open_prices_now(
    user: dict = Depends(get_current_user),
    force: bool = True,
):
    """Manually refresh the UK Open Prices catalog (also runs every 12h via Celery)."""
    from services.uk_open_prices import sync_uk_open_prices

    return await sync_uk_open_prices(force=force)


@router.post("/recipe/{recipe_id}/save")
async def save_recipe_cost(
    recipe_id: str,
    user: dict = Depends(get_current_user)
):
    """Calculate and save cost to recipe"""
    recipe = await recipe_repository.find_by_id(recipe_id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    cost_data = await calculate_recipe_cost(cost_scope_id(user), recipe.get("ingredients", []))
    servings = recipe.get("servings", 1) or 1

    cost_info = {
        "cost_total": cost_data["total"],
        "cost_per_serving": round(cost_data["total"] / servings, 2),
        "cost_calculated_at": datetime.now(timezone.utc).isoformat(),
        "cost_currency": DEFAULT_CURRENCY
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

    recipes_with_cost = [r for r in recipes if r.get("cost_total") is not None]

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
    per_servings = [r["cost_per_serving"] for r in recipes_with_cost if r.get("cost_per_serving") is not None]

    cheapest = min(recipes_with_cost, key=lambda x: x["cost_total"])
    expensive = max(recipes_with_cost, key=lambda x: x["cost_total"])

    return {
        "total_recipes": len(recipes),
        "recipes_with_cost": len(recipes_with_cost),
        "average_cost": round(sum(costs) / len(costs), 2),
        "average_per_serving": round(sum(per_servings) / len(per_servings), 2) if per_servings else 0,
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
        "currency": DEFAULT_CURRENCY
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
            AND cost_total IS NOT NULL
            AND cost_total <= $2
            ORDER BY cost_total ASC
            LIMIT 50
        """
        rows = await conn.fetch(query, user["id"], max_cost)

    recipes = rows_to_dicts(rows)

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
