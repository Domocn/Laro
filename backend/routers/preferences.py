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
    language: Optional[str] = "en-GB"  # en-US, en-GB, es, fr, …
    country: Optional[str] = "GB"  # ISO country code
    defaultServings: Optional[int] = 4
    measurementUnit: Optional[str] = "metric"  # metric, imperial, both
    dietaryRestrictions: Optional[List[str]] = []
    allergens: Optional[List[str]] = []  # Peanuts, Tree Nuts, Milk, Eggs, Wheat, Soy, Fish, Shellfish, Sesame
    dislikedIngredients: Optional[List[str]] = []  # Adult veto list (preference, not allergens)
    kidVetoIngredients: Optional[List[str]] = []  # Kid veto — kid-friendly / family meals only
    favoriteCuisines: Optional[List[str]] = []
    # Hostnames users prefer when asking for recipe ideas (e.g. bbcgoodfood.com)
    preferredRecipeSites: Optional[List[str]] = []
    # Daily nutrition goals (Foodzilla-style). Optional; high-protein pref applies defaults in AI.
    dailyProteinTarget: Optional[float] = None  # grams / day
    dailyCalorieTarget: Optional[float] = None  # kcal / day
    dailyCarbTarget: Optional[float] = None  # grams / day
    dailyFatTarget: Optional[float] = None  # grams / day
    # Lifestyle — meal-plan AI uses these for kid-friendly + WFH lunch pacing
    hasChildren: Optional[bool] = False
    kidFriendlyMeals: Optional[bool] = None  # defaults True when hasChildren
    # One shared dish for kids + adults (mild base + optional adult_boost tips)
    familyOneMeal: Optional[bool] = None  # defaults True when hasChildren
    worksFromHome: Optional[bool] = False
    wfhDays: Optional[List[str]] = []  # mon–sun weekday codes
    # Gym / activity days → higher protein dinner preference for AI + UI cues
    hasGymRoutine: Optional[bool] = False
    gymDays: Optional[List[str]] = []  # mon–sun weekday codes
    # Who's home for dinner (headcount); falls back to defaultServings in UI
    dinnerHeadcount: Optional[int] = None
    # Calendar → meal difficulty (ICS subscription; busy windows only, no titles in AI)
    calendarIcsUrl: Optional[str] = None
    useCalendarForMealDifficulty: Optional[bool] = False
    googleCalendarConnected: Optional[bool] = False  # reserved; Google freebusy not in MVP
    calendarTimezone: Optional[str] = None  # e.g. Europe/London; defaults from country
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


@router.get("/locales")
async def list_locales():
    """Public catalogue of languages + countries (flags match regions)."""
    from utils.locales import LANGUAGES, COUNTRIES

    return {
        "languages": [
            {"code": code, **meta} for code, meta in LANGUAGES.items()
        ],
        "countries": [
            {"code": code, **meta} for code, meta in COUNTRIES.items()
        ],
    }

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
    """Update user preferences (partial — only fields the client sent)."""
    from utils.locales import normalize_language, normalize_country

    # exclude_unset avoids a11y-only saves clobbering cooking prefs with defaults
    update_data = data.model_dump(exclude_unset=True)
    if "language" in update_data and update_data["language"] is not None:
        update_data["language"] = normalize_language(update_data["language"])
    if "country" in update_data and update_data["country"] is not None:
        update_data["country"] = normalize_country(update_data["country"])
    if "preferredRecipeSites" in update_data:
        from utils.preference_context import normalize_preferred_recipe_sites

        update_data["preferredRecipeSites"] = normalize_preferred_recipe_sites(
            update_data.get("preferredRecipeSites") or []
        )
    if "wfhDays" in update_data:
        from utils.preference_context import normalize_wfh_days

        update_data["wfhDays"] = normalize_wfh_days(update_data.get("wfhDays") or [])
    if "gymDays" in update_data:
        from utils.preference_context import normalize_wfh_days

        update_data["gymDays"] = normalize_wfh_days(update_data.get("gymDays") or [])
    if "dinnerHeadcount" in update_data and update_data["dinnerHeadcount"] is not None:
        try:
            hc = int(update_data["dinnerHeadcount"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="dinnerHeadcount must be an integer")
        if hc < 1 or hc > 20:
            raise HTTPException(status_code=400, detail="dinnerHeadcount out of range")
        update_data["dinnerHeadcount"] = hc
    if "calendarIcsUrl" in update_data:
        raw_url = update_data.get("calendarIcsUrl")
        if raw_url is None or str(raw_url).strip() == "":
            update_data["calendarIcsUrl"] = None
        else:
            from utils.calendar_busy import normalize_ics_url

            try:
                update_data["calendarIcsUrl"] = normalize_ics_url(str(raw_url))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    if "calendarTimezone" in update_data and update_data["calendarTimezone"]:
        tz = str(update_data["calendarTimezone"]).strip()
        update_data["calendarTimezone"] = tz or None
    # Kid-friendly + family one-meal defaults on when user has children
    if update_data.get("hasChildren") and "kidFriendlyMeals" not in update_data:
        update_data["kidFriendlyMeals"] = True
    if update_data.get("hasChildren") and "familyOneMeal" not in update_data:
        update_data["familyOneMeal"] = True
    if update_data.get("hasChildren") is False and "kidFriendlyMeals" not in update_data:
        # Leaving kidFriendlyMeals as previously stored is fine; only clear when explicitly false kids
        pass
    if update_data.get("hasChildren") is False and "familyOneMeal" not in update_data:
        pass
    for goal_key in (
        "dailyProteinTarget",
        "dailyCalorieTarget",
        "dailyCarbTarget",
        "dailyFatTarget",
    ):
        if goal_key in update_data and update_data[goal_key] is not None:
            try:
                val = float(update_data[goal_key])
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{goal_key} must be a number")
            if val < 0 or val > 10000:
                raise HTTPException(status_code=400, detail=f"{goal_key} out of range")
            update_data[goal_key] = val
    if not update_data:
        return {"message": "No preference changes"}
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
