"""
Shared subscription / Pro-access helpers.

Pro access sources:
- Active subscription_status premium/trial (including lifetime when expires is null)
- Active referral trial (referral_trial_end in the future)
- App owner: role == super_admin, or email listed in LARO_OWNER_EMAILS
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

# Keep in sync with Android SubscriptionRepository.FREE_RECIPE_LIMIT
FREE_RECIPE_LIMIT = 15

# Friend referral signup trial (and referrer reward when referee subscribes)
REFERRAL_TRIAL_DAYS = 14


async def assert_can_create_recipes(user: dict, recipe_repository, count_to_add: int = 1) -> None:
    """Raise HTTP 402 when a free user would exceed the recipe cap."""
    from fastapi import HTTPException

    if count_to_add <= 0:
        return
    if is_premium_user(user):
        return
    current = await recipe_repository.count({"author_id": user["id"]})
    bonus = int(user.get("recipe_bonus_slots") or 0)
    limit = FREE_RECIPE_LIMIT + max(0, bonus)
    if current + count_to_add > limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Free plan is limited to {limit} recipes. "
                "Upgrade to Pro for unlimited recipes, or redeem recipe slots in Rewards."
            ),
        )


def owner_emails() -> set[str]:
    raw = os.getenv("LARO_OWNER_EMAILS", "cowandom79@gmail.com")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_app_owner(user: dict) -> bool:
    """App owner gets lifetime Pro regardless of RevenueCat."""
    if (user.get("role") or "").lower() == "super_admin":
        return True
    email = (user.get("email") or "").strip().lower()
    return bool(email) and email in owner_emails()


def parse_expires(expires) -> Optional[datetime]:
    if not expires:
        return None
    try:
        if isinstance(expires, str):
            expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        else:
            expires_dt = expires
        if getattr(expires_dt, "tzinfo", None) is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None
    return expires_dt


def referral_trial_active(user: dict) -> bool:
    """True when referral_trial_end is in the future."""
    expires_dt = parse_expires(user.get("referral_trial_end"))
    if expires_dt is None:
        return False
    return expires_dt > datetime.now(timezone.utc)


def is_premium_user(user: dict) -> bool:
    """True when the user should get unlimited / Pro access."""
    if is_app_owner(user):
        return True

    if referral_trial_active(user):
        return True

    status = (user.get("subscription_status") or "free").lower()
    if status not in ("premium", "trial"):
        return False

    expires = user.get("subscription_expires")
    if not expires:
        return True  # lifetime / no expiry

    expires_dt = parse_expires(expires)
    if expires_dt is None:
        return True  # unparseable → assume active
    return expires_dt > datetime.now(timezone.utc)


def subscription_snapshot(user: dict) -> dict:
    """Fields for /subscriptions/status and auth payloads."""
    if is_app_owner(user):
        return {
            "status": "premium",
            "expires_at": None,
            "source": user.get("subscription_source") or "owner",
            "is_active": True,
            "is_lifetime": True,
            "is_owner": True,
        }

    status = (user.get("subscription_status") or "free").lower()
    expires = user.get("subscription_expires")
    expires_str = expires.isoformat() if hasattr(expires, "isoformat") else expires
    source = user.get("subscription_source")

    is_active = False
    is_lifetime = False
    if status in ("premium", "trial"):
        if expires:
            expires_dt = parse_expires(expires)
            if expires_dt is None:
                is_active = True
            elif expires_dt > datetime.now(timezone.utc):
                is_active = True
            else:
                status = "expired"
                is_active = False
        else:
            is_active = True
            is_lifetime = True

    # Friend referral trial counts as Pro even if subscription columns lag
    if not is_active and referral_trial_active(user):
        referral_end = user.get("referral_trial_end")
        expires_str = (
            referral_end.isoformat()
            if hasattr(referral_end, "isoformat")
            else referral_end
        )
        return {
            "status": "trial",
            "expires_at": expires_str,
            "source": source or "referral",
            "is_active": True,
            "is_lifetime": False,
            "is_owner": False,
        }

    return {
        "status": status,
        "expires_at": expires_str,
        "source": source,
        "is_active": is_active,
        "is_lifetime": is_lifetime,
        "is_owner": False,
    }


def user_subscription_fields(user: dict) -> dict:
    """Flatten snapshot onto auth/OAuth user payloads for seamless client Pro detection."""
    snap = subscription_snapshot(user)
    return {
        "subscription_status": snap["status"],
        "subscription_expires": snap["expires_at"],
        "subscription_source": snap["source"],
        "subscription_active": snap["is_active"],
        "is_pro": snap["is_active"],
        "is_lifetime": snap["is_lifetime"],
        "is_owner": snap["is_owner"],
    }
