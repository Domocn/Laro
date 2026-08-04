"""
Shopping List Repository - Handles all shopping list-related database operations
"""
import json
from typing import Optional, List
from .base_repository import BaseRepository


class ShoppingListRepository(BaseRepository):
    """Repository for shopping list operations"""

    JSON_FIELDS = ["items"]

    def __init__(self):
        super().__init__("shopping_lists")

    async def find_by_id(self, list_id: str) -> Optional[dict]:
        """Find shopping list by ID"""
        return await self.find_one(
            {"id": list_id},
            json_fields=self.JSON_FIELDS
        )

    async def create(self, list_data: dict) -> dict:
        """Create a new shopping list"""
        return await self.insert(list_data, json_fields=self.JSON_FIELDS)

    async def update_list(self, list_id: str, data: dict) -> int:
        """Update shopping list data"""
        return await self.update(
            {"id": list_id},
            data,
            json_fields=self.JSON_FIELDS
        )

    async def delete_list(self, list_id: str) -> int:
        """Delete a shopping list"""
        return await self.delete({"id": list_id})

    async def find_by_household(
        self,
        household_id: str,
        limit: int = 100
    ) -> List[dict]:
        """Find all shopping lists for a household"""
        return await self.find_many(
            {"household_id": household_id},
            json_fields=self.JSON_FIELDS,
            order_by="created_at",
            order_dir="DESC",
            limit=limit
        )

    async def update_item_checked(
        self,
        list_id: str,
        item_index: int,
        checked: bool
    ) -> bool:
        """Update the checked status of a specific item"""
        shopping_list = await self.find_by_id(list_id)
        if not shopping_list:
            return False

        items = shopping_list.get("items", [])
        if 0 <= item_index < len(items):
            items[item_index]["checked"] = checked
            await self.update(
                {"id": list_id},
                {"items": items},
                json_fields=["items"]
            )
            return True
        return False

    async def add_items(self, list_id: str, new_items: List[dict]) -> bool:
        """Add items to a shopping list"""
        shopping_list = await self.find_by_id(list_id)
        if not shopping_list:
            return False

        items = shopping_list.get("items", [])
        items.extend(new_items)

        await self.update(
            {"id": list_id},
            {"items": items},
            json_fields=["items"]
        )
        return True

    async def remove_item(self, list_id: str, item_index: int) -> bool:
        """Remove an item from a shopping list"""
        shopping_list = await self.find_by_id(list_id)
        if not shopping_list:
            return False

        items = shopping_list.get("items", [])
        if 0 <= item_index < len(items):
            items.pop(item_index)
            await self.update(
                {"id": list_id},
                {"items": items},
                json_fields=["items"]
            )
            return True
        return False

    async def delete_by_household(self, household_id: str) -> int:
        """Delete all shopping lists for a household"""
        return await self.delete({"household_id": household_id})

    async def delete_by_user(self, user_id: str) -> int:
        """Delete all shopping lists created by a user (for users without household)"""
        return await self.delete({"user_id": user_id})


# Singleton instance
shopping_list_repository = ShoppingListRepository()
