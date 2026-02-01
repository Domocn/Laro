"""
User Repository - Handles all user-related database operations
"""
import json
from typing import Optional, List, Dict, Any
from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    """Repository for user operations"""

    JSON_FIELDS = ["favorites", "allergies", "friends"]

    def __init__(self):
        super().__init__("users")

    async def find_by_id(self, user_id: str, exclude_password: bool = True) -> Optional[dict]:
        """Find user by ID"""
        exclude = ["password"] if exclude_password else None
        return await self.find_one(
            {"id": user_id},
            exclude_fields=exclude,
            json_fields=self.JSON_FIELDS
        )

    async def find_by_email(self, email: str, include_password: bool = False) -> Optional[dict]:
        """Find user by email"""
        exclude = None if include_password else ["password"]
        return await self.find_one(
            {"email": email},
            exclude_fields=exclude,
            json_fields=self.JSON_FIELDS
        )

    async def find_by_friend_code(self, friend_code: str) -> Optional[dict]:
        """Find user by friend code"""
        return await self.find_one(
            {"friend_code": friend_code},
            exclude_fields=["password"],
            json_fields=self.JSON_FIELDS
        )

    async def find_by_supabase_id(self, supabase_id: str) -> Optional[dict]:
        """Find user by Supabase auth user ID"""
        return await self.find_one(
            {"supabase_id": supabase_id},
            exclude_fields=["password"],
            json_fields=self.JSON_FIELDS
        )

    async def create(self, user_data: dict) -> dict:
        """Create a new user"""
        return await self.insert(user_data, json_fields=self.JSON_FIELDS)

    async def update_user(self, user_id: str, data: dict) -> int:
        """Update user data"""
        return await self.update(
            {"id": user_id},
            data,
            json_fields=self.JSON_FIELDS
        )

    async def delete_user(self, user_id: str) -> int:
        """Delete a user"""
        return await self.delete({"id": user_id})

    async def get_favorites(self, user_id: str) -> List[str]:
        """Get user's favorite recipe IDs"""
        user = await self.find_one({"id": user_id}, json_fields=["favorites"])
        if user and user.get("favorites"):
            return user["favorites"]
        return []

    async def add_favorite(self, user_id: str, recipe_id: str) -> bool:
        """Add a recipe to user's favorites"""
        favorites = await self.get_favorites(user_id)
        if recipe_id not in favorites:
            favorites.append(recipe_id)
            await self.update(
                {"id": user_id},
                {"favorites": favorites},
                json_fields=["favorites"]
            )
            return True
        return False

    async def remove_favorite(self, user_id: str, recipe_id: str) -> bool:
        """Remove a recipe from user's favorites"""
        favorites = await self.get_favorites(user_id)
        if recipe_id in favorites:
            favorites.remove(recipe_id)
            await self.update(
                {"id": user_id},
                {"favorites": favorites},
                json_fields=["favorites"]
            )
            return True
        return False

    async def list_users(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str = None,
        role: str = None,
        status: str = None
    ) -> tuple[List[dict], int]:
        """List users with pagination and filtering"""
        pool = await self._get_db()

        # Build query
        conditions = []
        values = []
        param_count = 1

        if search:
            conditions.append(f"(email LIKE ${param_count} OR name LIKE ${param_count + 1})")
            search_pattern = f"%{search}%"
            values.extend([search_pattern, search_pattern])
            param_count += 2

        if role:
            conditions.append(f"role = ${param_count}")
            values.append(role)
            param_count += 1

        if status:
            conditions.append(f"status = ${param_count}")
            values.append(status)
            param_count += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Count total
        count_query = f"SELECT COUNT(*) as count FROM users WHERE {where_clause}"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(count_query, *values)
            total = row[0] if row else 0

            # Get paginated results
            offset = (page - 1) * per_page
            query = f"""
                SELECT id, email, name, role, status, created_at, last_login, household_id
                FROM users
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            final_values = values + [per_page, offset]

            rows = await conn.fetch(query, *final_values)

        users = []
        for row in rows:
            users.append({
                "id": row[0],
                "email": row[1],
                "name": row[2],
                "role": row[3] or "user",
                "status": row[4] or "active",
                "created_at": row[5],
                "last_login": row[6],
                "household_id": row[7]
            })

        return users, total

    async def find_by_household(self, household_id: str) -> List[dict]:
        """Find all users in a household"""
        return await self.find_many(
            {"household_id": household_id},
            exclude_fields=["password"],
            json_fields=self.JSON_FIELDS
        )

    async def find_by_ids(self, user_ids: List[str]) -> List[dict]:
        """Find multiple users by IDs"""
        if not user_ids:
            return []
        return await self.find_many(
            {"id": {"$in": user_ids}},
            exclude_fields=["password"],
            json_fields=self.JSON_FIELDS
        )


# Singleton instance
user_repository = UserRepository()
