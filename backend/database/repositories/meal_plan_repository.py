"""
Meal Plan Repository - Handles all meal plan-related database operations
"""
from typing import Optional, List
from .base_repository import BaseRepository


class MealPlanRepository(BaseRepository):
    """Repository for meal plan operations"""

    def __init__(self):
        super().__init__("meal_plans")

    async def find_by_id(self, plan_id: str) -> Optional[dict]:
        """Find meal plan by ID"""
        return await self.find_one({"id": plan_id})

    async def create(self, plan_data: dict) -> dict:
        """Create a new meal plan"""
        return await self.insert(plan_data)

    async def delete_plan(self, plan_id: str) -> int:
        """Delete a meal plan"""
        return await self.delete({"id": plan_id})

    async def find_by_household(
        self,
        household_id: str,
        start_date: str = None,
        end_date: str = None,
        limit: int = 500
    ) -> List[dict]:
        """Find meal plans for a household with optional date range"""
        pool = await self._get_db()

        query = "SELECT * FROM meal_plans WHERE household_id = $1"
        values = [household_id]
        param_count = 2

        if start_date:
            query += f" AND date >= ${param_count}"
            values.append(start_date)
            param_count += 1

        if end_date:
            query += f" AND date <= ${param_count}"
            values.append(end_date)
            param_count += 1

        query += f" ORDER BY date ASC LIMIT ${param_count}"
        values.append(limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *values)

        from ..connection import rows_to_dicts
        return rows_to_dicts(rows)

    async def find_by_date_and_meal_type(
        self,
        household_id: str,
        date: str,
        meal_type: str
    ) -> Optional[dict]:
        """Find a specific meal plan by date and type"""
        pool = await self._get_db()

        query = """
            SELECT * FROM meal_plans
            WHERE household_id = $1 AND date = $2 AND (meal_type = $3 OR meal_type = $4)
            LIMIT 1
        """
        # Handle case-insensitive meal type matching
        meal_type_lower = meal_type.lower()
        meal_type_title = meal_type.title()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, household_id, date, meal_type_lower, meal_type_title)

        if row:
            from ..connection import dict_from_row
            return dict_from_row(row)
        return None

    async def delete_by_household(self, household_id: str) -> int:
        """Delete all meal plans for a household"""
        return await self.delete({"household_id": household_id})

    async def delete_by_user(self, user_id: str) -> int:
        """Delete all meal plans created by a user (for users without household)"""
        return await self.delete({"user_id": user_id})

    async def delete_by_recipe_ids(self, recipe_ids: List[str]) -> int:
        """Delete all meal plans that reference any of the given recipe IDs"""
        if not recipe_ids:
            return 0
        pool = await self._get_db()

        # Build placeholders for IN clause
        placeholders = ", ".join(f"${i+1}" for i in range(len(recipe_ids)))
        query = f"DELETE FROM meal_plans WHERE recipe_id IN ({placeholders})"

        async with pool.acquire() as conn:
            result = await conn.execute(query, *recipe_ids)

        # Parse rowcount from result string (e.g., "DELETE 5")
        rowcount = int(result.split()[-1]) if result else 0
        return rowcount


# Singleton instance
meal_plan_repository = MealPlanRepository()
