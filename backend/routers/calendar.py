"""
Calendar Router - Export meal plans as iCal + read busy times from ICS subscription
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from dependencies import get_current_user, meal_plan_repository, user_preferences_repository
import uuid

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("/ical")
async def export_calendar_ical(
    start_date: str = Query(...),
    end_date: str = Query(...),
    user: dict = Depends(get_current_user)
):
    """Export meal plans as iCal format for calendar sync"""
    from fastapi.responses import Response

    household_id = user.get("household_id") or user["id"]
    plans = await meal_plan_repository.find_by_household(
        household_id,
        start_date=start_date,
        end_date=end_date,
        limit=500
    )

    ical = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Kitchenry//Meal Plan//EN", "CALSCALE:GREGORIAN"]

    for plan in plans:
        event_id = str(uuid.uuid4())
        date_str = plan["date"].replace("-", "")

        times = {"Breakfast": "0800", "Lunch": "1200", "Dinner": "1800", "Snack": "1500"}
        start_time = times.get(plan["meal_type"], "1200")

        ical.extend([
            "BEGIN:VEVENT",
            f"UID:{event_id}@kitchenry",
            f"DTSTART:{date_str}T{start_time}00",
            f"DTEND:{date_str}T{str(int(start_time[:2])+1).zfill(2)}{start_time[2:]}00",
            f"SUMMARY:{plan['meal_type']}: {plan['recipe_title']}",
            f"DESCRIPTION:Recipe: {plan['recipe_title']}\\nMeal: {plan['meal_type']}",
            "END:VEVENT"
        ])

    ical.append("END:VCALENDAR")

    return Response(
        content="\r\n".join(ical),
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=kitchenry-meals.ics"}
    )


class CalendarIcsValidateRequest(BaseModel):
    url: str


@router.post("/ics/validate")
async def validate_calendar_ics(
    data: CalendarIcsValidateRequest,
    user: dict = Depends(get_current_user),
):
    """
    Fetch and parse a private ICS URL; return event count for the next 14 days.
    Never returns event titles (privacy).
    """
    from utils.calendar_busy import (
        fetch_ics_text,
        normalize_ics_url,
        parse_ics_busy_intervals,
        resolve_calendar_timezone,
    )

    try:
        safe = normalize_ics_url(data.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    prefs = await user_preferences_repository.find_by_user(user["id"]) or {}
    local_tz = resolve_calendar_timezone(prefs)
    try:
        text = await fetch_ics_text(safe)
        intervals = parse_ics_busy_intervals(text, default_tz=local_tz)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read calendar feed: {type(e).__name__}",
        )

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=14)
    upcoming = [iv for iv in intervals if iv.end > now and iv.start < horizon]
    return {
        "ok": True,
        "busy_blocks_next_14_days": len(upcoming),
        "privacy": "Event titles are not stored or returned; only busy intervals are used.",
    }


@router.get("/busyness")
async def get_calendar_busyness(
    start_date: str = Query(..., description="YYYY-MM-DD first plan day"),
    days: int = Query(7, ge=1, le=31),
    user: dict = Depends(get_current_user),
):
    """
    Per-day evening busyness for the meal-plan window.
    Uses saved calendarIcsUrl when useCalendarForMealDifficulty is on.
    Returns busy/free levels only — no event titles.
    """
    from utils.calendar_busy import load_busyness_for_prefs

    try:
        start = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")

    prefs = await user_preferences_repository.find_by_user(user["id"]) or {}
    enabled = bool(prefs.get("useCalendarForMealDifficulty")) and bool(
        (prefs.get("calendarIcsUrl") or "").strip()
    )
    if not enabled:
        return {
            "enabled": False,
            "days": [],
            "source": None,
            "privacy": "Calendar meal difficulty is off or no ICS URL is saved.",
        }

    levels = await load_busyness_for_prefs(prefs, start_date=start, days=days)
    if levels is None:
        return {
            "enabled": True,
            "days": [],
            "source": "ics",
            "error": "unavailable",
            "privacy": "Busy times only; event titles are never sent to AI.",
        }

    return {
        "enabled": True,
        "days": levels,
        "source": "ics",
        "privacy": "Busy times only; event titles are never sent to AI.",
    }
