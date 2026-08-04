"""
Cooking Router - Cooking sessions, feedback, and tonight suggestions
"""
from fastapi import APIRouter, HTTPException, Depends
from models import RecipeFeedback, CookSessionCreate, CookSessionComplete
from dependencies import (
    get_current_user, recipe_repository, meal_plan_repository,
    cook_session_repository, recipe_feedback_repository
)
from database.websocket_manager import ws_manager, EventType
import uuid
from datetime import datetime, timezone, date
from typing import List, Optional

router = APIRouter(prefix="/cooking", tags=["Cooking"])


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

    # If dinner is planned, return that recipe with a flag
    if planned_meal:
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

    session = {
        "id": session_id,
        "user_id": user["id"],
        "recipe_id": data.recipe_id,
        "started_at": data.started_at or datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "feedback": None
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
    """Complete a cooking session with feedback"""
    session = await cook_session_repository.find_by_id_and_user(session_id, user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if data.feedback not in ["yes", "no", "meh"]:
        raise HTTPException(status_code=400, detail="Feedback must be 'yes', 'no', or 'meh'")

    now = datetime.now(timezone.utc).isoformat()

    # Update session
    await cook_session_repository.update_session(session_id, {
        "completed_at": now,
        "feedback": data.feedback
    })

    # Store/update feedback for this recipe
    await recipe_feedback_repository.upsert_feedback(
        user_id=user["id"],
        recipe_id=session["recipe_id"],
        feedback=data.feedback,
        updated_at=now
    )

    # Broadcast cooking session completed
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.COOK_SESSION_COMPLETED,
        data={"session_id": session_id, "recipe_id": session["recipe_id"], "feedback": data.feedback}
    )

    return {"message": "Thanks for the feedback!", "feedback": data.feedback}


@router.post("/feedback")
async def submit_feedback(data: RecipeFeedback, user: dict = Depends(get_current_user)):
    """Quick feedback without a full cooking session"""
    if data.feedback not in ["yes", "no", "meh"]:
        raise HTTPException(status_code=400, detail="Feedback must be 'yes', 'no', or 'meh'")

    now = datetime.now(timezone.utc).isoformat()

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
