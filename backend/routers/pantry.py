"""
Pantry Router - CRUD operations for kitchen inventory management
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from models import (
    PantryItemCreate, PantryItemUpdate, PantryItemResponse,
    PantryBulkCreate, PantryBulkDelete, RecipeMatchRequest,
    RecipeMatchResponse, RecipeMatchResult, RecipeResponse, Ingredient
)
from dependencies import (
    get_current_user, pantry_repository, recipe_repository,
    PANTRY_CATEGORIES, STAPLE_INGREDIENTS
)
from database.websocket_manager import ws_manager, EventType
from utils.activity_logger import log_action
import uuid
import re
from datetime import datetime, timezone
from typing import List, Optional
from difflib import SequenceMatcher

router = APIRouter(prefix="/pantry", tags=["Pantry"])


# Ingredient synonym mapping for better matching
INGREDIENT_SYNONYMS = {
    "coriander": ["cilantro", "chinese parsley", "dhania"],
    "aubergine": ["eggplant", "brinjal"],
    "courgette": ["zucchini"],
    "spring onion": ["scallion", "green onion"],
    "rocket": ["arugula"],
    "pepper": ["capsicum", "bell pepper"],
    "prawns": ["shrimp"],
    "mince": ["ground meat", "ground beef"],
    "caster sugar": ["superfine sugar"],
    "icing sugar": ["powdered sugar", "confectioners sugar"],
    "plain flour": ["all-purpose flour", "ap flour"],
    "bicarbonate of soda": ["baking soda"],
    "double cream": ["heavy cream"],
    "single cream": ["light cream"],
    "tomato puree": ["tomato paste"],
    "chickpeas": ["garbanzo beans"],
}

# Pre-computed reverse synonym lookup for O(1) access
_SYNONYM_LOOKUP = {}
for _key, _values in INGREDIENT_SYNONYMS.items():
    _SYNONYM_LOOKUP[_key] = _key
    for _v in _values:
        _SYNONYM_LOOKUP[_v] = _key

# Cache for normalized synonyms (cleared periodically or on restart)
_SYNONYM_CACHE = {}


def normalize_ingredient(name: str) -> str:
    """Normalize an ingredient name for matching"""
    # Lowercase and strip
    name = name.lower().strip()
    # Remove common quantity prefixes
    name = re.sub(r'^(\d+[\s]*)?([a-z]+\s+of\s+)?', '', name)
    # Remove common modifiers
    modifiers = ['fresh', 'dried', 'frozen', 'canned', 'chopped', 'diced',
                 'minced', 'sliced', 'grated', 'large', 'small', 'medium',
                 'organic', 'ripe', 'raw', 'cooked']
    for mod in modifiers:
        name = re.sub(rf'\b{mod}\b', '', name)
    # Clean up whitespace
    name = ' '.join(name.split())
    return name


def get_all_synonyms(name: str) -> set:
    """Get all possible names for an ingredient including synonyms (cached)"""
    name = normalize_ingredient(name)

    # Check cache first for O(1) lookup
    if name in _SYNONYM_CACHE:
        return _SYNONYM_CACHE[name]

    synonyms = {name}

    # O(1) lookup using pre-computed reverse map
    if name in _SYNONYM_LOOKUP:
        key = _SYNONYM_LOOKUP[name]
        synonyms.add(key)
        synonyms.update(INGREDIENT_SYNONYMS.get(key, []))

    # Cache the result
    _SYNONYM_CACHE[name] = synonyms
    return synonyms


def fuzzy_match(ingredient: str, pantry_names: set, threshold: float = 0.7) -> bool:
    """
    Check if an ingredient fuzzy matches any pantry item.
    Optimized to reduce complexity by:
    1. Using cached synonym lookups (O(1) instead of O(n))
    2. Early termination on exact matches
    3. Length-based filtering before expensive similarity computation
    """
    ingredient = normalize_ingredient(ingredient)
    ingredient_synonyms = get_all_synonyms(ingredient)

    for pantry_name in pantry_names:
        pantry_synonyms = get_all_synonyms(pantry_name)

        # Fast path: exact match with synonyms (O(min(m,n)) set intersection)
        if ingredient_synonyms & pantry_synonyms:
            return True

        # Medium path: substring match (cheaper than SequenceMatcher)
        for ing_syn in ingredient_synonyms:
            for pan_syn in pantry_synonyms:
                if ing_syn in pan_syn or pan_syn in ing_syn:
                    return True

        # Slow path: fuzzy matching with optimizations
        for ing_syn in ingredient_synonyms:
            # Skip very short words (high false positive rate)
            if len(ing_syn) < 3:
                continue
            for pan_syn in pantry_synonyms:
                if len(pan_syn) < 3:
                    continue
                # Quick length filter - skip if lengths differ by >50%
                len_ratio = len(ing_syn) / len(pan_syn) if pan_syn else 0
                if 0.5 <= len_ratio <= 2.0:
                    ratio = SequenceMatcher(None, ing_syn, pan_syn).ratio()
                    if ratio >= threshold:
                        return True

    return False


@router.get("/categories")
async def get_pantry_categories():
    """Get available pantry categories"""
    return {"categories": PANTRY_CATEGORIES}


@router.get("/staples")
async def get_staple_ingredients():
    """Get list of common staple ingredients"""
    return {"staples": STAPLE_INGREDIENTS}


@router.get("", response_model=List[PantryItemResponse])
async def get_pantry_items(
    category: Optional[str] = None,
    search: Optional[str] = None,
    include_staples: Optional[bool] = True,
    user: dict = Depends(get_current_user)
):
    """Get all pantry items for the current user/household"""
    if search:
        items = await pantry_repository.search(
            user_id=user["id"],
            household_id=user.get("household_id"),
            search_term=search
        )
    else:
        items = await pantry_repository.find_by_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id"),
            category=category,
            include_staples=include_staples
        )

    # Convert expiry_date to string if present
    for item in items:
        if item.get("expiry_date"):
            item["expiry_date"] = str(item["expiry_date"])

    return [PantryItemResponse(**item) for item in items]


@router.get("/expiring")
async def get_expiring_items(
    days: Optional[int] = 7,
    user: dict = Depends(get_current_user)
):
    """Get pantry items expiring within specified days"""
    items = await pantry_repository.find_expiring_soon(
        user_id=user["id"],
        household_id=user.get("household_id"),
        days_ahead=days
    )

    # Convert expiry_date to string if present
    for item in items:
        if item.get("expiry_date"):
            item["expiry_date"] = str(item["expiry_date"])

    return {"items": [PantryItemResponse(**item) for item in items], "days_checked": days}


@router.post("", response_model=PantryItemResponse)
async def create_pantry_item(
    item: PantryItemCreate,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Create a new pantry item"""
    item_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    item_doc = {
        "id": item_id,
        "user_id": user["id"],
        "household_id": user.get("household_id"),
        "name": item.name,
        "quantity": item.quantity,
        "unit": item.unit,
        "category": item.category or "pantry",
        "expiry_date": item.expiry_date,
        "notes": item.notes,
        "is_staple": item.is_staple or False,
        "created_at": now,
        "updated_at": now
    }

    await pantry_repository.create(item_doc)

    # Log user activity
    await log_action(
        user, "pantry_item_added", request,
        target_type="pantry_item",
        target_id=item_id,
        details={"name": item.name, "category": item.category}
    )

    # Broadcast to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.DATA_SYNC,
        data={"type": "pantry_item_created", "item": item_doc}
    )

    return PantryItemResponse(**item_doc)


@router.post("/bulk", response_model=List[PantryItemResponse])
async def create_pantry_items_bulk(
    bulk: PantryBulkCreate,
    user: dict = Depends(get_current_user)
):
    """Create multiple pantry items at once"""
    now = datetime.now(timezone.utc).isoformat()
    created_items = []

    for item in bulk.items:
        item_id = str(uuid.uuid4())
        item_doc = {
            "id": item_id,
            "user_id": user["id"],
            "household_id": user.get("household_id"),
            "name": item.name,
            "quantity": item.quantity,
            "unit": item.unit,
            "category": item.category or "pantry",
            "expiry_date": item.expiry_date,
            "notes": item.notes,
            "is_staple": item.is_staple or False,
            "created_at": now,
            "updated_at": now
        }
        await pantry_repository.create(item_doc)
        created_items.append(item_doc)

    # Broadcast update
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.DATA_SYNC,
        data={"type": "pantry_bulk_created", "count": len(created_items)}
    )

    return [PantryItemResponse(**item) for item in created_items]


@router.get("/{item_id}", response_model=PantryItemResponse)
async def get_pantry_item(
    item_id: str,
    user: dict = Depends(get_current_user)
):
    """Get a specific pantry item"""
    item = await pantry_repository.find_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Pantry item not found")

    # Verify access
    if item["user_id"] != user["id"]:
        if not user.get("household_id") or item.get("household_id") != user["household_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view this item")

    if item.get("expiry_date"):
        item["expiry_date"] = str(item["expiry_date"])

    return PantryItemResponse(**item)


@router.put("/{item_id}", response_model=PantryItemResponse)
async def update_pantry_item(
    item_id: str,
    item_update: PantryItemUpdate,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Update a pantry item"""
    existing = await pantry_repository.find_by_id(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Pantry item not found")

    # Verify ownership
    if existing["user_id"] != user["id"]:
        if not user.get("household_id") or existing.get("household_id") != user["household_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to update this item")

    # Build update data (only include non-None fields)
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field, value in item_update.model_dump().items():
        if value is not None:
            update_data[field] = value

    await pantry_repository.update_item(item_id, update_data)
    updated = await pantry_repository.find_by_id(item_id)

    if updated.get("expiry_date"):
        updated["expiry_date"] = str(updated["expiry_date"])

    # Log user activity
    await log_action(
        user, "pantry_item_updated", request,
        target_type="pantry_item",
        target_id=item_id,
        details={"name": updated.get("name")}
    )

    # Broadcast update
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.DATA_SYNC,
        data={"type": "pantry_item_updated", "item": updated}
    )

    return PantryItemResponse(**updated)


@router.delete("/{item_id}")
async def delete_pantry_item(
    item_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Delete a pantry item"""
    existing = await pantry_repository.find_by_id(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Pantry item not found")

    # Verify ownership
    if existing["user_id"] != user["id"]:
        if not user.get("household_id") or existing.get("household_id") != user["household_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to delete this item")

    # Store name before deletion for logging
    item_name = existing.get("name", "Unknown")

    await pantry_repository.delete_item(item_id)

    # Log user activity
    await log_action(
        user, "pantry_item_deleted", request,
        target_type="pantry_item",
        target_id=item_id,
        details={"name": item_name}
    )

    # Broadcast deletion
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.DATA_SYNC,
        data={"type": "pantry_item_deleted", "id": item_id}
    )

    return {"message": "Pantry item deleted"}


@router.delete("/bulk/clear")
async def delete_pantry_items_bulk(
    bulk: PantryBulkDelete,
    user: dict = Depends(get_current_user)
):
    """Delete multiple pantry items at once"""
    deleted_count = await pantry_repository.bulk_delete(bulk.item_ids)

    # Broadcast deletion
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.DATA_SYNC,
        data={"type": "pantry_bulk_deleted", "count": deleted_count}
    )

    return {"message": f"Deleted {deleted_count} items", "deleted_count": deleted_count}


@router.post("/match", response_model=RecipeMatchResponse)
async def match_recipes_to_pantry(
    request: RecipeMatchRequest,
    user: dict = Depends(get_current_user)
):
    """Find recipes that can be made with current pantry items (What Can I Make?)"""
    # Get pantry items
    if request.pantry_item_ids:
        # Get specific items
        pantry_items = []
        for item_id in request.pantry_item_ids:
            item = await pantry_repository.find_by_id(item_id)
            if item:
                pantry_items.append(item)
    else:
        # Get all pantry items
        pantry_items = await pantry_repository.find_by_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id"),
            include_staples=not request.exclude_staples
        )

    if not pantry_items:
        return RecipeMatchResponse(
            matches=[],
            pantry_item_count=0,
            total_recipes_checked=0
        )

    # Build set of normalized pantry names
    pantry_names = {normalize_ingredient(item["name"]) for item in pantry_items}

    # Get all user's recipes
    recipes = await recipe_repository.find_all_for_user(
        user_id=user["id"],
        household_id=user.get("household_id")
    )

    matches = []
    staples_set = {normalize_ingredient(s) for s in STAPLE_INGREDIENTS}

    for recipe in recipes:
        ingredients = recipe.get("ingredients", [])
        if not ingredients:
            continue

        # Filter out staples if requested
        recipe_ingredients = []
        for ing in ingredients:
            name = ing.get("name", "") if isinstance(ing, dict) else str(ing)
            normalized = normalize_ingredient(name)
            if request.exclude_staples and normalized in staples_set:
                continue
            recipe_ingredients.append(normalized)

        if not recipe_ingredients:
            continue

        # Match ingredients
        matched = []
        missing = []

        for ing_name in recipe_ingredients:
            if fuzzy_match(ing_name, pantry_names):
                matched.append(ing_name)
            else:
                missing.append(ing_name)

        # Calculate match percentage
        match_pct = len(matched) / len(recipe_ingredients) if recipe_ingredients else 0

        # Check threshold
        if match_pct >= request.match_threshold:
            # Convert ingredients to proper format
            recipe_ingredients_formatted = []
            for ing in recipe.get("ingredients", []):
                if isinstance(ing, dict):
                    recipe_ingredients_formatted.append(Ingredient(**ing))
                else:
                    recipe_ingredients_formatted.append(Ingredient(name=str(ing), amount="", unit=""))

            matches.append(RecipeMatchResult(
                recipe=RecipeResponse(
                    id=recipe["id"],
                    title=recipe["title"],
                    description=recipe.get("description", ""),
                    ingredients=recipe_ingredients_formatted,
                    instructions=recipe.get("instructions", []),
                    prep_time=recipe.get("prep_time", 0),
                    cook_time=recipe.get("cook_time", 0),
                    servings=recipe.get("servings", 4),
                    category=recipe.get("category", "Other"),
                    tags=recipe.get("tags", []),
                    image_url=recipe.get("image_url", ""),
                    author_id=recipe["author_id"],
                    household_id=recipe.get("household_id"),
                    created_at=str(recipe.get("created_at", "")),
                    updated_at=str(recipe.get("updated_at", "")),
                    is_favorite=False
                ),
                match_percentage=round(match_pct, 2),
                matched_ingredients=matched,
                missing_ingredients=missing
            ))

    # Sort by match percentage (highest first)
    matches.sort(key=lambda x: x.match_percentage, reverse=True)

    return RecipeMatchResponse(
        matches=matches,
        pantry_item_count=len(pantry_items),
        total_recipes_checked=len(recipes)
    )
