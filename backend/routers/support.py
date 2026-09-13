"""
Support Tickets — in-app issue reporting and tracking.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import secrets
import uuid
import logging

from dependencies import get_current_user, user_repository
from database.repositories.support_ticket_repository import (
    support_ticket_repository,
    support_ticket_message_repository,
)
from utils.subscription import owner_emails

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["Support"])

VALID_CATEGORIES = {"bug", "feature", "support", "other"}
VALID_STATUSES = {"open", "in_progress", "waiting_on_user", "resolved", "closed"}
VALID_PRIORITIES = {"low", "normal", "high"}
USER_CLOSABLE = {"open", "in_progress", "waiting_on_user"}


class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=3, max_length=300)
    description: str = Field(..., min_length=10, max_length=10000)
    category: str = "support"
    app_version: Optional[str] = None
    platform: Optional[str] = None
    device_info: Optional[str] = None


class TicketMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    admin_notes: Optional[str] = None
    resolution: Optional[str] = None


def _is_admin(user: dict) -> bool:
    return user.get("role") in ("admin", "super_admin")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serialize_ticket(ticket: dict, include_private: bool = False) -> dict:
    out = {
        "id": ticket["id"],
        "ticket_number": ticket["ticket_number"],
        "category": ticket.get("category", "support"),
        "subject": ticket["subject"],
        "description": ticket["description"],
        "status": ticket.get("status", "open"),
        "priority": ticket.get("priority", "normal"),
        "app_version": ticket.get("app_version"),
        "platform": ticket.get("platform"),
        "device_info": ticket.get("device_info"),
        "resolution": ticket.get("resolution"),
        "created_at": _iso(ticket.get("created_at")),
        "updated_at": _iso(ticket.get("updated_at")),
        "resolved_at": _iso(ticket.get("resolved_at")),
    }
    if include_private:
        out["user_id"] = ticket.get("user_id")
        out["admin_notes"] = ticket.get("admin_notes")
    return out


def _serialize_message(msg: dict) -> dict:
    return {
        "id": msg["id"],
        "ticket_id": msg["ticket_id"],
        "user_id": msg["user_id"],
        "is_staff": bool(msg.get("is_staff")),
        "body": msg["body"],
        "created_at": _iso(msg.get("created_at")),
    }


async def _generate_ticket_number() -> str:
    for _ in range(12):
        number = f"LARO-{secrets.token_hex(3).upper()}"
        existing = await support_ticket_repository.find_by_number(number)
        if not existing:
            return number
    return f"LARO-{uuid.uuid4().hex[:8].upper()}"


async def _notify_ticket_created(ticket: dict, user: dict):
    try:
        from services.email import is_email_configured, send_email
        if not is_email_configured():
            return
        number = ticket["ticket_number"]
        subject = f"Ticket {number} received — {ticket['subject'][:60]}"
        html = f"""
        <p>Hi {user.get('name') or 'there'},</p>
        <p>We received your support ticket <strong>{number}</strong>.</p>
        <p><strong>{ticket['subject']}</strong></p>
        <p>Status: open. You can track updates in the app under Settings → My Tickets.</p>
        <p>— Laro Support</p>
        """
        await send_email(user["email"], subject, html)

        owners = owner_emails()
        admin_html = f"""
        <p>New support ticket <strong>{number}</strong> from {user.get('email')}.</p>
        <p>Category: {ticket.get('category')}<br/>Subject: {ticket['subject']}</p>
        <pre>{ticket['description'][:2000]}</pre>
        """
        for owner in owners:
            try:
                await send_email(owner, f"[Laro] New ticket {number}", admin_html)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Ticket email notify failed: {e}")


async def _notify_status_change(ticket: dict, user: dict, old_status: str):
    try:
        from services.email import is_email_configured, send_email
        if not is_email_configured() or not user.get("email"):
            return
        number = ticket["ticket_number"]
        html = f"""
        <p>Hi {user.get('name') or 'there'},</p>
        <p>Your ticket <strong>{number}</strong> status changed from
        <em>{old_status}</em> to <em>{ticket.get('status')}</em>.</p>
        <p>Subject: {ticket['subject']}</p>
        """
        if ticket.get("resolution"):
            html += f"<p>Resolution notes:<br/>{ticket['resolution']}</p>"
        html += "<p>— Laro Support</p>"
        await send_email(
            user["email"],
            f"Ticket {number} update — {ticket.get('status')}",
            html,
        )
    except Exception as e:
        logger.warning(f"Ticket status email failed: {e}")


@router.post("/tickets")
async def create_ticket(
    data: TicketCreate,
    request: Request,
    user: dict = Depends(get_current_user),
):
    category = (data.category or "support").lower().strip()
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Use: {', '.join(sorted(VALID_CATEGORIES))}")

    subject = data.subject.strip()
    description = data.description.strip()
    if len(subject) < 3 or len(description) < 10:
        raise HTTPException(status_code=400, detail="Subject and description are required")

    now = _now()
    ticket_id = str(uuid.uuid4())
    ticket_number = await _generate_ticket_number()
    ticket = {
        "id": ticket_id,
        "ticket_number": ticket_number,
        "user_id": user["id"],
        "category": category,
        "subject": subject,
        "description": description,
        "status": "open",
        "priority": "normal",
        "app_version": (data.app_version or "")[:50] or None,
        "platform": (data.platform or "")[:50] or None,
        "device_info": (data.device_info or "")[:8000] or None,
        "admin_notes": None,
        "resolution": None,
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    }
    await support_ticket_repository.insert(ticket)

    # Seed first message from description for a clean thread view
    await support_ticket_message_repository.insert({
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "user_id": user["id"],
        "is_staff": False,
        "body": description,
        "created_at": now,
    })

    await _notify_ticket_created(ticket, user)
    return _serialize_ticket(ticket)


@router.get("/tickets")
async def list_my_tickets(user: dict = Depends(get_current_user)):
    tickets = await support_ticket_repository.find_by_user(user["id"])
    return {
        "tickets": [_serialize_ticket(t) for t in tickets],
        "total": len(tickets),
    }


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, user: dict = Depends(get_current_user)):
    ticket = await support_ticket_repository.find_by_id(ticket_id)
    if not ticket:
        # allow lookup by ticket number too
        ticket = await support_ticket_repository.find_by_number(ticket_id.upper())
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    is_admin = _is_admin(user)
    if ticket["user_id"] != user["id"] and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    messages = await support_ticket_message_repository.find_by_ticket(ticket["id"])
    reporter = None
    if is_admin:
        reporter = await user_repository.find_by_id(ticket["user_id"])

    payload = _serialize_ticket(ticket, include_private=is_admin)
    payload["messages"] = [_serialize_message(m) for m in messages]
    if reporter:
        payload["user"] = {
            "id": reporter["id"],
            "name": reporter.get("name"),
            "email": reporter.get("email"),
        }
    return payload


@router.post("/tickets/{ticket_id}/messages")
async def add_ticket_message(
    ticket_id: str,
    data: TicketMessageCreate,
    user: dict = Depends(get_current_user),
):
    ticket = await support_ticket_repository.find_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    is_admin = _is_admin(user)
    if ticket["user_id"] != user["id"] and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    if ticket.get("status") in ("resolved", "closed") and not is_admin:
        raise HTTPException(status_code=400, detail="This ticket is closed. Open a new one if needed.")

    body = data.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    now = _now()
    msg = {
        "id": str(uuid.uuid4()),
        "ticket_id": ticket["id"],
        "user_id": user["id"],
        "is_staff": is_admin,
        "body": body,
        "created_at": now,
    }
    await support_ticket_message_repository.insert(msg)

    updates = {"updated_at": now}
    if is_admin and ticket.get("status") == "open":
        updates["status"] = "in_progress"
    elif not is_admin and ticket.get("status") == "waiting_on_user":
        updates["status"] = "open"
    await support_ticket_repository.update({"id": ticket["id"]}, updates)

    # Notify the other party
    try:
        from services.email import is_email_configured, send_email
        if is_email_configured():
            if is_admin:
                owner = await user_repository.find_by_id(ticket["user_id"])
                if owner and owner.get("email"):
                    await send_email(
                        owner["email"],
                        f"Reply on ticket {ticket['ticket_number']}",
                        f"<p>Staff replied to your ticket <strong>{ticket['ticket_number']}</strong>.</p>"
                        f"<p>{body[:1500]}</p><p>Open the app to respond.</p>",
                    )
            else:
                for owner in owner_emails():
                    await send_email(
                        owner,
                        f"[Laro] User reply on {ticket['ticket_number']}",
                        f"<p>{user.get('email')} replied on {ticket['ticket_number']}:</p><pre>{body[:1500]}</pre>",
                    )
    except Exception as e:
        logger.warning(f"Ticket reply email failed: {e}")

    return _serialize_message(msg)


@router.patch("/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    data: TicketUpdate,
    user: dict = Depends(get_current_user),
):
    ticket = await support_ticket_repository.find_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    is_admin = _is_admin(user)
    is_owner = ticket["user_id"] == user["id"]
    if not is_admin and not is_owner:
        raise HTTPException(status_code=403, detail="Not authorized")

    updates = {"updated_at": _now()}
    old_status = ticket.get("status", "open")

    if data.status is not None:
        status = data.status.lower().strip()
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        if not is_admin:
            # Users may only close their own open tickets
            if status != "closed" or old_status not in USER_CLOSABLE:
                raise HTTPException(status_code=403, detail="You can only close your own open tickets")
        updates["status"] = status
        if status in ("resolved", "closed"):
            updates["resolved_at"] = _now()

    if data.priority is not None:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only staff can change priority")
        priority = data.priority.lower().strip()
        if priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail="Invalid priority")
        updates["priority"] = priority

    if data.admin_notes is not None:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only staff can edit admin notes")
        updates["admin_notes"] = data.admin_notes.strip()[:5000]

    if data.resolution is not None:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only staff can set resolution")
        updates["resolution"] = data.resolution.strip()[:5000]

    await support_ticket_repository.update({"id": ticket["id"]}, updates)
    refreshed = await support_ticket_repository.find_by_id(ticket["id"])

    if "status" in updates and updates["status"] != old_status:
        owner = await user_repository.find_by_id(ticket["user_id"])
        if owner:
            await _notify_status_change(refreshed, owner, old_status)

    return _serialize_ticket(refreshed, include_private=is_admin)


@router.get("/admin/tickets")
async def admin_list_tickets(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    tickets = await support_ticket_repository.list_all(status=status, limit=limit, offset=offset)
    total = await support_ticket_repository.count_all(status=status)

    results = []
    for t in tickets:
        item = _serialize_ticket(t, include_private=True)
        reporter = await user_repository.find_by_id(t["user_id"])
        item["user"] = {
            "id": t["user_id"],
            "name": reporter.get("name") if reporter else None,
            "email": reporter.get("email") if reporter else None,
        }
        results.append(item)

    return {"tickets": results, "total": total, "limit": limit, "offset": offset}
