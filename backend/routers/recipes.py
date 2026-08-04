"""
Recipes Router - CRUD operations with live refresh support
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request
from models import RecipeCreate, RecipeResponse, UserRatingCreate, UserRatingResponse
from dependencies import get_current_user, recipe_repository, recipe_share_repository, user_repository, user_preferences_repository
from database.connection import get_pool
from database.websocket_manager import ws_manager, EventType
from config import settings
from utils.activity_logger import log_action
from utils.security import validate_image_content
import uuid
import aiofiles
import re
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pathlib import Path

router = APIRouter(prefix="/recipes", tags=["Recipes"])


# Common allergen keywords to match against ingredients
ALLERGEN_KEYWORDS = {
    "Peanuts": ["peanut", "peanuts", "groundnut"],
    "Tree Nuts": ["almond", "cashew", "walnut", "pecan", "pistachio", "hazelnut", "macadamia", "brazil nut", "chestnut", "pine nut"],
    "Milk": ["milk", "cream", "butter", "cheese", "yogurt", "dairy", "whey", "casein", "lactose", "ghee"],
    "Eggs": ["egg", "eggs", "mayonnaise", "meringue", "albumin"],
    "Wheat": ["wheat", "flour", "bread", "pasta", "noodle", "couscous", "semolina", "farina", "durum"],
    "Soy": ["soy", "soya", "tofu", "tempeh", "edamame", "miso", "soy sauce"],
    "Fish": ["fish", "cod", "salmon", "tuna", "halibut", "trout", "anchovy", "sardine", "tilapia", "bass"],
    "Shellfish": ["shrimp", "prawn", "crab", "lobster", "crawfish", "clam", "mussel", "oyster", "scallop", "squid", "calamari"],
    "Sesame": ["sesame", "tahini"]
}


def check_allergens_in_recipe(ingredients: List[dict], user_allergens: List[str]) -> List[dict]:
    """
    Check recipe ingredients against user's allergens.
    Returns a list of warnings with allergen and matching ingredient.
    """
    warnings = []
    if not user_allergens or not ingredients:
        return warnings

    for allergen in user_allergens:
        keywords = ALLERGEN_KEYWORDS.get(allergen, [allergen.lower()])

        for ingredient in ingredients:
            ingredient_name = ingredient.get("name", "").lower()
            for keyword in keywords:
                if keyword in ingredient_name:
                    warnings.append({
                        "allergen": allergen,
                        "ingredient": ingredient.get("name"),
                        "severity": "high"
                    })
                    break  # Found match for this allergen in this ingredient

    return warnings


async def get_user_allergens(user_id: str, user: dict = None) -> List[str]:
    """
    Get user's allergens from multiple sources:
    1. User preferences (Android onboarding)
    2. User model (web settings)
    Returns combined unique list.
    """
    all_allergens = set()

    # Check user model (web frontend saves here)
    if user:
        user_allergies = user.get("allergies", [])
        if isinstance(user_allergies, list):
            all_allergens.update(user_allergies)

    # Check user preferences (Android saves here)
    prefs = await user_preferences_repository.find_by_user(user_id)
    if prefs:
        allergens = prefs.get("allergens", "[]")
        if isinstance(allergens, str):
            try:
                allergens = json.loads(allergens)
            except (json.JSONDecodeError, TypeError):
                allergens = []
        if isinstance(allergens, list):
            all_allergens.update(allergens)

    return list(all_allergens)


def escape_regex(text: str) -> str:
    """Escape special regex characters to prevent ReDoS attacks"""
    return re.escape(text)


# Upload directory path
UPLOAD_DIR = Path(settings.upload_dir)


def ensure_upload_dir() -> Path:
    """Ensure upload directory exists, creating it if necessary."""
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Directory creation will be retried on actual file upload
        pass
    return UPLOAD_DIR


@router.post("", response_model=RecipeResponse)
async def create_recipe(recipe: RecipeCreate, request: Request, user: dict = Depends(get_current_user)):
    recipe_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Build nutrition dict if provided
    nutrition_data = None
    if recipe.nutrition:
        nutrition_data = recipe.nutrition.model_dump()

    recipe_doc = {
        "id": recipe_id,
        "title": recipe.title,
        "description": recipe.description or "",
        "ingredients": [i.model_dump() for i in recipe.ingredients],
        "instructions": recipe.instructions,
        "prep_time": recipe.prep_time or 0,
        "cook_time": recipe.cook_time or 0,
        "servings": recipe.servings or 4,
        "category": recipe.category or "Other",
        "tags": recipe.tags or [],
        "image_url": recipe.image_url or "",
        "author_id": user["id"],
        "household_id": user.get("household_id"),
        "created_at": now,
        "updated_at": now,
        "dietary_tags": recipe.dietary_tags or [],
        "difficulty": recipe.difficulty,
        "nutrition": nutrition_data
    }
    await recipe_repository.create(recipe_doc)

    # Log user activity
    await log_action(
        user, "recipe_created", request,
        target_type="recipe",
        target_id=recipe_id,
        details={"title": recipe.title, "category": recipe.category}
    )

    # Broadcast to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.RECIPE_CREATED,
        data=recipe_doc
    )

    return RecipeResponse(**recipe_doc)


@router.get("", response_model=List[RecipeResponse])
async def get_recipes(
    category: Optional[str] = None,
    search: Optional[str] = None,
    favorites_only: Optional[bool] = False,
    limit: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of recipes to return"),
    offset: Optional[int] = Query(None, ge=0, description="Number of recipes to skip"),
    user: dict = Depends(get_current_user)
):
    """
    Get recipes with optional pagination.
    - limit: Maximum recipes to return (1-100, default: all)
    - offset: Number of recipes to skip (for pagination)
    """
    user_favorites = user.get("favorites", [])

    recipes = await recipe_repository.find_by_household_or_author(
        author_id=user["id"],
        household_id=user.get("household_id"),
        category=category,
        search=search,
        favorite_ids=user_favorites,
        favorites_only=favorites_only
    )

    # Add is_favorite flag to each recipe
    for r in recipes:
        r["is_favorite"] = r["id"] in user_favorites

    # Apply pagination if specified
    if offset is not None:
        recipes = recipes[offset:]
    if limit is not None:
        recipes = recipes[:limit]

    return [RecipeResponse(**r) for r in recipes]


@router.get("/{recipe_id}")
async def get_recipe(recipe_id: str, user: dict = Depends(get_current_user)):
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    user_favorites = user.get("favorites", [])
    recipe["is_favorite"] = recipe["id"] in user_favorites

    # Check for allergen warnings
    user_allergens = await get_user_allergens(user["id"], user)
    allergen_warnings = check_allergens_in_recipe(
        recipe.get("ingredients", []),
        user_allergens
    )

    response = RecipeResponse(**recipe).model_dump()
    response["allergen_warnings"] = allergen_warnings

    return response


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(recipe_id: str, recipe: RecipeCreate, request: Request, user: dict = Depends(get_current_user)):
    existing = await recipe_repository.find_by_id(recipe_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if existing["author_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Build nutrition dict if provided
    nutrition_data = None
    if recipe.nutrition:
        nutrition_data = recipe.nutrition.model_dump()

    update_data = {
        "title": recipe.title,
        "description": recipe.description or "",
        "ingredients": [i.model_dump() for i in recipe.ingredients],
        "instructions": recipe.instructions,
        "prep_time": recipe.prep_time or 0,
        "cook_time": recipe.cook_time or 0,
        "servings": recipe.servings or 4,
        "category": recipe.category or "Other",
        "tags": recipe.tags or [],
        "image_url": recipe.image_url or "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "dietary_tags": recipe.dietary_tags or [],
        "difficulty": recipe.difficulty,
        "nutrition": nutrition_data
    }

    await recipe_repository.update_recipe(recipe_id, update_data)
    updated = await recipe_repository.find_by_id(recipe_id)

    # Log user activity
    await log_action(
        user, "recipe_updated", request,
        target_type="recipe",
        target_id=recipe_id,
        details={"title": recipe.title, "category": recipe.category}
    )

    # Broadcast update to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.RECIPE_UPDATED,
        data=updated
    )

    return RecipeResponse(**updated)


@router.delete("/{recipe_id}")
async def delete_recipe(recipe_id: str, request: Request, user: dict = Depends(get_current_user)):
    existing = await recipe_repository.find_by_id(recipe_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if existing["author_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Store title before deletion for logging
    recipe_title = existing.get("title", "Unknown")

    await recipe_repository.delete_recipe(recipe_id)

    # Log user activity
    await log_action(
        user, "recipe_deleted", request,
        target_type="recipe",
        target_id=recipe_id,
        details={"title": recipe_title}
    )

    # Broadcast deletion to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.RECIPE_DELETED,
        data={"id": recipe_id}
    )

    return {"message": "Recipe deleted"}


@router.post("/{recipe_id}/favorite")
async def toggle_favorite(recipe_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Toggle favorite status for a recipe"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    user_favorites = user.get("favorites", [])

    if recipe_id in user_favorites:
        await user_repository.remove_favorite(user["id"], recipe_id)
        is_favorite = False
        message = "Removed from favorites"
    else:
        await user_repository.add_favorite(user["id"], recipe_id)
        is_favorite = True
        message = "Added to favorites"

    # Log user activity
    action = "recipe_favorited" if is_favorite else "recipe_unfavorited"
    await log_action(
        user, action, request,
        target_type="recipe",
        target_id=recipe_id,
        details={"title": recipe.get("title", "Unknown")}
    )

    # Broadcast favorite change to user's devices
    await ws_manager.broadcast_to_user(
        user_id=user["id"],
        event_type=EventType.RECIPE_FAVORITED,
        data={"recipe_id": recipe_id, "is_favorite": is_favorite}
    )

    return {"is_favorite": is_favorite, "message": message}


@router.get("/{recipe_id}/scaled")
async def get_scaled_recipe(
    recipe_id: str,
    servings: int = Query(..., ge=1, le=100),
    user: dict = Depends(get_current_user)
):
    """Get recipe with scaled ingredient amounts"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    original_servings = recipe.get("servings", 4)
    if original_servings <= 0:
        original_servings = 4

    scale_factor = servings / original_servings

    scaled_ingredients = []
    for ing in recipe.get("ingredients", []):
        try:
            original_amount = ing.get("amount", "")
            if "/" in str(original_amount):
                parts = str(original_amount).split("/")
                if len(parts) == 2:
                    num = float(parts[0].strip())
                    denom = float(parts[1].strip())
                    original_num = num / denom
                else:
                    original_num = float(original_amount)
            else:
                original_num = float(original_amount)

            scaled_num = original_num * scale_factor
            if scaled_num == int(scaled_num):
                scaled_amount = str(int(scaled_num))
            else:
                scaled_amount = f"{scaled_num:.2f}".rstrip('0').rstrip('.')

            scaled_ingredients.append({
                "name": ing["name"],
                "amount": scaled_amount,
                "unit": ing.get("unit", "")
            })
        except (ValueError, TypeError):
            scaled_ingredients.append(ing)

    return {
        "id": recipe["id"],
        "title": recipe["title"],
        "original_servings": original_servings,
        "scaled_servings": servings,
        "scale_factor": round(scale_factor, 2),
        "ingredients": scaled_ingredients,
        "instructions": recipe.get("instructions", [])
    }


@router.get("/{recipe_id}/print")
async def get_print_recipe(recipe_id: str, user: dict = Depends(get_current_user)):
    """Get recipe formatted for printing"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    total_time = (recipe.get("prep_time", 0) or 0) + (recipe.get("cook_time", 0) or 0)

    return {
        "title": recipe["title"],
        "description": recipe.get("description", ""),
        "servings": recipe.get("servings", 4),
        "prep_time": recipe.get("prep_time", 0),
        "cook_time": recipe.get("cook_time", 0),
        "total_time": total_time,
        "category": recipe.get("category", "Other"),
        "tags": recipe.get("tags", []),
        "ingredients": recipe.get("ingredients", []),
        "instructions": recipe.get("instructions", []),
        "image_url": recipe.get("image_url", ""),
        "printed_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/{recipe_id}/allergen-check")
async def check_recipe_allergens(recipe_id: str, user: dict = Depends(get_current_user)):
    """Check a recipe against user's allergens and return warnings"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    user_allergens = await get_user_allergens(user["id"], user)
    warnings = check_allergens_in_recipe(
        recipe.get("ingredients", []),
        user_allergens
    )

    return {
        "recipe_id": recipe_id,
        "recipe_title": recipe.get("title", ""),
        "user_allergens": user_allergens,
        "warnings": warnings,
        "has_allergens": len(warnings) > 0
    }


@router.post("/{recipe_id}/image")
async def upload_recipe_image(recipe_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    existing = await recipe_repository.find_by_id(recipe_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Authorization check - only recipe author can upload images
    if existing["author_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to modify this recipe")

    # Whitelist allowed extensions
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    ext = file.filename.split(".")[-1].lower() if file.filename else "jpg"

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: jpg, jpeg, png, gif, webp")

    # Read content first to validate
    content = await file.read()

    # Validate file size (max 10MB)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")

    # Validate image content matches extension (prevents malicious file uploads)
    is_valid, error = validate_image_content(content, ext)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Ensure upload directory exists before writing
    ensure_upload_dir()

    filename = f"{recipe_id}.{ext}"
    file_path = UPLOAD_DIR / filename

    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)

    image_url = f"/api/uploads/{filename}"
    await recipe_repository.update_recipe(recipe_id, {"image_url": image_url})

    # Broadcast update
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.RECIPE_UPDATED,
        data={"id": recipe_id, "image_url": image_url}
    )

    return {"image_url": image_url}


@router.post("/{recipe_id}/share")
async def create_share_link(recipe_id: str, user: dict = Depends(get_current_user)):
    """Create a public share link for a recipe"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Authorization - only recipe author or household members can create share links
    if recipe["author_id"] != user["id"]:
        if not user.get("household_id") or recipe.get("household_id") != user["household_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to share this recipe")

    share_id = str(uuid.uuid4())[:8]
    share_doc = {
        "id": share_id,
        "recipe_id": recipe_id,
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    }
    await recipe_share_repository.create(share_doc)

    return {"share_id": share_id, "share_url": f"/shared/{share_id}"}


# ============ User Rating Endpoints ============

async def get_user_rating_for_recipe(user_id: str, recipe_id: str) -> Optional[dict]:
    """Get user's personal rating for a recipe"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, user_id, recipe_id, rating, personal_notes, created_at, updated_at
               FROM user_recipe_ratings WHERE user_id = $1 AND recipe_id = $2""",
            user_id, recipe_id
        )
        if row:
            return dict(row)
    return None


@router.get("/{recipe_id}/rating")
async def get_my_rating(recipe_id: str, user: dict = Depends(get_current_user)):
    """Get current user's rating for a recipe"""
    rating = await get_user_rating_for_recipe(user["id"], recipe_id)
    if not rating:
        return {"rating": None, "personal_notes": None}
    return {
        "rating": rating["rating"],
        "personal_notes": rating["personal_notes"]
    }


@router.post("/{recipe_id}/rating", response_model=UserRatingResponse)
async def set_rating(recipe_id: str, rating_data: UserRatingCreate, user: dict = Depends(get_current_user)):
    """Set or update user's personal rating for a recipe"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    pool = await get_pool()
    now = datetime.now(timezone.utc).isoformat()

    async with pool.acquire() as conn:
        # Check if rating exists
        existing = await get_user_rating_for_recipe(user["id"], recipe_id)

        if existing:
            # Update existing rating
            await conn.execute(
                """UPDATE user_recipe_ratings
                   SET rating = $1, personal_notes = $2, updated_at = $3
                   WHERE user_id = $4 AND recipe_id = $5""",
                rating_data.rating, rating_data.personal_notes or "", now, user["id"], recipe_id
            )
            rating_id = existing["id"]
        else:
            # Create new rating
            rating_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO user_recipe_ratings (id, user_id, recipe_id, rating, personal_notes, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                rating_id, user["id"], recipe_id, rating_data.rating, rating_data.personal_notes or "", now, now
            )

    return UserRatingResponse(
        id=rating_id,
        user_id=user["id"],
        recipe_id=recipe_id,
        rating=rating_data.rating,
        personal_notes=rating_data.personal_notes or "",
        created_at=now,
        updated_at=now
    )


@router.delete("/{recipe_id}/rating")
async def delete_rating(recipe_id: str, user: dict = Depends(get_current_user)):
    """Delete user's personal rating for a recipe"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM user_recipe_ratings WHERE user_id = $1 AND recipe_id = $2",
            user["id"], recipe_id
        )
    return {"deleted": True}
