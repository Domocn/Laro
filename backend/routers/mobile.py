"""
Mobile-optimized API endpoints for Android app integration.
Provides lightweight, combined endpoints to reduce network round-trips.
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import date, timedelta, datetime, timezone

from dependencies import (
    get_current_user,
    recipe_repository,
    meal_plan_repository,
    shopping_list_repository,
    pantry_repository,
)

router = APIRouter(prefix="/mobile", tags=["mobile"])


class RecipeSummary(BaseModel):
    """Lightweight recipe for list views"""
    id: str
    title: str
    image_url: Optional[str] = None
    category: str = "Other"
    total_time: int = 0
    servings: int = 4
    is_favorite: bool = False


class ShoppingListSummary(BaseModel):
    """Lightweight shopping list for list views"""
    id: str
    name: str
    item_count: int = 0
    checked_count: int = 0
    created_at: str


class MealPlanSummary(BaseModel):
    """Lightweight meal plan for list views"""
    id: str
    date: str
    meal_type: str
    recipe_title: str
    recipe_image: Optional[str] = None


class DashboardResponse(BaseModel):
    """Combined dashboard data for mobile home screen"""
    recent_recipes: List[RecipeSummary]
    upcoming_meals: List[MealPlanSummary]
    active_shopping_lists: List[ShoppingListSummary]
    pantry_low_items: int = 0
    total_recipes: int = 0


@router.get("/dashboard", response_model=DashboardResponse)
async def get_mobile_dashboard(
    user: dict = Depends(get_current_user)
):
    """
    Get combined dashboard data in a single request.
    Optimized for mobile app home screen to reduce network round-trips.
    """
    user_id = user["id"]
    household_id = user.get("household_id")
    today = date.today()
    week_end = today + timedelta(days=7)

    # Recent recipes (last 5)
    all_recipes = await recipe_repository.find_by_household_or_user(
        user_id=user_id,
        household_id=household_id
    )
    
    recent_recipes = []
    for r in (all_recipes or [])[:5]:
        total_time = (r.get("prep_time") or 0) + (r.get("cook_time") or 0)
        recent_recipes.append(RecipeSummary(
            id=r["id"],
            title=r.get("title", "Untitled"),
            image_url=r.get("image_url"),
            category=r.get("category") or "Other",
            total_time=total_time,
            servings=r.get("servings") or 4,
            is_favorite=r.get("is_favorite", False)
        ))

    # Upcoming meals (next 7 days)
    meal_plans = await meal_plan_repository.find_by_date_range(
        user_id=user_id,
        household_id=household_id,
        start_date=today.isoformat(),
        end_date=week_end.isoformat()
    )
    
    upcoming_meals = []
    for m in (meal_plans or [])[:10]:
        upcoming_meals.append(MealPlanSummary(
            id=m["id"],
            date=str(m.get("date", "")),
            meal_type=m.get("meal_type", ""),
            recipe_title=m.get("recipe_title", "Unknown"),
            recipe_image=m.get("recipe_image")
        ))

    # Shopping lists
    shopping_lists = await shopping_list_repository.find_by_household_or_user(
        user_id=user_id,
        household_id=household_id
    )
    
    active_shopping_lists = []
    for s in (shopping_lists or [])[:3]:
        items = s.get("items", [])
        checked = sum(1 for i in items if i.get("is_checked", False))
        active_shopping_lists.append(ShoppingListSummary(
            id=s["id"],
            name=s.get("name", "Shopping List"),
            item_count=len(items),
            checked_count=checked,
            created_at=s.get("created_at", "")
        ))

    # Pantry low items count
    pantry_low_count = 0
    try:
        pantry_items = await pantry_repository.find_by_household(household_id) if household_id else []
        pantry_low_count = sum(1 for p in pantry_items if p.get("quantity", 0) < p.get("min_quantity", 1))
    except Exception:
        pass

    return DashboardResponse(
        recent_recipes=recent_recipes,
        upcoming_meals=upcoming_meals,
        active_shopping_lists=active_shopping_lists,
        pantry_low_items=pantry_low_count,
        total_recipes=len(all_recipes or [])
    )


@router.get("/recipes/list", response_model=List[RecipeSummary])
async def get_recipes_list(
    category: Optional[str] = None,
    favorites_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user)
):
    """
    Get lightweight recipe list for mobile.
    Returns only essential fields to reduce payload size.
    """
    user_id = user["id"]
    household_id = user.get("household_id")

    all_recipes = await recipe_repository.find_by_household_or_user(
        user_id=user_id,
        household_id=household_id
    )
    
    # Filter by category
    if category and category != "All":
        all_recipes = [r for r in all_recipes if r.get("category") == category]
    
    # Filter by favorites
    if favorites_only:
        all_recipes = [r for r in all_recipes if r.get("is_favorite", False)]
    
    # Apply pagination
    paginated = all_recipes[offset:offset + limit]
    
    return [
        RecipeSummary(
            id=r["id"],
            title=r.get("title", "Untitled"),
            image_url=r.get("image_url"),
            category=r.get("category") or "Other",
            total_time=(r.get("prep_time") or 0) + (r.get("cook_time") or 0),
            servings=r.get("servings") or 4,
            is_favorite=r.get("is_favorite", False)
        )
        for r in paginated
    ]


@router.get("/sync/check")
async def check_sync_status(
    last_sync: Optional[str] = Query(None, description="ISO timestamp of last sync"),
    user: dict = Depends(get_current_user)
):
    """
    Check if data has changed since last sync.
    Returns counts of modified items to help mobile app decide if full sync needed.
    """
    user_id = user["id"]
    household_id = user.get("household_id")

    result = {
        "needs_sync": False,
        "changes": {}
    }

    if last_sync:
        try:
            sync_time = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
            
            # Get all items and count changes
            recipes = await recipe_repository.find_by_household_or_user(user_id, household_id)
            recipes_changed = sum(1 for r in (recipes or []) 
                                  if r.get("updated_at", "") > last_sync)
            
            meal_plans = await meal_plan_repository.find_by_household_or_user(user_id, household_id)
            meals_changed = sum(1 for m in (meal_plans or []) 
                               if m.get("updated_at", "") > last_sync)
            
            shopping_lists = await shopping_list_repository.find_by_household_or_user(user_id, household_id)
            lists_changed = sum(1 for s in (shopping_lists or []) 
                               if s.get("updated_at", "") > last_sync)

            result["changes"] = {
                "recipes": recipes_changed,
                "meal_plans": meals_changed,
                "shopping_lists": lists_changed
            }
            result["needs_sync"] = any([recipes_changed, meals_changed, lists_changed])
        except ValueError:
            result["needs_sync"] = True
    else:
        # No last sync time, always needs sync
        result["needs_sync"] = True

    return result
