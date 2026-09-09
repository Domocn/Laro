"""
Free-tier AI usage quota.

Free users get a small number of AI (LLM) calls, then must subscribe.
Schema/JSON-LD recipe imports do not consume quota.
Premium / trial users are unlimited.
"""
from __future__ import annotations

from fastapi import HTTPException

from config import settings
from utils.subscription import is_premium_user  # noqa: F401 — re-export for existing imports


def free_ai_limit() -> int:
    return int(getattr(settings, "free_ai_uses", 3) or 3)


async def get_ai_usage(user_id: str) -> int:
    from database.repositories.user_repository import user_repository

    row = await user_repository.find_by_id(user_id)
    if not row:
        return 0
    return int(row.get("ai_uses_count") or 0)


async def get_quota_status(user: dict) -> dict:
    used = await get_ai_usage(user["id"])
    bonus = int(user.get("ai_bonus_uses") or 0)
    limit = free_ai_limit() + max(0, bonus)
    premium = is_premium_user(user)
    remaining = None if premium else max(0, limit - used)
    return {
        "premium": premium,
        "used": used,
        "limit": limit,
        "bonus": bonus,
        "remaining": remaining,
        "unlimited": premium,
    }


async def require_ai_quota(user: dict) -> dict:
    """
    Raise 402 if the free user has exhausted their AI allowance.
    Returns quota status for callers that want to display remaining uses.
    """
    status = await get_quota_status(user)
    if status["premium"]:
        return status
    if status["remaining"] is not None and status["remaining"] <= 0:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "ai_quota_exceeded",
                "message": (
                    f"You've used your {status['limit']} free AI uses. "
                    "Upgrade to Premium for unlimited AI import and assistants."
                ),
                "used": status["used"],
                "limit": status["limit"],
                "upgrade_required": True,
            },
        )
    return status


async def consume_ai_quota(user_id: str) -> int:
    """Increment AI usage counter. Returns new count."""
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET ai_uses_count = COALESCE(ai_uses_count, 0) + 1
            WHERE id = $1
            RETURNING ai_uses_count
            """,
            user_id,
        )
    return int(row["ai_uses_count"]) if row else 0


async def meter_ai_for_user_id(user_id: str) -> dict:
    """
    Load user by id, enforce free-tier quota, and return the user dict.
    Used by background workers that only have user_id.
    """
    from database.repositories.user_repository import user_repository

    user = await user_repository.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await require_ai_quota(user)
    return user


async def consume_ai_quota_if_free(user: dict, usage_meta: dict | None = None) -> None:
    """Consume one free AI use unless premium or cache hit."""
    if is_premium_user(user):
        return
    if usage_meta and usage_meta.get("cached"):
        return
    await consume_ai_quota(user["id"])
