"""To-do platform for Laro: each Laro shopping list appears as a native HA to-do list."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=2)


class LaroShoppingCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Polls Laro shopping lists (keyed by list id)."""

    def __init__(self, hass: HomeAssistant, client) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_shopping", update_interval=SCAN_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            lists = await self.client.get_shopping_lists()
        except Exception as err:  # noqa: BLE001 - surface as UpdateFailed
            raise UpdateFailed(f"Error fetching Laro shopping lists: {err}") from err
        return {str(sl.get("id")): sl for sl in lists if sl.get("id")}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    coordinator = LaroShoppingCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    known: set[str] = set()

    @callback
    def _add_new_lists() -> None:
        new = [lid for lid in coordinator.data if lid not in known]
        if new:
            known.update(new)
            async_add_entities(LaroShoppingTodo(coordinator, entry, lid) for lid in new)

    _add_new_lists()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_lists))


class LaroShoppingTodo(CoordinatorEntity[LaroShoppingCoordinator], TodoListEntity):
    """A Laro shopping list as a to-do list."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:cart"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: LaroShoppingCoordinator, entry: ConfigEntry, list_id: str) -> None:
        super().__init__(coordinator)
        self._list_id = list_id
        self._attr_unique_id = f"{entry.entry_id}_shopping_{list_id}"

    @property
    def _list(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self._list_id, {})

    @property
    def available(self) -> bool:
        return super().available and self._list_id in (self.coordinator.data or {})

    @property
    def name(self) -> str:
        return self._list.get("name") or "Shopping list"

    @property
    def todo_items(self) -> list[TodoItem]:
        items = []
        for it in self._list.get("items") or []:
            if not it.get("id"):
                continue
            qty = " ".join(str(x) for x in (it.get("quantity"), it.get("unit")) if x)
            items.append(
                TodoItem(
                    uid=str(it["id"]),
                    summary=it.get("name") or "",
                    description=qty or None,
                    status=TodoItemStatus.COMPLETED if it.get("checked") else TodoItemStatus.NEEDS_ACTION,
                )
            )
        return items

    async def async_create_todo_item(self, item: TodoItem) -> None:
        await self.coordinator.client.add_to_shopping_list([item.summary or ""], list_id=self._list_id)
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        body: dict[str, Any] = {"checked": item.status == TodoItemStatus.COMPLETED}
        if item.summary:
            body["name"] = item.summary
        await self.coordinator.client.update_shopping_item(self._list_id, item.uid, body)
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self.coordinator.client.delete_shopping_item(self._list_id, uid)
        await self.coordinator.async_request_refresh()
