"""Calendar platform for Laro integration."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import LaroDataUpdateCoordinator
from .const import DOMAIN


# Meal type to time mapping (approximate meal times)
MEAL_TIMES = {
    "breakfast": (7, 0),
    "lunch": (12, 0),
    "dinner": (18, 0),
    "snack": (15, 0),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Laro calendar from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([LaroMealPlanCalendar(coordinator, entry.entry_id)])


class LaroMealPlanCalendar(CoordinatorEntity[LaroDataUpdateCoordinator], CalendarEntity):
    """Representation of a Laro meal plan calendar."""

    _attr_has_entity_name = True
    _attr_name = "Meal Plan"

    def __init__(
        self,
        coordinator: LaroDataUpdateCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_meal_plan_calendar"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Laro Recipe Manager",
            "manufacturer": "Laro",
            "model": "Recipe Manager",
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        if not self.coordinator.data:
            return None

        now = dt_util.now()
        meal_plans = self.coordinator.data.get("meal_plans", [])

        # Find the next meal
        upcoming_events = []
        for mp in meal_plans:
            event = self._create_event(mp)
            if event and event.start >= now:
                upcoming_events.append(event)

        if not upcoming_events:
            # Check today's meals that haven't passed
            for mp in self.coordinator.data.get("today_meals", []):
                event = self._create_event(mp)
                if event and event.end >= now:
                    upcoming_events.append(event)

        if upcoming_events:
            upcoming_events.sort(key=lambda e: e.start)
            return upcoming_events[0]

        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        if not self.coordinator.data:
            return []

        events = []
        meal_plans = self.coordinator.data.get("meal_plans", [])

        for mp in meal_plans:
            event = self._create_event(mp)
            if event:
                # Check if event is within range
                if event.start >= start_date and event.start <= end_date:
                    events.append(event)

        return events

    def _create_event(self, meal_plan: dict[str, Any]) -> CalendarEvent | None:
        """Create a calendar event from a meal plan."""
        date_str = meal_plan.get("date")
        if not date_str:
            return None

        try:
            # Parse date
            if "T" in date_str:
                base_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                base_date = datetime.strptime(date_str[:10], "%Y-%m-%d")

            # Get meal type and set appropriate time
            meal_type = meal_plan.get("meal_type", "dinner").lower()
            hour, minute = MEAL_TIMES.get(meal_type, (18, 0))

            start = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if start.tzinfo is None:
                start = dt_util.as_local(start)

            # Meal events are 1 hour long
            end = start + timedelta(hours=1)

            recipe_name = (
                meal_plan.get("recipe_title")
                or meal_plan.get("recipe_name")
                or meal_plan.get("notes")
                or "Meal"
            )
            meal_type_display = meal_type.capitalize()

            return CalendarEvent(
                start=start,
                end=end,
                summary=f"{meal_type_display}: {recipe_name}",
                description=f"Recipe: {recipe_name}\nMeal Type: {meal_type_display}",
                uid=meal_plan.get("id", f"{date_str}_{meal_type}"),
            )
        except (ValueError, TypeError) as e:
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return None

        today_meals = self.coordinator.data.get("today_meals", [])
        return {
            "today_meals": [
                {
                    "recipe_name": m.get("recipe_title") or m.get("recipe_name"),
                    "meal_type": m.get("meal_type"),
                    "recipe_id": m.get("recipe_id"),
                }
                for m in today_meals
            ],
            "meals_this_week": len(self.coordinator.data.get("meal_plans", [])),
        }


# Backwards-compatible alias
LaroMealPlanCalendar = LaroMealPlanCalendar
LaroDataUpdateCoordinator = LaroDataUpdateCoordinator
