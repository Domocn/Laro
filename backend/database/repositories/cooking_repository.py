"""
Cooking Repository - Handles cooking sessions and recipe feedback
"""
from typing import Optional, List
from .base_repository import BaseRepository


class CookSessionRepository(BaseRepository):
    """Repository for cooking sessions"""

    def __init__(self):
        super().__init__("cook_sessions")

    async def find_by_id(self, session_id: str) -> Optional[dict]:
        """Find cook session by ID"""
        return await self.find_one({"id": session_id})

    async def find_by_id_and_user(self, session_id: str, user_id: str) -> Optional[dict]:
        """Find cook session by ID and user"""
        return await self.find_one({"id": session_id, "user_id": user_id})

    async def create(self, session_data: dict) -> dict:
        """Create a new cook session"""
        return await self.insert(session_data)

    async def update_session(self, session_id: str, data: dict) -> int:
        """Update cook session"""
        return await self.update({"id": session_id}, data)

    async def find_by_user(
        self,
        user_id: str,
        completed_only: bool = False,
        limit: int = 100
    ) -> List[dict]:
        """Find cook sessions for a user"""
        conditions = {"user_id": user_id}
        if completed_only:
            conditions["completed_at"] = {"$ne": None}

        return await self.find_many(
            conditions,
            order_by="started_at",
            order_dir="DESC",
            limit=limit
        )

    async def count_completed(self, user_id: str) -> int:
        """Count completed cooking sessions for a user"""
        pool = await self._get_db()

        query = """
            SELECT COUNT(*) FROM cook_sessions
            WHERE user_id = $1 AND completed_at IS NOT NULL
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)

        return row[0] if row else 0


class RecipeFeedbackRepository(BaseRepository):
    """Repository for recipe feedback (would cook again)"""

    def __init__(self):
        super().__init__("recipe_feedback")

    async def find_by_user_and_recipe(
        self,
        user_id: str,
        recipe_id: str
    ) -> Optional[dict]:
        """Find feedback by user and recipe"""
        return await self.find_one({"user_id": user_id, "recipe_id": recipe_id})

    async def upsert_feedback(
        self,
        user_id: str,
        recipe_id: str,
        feedback: str,
        updated_at: str
    ) -> dict:
        """Create or update recipe feedback"""
        pool = await self._get_db()

        async with pool.acquire() as conn:
            # Try to update first
            result = await conn.execute(
                """
                UPDATE recipe_feedback
                SET feedback = $1, updated_at = $2
                WHERE user_id = $3 AND recipe_id = $4
                """,
                feedback, updated_at, user_id, recipe_id
            )

            # Parse rowcount from result string (e.g., "UPDATE 1")
            rowcount = int(result.split()[-1]) if result else 0

            if rowcount == 0:
                # Insert new
                import uuid
                feedback_id = str(uuid.uuid4())
                await conn.execute(
                    """
                    INSERT INTO recipe_feedback (id, user_id, recipe_id, feedback, updated_at)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    feedback_id, user_id, recipe_id, feedback, updated_at
                )

        return {
            "user_id": user_id,
            "recipe_id": recipe_id,
            "feedback": feedback,
            "updated_at": updated_at
        }

    async def find_by_user(self, user_id: str, limit: int = 500) -> List[dict]:
        """Find all feedback for a user"""
        return await self.find_many(
            {"user_id": user_id},
            limit=limit
        )

    async def count_by_feedback_type(self, user_id: str, feedback_type: str) -> int:
        """Count feedback of a specific type for a user"""
        return await self.count({"user_id": user_id, "feedback": feedback_type})

    async def get_boosted_recipes(self, user_id: str) -> set:
        """Get set of recipe IDs with 'yes' feedback"""
        feedback_list = await self.find_by_user(user_id)
        return {fb["recipe_id"] for fb in feedback_list if fb.get("feedback") == "yes"}

    async def get_buried_recipes(self, user_id: str) -> set:
        """Get set of recipe IDs with 'no' feedback"""
        feedback_list = await self.find_by_user(user_id)
        return {fb["recipe_id"] for fb in feedback_list if fb.get("feedback") == "no"}


class IngredientCostRepository(BaseRepository):
    """Repository for ingredient cost tracking"""

    def __init__(self):
        super().__init__("ingredient_costs")

    async def find_by_household(self, household_id: str) -> List[dict]:
        """Find all ingredient costs for a household"""
        return await self.find_many(
            {"household_id": household_id},
            order_by="ingredient_name",
            order_dir="ASC"
        )

    async def find_by_name(
        self,
        household_id: str,
        ingredient_name: str
    ) -> Optional[dict]:
        """Find cost for a specific ingredient"""
        return await self.find_one({
            "household_id": household_id,
            "ingredient_name": ingredient_name
        })

    async def upsert_cost(
        self,
        household_id: str,
        ingredient_name: str,
        cost: float,
        unit: str = None,
        store: str = None,
        updated_at: str = None
    ) -> dict:
        """Create or update ingredient cost"""
        pool = await self._get_db()

        async with pool.acquire() as conn:
            # Try to update first
            result = await conn.execute(
                """
                UPDATE ingredient_costs
                SET cost = $1, unit = $2, store = $3, updated_at = $4
                WHERE household_id = $5 AND ingredient_name = $6
                """,
                cost, unit, store, updated_at, household_id, ingredient_name
            )

            # Parse rowcount from result string (e.g., "UPDATE 1")
            rowcount = int(result.split()[-1]) if result else 0

            if rowcount == 0:
                # Insert new
                import uuid
                cost_id = str(uuid.uuid4())
                await conn.execute(
                    """
                    INSERT INTO ingredient_costs
                    (id, household_id, ingredient_name, cost, unit, store, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    cost_id, household_id, ingredient_name, cost, unit, store, updated_at
                )

        return {
            "household_id": household_id,
            "ingredient_name": ingredient_name,
            "cost": cost,
            "unit": unit,
            "store": store,
            "updated_at": updated_at
        }

    async def delete_cost(self, cost_id: str) -> int:
        """Delete an ingredient cost"""
        return await self.delete({"id": cost_id})


# Singleton instances
cook_session_repository = CookSessionRepository()
recipe_feedback_repository = RecipeFeedbackRepository()
ingredient_cost_repository = IngredientCostRepository()
