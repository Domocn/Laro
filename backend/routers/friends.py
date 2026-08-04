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
    """Add a friend by their friend code"""
    # Normalize the friend code
    friend_code = data.friend_code.strip().upper()

    # Find user by friend code
    friend = await user_repository.find_by_friend_code(friend_code)

    if not friend:
        raise HTTPException(status_code=404, detail="Friend code not found")

    if friend["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot add yourself as a friend")

    # Check if already friends
    current_friends = user.get("friends", [])
    if friend["id"] in current_friends:
        raise HTTPException(status_code=400, detail="You are already friends with this user")

    # Add friend to both users' friend lists
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Add to current user's friends
    current_friends.append(friend["id"])
    await user_repository.update_user(user["id"], {"friends": current_friends})

    # Add current user to friend's friends list (mutual friendship)
    friend_friends = friend.get("friends", [])
    if user["id"] not in friend_friends:
        friend_friends.append(user["id"])
        await user_repository.update_user(friend["id"], {"friends": friend_friends})

    return {
        "success": True,
        "friend": {
            "id": friend["id"],
            "name": friend.get("name", "Friend"),
            "friend_code": friend.get("friend_code", ""),
            "added_at": now.isoformat()
        }
    }


@router.get("/list")
async def list_friends(user: dict = Depends(get_current_user)):
    """Get list of friends"""
    friend_ids = user.get("friends", [])

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
    current_friends = user.get("friends", [])

    if friend_id not in current_friends:
        raise HTTPException(status_code=404, detail="Friend not found")

    # Remove from current user's friends
    current_friends.remove(friend_id)
    await user_repository.update_user(user["id"], {"friends": current_friends})

    # Remove current user from friend's friends list
    friend = await user_repository.find_by_id(friend_id)
    if friend:
        friend_friends = friend.get("friends", [])
        if user["id"] in friend_friends:
            friend_friends.remove(user["id"])
            await user_repository.update_user(friend_id, {"friends": friend_friends})

    return {"success": True, "message": "Friend removed"}


@router.get("/count")
async def get_friend_count(user: dict = Depends(get_current_user)):
    """Get current friend count"""
    friend_ids = user.get("friends", [])
    return {"count": len(friend_ids)}


@router.post("/confirm-subscription")
async def confirm_subscription(user: dict = Depends(get_current_user)):
    """Called when a user subscribes - grants referrer their reward"""
    referred_by = user.get("referred_by")

    if not referred_by:
        return {"success": True, "message": "No referrer to reward"}

    # Check if we already granted the reward
    if user.get("referral_reward_granted"):
        return {"success": True, "message": "Reward already granted"}

    # Get the referrer
    referrer = await user_repository.find_by_id(referred_by)
    if not referrer:
        return {"success": True, "message": "Referrer not found"}

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Grant/extend 30-day trial for the referrer
    from datetime import timedelta
    referrer_trial_end = referrer.get("referral_trial_end")
    if referrer_trial_end and referrer_trial_end > now:
        # Extend existing trial by 30 days
        new_referrer_trial = referrer_trial_end + timedelta(days=30)
    else:
        # Start new 30-day trial
        new_referrer_trial = now + timedelta(days=30)

    # Update referrer's trial and referral count
    referral_count = referrer.get("referral_count", 0) + 1

    # Remove from pending rewards
    pending_rewards = referrer.get("pending_referral_rewards", [])
    pending_rewards = [r for r in pending_rewards if r.get("referred_user_id") != user["id"]]

    await user_repository.update_user(referred_by, {
        "referral_trial_end": new_referrer_trial,
        "referral_count": referral_count,
        "pending_referral_rewards": pending_rewards
    })

    # Mark this user's referral reward as granted
    await user_repository.update_user(user["id"], {
        "referral_reward_granted": True
    })

    return {
        "success": True,
        "message": "Referrer rewarded with 30 days free",
        "referrer_new_trial_end": new_referrer_trial.isoformat()
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

    return {
        "referral_count": referral_count,
        "pending_referrals": len(pending_rewards),
        "has_referral_trial": has_referral_trial,
        "referral_trial_end": referral_trial_end,
        "days_remaining": days_remaining
    }
