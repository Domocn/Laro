"""
Referral reward points + redeemable store catalog.

Earn:
  - Friend signs up with your code → POINTS_SIGNUP
  - Friend subscribes (paid Pro) → POINTS_SUBSCRIBE

Redeem — mirrors gated free-tier limits:
  - Pro days
  - Extra AI uses
  - Extra recipe / friend / cookbook / household slots
  - Extra weekly share allowance
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

POINTS_SIGNUP = 50
POINTS_SUBSCRIBE = 150

REWARD_CATALOG = [
    {
        "sku": "pro_7d",
        "title": "7 days of Pro",
        "description": "Unlock Laro Pro for a week — unlimited AI, recipes, shares & household",
        "cost": 100,
        "kind": "pro_days",
        "amount": 7,
    },
    {
        "sku": "pro_14d",
        "title": "14 days of Pro",
        "description": "Two weeks of full Pro access",
        "cost": 175,
        "kind": "pro_days",
        "amount": 14,
    },
    {
        "sku": "pro_30d",
        "title": "30 days of Pro",
        "description": "A full month of Laro Pro",
        "cost": 300,
        "kind": "pro_days",
        "amount": 30,
    },
    {
        "sku": "ai_5",
        "title": "+5 AI uses",
        "description": "Extra free-tier AI requests (imports, meal plans, chat)",
        "cost": 40,
        "kind": "ai_bonus",
        "amount": 5,
    },
    {
        "sku": "ai_15",
        "title": "+15 AI uses",
        "description": "A bigger boost of free AI requests",
        "cost": 100,
        "kind": "ai_bonus",
        "amount": 15,
    },
    {
        "sku": "recipes_10",
        "title": "+10 recipe slots",
        "description": "Save more recipes on the free plan (permanent)",
        "cost": 60,
        "kind": "recipe_slots",
        "amount": 10,
    },
    {
        "sku": "recipes_25",
        "title": "+25 recipe slots",
        "description": "Add 25 more free recipe slots (permanent)",
        "cost": 120,
        "kind": "recipe_slots",
        "amount": 25,
    },
    {
        "sku": "friends_2",
        "title": "+2 friend slots",
        "description": "Connect with more cooking friends",
        "cost": 50,
        "kind": "friend_slots",
        "amount": 2,
    },
    {
        "sku": "shares_5",
        "title": "+5 weekly shares",
        "description": "Raise your free weekly recipe-share limit (permanent)",
        "cost": 45,
        "kind": "share_weekly",
        "amount": 5,
    },
    {
        "sku": "cookbooks_3",
        "title": "+3 cookbook slots",
        "description": "Organise recipes into more cookbooks",
        "cost": 55,
        "kind": "cookbook_slots",
        "amount": 3,
    },
    {
        "sku": "household_1",
        "title": "+1 household seat",
        "description": "Invite another person to your free household",
        "cost": 80,
        "kind": "household_members",
        "amount": 1,
    },
]

CATALOG_BY_SKU = {item["sku"]: item for item in REWARD_CATALOG}

_BONUS_COLUMNS = {
    "ai_bonus": "ai_bonus_uses",
    "recipe_slots": "recipe_bonus_slots",
    "friend_slots": "friend_bonus_slots",
    "share_weekly": "share_bonus_weekly",
    "cookbook_slots": "cookbook_bonus_slots",
    "household_members": "household_bonus_members",
}


def catalog_public() -> list[dict]:
    return [
        {
            "sku": i["sku"],
            "title": i["title"],
            "description": i["description"],
            "cost": i["cost"],
            "kind": i["kind"],
            "amount": i["amount"],
        }
        for i in REWARD_CATALOG
    ]


async def get_points(user_id: str) -> int:
    from database.repositories.user_repository import user_repository

    user = await user_repository.find_by_id(user_id)
    if not user:
        return 0
    return int(user.get("reward_points") or 0)


async def credit_points(
    user_id: str,
    amount: int,
    reason: str,
    meta: Optional[dict] = None,
) -> dict:
    if amount <= 0:
        raise ValueError("amount must be positive")

    from database.connection import get_db

    pool = await get_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    meta_json = json.dumps(meta or {})
    entry_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        async with conn.transaction():
            inserted = await conn.fetchrow(
                """
                INSERT INTO reward_ledger (id, user_id, delta, reason, meta, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (reason) DO NOTHING
                RETURNING id
                """,
                entry_id,
                user_id,
                amount,
                reason,
                meta_json,
                now,
            )
            if not inserted:
                row = await conn.fetchrow(
                    "SELECT COALESCE(reward_points, 0) AS pts FROM users WHERE id = $1",
                    user_id,
                )
                return {
                    "credited": False,
                    "points": int(row["pts"]) if row else 0,
                    "delta": 0,
                }

            row = await conn.fetchrow(
                """
                UPDATE users
                SET reward_points = COALESCE(reward_points, 0) + $2
                WHERE id = $1
                RETURNING reward_points
                """,
                user_id,
                amount,
            )

    return {
        "credited": True,
        "points": int(row["reward_points"]) if row else amount,
        "delta": amount,
    }


async def grant_pro_days(user_id: str, days: int, source: str = "rewards") -> dict:
    from database.repositories.user_repository import user_repository
    from utils.subscription import parse_expires

    if days <= 0:
        raise ValueError("days must be positive")

    user = await user_repository.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    candidates = []
    for key in ("subscription_expires", "referral_trial_end"):
        dt = parse_expires(user.get(key))
        if dt and dt > now:
            candidates.append(dt)
    base = max(candidates) if candidates else now
    new_end = (base + timedelta(days=days)).astimezone(timezone.utc).replace(tzinfo=None)

    await user_repository.update_user(user_id, {
        "subscription_status": "trial",
        "subscription_expires": new_end,
        "subscription_source": source,
        "referral_trial_end": new_end,
    })
    return {"expires_at": new_end.isoformat(), "days": days, "source": source}


async def _bump_int_column(user_id: str, column: str, amount: int) -> int:
    from database.connection import get_db

    allowed = set(_BONUS_COLUMNS.values()) | {"reward_points"}
    if amount <= 0:
        raise ValueError("amount must be positive")
    if column not in allowed:
        raise ValueError("invalid column")

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE users
            SET {column} = COALESCE({column}, 0) + $2
            WHERE id = $1
            RETURNING {column}
            """,
            user_id,
            amount,
        )
    return int(row[column]) if row else amount


async def redeem_sku(user: dict, sku: str) -> dict:
    item = CATALOG_BY_SKU.get(sku)
    if not item:
        raise HTTPException(status_code=400, detail="Unknown reward")

    cost = int(item["cost"])
    user_id = user["id"]
    reason = f"redeem:{sku}:{uuid.uuid4()}"

    from database.connection import get_db

    pool = await get_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    meta_json = json.dumps({"sku": sku, "kind": item["kind"], "amount": item["amount"]})
    entry_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE users
                SET reward_points = reward_points - $2
                WHERE id = $1 AND COALESCE(reward_points, 0) >= $2
                RETURNING reward_points
                """,
                user_id,
                cost,
            )
            if not row:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "insufficient_points",
                        "message": f"Need {cost} points to redeem this reward.",
                        "cost": cost,
                        "points": int(user.get("reward_points") or 0),
                    },
                )
            await conn.execute(
                """
                INSERT INTO reward_ledger (id, user_id, delta, reason, meta, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                entry_id,
                user_id,
                -cost,
                reason,
                meta_json,
                now,
            )
            new_balance = int(row["reward_points"])

    grant: dict[str, Any] = {}
    kind = item["kind"]
    amount = int(item["amount"])
    if kind == "pro_days":
        grant = await grant_pro_days(user_id, amount, source="rewards")
    elif kind in _BONUS_COLUMNS:
        col = _BONUS_COLUMNS[kind]
        value = await _bump_int_column(user_id, col, amount)
        grant = {col: value}
    else:
        raise HTTPException(status_code=500, detail="Unsupported reward kind")

    return {
        "success": True,
        "sku": sku,
        "title": item["title"],
        "cost": cost,
        "points": new_balance,
        "grant": grant,
    }


async def list_ledger(user_id: str, limit: int = 30) -> list[dict]:
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, delta, reason, meta, created_at
            FROM reward_ledger
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    out = []
    for r in rows:
        meta = r["meta"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        out.append({
            "id": r["id"],
            "delta": r["delta"],
            "reason": r["reason"],
            "meta": meta or {},
            "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"],
        })
    return out


# Back-compat aliases used by older call sites
async def grant_ai_bonus(user_id: str, amount: int) -> dict:
    value = await _bump_int_column(user_id, "ai_bonus_uses", amount)
    return {"ai_bonus_uses": value}


# Re-export for friends router
from utils.free_limits import friend_limit as friend_limit_for  # noqa: E402
