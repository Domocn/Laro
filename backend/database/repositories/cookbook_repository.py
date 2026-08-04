"""
Cookbook Repository - Handles all cookbook-related database operations
"""
from typing import Optional, List
from .base_repository import BaseRepository


class CookbookRepository(BaseRepository):
    """Repository for cookbook operations"""

    def __init__(self):
        super().__init__("cookbooks")

    async def find_by_id(self, cookbook_id: str) -> Optional[dict]:
        """Find cookbook by ID"""
        return await self.find_one({"id": cookbook_id})

    async def create(self, cookbook_data: dict) -> dict:
        """Create a new cookbook"""
        return await self.insert(cookbook_data)

    async def update_cookbook(self, cookbook_id: str, data: dict) -> int:
        """Update cookbook data"""
        return await self.update({"id": cookbook_id}, data)

    async def delete_cookbook(self, cookbook_id: str) -> int:
        """Delete a cookbook"""
        return await self.delete({"id": cookbook_id})

    async def find_by_user(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[dict]:
        """Find all cookbooks for a user"""
        return await self.find_many(
            {"user_id": user_id},
            order_by="created_at",
            order_dir="DESC",
            limit=limit
        )

    async def find_by_household(
        self,
        household_id: str,
        limit: int = 100
    ) -> List[dict]:
        """Find all cookbooks for a household"""
        return await self.find_many(
            {"household_id": household_id},
            order_by="created_at",
            order_dir="DESC",
            limit=limit
        )

    async def find_by_household_or_user(
        self,
        user_id: str,
        household_id: Optional[str] = None,
        limit: int = 100
    ) -> List[dict]:
        """Find all cookbooks accessible to a user (own or household)"""
        pool = await self._get_db()

        if household_id:
            # Get cookbooks from household or owned by user
            query = """
                SELECT * FROM cookbooks
                WHERE household_id = $1 OR (user_id = $2 AND household_id IS NULL)
                ORDER BY created_at DESC
                LIMIT $3
            """
            values = [household_id, user_id, limit]
        else:
            # Get only user's own cookbooks
            query = """
                SELECT * FROM cookbooks
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            values = [user_id, limit]

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *values)

        from ..connection import rows_to_dicts
        return rows_to_dicts(rows)

    async def find_by_isbn(
        self,
        isbn: str,
        user_id: str = None,
        household_id: str = None
    ) -> Optional[dict]:
        """Find a cookbook by ISBN within user's scope"""
        pool = await self._get_db()

        if household_id:
            query = """
                SELECT * FROM cookbooks
                WHERE isbn = $1 AND (household_id = $2 OR user_id = $3)
                LIMIT 1
            """
            values = [isbn, household_id, user_id]
        else:
            query = """
                SELECT * FROM cookbooks
                WHERE isbn = $1 AND user_id = $2
                LIMIT 1
            """
            values = [isbn, user_id]

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)

        if row:
            from ..connection import dict_from_row
            return dict_from_row(row)
        return None

    async def search(
        self,
        user_id: str,
        household_id: Optional[str],
        search_term: str,
        limit: int = 50
    ) -> List[dict]:
        """Search cookbooks by title or author"""
        pool = await self._get_db()

        search_pattern = f"%{search_term}%"

        if household_id:
            query = """
                SELECT * FROM cookbooks
                WHERE (household_id = $1 OR (user_id = $2 AND household_id IS NULL))
                AND (LOWER(title) LIKE LOWER($3) OR LOWER(author) LIKE LOWER($3))
                ORDER BY created_at DESC
                LIMIT $4
            """
            values = [household_id, user_id, search_pattern, limit]
        else:
            query = """
                SELECT * FROM cookbooks
                WHERE user_id = $1
                AND (LOWER(title) LIKE LOWER($2) OR LOWER(author) LIKE LOWER($2))
                ORDER BY created_at DESC
                LIMIT $3
            """
            values = [user_id, search_pattern, limit]

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *values)

        from ..connection import rows_to_dicts
        return rows_to_dicts(rows)

    async def delete_by_household(self, household_id: str) -> int:
        """Delete all cookbooks for a household"""
        return await self.delete({"household_id": household_id})


# Singleton instance
cookbook_repository = CookbookRepository()
