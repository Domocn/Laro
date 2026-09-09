"""Tests for free-tier gates and reward catalog."""
from datetime import datetime, timedelta, timezone

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
from utils.rewards import CATALOG_BY_SKU, POINTS_SIGNUP, POINTS_SUBSCRIBE, catalog_public
from utils.subscription import FREE_RECIPE_LIMIT, is_premium_user


def test_free_limits_defaults():
    user = {"subscription_status": "free", "role": "user", "email": "a@b.c"}
    assert friend_limit(user) == FREE_FRIEND_LIMIT
    assert share_weekly_limit(user) == FREE_SHARE_WEEKLY
    assert cookbook_limit(user) == FREE_COOKBOOK_LIMIT
    assert household_member_limit(user) == FREE_HOUSEHOLD_MEMBERS
    assert recipe_limit(user) == FREE_RECIPE_LIMIT


def test_bonus_slots_raise_ceilings():
    user = {
        "subscription_status": "free",
        "role": "user",
        "email": "a@b.c",
        "friend_bonus_slots": 2,
        "share_bonus_weekly": 5,
        "cookbook_bonus_slots": 3,
        "household_bonus_members": 1,
        "recipe_bonus_slots": 10,
    }
    assert friend_limit(user) == FREE_FRIEND_LIMIT + 2
    assert share_weekly_limit(user) == FREE_SHARE_WEEKLY + 5
    assert cookbook_limit(user) == FREE_COOKBOOK_LIMIT + 3
    assert household_member_limit(user) == FREE_HOUSEHOLD_MEMBERS + 1
    assert recipe_limit(user) == FREE_RECIPE_LIMIT + 10


def test_pro_bypasses_limits():
    user = {
        "subscription_status": "trial",
        "subscription_expires": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
        "role": "user",
        "email": "a@b.c",
    }
    assert is_premium_user(user)
    assert friend_limit(user) >= 1000
    assert share_weekly_limit(user) >= 1000


def test_catalog_has_gated_skus():
    skus = {i["sku"] for i in catalog_public()}
    for needed in (
        "pro_7d",
        "ai_5",
        "recipes_10",
        "friends_2",
        "shares_5",
        "cookbooks_3",
        "household_1",
    ):
        assert needed in skus
        assert needed in CATALOG_BY_SKU
    assert POINTS_SIGNUP == 50
    assert POINTS_SUBSCRIBE == 150
