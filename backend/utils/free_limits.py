"""
Free-tier limits + assert helpers for gated features.

Pro / referral-trial users bypass all caps via is_premium_user().
Bonus columns raise free-tier ceilings (redeemable in the rewards store).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import HTTPException

from utils.subscription import FREE_RECIPE_LIMIT, is_premium_user

# Keep friend limit aligned with Android SubscriptionRepository.FREE_FRIEND_LIMIT
FREE_FRIEND_LIMIT = 3
FREE_SHARE_WEEKLY = 5
FREE_COOKBOOK_LIMIT = 3
FREE_HOUSEHOLD_MEMBERS = 2  # owner + 1 guest on free


def _bonus(user: dict, key: str) -> int:
    return max(0, int(user.get(key) or 0))


def friend_limit(user: dict) -> int:
    if is_premium_user(user):
        return 10_000
    return FREE_FRIEND_LIMIT + _bonus(user, "friend_bonus_slots")


def share_weekly_limit(user: dict) -> int:
    if is_premium_user(user):
        return 10_000
    return FREE_SHARE_WEEKLY + _bonus(user, "share_bonus_weekly")


def cookbook_limit(user: dict) -> int:
    if is_premium_user(user):
        return 10_000
    return FREE_COOKBOOK_LIMIT + _bonus(user, "cookbook_bonus_slots")


def household_member_limit(owner_or_actor: dict) -> int:
    """Member cap for the household — based on the inviting user's bonuses / Pro."""
    if is_premium_user(owner_or_actor):
        return 10_000
    return FREE_HOUSEHOLD_MEMBERS + _bonus(owner_or_actor, "household_bonus_members")


def recipe_limit(user: dict) -> int:
    if is_premium_user(user):
        return 10_000
    return FREE_RECIPE_LIMIT + _bonus(user, "recipe_bonus_slots")


async def assert_can_add_friend(user: dict) -> None:
    if is_premium_user(user):
        return
    current = len(list(user.get("friends") or []))
    limit = friend_limit(user)
    if current >= limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Free plan is limited to {limit} friends. "
                "Upgrade to Pro or redeem friend slots in Rewards."
            ),
        )


async def assert_can_share(user: dict) -> None:
    if is_premium_user(user):
        return
    from database.connection import get_db

    week_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS c FROM recipe_shares
            WHERE user_id = $1 AND created_at >= $2
            """,
            user["id"],
            week_ago,
        )
    used = int(row["c"]) if row else 0
    limit = share_weekly_limit(user)
    if used >= limit:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "share_limit",
                "message": (
                    f"Free plan allows {limit} recipe shares per week. "
                    "Upgrade to Pro or redeem a share boost in Rewards."
                ),
                "used": used,
                "limit": limit,
            },
        )


async def assert_can_create_cookbook(user: dict, cookbook_repository) -> None:
    if is_premium_user(user):
        return
    existing = await cookbook_repository.find_by_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
    )
    # Count cookbooks the user owns (not household peers') when possible
    owned = [c for c in (existing or []) if c.get("user_id") == user["id"] or not c.get("user_id")]
    count = len(owned) if owned else len(existing or [])
    limit = cookbook_limit(user)
    if count >= limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Free plan is limited to {limit} cookbooks. "
                "Upgrade to Pro or redeem cookbook slots in Rewards."
            ),
        )


async def assert_can_add_household_member(actor: dict, household: dict) -> None:
    if is_premium_user(actor):
        return
    members = list(household.get("member_ids") or [])
    limit = household_member_limit(actor)
    if len(members) >= limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Free plan households are limited to {limit} members. "
                "Upgrade to Pro or redeem a household seat in Rewards."
            ),
        )
