"""
Friends Router - Friend codes and social features
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from dependencies import get_current_user, user_repository
import uuid
import random
import string

router = APIRouter(prefix="/friends", tags=["Friends"])


class AddFriendRequest(BaseModel):
    friend_code: str


class FriendResponse(BaseModel):
    id: str
    name: str
    friend_code: str
    added_at: str


def generate_friend_code(name: str) -> str:
    """Generate a friend code in format NAME#1234"""
    # Clean the name - take first part before space, uppercase, max 8 chars
    clean_name = name.split()[0].upper()[:8] if name else "CHEF"
    # Remove non-alphanumeric characters
    clean_name = ''.join(c for c in clean_name if c.isalnum())
    if not clean_name:
        clean_name = "CHEF"
    # Generate 4 digit code
    code = ''.join(random.choices(string.digits, k=4))
    return f"{clean_name}#{code}"


@router.get("/my-code")
async def get_my_friend_code(user: dict = Depends(get_current_user)):
    """Get current user's friend code"""
    friend_code = user.get("friend_code")

    # Generate friend code if user doesn't have one
    if not friend_code:
        friend_code = generate_friend_code(user.get("name", "Chef"))
        # Make sure it's unique
        existing = await user_repository.find_by_friend_code(friend_code)
        attempts = 0
        while existing and attempts < 10:
            friend_code = generate_friend_code(user.get("name", "Chef"))
            existing = await user_repository.find_by_friend_code(friend_code)
            attempts += 1

        await user_repository.update_user(user["id"], {"friend_code": friend_code})

    return {
        "friend_code": friend_code,
        "name": user.get("name", "Chef")
    }


@router.post("/add")
async def add_friend(
    data: AddFriendRequest,
    user: dict = Depends(get_current_user)
):
    """Send a friend request by friend code — recipient must accept."""
    from utils.free_limits import assert_can_add_friend
    await assert_can_add_friend(user)

    friend_code = data.friend_code.strip().upper()
    friend = await user_repository.find_by_friend_code(friend_code)

    if not friend:
        raise HTTPException(status_code=404, detail="Friend code not found")

    if friend["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot add yourself as a friend")

    current_friends = list(user.get("friends") or [])
    if friend["id"] in current_friends:
        raise HTTPException(status_code=400, detail="You are already friends with this user")

    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        # Reverse pending request → auto-accept (both sides already expressed intent)
        reverse = await conn.fetchrow(
            """
            SELECT id FROM friend_requests
            WHERE from_user_id = $1 AND to_user_id = $2 AND status = 'pending'
            """,
            friend["id"],
            user["id"],
        )
        if reverse:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            await conn.execute(
                """
                UPDATE friend_requests
                SET status = 'accepted', responded_at = $1
                WHERE id = $2
                """,
                now,
                reverse["id"],
            )
            current_friends.append(friend["id"])
            await user_repository.update_user(user["id"], {"friends": current_friends})
            friend_friends = list(friend.get("friends") or [])
            if user["id"] not in friend_friends:
                friend_friends.append(user["id"])
                await user_repository.update_user(friend["id"], {"friends": friend_friends})
            return {
                "success": True,
                "pending": False,
                "message": "Friend request accepted",
                "friend": {
                    "id": friend["id"],
                    "name": friend.get("name", "Friend"),
                    "friend_code": friend.get("friend_code", ""),
                    "added_at": now.isoformat(),
                },
            }

        existing = await conn.fetchrow(
            """
            SELECT id FROM friend_requests
            WHERE from_user_id = $1 AND to_user_id = $2 AND status = 'pending'
            """,
            user["id"],
            friend["id"],
        )
        if existing:
            raise HTTPException(status_code=400, detail="Friend request already pending")

        request_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await conn.execute(
            """
            INSERT INTO friend_requests
                (id, from_user_id, to_user_id, status, created_at)
            VALUES ($1, $2, $3, 'pending', $4)
            """,
            request_id,
            user["id"],
            friend["id"],
            now,
        )

    try:
        from services.notifications import notify_user, NotificationType
        await notify_user(
            user_id=friend["id"],
            notification_type=NotificationType.FRIEND_REQUEST,
            data={"from_name": user.get("name", "Someone"), "request_id": request_id},
        )
    except Exception:
        pass

    return {
        "success": True,
        "pending": True,
        "message": "Friend request sent — they must accept",
        "request_id": request_id,
        "friend": {
            "id": friend["id"],
            "name": friend.get("name", "Friend"),
            "friend_code": friend.get("friend_code", ""),
        },
    }


@router.get("/requests")
async def list_friend_requests(user: dict = Depends(get_current_user)):
    """List incoming and outgoing pending friend requests."""
    from database.connection import get_db, dict_from_row

    pool = await get_db()
    async with pool.acquire() as conn:
        incoming_rows = await conn.fetch(
            """
            SELECT fr.id, fr.from_user_id, fr.created_at,
                   u.name AS from_name, u.friend_code AS from_friend_code
            FROM friend_requests fr
            JOIN users u ON u.id = fr.from_user_id
            WHERE fr.to_user_id = $1 AND fr.status = 'pending'
            ORDER BY fr.created_at DESC
            """,
            user["id"],
        )
        outgoing_rows = await conn.fetch(
            """
            SELECT fr.id, fr.to_user_id, fr.created_at,
                   u.name AS to_name, u.friend_code AS to_friend_code
            FROM friend_requests fr
            JOIN users u ON u.id = fr.to_user_id
            WHERE fr.from_user_id = $1 AND fr.status = 'pending'
            ORDER BY fr.created_at DESC
            """,
            user["id"],
        )

    def _serialize(rows):
        out = []
        for row in rows:
            d = dict_from_row(row)
            if d.get("created_at") is not None and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out

    return {
        "incoming": _serialize(incoming_rows),
        "outgoing": _serialize(outgoing_rows),
    }


@router.post("/requests/{request_id}/accept")
async def accept_friend_request(request_id: str, user: dict = Depends(get_current_user)):
    """Accept an incoming friend request."""
    from utils.free_limits import assert_can_add_friend
    await assert_can_add_friend(user)

    from database.connection import get_db, dict_from_row

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM friend_requests
            WHERE id = $1 AND to_user_id = $2 AND status = 'pending'
            """,
            request_id,
            user["id"],
        )
        if not row:
            raise HTTPException(status_code=404, detail="Friend request not found")
        req = dict_from_row(row)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await conn.execute(
            """
            UPDATE friend_requests
            SET status = 'accepted', responded_at = $1
            WHERE id = $2
            """,
            now,
            request_id,
        )

    from_user = await user_repository.find_by_id(req["from_user_id"])
    if not from_user:
        raise HTTPException(status_code=404, detail="User no longer exists")

    current_friends = list(user.get("friends") or [])
    if from_user["id"] not in current_friends:
        current_friends.append(from_user["id"])
        await user_repository.update_user(user["id"], {"friends": current_friends})

    from_friends = list(from_user.get("friends") or [])
    if user["id"] not in from_friends:
        from_friends.append(user["id"])
        await user_repository.update_user(from_user["id"], {"friends": from_friends})

    return {
        "success": True,
        "friend": {
            "id": from_user["id"],
            "name": from_user.get("name", "Friend"),
            "friend_code": from_user.get("friend_code", ""),
            "added_at": now.isoformat(),
        },
    }


@router.post("/requests/{request_id}/decline")
async def decline_friend_request(request_id: str, user: dict = Depends(get_current_user)):
    """Decline an incoming friend request."""
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id FROM friend_requests
            WHERE id = $1 AND to_user_id = $2 AND status = 'pending'
            """,
            request_id,
            user["id"],
        )
        if not row:
            raise HTTPException(status_code=404, detail="Friend request not found")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await conn.execute(
            """
            UPDATE friend_requests
            SET status = 'declined', responded_at = $1
            WHERE id = $2
            """,
            now,
            request_id,
        )
    return {"success": True, "message": "Friend request declined"}


@router.get("/list")
async def list_friends(user: dict = Depends(get_current_user)):
    """Get list of friends"""
    friend_ids = list(user.get("friends") or [])

    friends = []
    for friend_id in friend_ids:
        friend = await user_repository.find_by_id(friend_id)
        if friend:
            friends.append({
                "id": friend["id"],
                "name": friend.get("name", "Friend"),
                "friend_code": friend.get("friend_code", ""),
            })

    return {
        "friends": friends,
        "total": len(friends)
    }


@router.delete("/{friend_id}")
async def remove_friend(
    friend_id: str,
    user: dict = Depends(get_current_user)
):
    """Remove a friend"""
    current_friends = list(user.get("friends") or [])

    if friend_id not in current_friends:
        raise HTTPException(status_code=404, detail="Friend not found")

    # Remove from current user's friends
    current_friends.remove(friend_id)
    await user_repository.update_user(user["id"], {"friends": current_friends})

    # Remove current user from friend's friends list
    friend = await user_repository.find_by_id(friend_id)
    if friend:
        friend_friends = list(friend.get("friends") or [])
        if user["id"] in friend_friends:
            friend_friends.remove(user["id"])
            await user_repository.update_user(friend_id, {"friends": friend_friends})

    return {"success": True, "message": "Friend removed"}


@router.get("/count")
async def get_friend_count(user: dict = Depends(get_current_user)):
    """Get current friend count"""
    friend_ids = list(user.get("friends") or [])
    return {"count": len(friend_ids)}


@router.post("/confirm-subscription")
async def confirm_subscription(user: dict = Depends(get_current_user)):
    """Called when a user subscribes - grants referrer their reward"""
    result = await grant_referrer_reward_for_subscriber(user)
    return result


async def grant_referrer_reward_for_subscriber(user: dict) -> dict:
    """
    When a referred user subscribes, credit the referrer with subscribe points.
    Safe to call multiple times — rewards once per referred user.
    """
    referred_by = user.get("referred_by")

    if not referred_by:
        return {"success": True, "message": "No referrer to reward"}

    if user.get("referral_reward_granted"):
        return {"success": True, "message": "Reward already granted"}

    referrer = await user_repository.find_by_id(referred_by)
    if not referrer:
        return {"success": True, "message": "Referrer not found"}

    from utils.rewards import credit_points, POINTS_SUBSCRIBE

    referral_count = int(referrer.get("referral_count", 0) or 0) + 1

    pending_rewards = referrer.get("pending_referral_rewards", [])
    if isinstance(pending_rewards, str):
        import json
        try:
            pending_rewards = json.loads(pending_rewards) or []
        except Exception:
            pending_rewards = []
    pending_rewards = [r for r in pending_rewards if r.get("referred_user_id") != user["id"]]

    credit = await credit_points(
        referred_by,
        POINTS_SUBSCRIBE,
        reason=f"referral_subscribe:{user['id']}",
        meta={"referred_user_id": user["id"]},
    )

    await user_repository.update_user(referred_by, {
        "referral_count": referral_count,
        "pending_referral_rewards": pending_rewards,
    })

    await user_repository.update_user(user["id"], {
        "referral_reward_granted": True
    })

    return {
        "success": True,
        "message": f"Referrer rewarded with {POINTS_SUBSCRIBE} points",
        "points_credited": credit.get("delta", 0),
        "referrer_points": credit.get("points"),
        "referral_count": referral_count,
    }


@router.get("/referral-stats")
async def get_referral_stats(user: dict = Depends(get_current_user)):
    """Get user's referral statistics"""
    referral_count = user.get("referral_count", 0)
    referral_trial_end = user.get("referral_trial_end")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    has_referral_trial = False
    days_remaining = 0

    if referral_trial_end:
        if hasattr(referral_trial_end, 'replace'):
            has_referral_trial = referral_trial_end > now
            if has_referral_trial:
                days_remaining = (referral_trial_end - now).days
        referral_trial_end = referral_trial_end.isoformat() if hasattr(referral_trial_end, 'isoformat') else referral_trial_end

    pending_rewards = user.get("pending_referral_rewards", [])
    if isinstance(pending_rewards, str):
        import json
        try:
            pending_rewards = json.loads(pending_rewards) or []
        except Exception:
            pending_rewards = []

    return {
        "referral_count": referral_count,
        "pending_referrals": len(pending_rewards) if isinstance(pending_rewards, list) else 0,
        "has_referral_trial": has_referral_trial,
        "referral_trial_end": referral_trial_end,
        "days_remaining": days_remaining,
        "reward_points": int(user.get("reward_points") or 0),
    }
