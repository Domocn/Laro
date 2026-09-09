"""
Households Router - Family/household management with live refresh support
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from models import HouseholdCreate, HouseholdResponse, UserResponse, HouseholdInvite, JoinHouseholdRequest
from dependencies import get_current_user, household_repository, user_repository
from database.websocket_manager import ws_manager, EventType
from utils.activity_logger import log_action
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional

router = APIRouter(prefix="/households", tags=["Households"])


@router.post("", response_model=HouseholdResponse)
async def create_household(data: HouseholdCreate, request: Request, user: dict = Depends(get_current_user)):
    if user.get("household_id"):
        raise HTTPException(status_code=400, detail="Already in a household")

    household_id = str(uuid.uuid4())
    household_doc = {
        "id": household_id,
        "name": data.name,
        "owner_id": user["id"],
        "member_ids": [user["id"]],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await household_repository.create(household_doc)
    await user_repository.update_user(user["id"], {"household_id": household_id})

    # Log household creation
    await log_action(
        user, "household_created", request,
        target_type="household",
        target_id=household_id,
        details={"name": data.name}
    )

    return HouseholdResponse(**household_doc)


@router.get("/me", response_model=Optional[HouseholdResponse])
async def get_my_household(user: dict = Depends(get_current_user)):
    if not user.get("household_id"):
        return None
    household = await household_repository.find_by_id(user["household_id"])
    if not household:
        return None
    return HouseholdResponse(**household)


@router.get("/members", response_model=List[UserResponse])
async def get_household_members(user: dict = Depends(get_current_user)):
    if not user.get("household_id"):
        return []
    household = await household_repository.find_by_id(user["household_id"])
    if not household:
        return []
    members = await user_repository.find_by_ids(household.get("member_ids", []))
    return [UserResponse(**m) for m in members]


@router.post("/invite")
async def invite_to_household(data: HouseholdInvite, user: dict = Depends(get_current_user)):
    """Send a pending household invite — invitee must accept before joining."""
    if not user.get("household_id"):
        raise HTTPException(status_code=400, detail="You must be in a household")

    invitee = await user_repository.find_by_email(data.email)
    if not invitee:
        raise HTTPException(status_code=404, detail="User not found")
    if invitee["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot invite yourself")
    if invitee.get("household_id"):
        raise HTTPException(status_code=400, detail="User already in a household")

    household = await household_repository.find_by_id(user["household_id"])
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    from utils.free_limits import assert_can_add_household_member
    await assert_can_add_household_member(user, household)

    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id FROM household_invites
            WHERE household_id = $1 AND invitee_id = $2 AND status = 'pending'
              AND expires_at > NOW()
            """,
            user["household_id"],
            invitee["id"],
        )
        if existing:
            raise HTTPException(status_code=400, detail="Invite already pending for this user")

        invite_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires = now + timedelta(days=7)
        await conn.execute(
            """
            INSERT INTO household_invites
                (id, household_id, inviter_id, invitee_id, status, created_at, expires_at)
            VALUES ($1, $2, $3, $4, 'pending', $5, $6)
            """,
            invite_id,
            user["household_id"],
            user["id"],
            invitee["id"],
            now,
            expires,
        )

    try:
        from services.notifications import notify_user, NotificationType
        await notify_user(
            user_id=invitee["id"],
            notification_type=NotificationType.HOUSEHOLD_INVITE,
            data={
                "inviter_name": user.get("name", "Someone"),
                "household_name": household.get("name", "a household"),
                "invite_id": invite_id,
            },
        )
    except Exception:
        pass

    return {
        "message": "Invite sent — they must accept before joining",
        "invite_id": invite_id,
        "pending": True,
    }


@router.get("/invites")
async def list_my_household_invites(user: dict = Depends(get_current_user)):
    """List pending household invites for the current user."""
    from database.connection import get_db, dict_from_row

    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT hi.id, hi.household_id, hi.inviter_id, hi.created_at, hi.expires_at,
                   h.name AS household_name, u.name AS inviter_name, u.email AS inviter_email
            FROM household_invites hi
            JOIN households h ON h.id = hi.household_id
            JOIN users u ON u.id = hi.inviter_id
            WHERE hi.invitee_id = $1 AND hi.status = 'pending' AND hi.expires_at > NOW()
            ORDER BY hi.created_at DESC
            """,
            user["id"],
        )
    invites = []
    for row in rows:
        d = dict_from_row(row)
        for key in ("created_at", "expires_at"):
            if d.get(key) is not None and hasattr(d[key], "isoformat"):
                d[key] = d[key].isoformat()
        invites.append(d)
    return {"invites": invites, "total": len(invites)}


@router.post("/invites/{invite_id}/accept")
async def accept_household_invite(
    invite_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Accept a pending household invite."""
    if user.get("household_id"):
        raise HTTPException(status_code=400, detail="Already in a household")

    from database.connection import get_db, dict_from_row

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM household_invites
            WHERE id = $1 AND invitee_id = $2 AND status = 'pending'
            """,
            invite_id,
            user["id"],
        )
        if not row:
            raise HTTPException(status_code=404, detail="Invite not found")
        invite = dict_from_row(row)
        expires = invite.get("expires_at")
        if expires is not None:
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            if isinstance(expires, str):
                expires = datetime.fromisoformat(expires.replace("Z", "+00:00")).replace(tzinfo=None)
            elif getattr(expires, "tzinfo", None) is not None:
                expires = expires.replace(tzinfo=None)
            if now_naive > expires:
                await conn.execute(
                    "UPDATE household_invites SET status = 'expired' WHERE id = $1",
                    invite_id,
                )
                raise HTTPException(status_code=400, detail="Invite has expired")

        household = await household_repository.find_by_id(invite["household_id"])
        if not household:
            raise HTTPException(status_code=404, detail="Household no longer exists")

        owner = await user_repository.find_by_id(household.get("owner_id"))
        from utils.free_limits import assert_can_add_household_member
        await assert_can_add_household_member(owner or user, household)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await conn.execute(
            """
            UPDATE household_invites
            SET status = 'accepted', responded_at = $1
            WHERE id = $2
            """,
            now,
            invite_id,
        )

    await user_repository.update_user(user["id"], {"household_id": invite["household_id"]})
    await household_repository.add_member(invite["household_id"], user["id"])

    await log_action(
        user,
        "household_joined",
        request,
        target_type="household",
        target_id=invite["household_id"],
        details={"household_name": household.get("name"), "via": "invite"},
    )

    await ws_manager.broadcast_to_household(
        household_id=invite["household_id"],
        event_type=EventType.HOUSEHOLD_MEMBER_JOINED,
        data={"user_id": user["id"], "name": user["name"], "email": user["email"]},
    )

    try:
        from services.notifications import notify_user, NotificationType
        await notify_user(
            user_id=invite["inviter_id"],
            notification_type=NotificationType.HOUSEHOLD_JOINED,
            data={"member_name": user.get("name", "Someone")},
        )
    except Exception:
        pass

    return {
        "message": f"Joined household: {household.get('name')}",
        "household_id": invite["household_id"],
    }


@router.post("/invites/{invite_id}/decline")
async def decline_household_invite(invite_id: str, user: dict = Depends(get_current_user)):
    """Decline a pending household invite."""
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id FROM household_invites
            WHERE id = $1 AND invitee_id = $2 AND status = 'pending'
            """,
            invite_id,
            user["id"],
        )
        if not row:
            raise HTTPException(status_code=404, detail="Invite not found")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await conn.execute(
            """
            UPDATE household_invites
            SET status = 'declined', responded_at = $1
            WHERE id = $2
            """,
            now,
            invite_id,
        )
    return {"message": "Invite declined"}


@router.post("/leave")
async def leave_household(request: Request, user: dict = Depends(get_current_user)):
    if not user.get("household_id"):
        raise HTTPException(status_code=400, detail="Not in a household")

    household = await household_repository.find_by_id(user["household_id"])
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    if household["owner_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Owner cannot leave. Transfer ownership first.")

    household_id = user["household_id"]
    household_name = household.get("name", "Unknown")

    await user_repository.update_user(user["id"], {"household_id": None})
    await household_repository.remove_member(household_id, user["id"])

    # Log household leave
    await log_action(
        user, "household_left", request,
        target_type="household",
        target_id=household_id,
        details={"household_name": household_name}
    )

    # Broadcast member left event
    await ws_manager.broadcast_to_household(
        household_id=household_id,
        event_type=EventType.HOUSEHOLD_MEMBER_LEFT,
        data={"user_id": user["id"], "name": user["name"]}
    )

    return {"message": "Left household"}


@router.post("/join-code")
async def generate_join_code(user: dict = Depends(get_current_user)):
    """Generate a join code for the household"""
    if not user.get("household_id"):
        raise HTTPException(status_code=400, detail="Not in a household")

    household = await household_repository.find_by_id(user["household_id"])
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    # Only owner can generate join codes
    if household["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Only household owner can generate join codes")

    # Generate 8-character code
    join_code = secrets.token_urlsafe(6).upper()[:8]
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    await household_repository.set_join_code(user["household_id"], join_code, expires)

    return {"join_code": join_code, "expires": expires}


@router.delete("/join-code")
async def revoke_join_code(user: dict = Depends(get_current_user)):
    """Revoke the current join code"""
    if not user.get("household_id"):
        raise HTTPException(status_code=400, detail="Not in a household")

    household = await household_repository.find_by_id(user["household_id"])
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    if household["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Only household owner can revoke join codes")

    await household_repository.clear_join_code(user["household_id"])

    return {"message": "Join code revoked"}


@router.post("/join")
async def join_with_code(data: JoinHouseholdRequest, request: Request, user: dict = Depends(get_current_user)):
    """Join a household using a join code"""
    if user.get("household_id"):
        raise HTTPException(status_code=400, detail="Already in a household")

    # Find household with this join code
    household = await household_repository.find_by_join_code(data.join_code.upper())
    if not household:
        raise HTTPException(status_code=404, detail="Invalid join code")

    owner = await user_repository.find_by_id(household.get("owner_id"))
    from utils.free_limits import assert_can_add_household_member
    await assert_can_add_household_member(owner or user, household)

    # Check if code is expired
    if household.get("join_code_expires"):
        expires = datetime.fromisoformat(household["join_code_expires"].replace('Z', '+00:00'))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(status_code=400, detail="Join code has expired")

    # Add user to household
    await user_repository.update_user(user["id"], {"household_id": household["id"]})
    await household_repository.add_member(household["id"], user["id"])

    # Log household join
    await log_action(
        user, "household_joined", request,
        target_type="household",
        target_id=household["id"],
        details={"household_name": household["name"]}
    )

    # Broadcast member joined event
    await ws_manager.broadcast_to_household(
        household_id=household["id"],
        event_type=EventType.HOUSEHOLD_MEMBER_JOINED,
        data={"user_id": user["id"], "name": user["name"], "email": user["email"]}
    )

    # Update the user's WebSocket connection with the new household
    # This will be handled on the client side by reconnecting

    return {"message": f"Joined household: {household['name']}", "household_id": household["id"]}


@router.delete("")
async def delete_household(request: Request, user: dict = Depends(get_current_user)):
    """Delete household (owner only)"""
    if not user.get("household_id"):
        raise HTTPException(status_code=400, detail="Not in a household")

    household = await household_repository.find_by_id(user["household_id"])
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    if household["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Only the owner can delete the household")

    household_id = user["household_id"]
    household_name = household.get("name", "Unknown")
    member_count = len(household.get("member_ids", []))

    # Remove household_id from all members
    for member_id in household.get("member_ids", []):
        await user_repository.update_user(member_id, {"household_id": None})

    # Delete the household
    await household_repository.delete_household(household_id)

    # Log household deletion
    await log_action(
        user, "household_deleted", request,
        target_type="household",
        target_id=household_id,
        details={"household_name": household_name, "member_count": member_count}
    )

    # Broadcast household deleted event
    await ws_manager.broadcast_to_household(
        household_id=household_id,
        event_type=EventType.HOUSEHOLD_DELETED,
        data={"household_id": household_id}
    )

    return {"message": "Household deleted"}
