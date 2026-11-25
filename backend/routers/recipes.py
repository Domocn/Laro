"""
Recipes Router - CRUD operations with live refresh support
"""
from utils.recipe_fields import normalize_adaptations, normalize_category, normalize_ingredient
from utils.ingredient_groups import with_group
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request
from models import (
    RecipeCreate,
    RecipeResponse,
    UserRatingCreate,
    UserRatingResponse,
    RecipeBulkDelete,
    CheckVetoRequest,
    CheckVetoResponse,
    IngredientSubstitutionRequest,
    IngredientSubstitutionResponse,
)
from dependencies import get_current_user, recipe_repository, recipe_share_repository, user_repository, user_preferences_repository
from utils.subscription import is_premium_user
from utils.region import DEFAULT_REGION, food_lookups_region_aware, user_region, with_total_carbs
from database.connection import get_pool
from database.websocket_manager import ws_manager, EventType
from config import settings
from utils.activity_logger import log_action
from utils.security import validate_image_content
from utils.authorization import require_recipe_view, require_recipe_edit
from utils.recipe_fields import (
    ensure_list_field,
    nutrition_to_columns,
    prepare_recipe_for_response,
)
from pydantic import BaseModel
from utils.veto_replacements import check_ingredients_for_vetoes, suggest_ingredient_substitutions
from services.recipe_variants import find_version
from services.version_macros import (
    choice_macros,
    adaptations_need_macros,
    macros_consistent,
    original_badges_current,
    per_serving,
    plausibility_flags,
    recipe_lookup,
    recipe_servings,
    refresh_recipe_macros,
    stored_badges,
    totals_match,
)
from services.recipe_macros_jobs import schedule_recipe_macros
import asyncio
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


@router.post("/check-veto", response_model=CheckVetoResponse)
async def check_recipe_veto(
    body: CheckVetoRequest,
    user: dict = Depends(get_current_user),
):
    """
    Check ingredients against the user's adult (dislikedIngredients) and
    kid (kidVetoIngredients, when kid-friendly meals apply) veto lists.

    Returns hits plus category-aware replacement suggestions.
    """
    prefs = await user_preferences_repository.find_by_user(user["id"]) or {}
    result = check_ingredients_for_vetoes(body.ingredients or [], prefs)
    return CheckVetoResponse(**result)


@router.post("/backfill-fodmap")
async def backfill_fodmap_adaptations(user: dict = Depends(get_current_user)):
    """
    Turn "Low FODMAP adaptation: …" steps from older PDF imports into structured
    ``adaptations.low_fodmap`` (swaps + notes) so the Original / Low FODMAP switch works.
    Only the caller's own recipes; recipes that already have adaptations are skipped and
    the original step is left in place. Rule-based (no AI quota used).
    """
    from services.recipe_pdf_import import plan_fodmap_backfill

    recipes = await recipe_repository.find_by_author(user["id"], limit=5000)
    plan = plan_fodmap_backfill(recipes)
    now = datetime.now(timezone.utc).isoformat()  # bump so synced clients pick it up
    for recipe_id, adaptations in plan:
        await recipe_repository.update_recipe(recipe_id, {"adaptations": adaptations, "updated_at": now})
    return {
        "scanned": len(recipes),
        "updated": len(plan),
        "recipe_ids": [rid for rid, _ in plan],
    }


BACKFILL_SECONDS = 50  # stay under proxy timeouts; call again to continue
BACKFILL_CHUNK = 10  # recipes whose uncached lines go to the AI together


@router.post("/backfill-macros")
async def backfill_macros(user: dict = Depends(get_current_user)):
    """
    Make the caller's own recipes follow the one-source rule: totals = sum(line macros) / servings
    for the Original, every version and the Low FODMAP option.

    Recomputes recipes with no line macros, whose totals are more than 5% off the line sum, or
    whose versions / Low FODMAP macros are missing or stale, or whose AI lines have no grams yet
    (needed for per-100 g nutrition / ``total_grams``). Time-boxed (~50 s): ``remaining`` > 0
    means call again. Idempotent: consistent recipes are left alone (and only re-checked).
    ``flagged`` lists implausible lines / per-serving totals to look at.
    """
    import time

    started = time.monotonic()
    deadline = started + BACKFILL_SECONDS
    recipes = await recipe_repository.find_by_author(user["id"], limit=5000)
    todo = [r for r in recipes if not macros_consistent(r)]
    todo_ids = {r["id"] for r in todo}
    now = datetime.now(timezone.utc).isoformat()  # bump so synced clients pick it up
    updated, incomplete, flagged = [], [], []
    done_ids = set()
    from services.line_macros import estimate_line_macros, fill_grams
    from services.version_macros import lines_to_estimate, weightless_lines

    for start in range(0, len(todo), BACKFILL_CHUNK):
        left = deadline - time.monotonic()
        if left <= 1:
            break
        chunk = todo[start:start + BACKFILL_CHUNK]
        lines = [line for row in chunk for line in lines_to_estimate(row)]
        # Older AI badges without grams: one weights-only AI call per batch (per-100 g needs them).
        weightless = list({k: (k, t, b) for row in chunk for k, t, b in weightless_lines(row)}.values())
        try:
            # Finished AI batches are cached as they land, so a timeout still saves progress.
            # UK lookups on purpose: these macros are saved on the shared recipe (see
            # _regional_recipe_macros); region-aware lookups would be recomputed as stale.
            await asyncio.wait_for(
                asyncio.gather(estimate_line_macros(lines, fill_weights=True), fill_grams(weightless)),
                timeout=left,
            )
        except asyncio.TimeoutError:
            break
        for row in chunk:
            result = await refresh_recipe_macros(row, row.get("adaptations"), allow_ai=False, fill_weights=True)
            done_ids.add(row["id"])
            if not result["complete"]:
                incomplete.append(row["id"])
            fields = _changed_macro_fields(row, result["fields"])
            if fields:
                await recipe_repository.update_recipe(row["id"], {**fields, "updated_at": now})
                updated.append(row["id"])
                row = {**row, **fields}
            lookup = await recipe_lookup(row, allow_ai=False)
            flagged.extend(plausibility_flags(row, lookup))

    # Already-consistent recipes: plausibility only (cache reads, no AI), while time allows.
    for row in recipes:
        if row["id"] in todo_ids or time.monotonic() > deadline:
            continue
        lookup = await recipe_lookup(row, allow_ai=False)
        flagged.extend(plausibility_flags(row, lookup))

    return {
        "scanned": len(recipes),
        "updated": len(updated),
        "remaining": len(todo_ids - done_ids),  # > 0: call again
        "incomplete": len(incomplete),  # some lines could not be estimated (AI unavailable)
        "flagged": flagged,
        "recipe_ids": updated,
    }


@router.post("/backfill-version-macros")
async def backfill_version_macros(user: dict = Depends(get_current_user)):
    """Old name for POST /backfill-macros (kept for older clients / scripts)."""
    return await backfill_macros(user=user)


def _changed_macro_fields(row: dict, fields: dict) -> dict:
    from services.recipe_macros_jobs import _changed

    return _changed(row, fields)


@router.post("/substitutions", response_model=IngredientSubstitutionResponse)
async def get_ingredient_substitutions(
    body: IngredientSubstitutionRequest,
    user: dict = Depends(get_current_user),
):
    """Suggest substitutions for a single ingredient (Honeydew-style swap button).

    When recipe context is provided (or recipe_id resolves), Laro AI ranks swaps
    so they fit this dish. Falls back to curated/function/food_db maps.
    """
    name = (body.ingredient or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Ingredient is required")
    prefs = await user_preferences_repository.find_by_user(user["id"]) or {}
    limit = body.limit if body.limit is not None else 5
    limit = max(1, min(int(limit), 8))

    recipe_title = (body.recipe_title or "").strip()
    recipe_description = (body.recipe_description or "").strip()
    ingredients = list(body.ingredients or [])
    instructions = list(body.instructions or [])

    if body.recipe_id and (not recipe_title or not ingredients):
        recipe = await recipe_repository.find_by_id(body.recipe_id)
        if recipe:
            require_recipe_view(user, recipe)
            recipe_title = recipe_title or (recipe.get("title") or "")
            recipe_description = recipe_description or (recipe.get("description") or "")
            if not ingredients:
                ingredients = list(recipe.get("ingredients") or [])
            if not instructions:
                instructions = list(recipe.get("instructions") or [])

    local = suggest_ingredient_substitutions(name, prefs, limit=limit)
    suggestions = list(local.get("suggestions") or [])
    ai_used = False
    source = "local"

    use_ai = body.use_ai is not False
    has_context = bool(recipe_title or ingredients)
    if use_ai and has_context:
        from utils.ai_substitutions import ai_rank_substitutions
        from utils.preference_context import format_veto_exclusion_lines

        diet_notes = "\n".join(format_veto_exclusion_lines(prefs) or [])
        ai_result = await ai_rank_substitutions(
            name,
            recipe_title=recipe_title,
            recipe_description=recipe_description,
            ingredients=ingredients,
            instructions=instructions,
            seed_suggestions=suggestions,
            diet_notes=diet_notes,
            limit=limit,
            user=user,
            meter_quota=True,
        )
        if ai_result.get("suggestions"):
            suggestions = ai_result["suggestions"]
            ai_used = True
            source = "ai"

    return IngredientSubstitutionResponse(
        ingredient=name,
        suggestions=suggestions,
        category=local.get("category"),
        roles=local.get("roles"),
        ai_used=ai_used,
        source=source,
    )


@router.post("", response_model=RecipeResponse)
async def create_recipe(recipe: RecipeCreate, request: Request, user: dict = Depends(get_current_user)):
    from utils.subscription import assert_can_create_recipes

    await assert_can_create_recipes(user, recipe_repository, 1)

    recipe_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # DB stores flat nutrition_* columns (not a JSON "nutrition" blob)
    recipe_doc = {
        "id": recipe_id,
        "title": recipe.title,
        "description": recipe.description or "",
        "ingredients": [normalize_ingredient(i.model_dump()) for i in recipe.ingredients],
        "instructions": recipe.instructions,
        "prep_time": recipe.prep_time or 0,
        "cook_time": recipe.cook_time or 0,
        "servings": recipe.servings or 4,
        "category": normalize_category(recipe.category) if recipe.category else "Other",
        "tags": recipe.tags or [],
        "image_url": recipe.image_url or "",
        "author_id": user["id"],
        "household_id": user.get("household_id"),
        "created_at": now,
        "updated_at": now,
        "dietary_tags": recipe.dietary_tags or [],
        "difficulty": recipe.difficulty,
        **nutrition_to_columns(recipe.nutrition),
    }
    if recipe.cookbook_id:
        recipe_doc["cookbook_id"] = recipe.cookbook_id
        recipe_doc["source_type"] = recipe.source_type or "cookbook"
    elif recipe.source_type:
        recipe_doc["source_type"] = recipe.source_type
    if recipe.source_url:
        recipe_doc["source_url"] = recipe.source_url
    if recipe.source_author:
        recipe_doc["source_author"] = recipe.source_author.strip().lstrip("@")
    if recipe.cookbook_page is not None:
        recipe_doc["cookbook_page"] = recipe.cookbook_page
    if recipe.video_url:
        recipe_doc["video_url"] = _clean_video_url(recipe.video_url)
    adaptations = normalize_adaptations(recipe.adaptations)
    if adaptations:
        recipe_doc["adaptations"] = adaptations
    # Totals = sum(line macros) / servings for the Original, versions and Low FODMAP. Cached
    # lines apply now; anything new is estimated in the background (the save never waits on AI).
    macros = await refresh_recipe_macros(recipe_doc, allow_ai=False)
    recipe_doc.update(macros["fields"])
    await recipe_repository.create(recipe_doc)
    if not macros["complete"]:
        schedule_recipe_macros([recipe_id], user)

    response_doc = prepare_recipe_for_response(recipe_doc)

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
        data=response_doc
    )

    return RecipeResponse(**response_doc)


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

    # Add is_favorite flag and shape nutrition/dietary fields for the API
    shaped = []
    for r in recipes:
        r["is_favorite"] = r["id"] in user_favorites
        shaped.append(prepare_recipe_for_response(r))

    # Apply pagination if specified
    if offset is not None:
        shaped = shaped[offset:]
    if limit is not None:
        shaped = shaped[:limit]

    return [RecipeResponse(**r) for r in shaped]


@router.get("/{recipe_id}")
async def get_recipe(recipe_id: str, user: dict = Depends(get_current_user)):
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    require_recipe_view(user, recipe)

    recipe = prepare_recipe_for_response(recipe)
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


def _ingredient_keys(value) -> list:
    from services.version_macros import line_key

    return [line_key(i) for i in ensure_list_field(value)]


def _clean_video_url(url):
    """Only http(s) links (no javascript:/data: URLs rendered as links on web)."""
    url = (url or "").strip()
    if not url:
        return None
    if not url.lower().startswith(("http://", "https://")) or len(url) > 2000:
        raise HTTPException(status_code=400, detail="Video link must be an http(s) URL")
    return url


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(recipe_id: str, recipe: RecipeCreate, request: Request, user: dict = Depends(get_current_user)):
    existing = await recipe_repository.find_by_id(recipe_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Recipe not found")

    require_recipe_edit(user, existing)

    update_data = {
        "title": recipe.title,
        "description": recipe.description or "",
        # Section in ``group``, clean name (a legacy "Sauce: tahini" prefix is split off).
        "ingredients": [with_group(i.model_dump()) for i in recipe.ingredients],
        "instructions": recipe.instructions,
        "prep_time": recipe.prep_time or 0,
        "cook_time": recipe.cook_time or 0,
        "servings": recipe.servings or 4,
        "category": recipe.category or "Other",
        "tags": recipe.tags or [],
        "image_url": recipe.image_url or "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Only overwrite nutrition / dietary tags / difficulty when the client actually sent them.
    # Older clients (and the web edit form before 4.4.41) omitted these fields, and treating
    # "missing" as "empty" silently wiped imported macros and diet tags on every edit.
    sent = recipe.model_fields_set
    if "dietary_tags" in sent:
        update_data["dietary_tags"] = recipe.dietary_tags or []
    if "difficulty" in sent:
        update_data["difficulty"] = recipe.difficulty
    if "nutrition" in sent:
        update_data.update(nutrition_to_columns(recipe.nutrition))
    if "video_url" in sent:
        update_data["video_url"] = _clean_video_url(recipe.video_url)
    # Checked line macros ("Check the numbers") survive editors that don't send them; a
    # confirmation whose line was edited / removed is dropped (services/confirmed_lines.py).
    from services.confirmed_lines import _MISSING, reconcile_on_update

    reconciled, adaptations_changed = reconcile_on_update(
        existing.get("adaptations"),
        recipe.adaptations if "adaptations" in sent else _MISSING,
        {**existing, **update_data},
    )
    if "adaptations" in sent or adaptations_changed:
        update_data["adaptations"] = reconciled

    # The Original's line macros are indexed to its old list; drop them when the list changed.
    if _ingredient_keys(existing.get("ingredients")) != _ingredient_keys(update_data["ingredients"]):
        update_data["ingredient_macros"] = None
    # One source of truth: totals = sum(line macros) / servings for the Original and every
    # version / Low FODMAP list (a typed-in total would disagree with the badges, so it is
    # replaced once the lines are known). Cached lines apply now; new lines are estimated in
    # the background and pushed to open pages.
    merged = {**existing, **update_data}
    macros = await refresh_recipe_macros(merged, existing.get("adaptations"), allow_ai=False)
    fields = dict(macros["fields"])
    if "adaptations" in fields and (
        fields["adaptations"] != normalize_adaptations(existing.get("adaptations")) or "adaptations" in sent
    ):
        update_data["adaptations"] = fields.pop("adaptations")
    else:
        fields.pop("adaptations", None)
    update_data.update(fields)

    await recipe_repository.update_recipe(recipe_id, update_data)
    if not macros["complete"]:
        schedule_recipe_macros([recipe_id], user)
    updated = await recipe_repository.find_by_id(recipe_id)
    updated = prepare_recipe_for_response(updated)

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


@router.delete("/bulk")
async def delete_recipes_bulk(
    bulk: RecipeBulkDelete,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Delete multiple recipes the user is allowed to edit (author or admin).
    Unauthorized / missing ids are skipped and reported in the response.
    """
    ids = [i for i in (bulk.recipe_ids or []) if i]
    if not ids:
        raise HTTPException(status_code=400, detail="recipe_ids required")
    if len(ids) > 200:
        raise HTTPException(status_code=400, detail="At most 200 recipes per bulk delete")

    deleted = []
    skipped = []
    for recipe_id in ids:
        existing = await recipe_repository.find_by_id(recipe_id)
        if not existing:
            skipped.append({"id": recipe_id, "reason": "not_found"})
            continue
        try:
            require_recipe_edit(user, existing)
        except HTTPException:
            skipped.append({"id": recipe_id, "reason": "forbidden"})
            continue

        title = existing.get("title", "Unknown")
        await recipe_repository.delete_recipe(recipe_id)
        deleted.append({"id": recipe_id, "title": title})

        await log_action(
            user, "recipe_deleted", request,
            target_type="recipe",
            target_id=recipe_id,
            details={"title": title, "bulk": True},
        )
        await ws_manager.broadcast_to_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id"),
            event_type=EventType.RECIPE_DELETED,
            data={"id": recipe_id},
        )

    return {
        "message": f"Deleted {len(deleted)} recipes",
        "deleted_count": len(deleted),
        "skipped_count": len(skipped),
        "deleted": deleted,
        "skipped": skipped,
    }


@router.delete("/{recipe_id}")
async def delete_recipe(recipe_id: str, request: Request, user: dict = Depends(get_current_user)):
    existing = await recipe_repository.find_by_id(recipe_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Recipe not found")

    require_recipe_edit(user, existing)

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
    require_recipe_view(user, recipe)

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
    require_recipe_view(user, recipe)

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


@router.get("/{recipe_id}/ingredient-macros")
async def get_ingredient_macros(recipe_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Per-ingredient macro breakdown (Laro Pro) plus the per-serving totals they add up to.

    Line macros come from ``services.line_macros`` (AI, cached per line). Computing them also
    writes the recipe's totals (= sum / servings) and its version / Low FODMAP macros, so the
    totals card and the badges always agree.
    """
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    require_recipe_view(user, recipe)
    if not is_premium_user(user):
        raise HTTPException(status_code=403, detail="Laro Pro required for the per-ingredient macro breakdown")

    if not ensure_list_field(recipe.get("ingredients")):
        return {"ingredient_macros": [], "nutrition": None}

    client = getattr(request.app.state, "http_client", None)
    region = await user_region(user)
    if region != DEFAULT_REGION and food_lookups_region_aware():
        regional = await _regional_recipe_macros(recipe, region, client=client)
        if regional is not None and regional["ingredient_macros"] is not None:
            return {
                "ingredient_macros": regional["ingredient_macros"],
                "nutrition": with_total_carbs(regional["nutrition"], regional["ingredient_macros"], recipe_servings(recipe)),
                "region": region,
            }

    cached = stored_badges(recipe)
    if cached is not None and not original_badges_current(recipe):
        cached = None  # saved before the food-database-first rule (or the database changed): recompute
    if cached is not None:
        totals = per_serving(cached, recipe_servings(recipe))
        stored = {k: recipe.get(f"nutrition_{k}") for k in totals}
        if not totals_match(stored, totals, tolerance=0):
            # Totals drifted from the badges (older import / AI guess): the badges win.
            try:
                await recipe_repository.update_recipe(recipe_id, {
                    **{f"nutrition_{k}": v for k, v in totals.items()},
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass
        return {"ingredient_macros": cached, "nutrition": with_total_carbs(totals, cached, recipe_servings(recipe))}

    result = await refresh_recipe_macros(recipe, recipe.get("adaptations"), allow_ai=True, client=client,
                                         fill_weights=True)
    fields = result["fields"]
    if "ingredient_macros" not in fields:
        raise HTTPException(status_code=502, detail="Could not compute the ingredient breakdown right now")
    changed = _changed_macro_fields(recipe, fields)
    if changed:
        changed["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            await recipe_repository.update_recipe(recipe_id, changed)
        except Exception:
            pass
    response = {
        "ingredient_macros": fields["ingredient_macros"],
        "nutrition": with_total_carbs(result["nutrition"], fields["ingredient_macros"], recipe_servings(recipe)),
    }
    # Same shape as the recipe response (incl. the derived per-100 g fields): the page swaps it in.
    from services.nutrition_basis import attach_weight_fields

    adaptations = fields["adaptations"] if "adaptations" in fields else normalize_adaptations(recipe.get("adaptations"))
    response["adaptations"] = attach_weight_fields(recipe, adaptations, fields["ingredient_macros"])
    return response


async def _regional_recipe_macros(recipe: dict, region: str, *, version=None, low_fodmap: bool = False, client=None):
    """{nutrition, ingredient_macros} for a non-UK region, computed per request and never saved.

    The recipe's stored macros stay on the UK default: they are shared with everyone who can see
    the recipe, and the stale-badge check compares them with UK lookups (saving US numbers would
    make the next UK view recompute them, and back again - the backfill stays on UK for the same
    reason). Lines the AI estimated are cached per line, so this costs database lookups only.
    None when nothing could be computed."""
    computed = await refresh_recipe_macros(
        recipe, recipe.get("adaptations"), allow_ai=True, force=True, client=client, region=region
    )
    fields = computed.get("fields") or {}
    if not fields:
        return None
    preview = {**recipe, **fields}
    chosen = choice_macros(preview, version, low_fodmap) if (version or low_fodmap) else None
    if chosen is not None:
        return {"nutrition": chosen.get("nutrition"), "ingredient_macros": chosen.get("ingredient_macros") or []}
    return {"nutrition": computed.get("nutrition"), "ingredient_macros": fields.get("ingredient_macros")}


class MacrosPreviewRequest(BaseModel):
    version: Optional[str] = None
    low_fodmap: bool = False


@router.post("/{recipe_id}/macros-preview")
async def macros_preview(recipe_id: str, body: MacrosPreviewRequest, user: dict = Depends(get_current_user)):
    """{nutrition, ingredient_macros} for a version / Low FODMAP choice as shown on the recipe page.

    Uses the stored per-version macros; when missing they are computed now from the line macros
    (cached per line, AI for new lines) and saved for next time. ``ingredient_macros`` is Laro Pro only (same as
    GET /ingredient-macros). Plain Original returns the recipe's own nutrition.
    """
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    require_recipe_view(user, recipe)

    region = await user_region(user)
    if region != DEFAULT_REGION and food_lookups_region_aware():
        regional = await _regional_recipe_macros(recipe, region, version=body.version, low_fodmap=body.low_fodmap)
        if regional is not None and regional.get("nutrition"):
            from services.nutrition_basis import bake_yield, weight_info

            badges = regional.get("ingredient_macros") or []
            weights = weight_info(badges or None, bake_yield(recipe.get("title")))
            return {
                "nutrition": with_total_carbs(regional["nutrition"], badges, recipe_servings(recipe)),
                "ingredient_macros": badges if is_premium_user(user) else [],
                "region": region,
                **(weights or {}),
            }

    result = choice_macros(recipe, body.version, body.low_fodmap)
    current = normalize_adaptations(recipe.get("adaptations")) or {}
    wants_variant = bool(find_version(recipe, body.version)) or (
        body.low_fodmap and bool((current.get("low_fodmap") or {}).get("swaps"))
    )
    if wants_variant and (result is None or adaptations_need_macros(current)):
        computed = await refresh_recipe_macros(recipe, current, allow_ai=True, fill_weights=True)
        changed = _changed_macro_fields(recipe, computed["fields"])
        if changed:
            recipe = {**recipe, **changed}
            try:
                await recipe_repository.update_recipe(
                    recipe_id, {**changed, "updated_at": datetime.now(timezone.utc).isoformat()}
                )
            except Exception:
                pass
        result = choice_macros(recipe, body.version, body.low_fodmap)
    if result is None:
        shaped = prepare_recipe_for_response(recipe)
        result = {
            "nutrition": shaped.get("nutrition"),
            "ingredient_macros": stored_badges(recipe) or [],
        }
    from services.nutrition_basis import bake_yield, weight_info

    badges = result.get("ingredient_macros") or []
    weights = weight_info(badges or None, bake_yield(recipe.get("title")))
    return {
        "nutrition": with_total_carbs(result.get("nutrition"), badges, recipe_servings(recipe)),
        "ingredient_macros": badges if is_premium_user(user) else [],
        # Per-100 g view (batch / base recipes): whole-list weight + macros per 100 g.
        **(weights or {}),
    }


@router.get("/{recipe_id}/print")
async def get_print_recipe(recipe_id: str, user: dict = Depends(get_current_user)):
    """Get recipe formatted for printing"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    require_recipe_view(user, recipe)

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
    require_recipe_view(user, recipe)

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

    require_recipe_edit(user, existing)

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

    ensure_upload_dir()
    from utils.image_store import compress_image_bytes, upload_dir as image_upload_dir

    compressed = compress_image_bytes(content)
    filename = f"{uuid.uuid4().hex}.jpg"
    file_path = image_upload_dir() / filename
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(compressed)

    image_url = f"/api/uploads/{filename}"
    await recipe_repository.update_recipe(recipe_id, {"image_url": image_url})

    from utils.upload_tokens import sign_upload_path
    signed_url = sign_upload_path(image_url)

    # Broadcast update
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.RECIPE_UPDATED,
        data={"id": recipe_id, "image_url": signed_url}
    )

    return {"image_url": signed_url}


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
        "share_code": share_id,
        "recipe_id": recipe_id,
        "user_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "is_active": True,
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
    require_recipe_view(user, recipe)

    pool = await get_pool()
    now = datetime.now(timezone.utc).isoformat()
    # Raw asyncpg needs a datetime for TIMESTAMP columns; the ISO string 500'd every rating save.
    db_now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with pool.acquire() as conn:
        # Check if rating exists
        existing = await get_user_rating_for_recipe(user["id"], recipe_id)

        if existing:
            # Update existing rating
            await conn.execute(
                # COALESCE: saving just a note keeps the user's existing star rating.
                """UPDATE user_recipe_ratings
                   SET rating = COALESCE($1, rating), personal_notes = $2, updated_at = $3
                   WHERE user_id = $4 AND recipe_id = $5""",
                rating_data.rating, rating_data.personal_notes or "", db_now, user["id"], recipe_id
            )
            rating_id = existing["id"]
            saved_rating = rating_data.rating if rating_data.rating is not None else existing.get("rating")
        else:
            # Create new rating
            rating_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO user_recipe_ratings (id, user_id, recipe_id, rating, personal_notes, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                rating_id, user["id"], recipe_id, rating_data.rating, rating_data.personal_notes or "", db_now, db_now
            )
            saved_rating = rating_data.rating

    return UserRatingResponse(
        id=rating_id,
        user_id=user["id"],
        recipe_id=recipe_id,
        rating=saved_rating,
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
