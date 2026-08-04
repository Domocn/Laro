"""
Meal Plans Router - CRUD operations with live refresh support
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from models import MealPlanCreate, MealPlanResponse
from dependencies import get_current_user, meal_plan_repository, recipe_repository
from database.websocket_manager import ws_manager, EventType
from utils.activity_logger import log_action
import uuid
from datetime import datetime, timezone
from typing import List, Optional

router = APIRouter(prefix="/meal-plans", tags=["Meal Plans"])


@router.post("", response_model=MealPlanResponse)
async def create_meal_plan(plan: MealPlanCreate, request: Request, user: dict = Depends(get_current_user)):
    recipe = await recipe_repository.find_by_id(plan.recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    plan_id = str(uuid.uuid4())
    household_id = user.get("household_id") or user["id"]

    plan_doc = {
        "id": plan_id,
        "date": plan.date,
        "meal_type": plan.meal_type,
        "recipe_id": plan.recipe_id,
        "recipe_title": recipe["title"],
        "notes": plan.notes or "",
        "household_id": household_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await meal_plan_repository.create(plan_doc)

    # Log user activity
    await log_action(
        user, "meal_plan_created", request,
        target_type="meal_plan",
        target_id=plan_id,
        details={"date": plan.date, "meal_type": plan.meal_type, "recipe_title": recipe["title"]}
    )

    # Broadcast to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.MEAL_PLAN_CREATED,
        data=plan_doc
    )

    return MealPlanResponse(**plan_doc)


@router.get("", response_model=List[MealPlanResponse])
async def get_meal_plans(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    household_id = user.get("household_id") or user["id"]

    plans = await meal_plan_repository.find_by_household(
        household_id=household_id,
        start_date=start_date,
        end_date=end_date
    )

    return [MealPlanResponse(**p) for p in plans]


@router.delete("/{plan_id}")
async def delete_meal_plan(plan_id: str, request: Request, user: dict = Depends(get_current_user)):
    # Check ownership or household
    plan = await meal_plan_repository.find_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    household_id = user.get("household_id") or user["id"]
    if plan.get("household_id") != household_id and plan.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    await meal_plan_repository.delete_plan(plan_id)

    # Log user activity
    await log_action(
        user, "meal_plan_deleted", request,
        target_type="meal_plan",
        target_id=plan_id,
        details={"date": plan.get("date"), "meal_type": plan.get("meal_type")}
    )

    # Broadcast deletion to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.MEAL_PLAN_DELETED,
        data={"id": plan_id, "date": plan.get("date"), "meal_type": plan.get("meal_type")}
    )

    return {"message": "Meal plan deleted"}
