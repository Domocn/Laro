"""
Notification Repository - Handles push subscriptions and notification settings
"""
import json
from typing import Optional, List
from .base_repository import BaseRepository


class PushSubscriptionRepository(BaseRepository):
    """Repository for push notification subscriptions"""

    JSON_FIELDS = ["subscription"]

    def __init__(self):
        super().__init__("push_subscriptions")

    async def find_by_user(self, user_id: str) -> List[dict]:
        """Find all subscriptions for a user"""
        return await self.find_many(
            {"user_id": user_id},
            json_fields=self.JSON_FIELDS
        )

    async def create(self, subscription_data: dict) -> dict:
        """Create a new push subscription"""
        return await self.insert(subscription_data, json_fields=self.JSON_FIELDS)

    async def delete_subscription(self, subscription_id: str) -> int:
        """Delete a subscription"""
        return await self.delete({"id": subscription_id})

    async def delete_by_user(self, user_id: str) -> int:
        """Delete all subscriptions for a user"""
        return await self.delete({"user_id": user_id})

    async def find_by_household(self, household_id: str) -> List[dict]:
        """Find all subscriptions for users in a household"""
        # This requires a join with users table
        pool = await self._get_db()

        query = """
            SELECT ps.* FROM push_subscriptions ps
            JOIN users u ON ps.user_id = u.id
            WHERE u.household_id = $1
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, household_id)

        from ..connection import rows_to_dicts
        results = rows_to_dicts(rows)

        for result in results:
            if result.get("subscription"):
                try:
                    result["subscription"] = json.loads(result["subscription"])
                except (json.JSONDecodeError, TypeError):
                    pass

        return results


class NotificationSettingsRepository(BaseRepository):
    """Repository for user notification settings"""

    def __init__(self):
        super().__init__("notification_settings")

    async def find_by_user(self, user_id: str) -> Optional[dict]:
        """Get notification settings for a user"""
        return await self.find_one({"user_id": user_id})

    async def upsert_settings(self, user_id: str, settings: dict) -> dict:
        """Create or update notification settings"""
        existing = await self.find_by_user(user_id)

        if existing:
            await self.update({"user_id": user_id}, settings)
        else:
            await self.insert({"user_id": user_id, **settings})

        return {"user_id": user_id, **settings}

    async def get_users_with_reminders_enabled(self) -> List[dict]:
        """Get all users who have meal reminders enabled"""
        return await self.find_many(
            {"enabled": True, "meal_reminders": True}
        )


# Singleton instances
push_subscription_repository = PushSubscriptionRepository()
notification_settings_repository = NotificationSettingsRepository()
