from fastapi import APIRouter, Depends, HTTPException
from dependencies import (
    get_current_user,
    meal_plan_repository,
    shopping_list_repository,
    recipe_repository,
)
from datetime import datetime, timezone, timedelta
from typing import Optional
import json

router = APIRouter(prefix="/homeassistant", tags=["Home Assistant"])


@router.get("/config")
async def get_homeassistant_config():
    """Get Home Assistant REST sensor configuration"""
    return {
        "sensors": [
            {
                "name": "Laro Today's Meals",
                "resource": "/api/homeassistant/today",
                "value_template": "{{ value_json.meals | length }} meals planned"
            },
            {
                "name": "Laro Shopping List",
                "resource": "/api/homeassistant/shopping",
                "value_template": "{{ value_json.unchecked }} items"
            }
        ],
        "integration_note": "For the full Home Assistant integration, install the custom component from the Laro repository.",
        "example_config": """
# configuration.yaml
rest:
  - resource: http://YOUR_LARO_IP:8001/api/homeassistant/today
    headers:
      Authorization: Bearer YOUR_TOKEN
    sensor:
      - name: "Today's Meals"
        value_template: "{{ value_json.summary }}"
        json_attributes:
          - meals
          - next_meal
  - resource: http://YOUR_LARO_IP:8001/api/homeassistant/shopping
    headers:
      Authorization: Bearer YOUR_TOKEN
    sensor:
      - name: "Shopping List"
        value_template: "{{ value_json.summary }}"
        json_attributes:
          - items
          - unchecked
          - total
"""
    }


@router.get("/all")
async def homeassistant_all(user: dict = Depends(get_current_user)):
    """Get all data for Home Assistant integration in a single call"""
    household_id = user.get("household_id") or user["id"]
    user_id = user["id"]
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    week_end = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    # Get recipes
    recipes = await recipe_repository.find_by_household_or_author(
        author_id=user_id, household_id=household_id, limit=1000
    )
    recipe_count = len(recipes)

    # Get meal plans for the week
    meal_plans = await meal_plan_repository.find_by_household(
        household_id, start_date=today_str, end_date=week_end
    )

    # Get today's meals
    today_meals = [
        mp for mp in meal_plans
        if mp.get("date", "").startswith(today_str)
    ]

    # Get shopping lists
    shopping_lists = await shopping_list_repository.find_by_household(household_id)

    # Calculate shopping stats
    total_items = 0
    unchecked_items = 0
    for sl in shopping_lists:
        items = sl.get("items", [])
        total_items += len(items)
        unchecked_items += sum(1 for item in items if not item.get("checked", False))

    # Get favorites (stored as JSON array in user object)
    favorites_raw = user.get("favorites", "[]")
    if isinstance(favorites_raw, str):
        try:
            favorites = json.loads(favorites_raw)
        except json.JSONDecodeError:
            favorites = []
    else:
        favorites = favorites_raw if favorites_raw else []
    favorite_count = len(favorites)

    # Find next meal
    current_hour = today.hour
    meal_order = {"breakfast": 8, "lunch": 12, "dinner": 18, "snack": 15}
    next_meal = None
    for plan in sorted(today_meals, key=lambda x: meal_order.get(x.get("meal_type", "").lower(), 12)):
        if meal_order.get(plan.get("meal_type", "").lower(), 12) > current_hour:
            next_meal = plan
            break

    return {
        "recipe_count": recipe_count,
        "meal_plans": meal_plans,
        "today_meals": today_meals,
        "next_meal": next_meal,
        "shopping_lists": shopping_lists,
        "shopping_list_count": len(shopping_lists),
        "shopping_items_total": total_items,
        "shopping_items_unchecked": unchecked_items,
        "favorites": favorites,
        "favorite_count": favorite_count,
        "user": {
            "id": user["id"],
            "email": user.get("email"),
            "name": user.get("name"),
        },
    }


@router.get("/today")
async def homeassistant_today(user: dict = Depends(get_current_user)):
    """Get today's meals for Home Assistant"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    household_id = user.get("household_id") or user["id"]

    plans = await meal_plan_repository.find_by_household(
        household_id, start_date=today, end_date=today
    )

    # Find next meal
    current_hour = datetime.now(timezone.utc).hour
    meal_order = {"Breakfast": 8, "Lunch": 12, "Dinner": 18, "Snack": 15}
    next_meal = None
    for plan in sorted(plans, key=lambda x: meal_order.get(x.get("meal_type", ""), 12)):
        if meal_order.get(plan.get("meal_type", ""), 12) > current_hour:
            next_meal = plan
            break

    meals_summary = ", ".join([f"{p.get('meal_type', '')}: {p.get('recipe_title', '')}" for p in plans])

    return {
        "date": today,
        "meals": plans,
        "next_meal": next_meal,
        "summary": meals_summary or "No meals planned",
        "count": len(plans)
    }


@router.get("/shopping")
async def homeassistant_shopping(user: dict = Depends(get_current_user)):
    """Get shopping list summary for Home Assistant"""
    household_id = user.get("household_id") or user["id"]

    lists = await shopping_list_repository.find_by_household(household_id, limit=1)

    if not lists:
        return {"unchecked": 0, "total": 0, "items": [], "list_name": None, "summary": "No shopping list"}

    current_list = lists[0]
    items = current_list.get("items", [])
    unchecked = [i for i in items if not i.get("checked")]

    return {
        "list_name": current_list.get("name"),
        "unchecked": len(unchecked),
        "total": len(items),
        "items": unchecked[:10],  # First 10 unchecked items
        "summary": f"{len(unchecked)} items to buy"
    }


@router.get("/week")
async def homeassistant_week(user: dict = Depends(get_current_user)):
    """Get this week's meal plans for Home Assistant"""
    household_id = user.get("household_id") or user["id"]
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    week_end = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    meal_plans = await meal_plan_repository.find_by_household(
        household_id, start_date=today_str, end_date=week_end
    )

    # Group by date
    by_date = {}
    for mp in meal_plans:
        date = mp.get("date", "")[:10]
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(mp)

    return {
        "start_date": today_str,
        "end_date": week_end,
        "meal_plans": meal_plans,
        "by_date": by_date,
        "total_meals": len(meal_plans),
    }


@router.get("/recipes")
async def homeassistant_recipes(
    user: dict = Depends(get_current_user),
    limit: int = 50
):
    """Get recipes for Home Assistant"""
    household_id = user.get("household_id") or user["id"]
    user_id = user["id"]
    recipes = await recipe_repository.find_by_household_or_author(
        author_id=user_id, household_id=household_id, limit=limit
    )

    return {
        "recipes": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "description": r.get("description", "")[:100],
                "prep_time": r.get("prep_time"),
                "cook_time": r.get("cook_time"),
                "servings": r.get("servings"),
            }
            for r in recipes
        ],
        "count": len(recipes),
    }

