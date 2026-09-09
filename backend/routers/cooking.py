"""
Cooking Router - Cooking sessions, feedback, and tonight suggestions
"""
from fastapi import APIRouter, HTTPException, Depends
from models import RecipeFeedback, CookSessionCreate, CookSessionComplete, MarkCookedRequest
from dependencies import (
    get_current_user, recipe_repository, meal_plan_repository,
    cook_session_repository, recipe_feedback_repository
)
from database.websocket_manager import ws_manager, EventType
from database.connection import get_db
import logging
import uuid
from datetime import datetime, timezone, date
from typing import List, Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cooking", tags=["Cooking"])


async def _maybe_sync_google_health(
    user_id: str,
    recipe_id: str,
    cook_session_id: Optional[str] = None,
) -> Optional[dict]:
    """Best-effort Google Health nutrition sync; never fails the cook flow."""
    try:
        from services import google_health as gh

        if not await gh.get_link(user_id):
            return None
        recipe = await recipe_repository.find_by_id(recipe_id)
        if not recipe:
            return None
        return await gh.sync_recipe_to_google_health(
            user_id=user_id,
            recipe=recipe,
            cook_session_id=cook_session_id,
            servings=1.0,
        )
    except Exception:
        logger.warning(
            "Google Health sync skipped/failed for recipe %s",
            recipe_id,
            exc_info=True,
        )
        return None


async def _touch_last_cooked(recipe_id: str, when: datetime) -> None:
    """Stamp recipes.last_cooked_at when a cook finishes."""
    await recipe_repository.update_recipe(recipe_id, {"last_cooked_at": when})


async def _merge_personal_note(user_id: str, recipe_id: str, notes: str, when: datetime) -> None:
    """Append cook note into user_recipe_ratings.personal_notes when present."""
    notes = (notes or "").strip()
    if not notes:
        return
    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """SELECT id, personal_notes FROM user_recipe_ratings
               WHERE user_id = $1 AND recipe_id = $2""",
            user_id, recipe_id,
        )
        if existing:
            prev = (existing["personal_notes"] or "").strip()
            if prev and notes in prev:
                merged = prev
            elif prev:
                merged = f"{prev}\n{notes}"
            else:
                merged = notes
            await conn.execute(
                """UPDATE user_recipe_ratings
                   SET personal_notes = $1, updated_at = $2
                   WHERE id = $3""",
                merged, when, existing["id"],
            )
        else:
            # Rating is required on the table — use a neutral 3 until user rates
            await conn.execute(
                """INSERT INTO user_recipe_ratings
                   (id, user_id, recipe_id, rating, personal_notes, created_at, updated_at)
                   VALUES ($1, $2, $3, 3, $4, $5, $5)""",
                str(uuid.uuid4()), user_id, recipe_id, notes, when,
            )


@router.get("/tonight")
async def get_tonight_suggestions(user: dict = Depends(get_current_user)):
    """Get 3 quick recipe suggestions for tonight based on user preferences"""
    user_id = user["id"]
    household_id = user.get("household_id")
    today = date.today().isoformat()

    # First check if there's already a meal planned for tonight
    if household_id:
        planned_meal = await meal_plan_repository.find_by_date_and_meal_type(
            household_id, today, "dinner"
        )
    else:
        planned_meal = None

    # If dinner is planned with a real recipe, return that
    if planned_meal and planned_meal.get("recipe_id"):
        recipe = await recipe_repository.find_by_id(planned_meal["recipe_id"])
        if recipe:
            total_time = (recipe.get("prep_time", 0) or 0) + (recipe.get("cook_time", 0) or 0)
            effort = "Low"
            if total_time > 45 or len(recipe.get("ingredients", [])) > 10:
                effort = "Medium"
            if total_time > 75 or len(recipe.get("ingredients", [])) > 15:
                effort = "High"

            return {
                "planned": True,
                "meal_type": planned_meal.get("meal_type", "Dinner"),
                "recipe": {
                    **recipe,
                    "effort": effort,
                    "total_time": total_time
                }
            }

    # Get user's feedback history to boost/bury recipes
    boosted = await recipe_feedback_repository.get_boosted_recipes(user_id)
    buried = await recipe_feedback_repository.get_buried_recipes(user_id)

    # Build query for user's recipes - get recipes they own OR in their household
    recipes = await recipe_repository.find_by_household_or_author(
        author_id=user_id,
        household_id=household_id,
        limit=100
    )

    # Score recipes
    scored = []
    for recipe in recipes:
        score = 50  # Base score

        # Boost 'yes' recipes
        if recipe["id"] in boosted:
            score += 30

        # Bury 'no' recipes heavily
        if recipe["id"] in buried:
            score -= 50

        # Prefer quick recipes (< 45 min total)
        total_time = (recipe.get("prep_time", 0) or 0) + (recipe.get("cook_time", 0) or 0)
        if total_time <= 30:
            score += 20
        elif total_time <= 45:
            score += 10
        elif total_time > 60:
            score -= 10

        # Calculate effort level
        effort = "Low"
        if total_time > 45 or len(recipe.get("ingredients", [])) > 10:
            effort = "Medium"
        if total_time > 75 or len(recipe.get("ingredients", [])) > 15:
            effort = "High"

        scored.append({
            **recipe,
            "_score": score,
            "effort": effort,
            "total_time": total_time
        })

    # Sort by score and pick top 3
    scored.sort(key=lambda x: x["_score"], reverse=True)
    suggestions = scored[:3]

    # Remove internal score from response
    for s in suggestions:
        del s["_score"]

    return {"planned": False, "suggestions": suggestions}


@router.post("/session")
async def start_cook_session(data: CookSessionCreate, user: dict = Depends(get_current_user)):
    """Start a cooking session for a recipe"""
    session_id = str(uuid.uuid4())

    if data.started_at:
        started_at = datetime.fromisoformat(data.started_at.replace("Z", "+00:00")).replace(tzinfo=None)
    else:
        started_at = datetime.now(timezone.utc).replace(tzinfo=None)

    session = {
        "id": session_id,
        "user_id": user["id"],
        "recipe_id": data.recipe_id,
        "started_at": started_at,
        "completed_at": None,
        "feedback": None,
        "notes": "",
    }

    await cook_session_repository.create(session)

    # Broadcast cooking session started (useful for household to see who's cooking)
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.COOK_SESSION_STARTED,
        data={"session_id": session_id, "recipe_id": data.recipe_id, "user_name": user["name"]}
    )

    return {"session_id": session_id}


@router.post("/session/{session_id}/complete")
async def complete_cook_session(session_id: str, data: CookSessionComplete, user: dict = Depends(get_current_user)):
    """Complete a cooking session with optional feedback + personal note"""
    session = await cook_session_repository.find_by_id_and_user(session_id, user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    feedback = data.feedback
    if feedback is not None and feedback not in ["yes", "no", "meh"]:
        raise HTTPException(status_code=400, detail="Feedback must be 'yes', 'no', or 'meh'")

    # asyncpg TIMESTAMP columns need datetime objects (naive UTC)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    notes = (data.notes or "").strip()

    await cook_session_repository.update_session(session_id, {
        "completed_at": now,
        "feedback": feedback,
        "notes": notes,
    })

    if feedback:
        await recipe_feedback_repository.upsert_feedback(
            user_id=user["id"],
            recipe_id=session["recipe_id"],
            feedback=feedback,
            updated_at=now
        )

    await _touch_last_cooked(session["recipe_id"], now)
    if notes:
        await _merge_personal_note(user["id"], session["recipe_id"], notes, now)

    google_health_log = await _maybe_sync_google_health(
        user["id"], session["recipe_id"], session_id
    )

    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.COOK_SESSION_COMPLETED,
        data={"session_id": session_id, "recipe_id": session["recipe_id"], "feedback": feedback}
    )

    return {
        "message": "Thanks for the feedback!" if feedback else "Cook session saved",
        "feedback": feedback,
        "last_cooked_at": now.isoformat(),
        "notes": notes,
        "google_health_synced": bool(google_health_log),
        "google_health_log_id": google_health_log.get("id") if google_health_log else None,
    }


@router.post("/recipes/{recipe_id}/mark-cooked")
async def mark_recipe_cooked(
    recipe_id: str,
    data: MarkCookedRequest,
    user: dict = Depends(get_current_user),
):
    """Mark a recipe as cooked (skip full cook mode) + optional note/feedback."""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    feedback = data.feedback
    if feedback is not None and feedback not in ["yes", "no", "meh"]:
        raise HTTPException(status_code=400, detail="Feedback must be 'yes', 'no', or 'meh'")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    notes = (data.notes or "").strip()
    session_id = str(uuid.uuid4())

    await cook_session_repository.create({
        "id": session_id,
        "user_id": user["id"],
        "recipe_id": recipe_id,
        "started_at": now,
        "completed_at": now,
        "feedback": feedback,
        "notes": notes,
    })

    if feedback:
        await recipe_feedback_repository.upsert_feedback(
            user_id=user["id"],
            recipe_id=recipe_id,
            feedback=feedback,
            updated_at=now,
        )

    await _touch_last_cooked(recipe_id, now)
    if notes:
        await _merge_personal_note(user["id"], recipe_id, notes, now)

    google_health_log = await _maybe_sync_google_health(
        user["id"], recipe_id, session_id
    )

    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.COOK_SESSION_COMPLETED,
        data={"session_id": session_id, "recipe_id": recipe_id, "feedback": feedback},
    )

    return {
        "message": "Marked as cooked",
        "session_id": session_id,
        "last_cooked_at": now.isoformat(),
        "notes": notes,
        "feedback": feedback,
        "google_health_synced": bool(google_health_log),
        "google_health_log_id": google_health_log.get("id") if google_health_log else None,
    }


@router.post("/feedback")
async def submit_feedback(data: RecipeFeedback, user: dict = Depends(get_current_user)):
    """Quick feedback without a full cooking session"""
    if data.feedback not in ["yes", "no", "meh"]:
        raise HTTPException(status_code=400, detail="Feedback must be 'yes', 'no', or 'meh'")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    await recipe_feedback_repository.upsert_feedback(
        user_id=user["id"],
        recipe_id=data.recipe_id,
        feedback=data.feedback,
        updated_at=now
    )

    return {"message": "Feedback saved"}


@router.get("/stats")
async def get_cooking_stats(user: dict = Depends(get_current_user)):
    """Get user's cooking statistics"""
    user_id = user["id"]

    # Count sessions
    total_sessions = await cook_session_repository.count_completed(user_id)

    # Count feedback
    yes_count = await recipe_feedback_repository.count_by_feedback_type(user_id, "yes")
    no_count = await recipe_feedback_repository.count_by_feedback_type(user_id, "no")
    meh_count = await recipe_feedback_repository.count_by_feedback_type(user_id, "meh")

    return {
        "total_cooked": total_sessions,
        "would_cook_again": yes_count,
        "would_not_cook_again": no_count,
        "meh": meh_count
    }
