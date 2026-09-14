"""
Meal Plans Router - CRUD operations with live refresh support
Supports recipe entries plus Mealie-style note/leftover placeholders.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from models import MealPlanCreate, MealPlanUpdate, MealPlanResponse
from dependencies import get_current_user, meal_plan_repository, recipe_repository
from database.websocket_manager import ws_manager, EventType
from utils.activity_logger import log_action
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger("laro.meal_plans")

router = APIRouter(prefix="/meal-plans", tags=["Meal Plans"])

VALID_ENTRY_TYPES = {"recipe", "note", "leftover"}


def _shape_plan(plan: dict) -> dict:
    shaped = dict(plan)
    if not shaped.get("entry_type"):
        shaped["entry_type"] = "recipe" if shaped.get("recipe_id") else "note"
    if shaped.get("adult_boost") is None:
        shaped["adult_boost"] = ""
    return shaped


def _normalize_adult_boost(raw) -> str:
    """Trim adult boost; strip a duplicated 'For adults:' prefix if present."""
    text = (raw or "").strip()
    if not text:
        return ""
    lower = text.lower()
    for prefix in ("for adults:", "for adults —", "for adults -"):
        if lower.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text[:500]


@router.post("", response_model=MealPlanResponse)
async def create_meal_plan(plan: MealPlanCreate, request: Request, user: dict = Depends(get_current_user)):
    entry_type = (plan.entry_type or "recipe").lower().strip()
    if entry_type not in VALID_ENTRY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"entry_type must be one of: {', '.join(sorted(VALID_ENTRY_TYPES))}",
        )

    recipe_id = plan.recipe_id
    recipe_title = (plan.recipe_title or "").strip()

    if entry_type == "recipe":
        if not recipe_id:
            raise HTTPException(status_code=400, detail="recipe_id is required for recipe entries")
        recipe = await recipe_repository.find_by_id(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        recipe_title = recipe["title"]
    else:
        # Note / leftover — no recipe required
        recipe_id = None
        if not recipe_title:
            raise HTTPException(
                status_code=400,
                detail="recipe_title is required for note and leftover entries",
            )

    plan_id = str(uuid.uuid4())
    household_id = user.get("household_id") or user["id"]

    plan_doc = {
        "id": plan_id,
        "date": plan.date,
        "meal_type": plan.meal_type,
        "recipe_id": recipe_id,
        "recipe_title": recipe_title,
        "notes": plan.notes or "",
        "adult_boost": _normalize_adult_boost(plan.adult_boost),
        "entry_type": entry_type,
        "household_id": household_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await meal_plan_repository.create(plan_doc)

    await log_action(
        user, "meal_plan_created", request,
        target_type="meal_plan",
        target_id=plan_id,
        details={
            "date": plan.date,
            "meal_type": plan.meal_type,
            "recipe_title": recipe_title,
            "entry_type": entry_type,
        }
    )

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

    # Drop ghost slots whose recipe was deleted (older deletes left meal_plans rows behind).
    cleaned = []
    for plan in plans or []:
        entry_type = (plan.get("entry_type") or "recipe").lower()
        recipe_id = plan.get("recipe_id")
        if entry_type == "recipe" and recipe_id:
            recipe = await recipe_repository.find_by_id(recipe_id)
            if not recipe:
                try:
                    await meal_plan_repository.delete_plan(plan["id"])
                except Exception:
                    logger.warning(
                        "Failed to purge orphan meal plan %s (missing recipe %s)",
                        plan.get("id"),
                        recipe_id,
                    )
                continue
        cleaned.append(plan)

    return [MealPlanResponse(**_shape_plan(p)) for p in cleaned]


@router.put("/{plan_id}", response_model=MealPlanResponse)
async def update_meal_plan(
    plan_id: str,
    updates: MealPlanUpdate,
    request: Request,
    user: dict = Depends(get_current_user),
):
    plan = await meal_plan_repository.find_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    household_id = user.get("household_id") or user["id"]
    if plan.get("household_id") != household_id and plan.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    payload = updates.model_dump(exclude_unset=True)
    entry_type = (payload.get("entry_type") or plan.get("entry_type") or "recipe").lower().strip()
    if entry_type not in VALID_ENTRY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"entry_type must be one of: {', '.join(sorted(VALID_ENTRY_TYPES))}",
        )

    recipe_id = payload["recipe_id"] if "recipe_id" in payload else plan.get("recipe_id")
    recipe_title = (
        (payload.get("recipe_title") if "recipe_title" in payload else plan.get("recipe_title"))
        or ""
    ).strip()

    if entry_type == "recipe":
        if not recipe_id:
            raise HTTPException(status_code=400, detail="recipe_id is required for recipe entries")
        recipe = await recipe_repository.find_by_id(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        recipe_title = recipe["title"]
    else:
        recipe_id = None
        if not recipe_title:
            raise HTTPException(
                status_code=400,
                detail="recipe_title is required for note and leftover entries",
            )

    update_doc = {
        "date": payload.get("date", plan.get("date")),
        "meal_type": payload.get("meal_type", plan.get("meal_type")),
        "recipe_id": recipe_id,
        "recipe_title": recipe_title,
        "notes": payload.get("notes", plan.get("notes") or ""),
        "adult_boost": _normalize_adult_boost(
            payload["adult_boost"] if "adult_boost" in payload else plan.get("adult_boost") or ""
        ),
        "entry_type": entry_type,
    }
    await meal_plan_repository.update_plan(plan_id, update_doc)

    updated = {**plan, **update_doc}
    await log_action(
        user, "meal_plan_updated", request,
        target_type="meal_plan",
        target_id=plan_id,
        details={
            "date": updated.get("date"),
            "meal_type": updated.get("meal_type"),
            "recipe_title": recipe_title,
            "entry_type": entry_type,
        },
    )

    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.MEAL_PLAN_UPDATED,
        data=_shape_plan(updated),
    )

    return MealPlanResponse(**_shape_plan(updated))


@router.delete("/{plan_id}")
async def delete_meal_plan(plan_id: str, request: Request, user: dict = Depends(get_current_user)):
    # Check ownership or household
    plan = await meal_plan_repository.find_by_id(plan_id)
    if not plan:
        # Idempotent delete: already gone is success (E-MP003 / stale UI ghosts)
        return {"message": "Meal plan already deleted", "already_gone": True}

    household_id = user.get("household_id") or user["id"]
    if plan.get("household_id") != household_id and plan.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    await meal_plan_repository.delete_plan(plan_id)

    await log_action(
        user, "meal_plan_deleted", request,
        target_type="meal_plan",
        target_id=plan_id,
        details={"date": plan.get("date"), "meal_type": plan.get("meal_type")}
    )

    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.MEAL_PLAN_DELETED,
        data={"id": plan_id, "date": plan.get("date"), "meal_type": plan.get("meal_type")}
    )

    return {"message": "Meal plan deleted"}


class RepeatWeekRequest(BaseModel):
    """Copy meals from source week onto the following week (replace destination)."""
    start_date: str  # yyyy-MM-dd — first day of source week
    end_date: str  # yyyy-MM-dd — last day of source week
    day_offset: int = 7


@router.post("/repeat-week")
async def repeat_week(
    data: RepeatWeekRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    from datetime import datetime as dt, timedelta

    try:
        start = dt.strptime(data.start_date[:10], "%Y-%m-%d").date()
        end = dt.strptime(data.end_date[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="start_date and end_date must be YYYY-MM-DD")

    offset = int(data.day_offset or 7)
    if offset < 1 or offset > 60:
        raise HTTPException(status_code=400, detail="day_offset out of range")

    household_id = user.get("household_id") or user["id"]
    source = await meal_plan_repository.find_by_household(
        household_id=household_id,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )
    if not source:
        raise HTTPException(status_code=400, detail="No meals in the source week to copy")

    dest_start = (start + timedelta(days=offset)).isoformat()
    dest_end = (end + timedelta(days=offset)).isoformat()
    replaced = await meal_plan_repository.delete_in_date_range(
        household_id=household_id,
        start_date=dest_start,
        end_date=dest_end,
    )

    created = 0
    for plan in source:
        try:
            src_date = dt.strptime(str(plan.get("date"))[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        new_date = (src_date + timedelta(days=offset)).isoformat()
        entry_type = (plan.get("entry_type") or ("recipe" if plan.get("recipe_id") else "note")).lower()
        plan_id = str(uuid.uuid4())
        plan_doc = {
            "id": plan_id,
            "date": new_date,
            "meal_type": plan.get("meal_type") or "Dinner",
            "recipe_id": plan.get("recipe_id") if entry_type == "recipe" else None,
            "recipe_title": plan.get("recipe_title") or "",
            "notes": plan.get("notes") or "",
            "adult_boost": plan.get("adult_boost") or "",
            "entry_type": entry_type,
            "household_id": household_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if entry_type == "recipe" and not plan_doc["recipe_id"]:
            continue
        if entry_type != "recipe" and not plan_doc["recipe_title"]:
            plan_doc["recipe_title"] = "Note"
        await meal_plan_repository.create(plan_doc)
        created += 1
        await ws_manager.broadcast_to_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id"),
            event_type=EventType.MEAL_PLAN_CREATED,
            data=plan_doc,
        )

    await log_action(
        user, "meal_plan_week_repeated", request,
        target_type="meal_plan",
        target_id=None,
        details={
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "day_offset": offset,
            "created": created,
            "replaced": replaced,
        },
    )

    return {
        "message": "Week repeated",
        "created": created,
        "replaced": replaced or 0,
        "dest_start": dest_start,
        "dest_end": dest_end,
    }
