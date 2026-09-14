"""Sensor platform for Laro integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LaroDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class LaroSensorEntityDescriptionMixin:
    """Mixin for Laro sensor descriptions."""

    value_fn: Callable[[dict[str, Any]], Any]
    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


@dataclass
class LaroSensorEntityDescription(
    SensorEntityDescription, LaroSensorEntityDescriptionMixin
):
    """Describes a Laro sensor entity."""


def _meal_title(meal: dict) -> str:
    return (
        meal.get("recipe_title")
        or meal.get("recipe_name")
        or meal.get("title")
        or meal.get("notes")
        or "Unknown"
    )


def get_today_meals_value(data: dict) -> str:
    """Get today's meal summary."""
    meals = data.get("today_meals", [])
    if not meals:
        return "No meals planned"
    meal_names = [_meal_title(m) for m in meals]
    return ", ".join(meal_names[:3])


def get_today_meals_attrs(data: dict) -> dict:
    """Get today's meal attributes."""
    meals = data.get("today_meals", [])
    return {
        "meals": [
            {
                "recipe_id": m.get("recipe_id"),
                "recipe_name": _meal_title(m),
                "meal_type": m.get("meal_type"),
            }
            for m in meals
        ],
        "meal_count": len(meals),
    }


def get_tonight_value(data: dict) -> str:
    """Get tonight's suggestion."""
    suggestions = data.get("tonight_suggestions", [])
    if not suggestions:
        return "No suggestions"
    first = suggestions[0]
    return first.get("name") or first.get("title") or "Unknown"


def get_tonight_attrs(data: dict) -> dict:
    """Get tonight's suggestion attributes."""
    suggestions = data.get("tonight_suggestions", [])
    return {
        "suggestions": [
            {
                "recipe_id": s.get("id"),
                "name": s.get("name") or s.get("title"),
                "reason": s.get("reason"),
            }
            for s in suggestions[:5]
        ],
    }


def get_shopping_list_attrs(data: dict) -> dict:
    """Get shopping list attributes."""
    lists = data.get("shopping_lists", [])
    if not lists:
        return {"lists": []}

    # Get items from first/active list
    first_list = lists[0] if lists else {}
    items = first_list.get("items", [])
    unchecked = [i for i in items if not i.get("checked", False)]

    return {
        "list_name": first_list.get("name", "Shopping List"),
        "total_items": len(items),
        "unchecked_items": [i.get("name") for i in unchecked[:10]],
        "all_lists": [{"id": l.get("id"), "name": l.get("name")} for l in lists],
    }


def get_favorites_attrs(data: dict) -> dict:
    """Get favorites attributes."""
    favorites = data.get("favorites", [])
    recipes = []
    for fav in favorites[:10]:
        if isinstance(fav, dict):
            recipes.append({
                "id": fav.get("id"),
                "name": fav.get("name") or fav.get("title") or "Recipe",
            })
        else:
            recipes.append({"id": fav, "name": "Recipe"})
    return {"recipes": recipes}


def get_ai_quota_value(data: dict) -> Any:
    """Remaining free AI uses, or unlimited for premium."""
    if data.get("ai_unlimited"):
        return "unlimited"
    remaining = data.get("ai_remaining")
    if remaining is None:
        quota = data.get("ai_quota") or {}
        if quota.get("unlimited") or quota.get("premium"):
            return "unlimited"
        remaining = quota.get("remaining")
    return remaining if remaining is not None else "unknown"


def get_ai_quota_attrs(data: dict) -> dict:
    """AI quota details for automations."""
    quota = data.get("ai_quota") or {}
    return {
        "premium": bool(quota.get("premium") or data.get("ai_unlimited")),
        "used": quota.get("used"),
        "limit": quota.get("limit"),
        "bonus": quota.get("bonus"),
        "remaining": data.get("ai_remaining", quota.get("remaining")),
        "unlimited": bool(quota.get("unlimited") or data.get("ai_unlimited")),
    }


SENSOR_DESCRIPTIONS: tuple[LaroSensorEntityDescription, ...] = (
    LaroSensorEntityDescription(
        key="recipe_count",
        name="Recipe Count",
        icon="mdi:book-open-variant",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="recipes",
        value_fn=lambda data: data.get("recipe_count", 0),
    ),
    LaroSensorEntityDescription(
        key="today_meals",
        name="Today's Meals",
        icon="mdi:food",
        value_fn=get_today_meals_value,
        attr_fn=get_today_meals_attrs,
    ),
    LaroSensorEntityDescription(
        key="tonight_suggestion",
        name="Tonight's Suggestion",
        icon="mdi:chef-hat",
        value_fn=get_tonight_value,
        attr_fn=get_tonight_attrs,
    ),
    LaroSensorEntityDescription(
        key="shopping_items_unchecked",
        name="Shopping List Items",
        icon="mdi:cart",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="items",
        value_fn=lambda data: data.get("shopping_items_unchecked", 0),
        attr_fn=get_shopping_list_attrs,
    ),
    LaroSensorEntityDescription(
        key="favorite_count",
        name="Favorite Recipes",
        icon="mdi:heart",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="recipes",
        value_fn=lambda data: data.get("favorite_count", 0),
        attr_fn=get_favorites_attrs,
    ),
    LaroSensorEntityDescription(
        key="meal_plans_this_week",
        name="Meals This Week",
        icon="mdi:calendar-week",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="meals",
        value_fn=lambda data: len(data.get("meal_plans", [])),
    ),
    LaroSensorEntityDescription(
        key="ai_quota_remaining",
        name="AI Quota Remaining",
        icon="mdi:robot",
        value_fn=get_ai_quota_value,
        attr_fn=get_ai_quota_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Laro sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        LaroSensor(coordinator, description, entry.entry_id)
        for description in SENSOR_DESCRIPTIONS
    )


class LaroSensor(CoordinatorEntity[LaroDataUpdateCoordinator], SensorEntity):
    """Representation of a Laro sensor."""

    entity_description: LaroSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LaroDataUpdateCoordinator,
        description: LaroSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Laro Recipe Manager",
            "manufacturer": "Laro",
            "model": "Recipe Manager",
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.entity_description.value_fn(self.coordinator.data)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.coordinator.data and self.entity_description.attr_fn:
            return self.entity_description.attr_fn(self.coordinator.data)
        return None


# Backwards-compatible aliases
LaroSensorEntityDescription = LaroSensorEntityDescription
LaroSensor = LaroSensor
LaroDataUpdateCoordinator = LaroDataUpdateCoordinator
