"""
Preferences Router - User preferences and setup wizard
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from dependencies import get_current_user, user_preferences_repository, system_settings_repository
from datetime import datetime, timezone

router = APIRouter(prefix="/preferences", tags=["Preferences"])

# =============================================================================
# MODELS
# =============================================================================

class UserPreferences(BaseModel):
    # General preferences
    theme: Optional[str] = "system"  # light, dark, system
    defaultServings: Optional[int] = 4
    measurementUnit: Optional[str] = "metric"  # metric, imperial, both
    dietaryRestrictions: Optional[List[str]] = []
    showNutrition: Optional[bool] = True
    compactView: Optional[bool] = False
    weekStartsOn: Optional[str] = "monday"  # sunday, monday, saturday
    mealPlanNotifications: Optional[bool] = True
    shoppingListAutoSort: Optional[bool] = True
    defaultCookingTime: Optional[int] = 30

    # Accessibility: Reading Support (Dyslexia)
    dyslexicFont: Optional[bool] = False
    textSpacing: Optional[str] = "normal"  # normal, comfortable, spacious
    lineHeight: Optional[str] = "normal"  # normal, relaxed, loose
    readingRuler: Optional[bool] = False

    # Accessibility: Focus & Attention (ADHD)
    focusMode: Optional[bool] = False
    simplifiedMode: Optional[bool] = False
    highlightCurrentStep: Optional[bool] = True
    showProgressIndicators: Optional[bool] = True

    # Accessibility: Visual Clarity
    iconLabels: Optional[bool] = False
    contrastLevel: Optional[str] = "normal"  # normal, high, maximum
    animationLevel: Optional[str] = "normal"  # none, reduced, normal, enhanced

    # Accessibility: Interaction (Autism Support)
    confirmActions: Optional[bool] = True

    # Accessibility: Sensory Preferences
    soundEffects: Optional[bool] = False
    hapticFeedback: Optional[bool] = False
    timerNotifications: Optional[str] = "both"  # visual, audio, both, none

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("")
async def get_preferences(user: dict = Depends(get_current_user)):
    """Get user preferences"""
    prefs = await user_preferences_repository.find_by_user(user["id"])

    if not prefs:
        # Return defaults
        return UserPreferences().model_dump()

    prefs.pop("user_id", None)
    return prefs

@router.put("")
async def update_preferences(
    data: UserPreferences,
    user: dict = Depends(get_current_user)
):
    """Update user preferences"""
    update_data = data.model_dump()
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await user_preferences_repository.upsert_preferences(user["id"], update_data)

    return {"message": "Preferences saved"}

# =============================================================================
# SETUP WIZARD
# =============================================================================

@router.get("/setup/status", name="setup_status")
async def get_setup_status():
    """Check if initial setup is complete"""
    setup = await system_settings_repository.get_settings("setup")

    return {
        "setup_complete": setup.get("complete", False) if setup else False
    }

@router.post("/setup/complete", name="setup_complete")
async def complete_setup(user: dict = Depends(get_current_user)):
    """Mark initial setup as complete"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    await system_settings_repository.update_settings("setup", {
        "complete": True,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "completed_by": user["id"]
    })

    return {"message": "Setup completed"}
