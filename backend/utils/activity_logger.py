"""
User Activity Logger - Logs user actions to audit_logs table for tracking and debugging

Usage:
    from utils.activity_logger import log_user_activity

    await log_user_activity(
        user_id="abc123",
        user_email="user@example.com",
        action="recipe_created",
        target_type="recipe",
        target_id="recipe-456",
        details={"title": "Pancakes"},
        ip_address="192.168.1.1"
    )
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger("mise.activity")


async def log_user_activity(
    user_id: str,
    user_email: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> bool:
    """
    Log user activity to the audit_logs table.

    Actions include:
    - login, logout, login_failed
    - recipe_created, recipe_updated, recipe_deleted
    - meal_plan_created, meal_plan_deleted
    - pantry_item_added, pantry_item_updated, pantry_item_deleted
    - shopping_list_created, shopping_list_completed
    - household_joined, household_left
    - password_changed, profile_updated
    - data_exported, data_imported

    Args:
        user_id: The user's ID
        user_email: The user's email
        action: The action performed
        target_type: Type of target (e.g., "recipe", "meal_plan")
        target_id: ID of the target resource
        details: Additional details as a dictionary
        ip_address: Client IP address

    Returns:
        True if logged successfully, False otherwise
    """
    try:
        import json
        from database.connection import get_db

        pool = await get_db()

        log_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        details_json = json.dumps(details) if details else None

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs (id, user_id, user_email, action, target_type, target_id, details, ip_address, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                log_id,
                user_id,
                user_email,
                action,
                target_type,
                target_id,
                details_json,
                ip_address,
                timestamp
            )

        # Also log to console for immediate visibility
        logger.info(
            f"ACTIVITY: user={user_id[:8]}... action={action} "
            f"target={target_type or '-'}:{target_id[:8] if target_id else '-'}... "
            f"ip={ip_address or 'unknown'}"
        )

        return True

    except Exception as e:
        logger.error(f"Failed to log user activity: {e}")
        return False


async def log_action(user: dict, action: str, request=None, **kwargs) -> bool:
    """
    Convenience function to log action from a user dict and FastAPI request.

    Args:
        user: User dict from get_current_user dependency
        action: The action performed
        request: FastAPI Request object (optional)
        **kwargs: Additional arguments passed to log_user_activity
    """
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None

    return await log_user_activity(
        user_id=user.get("id", "unknown"),
        user_email=user.get("email", "unknown"),
        action=action,
        ip_address=ip_address,
        **kwargs
    )
