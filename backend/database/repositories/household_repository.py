"""
Household Repository - Handles all household-related database operations
"""
import json
from typing import Optional, List
from .base_repository import BaseRepository


class HouseholdRepository(BaseRepository):
    """Repository for household operations"""

    JSON_FIELDS = ["member_ids"]

    def __init__(self):
        super().__init__("households")

    async def find_by_id(self, household_id: str) -> Optional[dict]:
        """Find household by ID"""
        return await self.find_one(
            {"id": household_id},
            json_fields=self.JSON_FIELDS
        )

    async def find_by_join_code(self, join_code: str) -> Optional[dict]:
        """Find household by join code"""
        return await self.find_one(
            {"join_code": join_code},
            json_fields=self.JSON_FIELDS
        )

    async def create(self, household_data: dict) -> dict:
        """Create a new household"""
        return await self.insert(household_data, json_fields=self.JSON_FIELDS)

    async def update_household(self, household_id: str, data: dict) -> int:
        """Update household data"""
        return await self.update(
            {"id": household_id},
            data,
            json_fields=self.JSON_FIELDS
        )

    async def delete_household(self, household_id: str) -> int:
        """Delete a household"""
        return await self.delete({"id": household_id})

    async def add_member(self, household_id: str, user_id: str) -> bool:
        """Add a member to the household"""
        household = await self.find_by_id(household_id)
        if not household:
            return False

        member_ids = household.get("member_ids", [])
        if user_id not in member_ids:
            member_ids.append(user_id)
            await self.update(
                {"id": household_id},
                {"member_ids": member_ids},
                json_fields=["member_ids"]
            )
            return True
        return False

    async def remove_member(self, household_id: str, user_id: str) -> bool:
        """Remove a member from the household"""
        household = await self.find_by_id(household_id)
        if not household:
            return False

        member_ids = household.get("member_ids", [])
        if user_id in member_ids:
            member_ids.remove(user_id)
            await self.update(
                {"id": household_id},
                {"member_ids": member_ids},
                json_fields=["member_ids"]
            )
            return True
        return False

    async def set_join_code(self, household_id: str, join_code: str, expires: str) -> int:
        """Set a join code for the household"""
        return await self.update(
            {"id": household_id},
            {"join_code": join_code, "join_code_expires": expires}
        )

    async def clear_join_code(self, household_id: str) -> int:
        """Clear the join code for the household"""
        return await self.update(
            {"id": household_id},
            {"join_code": None, "join_code_expires": None}
        )


# Singleton instance
household_repository = HouseholdRepository()
