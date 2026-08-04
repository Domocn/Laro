"""
Pantry Repository - Handles all pantry item database operations
"""
from typing import Optional, List
from datetime import date
from .base_repository import BaseRepository


# Standard pantry categories
PANTRY_CATEGORIES = [
    "produce",
    "dairy",
    "meat",
    "seafood",
    "pantry",
    "frozen",
    "spices",
    "condiments",
    "beverages",
    "baking",
    "grains",
    "canned",
    "snacks",
    "other"
]

# Common staple ingredients that should be excluded from recipe matching
STAPLE_INGREDIENTS = [
    "salt", "pepper", "black pepper", "water", "oil", "olive oil",
    "vegetable oil", "canola oil", "cooking spray", "butter",
    "flour", "all-purpose flour", "sugar", "garlic", "onion"
]


class PantryRepository(BaseRepository):
    """Repository for pantry item operations"""

    def __init__(self):
        super().__init__("pantry_items")

    async def find_by_id(self, item_id: str) -> Optional[dict]:
        """Find pantry item by ID"""
        return await self.find_one({"id": item_id})

    async def create(self, item_data: dict) -> dict:
        """Create a new pantry item"""
        return await self.insert(item_data)

    async def update_item(self, item_id: str, data: dict) -> int:
        """Update pantry item data"""
        return await self.update({"id": item_id}, data)

    async def delete_item(self, item_id: str) -> int:
        """Delete a pantry item"""
        return await self.delete({"id": item_id})

    async def find_by_user(
        self,
        user_id: str,
        category: str = None,
        limit: int = 500
    ) -> List[dict]:
        """Find all pantry items for a user"""
        conditions = {"user_id": user_id}
        if category and category != "all":
            conditions["category"] = category

        return await self.find_many(
            conditions,
            order_by="name",
            order_dir="ASC",
            limit=limit
        )

    async def find_by_household(
        self,
        household_id: str,
        category: str = None,
        limit: int = 500
    ) -> List[dict]:
        """Find all pantry items for a household"""
        conditions = {"household_id": household_id}
        if category and category != "all":
            conditions["category"] = category

        return await self.find_many(
            conditions,
            order_by="name",
            order_dir="ASC",
            limit=limit
        )

    async def find_by_household_or_user(
        self,
        user_id: str,
        household_id: Optional[str] = None,
        category: str = None,
        include_staples: bool = True,
        limit: int = 500
    ) -> List[dict]:
        """Find all pantry items accessible to a user (own or household)"""
        pool = await self._get_db()

        params = []
        param_idx = 1

        if household_id:
            base_query = f"""
                SELECT * FROM pantry_items
                WHERE (household_id = ${param_idx} OR (user_id = ${param_idx + 1} AND household_id IS NULL))
            """
            params = [household_id, user_id]
            param_idx = 3
        else:
            base_query = f"""
                SELECT * FROM pantry_items
                WHERE user_id = ${param_idx}
            """
            params = [user_id]
            param_idx = 2

        # Add category filter
        if category and category.lower() != "all":
            base_query += f" AND category = ${param_idx}"
            params.append(category)
            param_idx += 1

        # Exclude staples if requested
        if not include_staples:
            base_query += " AND is_staple = FALSE"

        base_query += f" ORDER BY category, name ASC LIMIT ${param_idx}"
        params.append(limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(base_query, *params)

        from ..connection import rows_to_dicts
        return rows_to_dicts(rows)

    async def find_expiring_soon(
        self,
        user_id: str,
        household_id: Optional[str],
        days_ahead: int = 7
    ) -> List[dict]:
        """Find pantry items expiring within specified days"""
        pool = await self._get_db()
        from datetime import timedelta

        expiry_threshold = date.today() + timedelta(days=days_ahead)

        if household_id:
            query = """
                SELECT * FROM pantry_items
                WHERE (household_id = $1 OR (user_id = $2 AND household_id IS NULL))
                AND expiry_date IS NOT NULL
                AND expiry_date <= $3
                ORDER BY expiry_date ASC
            """
            values = [household_id, user_id, expiry_threshold]
        else:
            query = """
                SELECT * FROM pantry_items
                WHERE user_id = $1
                AND expiry_date IS NOT NULL
                AND expiry_date <= $2
                ORDER BY expiry_date ASC
            """
            values = [user_id, expiry_threshold]

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *values)

        from ..connection import rows_to_dicts
        return rows_to_dicts(rows)

    async def bulk_create(self, items: List[dict]) -> List[dict]:
        """Create multiple pantry items at once"""
        created = []
        for item in items:
            result = await self.create(item)
            created.append(result)
        return created

    async def bulk_delete(self, item_ids: List[str]) -> int:
        """Delete multiple pantry items"""
        if not item_ids:
            return 0

        pool = await self._get_db()
        placeholders = ",".join([f"${i+1}" for i in range(len(item_ids))])
        query = f"DELETE FROM pantry_items WHERE id IN ({placeholders})"

        async with pool.acquire() as conn:
            result = await conn.execute(query, *item_ids)

        return int(result.split()[-1]) if result else 0

    async def search(
        self,
        user_id: str,
        household_id: Optional[str],
        search_term: str,
        limit: int = 50
    ) -> List[dict]:
        """Search pantry items by name"""
        pool = await self._get_db()

        search_pattern = f"%{search_term}%"

        if household_id:
            query = """
                SELECT * FROM pantry_items
                WHERE (household_id = $1 OR (user_id = $2 AND household_id IS NULL))
                AND LOWER(name) LIKE LOWER($3)
                ORDER BY name ASC
                LIMIT $4
            """
            values = [household_id, user_id, search_pattern, limit]
        else:
            query = """
                SELECT * FROM pantry_items
                WHERE user_id = $1
                AND LOWER(name) LIKE LOWER($2)
                ORDER BY name ASC
                LIMIT $3
            """
            values = [user_id, search_pattern, limit]

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *values)

        from ..connection import rows_to_dicts
        return rows_to_dicts(rows)

    async def get_item_names(
        self,
        user_id: str,
        household_id: Optional[str],
        exclude_staples: bool = False
    ) -> List[str]:
        """Get just the names of pantry items (for recipe matching)"""
        pool = await self._get_db()

        if household_id:
            query = """
                SELECT DISTINCT LOWER(name) as name FROM pantry_items
                WHERE (household_id = $1 OR (user_id = $2 AND household_id IS NULL))
            """
            values = [household_id, user_id]
        else:
            query = """
                SELECT DISTINCT LOWER(name) as name FROM pantry_items
                WHERE user_id = $1
            """
            values = [user_id]

        if exclude_staples:
            query += " AND is_staple = FALSE"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *values)

        return [row["name"] for row in rows]

    async def delete_by_household(self, household_id: str) -> int:
        """Delete all pantry items for a household"""
        return await self.delete({"household_id": household_id})

    async def clear_checked(
        self,
        user_id: str,
        household_id: Optional[str],
        item_ids: List[str]
    ) -> int:
        """Delete specific items (used when clearing checked items)"""
        return await self.bulk_delete(item_ids)


# Singleton instance
pantry_repository = PantryRepository()
