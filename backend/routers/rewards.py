"""
Rewards Router — referral points balance + redeemable store.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import settings
from dependencies import get_current_user
from utils.subscription import FREE_RECIPE_LIMIT
from utils.free_limits import (
    FREE_FRIEND_LIMIT,
    FREE_SHARE_WEEKLY,
    FREE_COOKBOOK_LIMIT,
    FREE_HOUSEHOLD_MEMBERS,
    friend_limit,
    share_weekly_limit,
    cookbook_limit,
    household_member_limit,
    recipe_limit,
)
from utils.rewards import (
    POINTS_SIGNUP,
    POINTS_SUBSCRIBE,
    catalog_public,
    get_points,
    list_ledger,
    redeem_sku,
)
from utils.ai_quota import get_quota_status

router = APIRouter(prefix="/rewards", tags=["Rewards"])


class RedeemRequest(BaseModel):
    sku: str = Field(..., min_length=2, max_length=64)


@router.get("/catalog")
async def get_catalog(user: dict = Depends(get_current_user)):
    """Reward store catalog + how points are earned + current free-tier ceilings."""
    points = await get_points(user["id"])
    return {
        "points": points,
        "earn": {
            "referral_signup": POINTS_SIGNUP,
            "referral_subscribe": POINTS_SUBSCRIBE,
        },
        "limits": {
            "recipes": recipe_limit(user),
            "friends": friend_limit(user),
            "shares_weekly": share_weekly_limit(user),
            "cookbooks": cookbook_limit(user),
            "household_members": household_member_limit(user),
            "ai_base": int(getattr(settings, "free_ai_uses", 3) or 3),
            "free_defaults": {
                "recipes": FREE_RECIPE_LIMIT,
                "friends": FREE_FRIEND_LIMIT,
                "shares_weekly": FREE_SHARE_WEEKLY,
                "cookbooks": FREE_COOKBOOK_LIMIT,
                "household_members": FREE_HOUSEHOLD_MEMBERS,
            },
        },
        "bonuses": {
            "ai_bonus_uses": int(user.get("ai_bonus_uses") or 0),
            "recipe_bonus_slots": int(user.get("recipe_bonus_slots") or 0),
            "friend_bonus_slots": int(user.get("friend_bonus_slots") or 0),
            "share_bonus_weekly": int(user.get("share_bonus_weekly") or 0),
            "cookbook_bonus_slots": int(user.get("cookbook_bonus_slots") or 0),
            "household_bonus_members": int(user.get("household_bonus_members") or 0),
        },
        "catalog": catalog_public(),
    }


@router.get("/balance")
async def get_balance(user: dict = Depends(get_current_user)):
    points = await get_points(user["id"])
    quota = await get_quota_status(user)
    return {
        "points": points,
        "ai_bonus_uses": int(user.get("ai_bonus_uses") or 0),
        "recipe_bonus_slots": int(user.get("recipe_bonus_slots") or 0),
        "friend_bonus_slots": int(user.get("friend_bonus_slots") or 0),
        "share_bonus_weekly": int(user.get("share_bonus_weekly") or 0),
        "cookbook_bonus_slots": int(user.get("cookbook_bonus_slots") or 0),
        "household_bonus_members": int(user.get("household_bonus_members") or 0),
        "limits": {
            "recipes": recipe_limit(user),
            "friends": friend_limit(user),
            "shares_weekly": share_weekly_limit(user),
            "cookbooks": cookbook_limit(user),
            "household_members": household_member_limit(user),
        },
        "ai_quota": quota,
        "earn": {
            "referral_signup": POINTS_SIGNUP,
            "referral_subscribe": POINTS_SUBSCRIBE,
        },
    }


@router.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    return {"entries": await list_ledger(user["id"])}


@router.post("/redeem")
async def redeem(data: RedeemRequest, user: dict = Depends(get_current_user)):
    try:
        result = await redeem_sku(user, data.sku.strip())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return result
