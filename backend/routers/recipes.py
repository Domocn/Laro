"""
Recipes Router - CRUD operations with live refresh support
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request
from models import RecipeCreate, RecipeResponse
from dependencies import get_current_user, recipe_repository, recipe_share_repository, user_repository
from database.websocket_manager import ws_manager, EventType
from config import settings
from utils.activity_logger import log_action
from utils.security import validate_image_content
import uuid
import aiofiles
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pathlib import Path

router = APIRouter(prefix="/recipes", tags=["Recipes"])


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
        "updated_at": now
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


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(recipe_id: str, user: dict = Depends(get_current_user)):
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    user_favorites = user.get("favorites", [])
    recipe["is_favorite"] = recipe["id"] in user_favorites

    return RecipeResponse(**recipe)


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(recipe_id: str, recipe: RecipeCreate, request: Request, user: dict = Depends(get_current_user)):
    existing = await recipe_repository.find_by_id(recipe_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if existing["author_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

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
        "updated_at": datetime.now(timezone.utc).isoformat()
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
