"""
Recipe Repository - Handles all recipe-related database operations
"""
import json
from typing import Optional, List, Dict, Any
from .base_repository import BaseRepository


class RecipeRepository(BaseRepository):
    """Repository for recipe operations"""

    JSON_FIELDS = ["ingredients", "instructions", "tags"]

    def __init__(self):
        super().__init__("recipes")

    async def find_by_id(self, recipe_id: str) -> Optional[dict]:
        """Find recipe by ID"""
        return await self.find_one(
            {"id": recipe_id},
            json_fields=self.JSON_FIELDS
        )

    async def create(self, recipe_data: dict) -> dict:
        """Create a new recipe"""
        return await self.insert(recipe_data, json_fields=self.JSON_FIELDS)

    async def update_recipe(self, recipe_id: str, data: dict) -> int:
        """Update recipe data"""
        return await self.update(
            {"id": recipe_id},
            data,
            json_fields=self.JSON_FIELDS
        )

    async def delete_recipe(self, recipe_id: str) -> int:
        """Delete a recipe"""
        return await self.delete({"id": recipe_id})

    async def find_by_author(
        self,
        author_id: str,
        category: str = None,
        search: str = None,
        limit: int = 500
    ) -> List[dict]:
        """Find recipes by author"""
        pool = await self._get_db()

        query = "SELECT * FROM recipes WHERE author_id = $1"
        values = [author_id]
        param_count = 2

        if category and category != "All":
            query += f" AND category = ${param_count}"
            values.append(category)
            param_count += 1

        if search:
            query += f" AND (title LIKE ${param_count} OR description LIKE ${param_count + 1} OR tags LIKE ${param_count + 2})"
            search_pattern = f"%{search}%"
            values.extend([search_pattern, search_pattern, search_pattern])
            param_count += 3

        query += f" ORDER BY created_at DESC LIMIT ${param_count}"
        values.append(limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *values)

        from ..connection import rows_to_dicts
        results = rows_to_dicts(rows)

        # Deserialize JSON fields
        for result in results:
            result = self._deserialize_json_fields(result, self.JSON_FIELDS)

        return [self._deserialize_json_fields(r, self.JSON_FIELDS) for r in results]

    async def find_by_household_or_author(
        self,
        author_id: str,
        household_id: str = None,
        category: str = None,
        search: str = None,
        favorite_ids: List[str] = None,
        favorites_only: bool = False,
        limit: int = 500
    ) -> List[dict]:
        """Find recipes by author or household"""
        pool = await self._get_db()

        param_count = 1

        if favorites_only and favorite_ids:
            if not favorite_ids:
                return []
            placeholders = ",".join([f"${i+1}" for i in range(len(favorite_ids))])
            query = f"SELECT * FROM recipes WHERE id IN ({placeholders})"
            values = list(favorite_ids)
            param_count = len(favorite_ids) + 1
        elif household_id:
            query = "SELECT * FROM recipes WHERE (author_id = $1 OR household_id = $2)"
            values = [author_id, household_id]
            param_count = 3
        else:
            query = "SELECT * FROM recipes WHERE author_id = $1"
            values = [author_id]
            param_count = 2

        if category and category != "All":
            query += f" AND category = ${param_count}"
            values.append(category)
            param_count += 1

        if search:
            query += f" AND (title LIKE ${param_count} OR description LIKE ${param_count + 1} OR tags LIKE ${param_count + 2})"
            search_pattern = f"%{search}%"
            values.extend([search_pattern, search_pattern, search_pattern])
            param_count += 3

        query += f" ORDER BY created_at DESC LIMIT ${param_count}"
        values.append(limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *values)

        from ..connection import rows_to_dicts
        results = rows_to_dicts(rows)

        return [self._deserialize_json_fields(r, self.JSON_FIELDS) for r in results]

    async def find_by_ids(self, recipe_ids: List[str]) -> List[dict]:
        """Find multiple recipes by IDs"""
        if not recipe_ids:
            return []

        pool = await self._get_db()
        placeholders = ",".join([f"${i+1}" for i in range(len(recipe_ids))])
        query = f"SELECT * FROM recipes WHERE id IN ({placeholders})"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *recipe_ids)

        from ..connection import rows_to_dicts
        results = rows_to_dicts(rows)

        return [self._deserialize_json_fields(r, self.JSON_FIELDS) for r in results]

    async def delete_by_author(self, author_id: str, household_id: str = None) -> int:
        """Delete all recipes by author, optionally excluding household recipes"""
        pool = await self._get_db()

        if household_id is None:
            # Only delete recipes not in a household
            query = "DELETE FROM recipes WHERE author_id = $1 AND household_id IS NULL"
            values = [author_id]
        else:
            query = "DELETE FROM recipes WHERE author_id = $1"
            values = [author_id]

        async with pool.acquire() as conn:
            result = await conn.execute(query, *values)

        # Parse rowcount from result string (e.g., "DELETE 1")
        rowcount = int(result.split()[-1]) if result else 0
        return rowcount

    async def find_by_cookbook(self, cookbook_id: str, limit: int = 100) -> List[dict]:
        """Find all recipes from a specific cookbook"""
        pool = await self._get_db()

        query = """
            SELECT * FROM recipes
            WHERE cookbook_id = $1
            ORDER BY cookbook_page ASC NULLS LAST, created_at DESC
            LIMIT $2
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, cookbook_id, limit)

        from ..connection import rows_to_dicts
        results = rows_to_dicts(rows)

        return [self._deserialize_json_fields(r, self.JSON_FIELDS) for r in results]

    async def find_all_for_user(
        self,
        user_id: str,
        household_id: str = None,
        limit: int = 1000
    ) -> List[dict]:
        """Find all recipes accessible to a user (for recipe matching)"""
        pool = await self._get_db()

        if household_id:
            query = """
                SELECT * FROM recipes
                WHERE author_id = $1 OR household_id = $2
                ORDER BY created_at DESC
                LIMIT $3
            """
            values = [user_id, household_id, limit]
        else:
            query = """
                SELECT * FROM recipes
                WHERE author_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            values = [user_id, limit]

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *values)

        from ..connection import rows_to_dicts
        results = rows_to_dicts(rows)

        return [self._deserialize_json_fields(r, self.JSON_FIELDS) for r in results]


# Recipe Shares Repository
class RecipeShareRepository(BaseRepository):
    """Repository for recipe share links"""

    def __init__(self):
        super().__init__("recipe_shares")

    async def find_by_id(self, share_id: str) -> Optional[dict]:
        """Find share by ID"""
        return await self.find_one({"id": share_id})

    async def create(self, share_data: dict) -> dict:
        """Create a new share link"""
        return await self.insert(share_data)

    async def find_by_recipe(self, recipe_id: str) -> List[dict]:
        """Find all shares for a recipe"""
        return await self.find_many({"recipe_id": recipe_id})

    async def find_by_share_code(self, share_code: str) -> Optional[dict]:
        """Find share link by share code"""
        return await self.find_one({"share_code": share_code})

    async def find_by_user(self, user_id: str, active_only: bool = True) -> List[dict]:
        """Find all share links for a user"""
        conditions = {"user_id": user_id}
        if active_only:
            conditions["is_active"] = True
        return await self.find_many(
            conditions,
            order_by="created_at",
            order_dir="DESC"
        )

    async def update(self, share_id: str, data: dict) -> int:
        """Update a share link"""
        return await super().update({"id": share_id}, data)

    async def increment_view_count(self, share_id: str) -> int:
        """Increment view count for a share link"""
        pool = await self._get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE recipe_shares SET view_count = view_count + 1 WHERE id = $1",
                share_id
            )
        # Parse rowcount from result string (e.g., "UPDATE 1")
        rowcount = int(result.split()[-1]) if result else 0
        return rowcount


# Recipe Versions Repository
class RecipeVersionRepository(BaseRepository):
    """Repository for recipe version history"""

    JSON_FIELDS = ["data"]

    def __init__(self):
        super().__init__("recipe_versions")

    async def create_version(self, version_data: dict) -> dict:
        """Create a new version snapshot"""
        return await self.insert(version_data, json_fields=self.JSON_FIELDS)

    async def find_by_recipe(self, recipe_id: str) -> List[dict]:
        """Find all versions for a recipe"""
        return await self.find_many(
            {"recipe_id": recipe_id},
            json_fields=self.JSON_FIELDS,
            order_by="version",
            order_dir="DESC"
        )

    async def get_version(self, recipe_id: str, version: int) -> Optional[dict]:
        """Get a specific version"""
        return await self.find_one(
            {"recipe_id": recipe_id, "version": version},
            json_fields=self.JSON_FIELDS
        )

    async def get_next_version_number(self, recipe_id: str) -> int:
        """Get the next version number for a recipe"""
        pool = await self._get_db()
        query = "SELECT MAX(version) FROM recipe_versions WHERE recipe_id = $1"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, recipe_id)
        return (row[0] or 0) + 1


# Reviews Repository
class ReviewRepository(BaseRepository):
    """Repository for recipe reviews"""

    JSON_FIELDS = ["tags"]

    def __init__(self):
        super().__init__("reviews")

    async def find_by_recipe(self, recipe_id: str) -> List[dict]:
        """Find all reviews for a recipe"""
        return await self.find_many(
            {"recipe_id": recipe_id},
            json_fields=self.JSON_FIELDS,
            order_by="created_at",
            order_dir="DESC"
        )

    async def find_by_user_and_recipe(self, user_id: str, recipe_id: str) -> Optional[dict]:
        """Find a user's review for a recipe"""
        return await self.find_one(
            {"user_id": user_id, "recipe_id": recipe_id},
            json_fields=self.JSON_FIELDS
        )

    async def create(self, review_data: dict) -> dict:
        """Create a new review"""
        return await self.insert(review_data, json_fields=self.JSON_FIELDS)

    async def update_review(self, review_id: str, data: dict) -> int:
        """Update a review"""
        return await self.update(
            {"id": review_id},
            data,
            json_fields=self.JSON_FIELDS
        )

    async def delete_review(self, review_id: str) -> int:
        """Delete a review"""
        return await self.delete({"id": review_id})


# Singleton instances
recipe_repository = RecipeRepository()
recipe_share_repository = RecipeShareRepository()
recipe_version_repository = RecipeVersionRepository()
review_repository = ReviewRepository()
