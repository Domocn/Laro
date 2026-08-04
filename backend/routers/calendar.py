"""
Calendar Router - Export meal plans as iCal format
"""
from fastapi import APIRouter, Depends, Query
from dependencies import get_current_user, meal_plan_repository
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

    # Build iCal
    ical = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Kitchenry//Meal Plan//EN", "CALSCALE:GREGORIAN"]

    for plan in plans:
        event_id = str(uuid.uuid4())
        date_str = plan["date"].replace("-", "")

        # Set meal times
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
