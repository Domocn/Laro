"""Laro Recipe Manager integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    PLATFORMS,
    SERVICE_ADD_TO_SHOPPING_LIST,
    SERVICE_CREATE_MEAL_PLAN,
    SERVICE_IMPORT_RECIPE,
    ATTR_RECIPE_ID,
    ATTR_DATE,
    ATTR_MEAL_TYPE,
    ATTR_ITEMS,
    ATTR_URL,
)

_LOGGER = logging.getLogger(__name__)


def _as_list(data: Any, key: str | None = None) -> list:
    """Normalize API list/dict responses."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and key:
        value = data.get(key, [])
        return value if isinstance(value, list) else []
    return []


class LaroApiClient:
    """API client for Laro."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._url = url.rstrip("/")
        self._token = token
        # Identifiable UA helps cloud WAF allowlists (laro.food) and debugging.
        self._headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "HomeAssistant-Laro/1.2.1",
            "Accept": "application/json",
        }

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an API request."""
        url = f"{self._url}/api{endpoint}"
        try:
            async with self._session.request(
                method, url, headers=self._headers, **kwargs
            ) as response:
                response.raise_for_status()
                if response.status == 204:
                    return {}
                return await response.json()
        except aiohttp.ClientError as err:
            _LOGGER.error("Error communicating with Laro API: %s", err)
            raise

    async def get_all(self) -> dict[str, Any]:
        """Fetch aggregated HA payload (preferred)."""
        data = await self._request("GET", "/homeassistant/all")
        return data if isinstance(data, dict) else {}

    async def get_recipes(self) -> list[dict]:
        """Get all recipes."""
        data = await self._request("GET", "/recipes")
        return _as_list(data, "recipes")

    async def get_meal_plans(self, start_date: str = None, end_date: str = None) -> list[dict]:
        """Get meal plans."""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        data = await self._request("GET", "/meal-plans", params=params)
        plans = _as_list(data, "meal_plans")
        for mp in plans:
            title = mp.get("recipe_title") or mp.get("recipe_name") or mp.get("notes") or "Meal"
            mp["recipe_name"] = title
            mp["recipe_title"] = title
        return plans

    async def get_shopping_lists(self) -> list[dict]:
        """Get shopping lists."""
        data = await self._request("GET", "/shopping-lists")
        return _as_list(data, "shopping_lists")

    async def create_meal_plan(self, recipe_id: str, date: str, meal_type: str = "dinner") -> dict:
        """Create a meal plan entry."""
        return await self._request(
            "POST",
            "/meal-plans",
            json={"recipe_id": recipe_id, "date": date, "meal_type": meal_type},
        )

    async def add_to_shopping_list(self, items: list[str], list_id: str = None) -> dict:
        """Add items to shopping list."""
        # Prefer appending via POST /items on an existing list
        target_id = list_id
        if not target_id:
            lists = await self.get_shopping_lists()
            if lists:
                target_id = lists[0].get("id")
            else:
                created = await self._request(
                    "POST",
                    "/shopping-lists",
                    json={"name": "Home Assistant List", "items": []},
                )
                target_id = created.get("id") if isinstance(created, dict) else None

        if not target_id:
            raise RuntimeError("Could not create or find a shopping list")

        last = {}
        for item in items:
            name = item if isinstance(item, str) else item.get("name", str(item))
            last = await self._request(
                "POST",
                f"/shopping-lists/{target_id}/items",
                json={"name": name},
            )
        return last

    async def import_recipe_from_url(self, url: str) -> dict:
        """Extract a recipe from URL and save it to the library."""
        extracted = await self._request("POST", "/ai/import-url", json={"url": url})
        if not isinstance(extracted, dict):
            return {"status": "error", "message": "Unexpected import response"}

        recipe = extracted.get("recipe")
        if not recipe or not isinstance(recipe, dict):
            return extracted

        ingredients: list[dict] = []
        for ing in recipe.get("ingredients") or []:
            if isinstance(ing, str):
                ingredients.append({"name": ing, "amount": "", "unit": ""})
            elif isinstance(ing, dict):
                ingredients.append(
                    {
                        "name": ing.get("name") or str(ing),
                        "amount": str(ing.get("amount") or ""),
                        "unit": ing.get("unit") or "",
                    }
                )

        instructions = recipe.get("instructions") or []
        normalized_instructions: list[str] = []
        for step in instructions:
            if isinstance(step, str):
                normalized_instructions.append(step)
            elif isinstance(step, dict):
                normalized_instructions.append(
                    step.get("text") or step.get("step") or str(step)
                )
            else:
                normalized_instructions.append(str(step))

        if not ingredients:
            ingredients = [{"name": "See source", "amount": "", "unit": ""}]
        if not normalized_instructions:
            normalized_instructions = ["See source URL"]

        payload = {
            "title": recipe.get("title") or recipe.get("name") or "Imported Recipe",
            "description": recipe.get("description") or "",
            "ingredients": ingredients,
            "instructions": normalized_instructions,
            "prep_time": recipe.get("prep_time") or 0,
            "cook_time": recipe.get("cook_time") or 0,
            "servings": recipe.get("servings") or 4,
            "category": recipe.get("category") or "Other",
            "tags": recipe.get("tags") or [],
            "image_url": recipe.get("image_url") or recipe.get("image") or "",
            "source_type": "url_import",
        }
        saved = await self._request("POST", "/recipes", json=payload)
        return {
            "status": "saved",
            "recipe": saved,
            "source_url": extracted.get("source_url") or url,
            "used_ai": extracted.get("used_ai"),
        }

    async def health_check(self) -> bool:
        """Check API health."""
        try:
            # Health is public; still go through client for consistent base URL
            url = f"{self._url}/api/health"
            async with self._session.get(url) as response:
                return response.status < 400
        except Exception:
            return False


class LaroDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Laro data."""

    def __init__(self, hass: HomeAssistant, client: LaroApiClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Laro API."""
        try:
            data = await self.client.get_all()
            if data:
                # Ensure normalized titles on meal plans
                for mp in data.get("meal_plans", []) or []:
                    title = mp.get("recipe_title") or mp.get("recipe_name") or mp.get("notes") or "Meal"
                    mp["recipe_name"] = title
                    mp["recipe_title"] = title
                for mp in data.get("today_meals", []) or []:
                    title = mp.get("recipe_title") or mp.get("recipe_name") or mp.get("notes") or "Meal"
                    mp["recipe_name"] = title
                    mp["recipe_title"] = title
                return data

            # Fallback to individual endpoints if /homeassistant/all unavailable
            from datetime import date, timedelta as td

            today = date.today()
            week_end = today + td(days=7)
            recipes = await self.client.get_recipes()
            meal_plans = await self.client.get_meal_plans(
                start_date=today.isoformat(),
                end_date=week_end.isoformat(),
            )
            shopping_lists = await self.client.get_shopping_lists()
            today_meals = [
                mp for mp in meal_plans
                if str(mp.get("date", "")).startswith(today.isoformat())
            ]
            total_items = 0
            unchecked_items = 0
            for sl in shopping_lists:
                items = sl.get("items", []) or []
                total_items += len(items)
                unchecked_items += sum(1 for item in items if not item.get("checked", False))

            return {
                "recipes": recipes,
                "recipe_count": len(recipes),
                "meal_plans": meal_plans,
                "today_meals": today_meals,
                "shopping_lists": shopping_lists,
                "shopping_list_count": len(shopping_lists),
                "shopping_items_total": total_items,
                "shopping_items_unchecked": unchecked_items,
                "favorites": [],
                "favorite_count": 0,
                "tonight_suggestions": [
                    {"id": r.get("id"), "name": r.get("title") or r.get("name"), "title": r.get("title")}
                    for r in recipes[:3]
                ],
                "ai_quota": {},
                "ai_remaining": None,
                "ai_unlimited": False,
            }
        except Exception as err:
            raise UpdateFailed(f"Error fetching Laro data: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Laro from a config entry."""
    session = async_get_clientsession(hass)
    client = LaroApiClient(
        session,
        entry.data[CONF_URL],
        entry.data[CONF_TOKEN],
    )

    if not await client.health_check():
        _LOGGER.error("Cannot connect to Laro API")
        return False

    coordinator = LaroDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass, client)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_setup_services(hass: HomeAssistant, client: LaroApiClient) -> None:
    """Set up Laro services."""

    async def handle_add_to_shopping_list(call: ServiceCall) -> None:
        items = call.data.get(ATTR_ITEMS, [])
        if items:
            await client.add_to_shopping_list(items)

    async def handle_create_meal_plan(call: ServiceCall) -> None:
        recipe_id = call.data.get(ATTR_RECIPE_ID)
        date = call.data.get(ATTR_DATE)
        meal_type = call.data.get(ATTR_MEAL_TYPE, "dinner")
        if recipe_id and date:
            await client.create_meal_plan(recipe_id, date, meal_type)

    async def handle_import_recipe(call: ServiceCall) -> None:
        url = call.data.get(ATTR_URL)
        if url:
            await client.import_recipe_from_url(url)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TO_SHOPPING_LIST, handle_add_to_shopping_list
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_MEAL_PLAN, handle_create_meal_plan
    )
    hass.services.async_register(
        DOMAIN, SERVICE_IMPORT_RECIPE, handle_import_recipe
    )


# Backwards-compatible aliases for platform imports
LaroApiClient = LaroApiClient
LaroDataUpdateCoordinator = LaroDataUpdateCoordinator
