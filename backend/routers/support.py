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
import os
import re
import json
from html import escape as _html_escape

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


class AdminOutboundMessage(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    subject: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1, max_length=10000)
    create_ticket: bool = True


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
        out["reporter_email"] = ticket.get("reporter_email")
        out["reporter_name"] = ticket.get("reporter_name")
        out["admin_notes"] = ticket.get("admin_notes")
        out["source"] = "email" if not ticket.get("user_id") else "app"
    return out


def _serialize_message(msg: dict) -> dict:
    return {
        "id": msg["id"],
        "ticket_id": msg["ticket_id"],
        "user_id": msg.get("user_id"),
        "reporter_email": msg.get("reporter_email"),
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


async def _notify_ticket_created(ticket: dict, user: Optional[dict] = None):
    try:
        from services.email import (
            is_email_configured,
            send_email,
            send_support_email,
            get_base_template,
            SUPPORT_NOTIFY_OWNERS,
        )
        if not is_email_configured():
            return
        number = ticket["ticket_number"]
        user = user or {}
        # Recipient: the app user's address, or the external sender for email-originated tickets.
        recipient = user.get("email") or ticket.get("reporter_email")
        name = user.get("name") or ticket.get("reporter_name") or "there"

        if recipient:
            subject = f"Ticket {number} received: {ticket['subject'][:60]}"
            inner = f"""
            <p>Hi {name},</p>
            <p>We received your support ticket <strong>{number}</strong>.</p>
            <p><strong>{ticket['subject']}</strong></p>
            <p>Status: open. Reply to this email to add to your ticket, or track it in the app under Settings &rsaquo; My Tickets.</p>
            <p>Thanks,<br/>Laro Support</p>
            """
            # send_support_email sets Reply-To to the ticket alias so replies thread back.
            await send_support_email(recipient, subject, get_base_template(inner), ticket_number=number)

        if SUPPORT_NOTIFY_OWNERS:
            reporter = recipient or "unknown sender"
            admin_html = f"""
            <p>New support ticket <strong>{number}</strong> from {reporter}.</p>
            <p>Category: {ticket.get('category')}<br/>Subject: {ticket['subject']}</p>
            <pre>{ticket['description'][:2000]}</pre>
            <p>Open Admin → Tickets in Laro to reply.</p>
            """
            for owner in owner_emails():
                try:
                    await send_email(owner, f"[Laro] New ticket {number}", admin_html)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Ticket email notify failed: {e}")


async def _notify_status_change(ticket: dict, user: dict, old_status: str):
    try:
        from services.email import is_email_configured, send_support_email, get_base_template
        if not is_email_configured() or not user.get("email"):
            return
        number = ticket["ticket_number"]
        inner = f"""
        <p>Hi {user.get('name') or 'there'},</p>
        <p>Your ticket <strong>{number}</strong> status changed from
        <em>{old_status}</em> to <em>{ticket.get('status')}</em>.</p>
        <p>Subject: {ticket['subject']}</p>
        """
        if ticket.get("resolution"):
            inner += f"<p>Resolution notes:<br/>{ticket['resolution']}</p>"
        inner += "<p>Thanks,<br/>Laro Support</p>"
        await send_support_email(
            user["email"],
            f"Ticket {number} update: {ticket.get('status')}",
            get_base_template(inner),
            ticket_number=number,
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
        "reporter_email": user.get("email"),
        "reporter_name": user.get("name"),
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
    if is_admin and ticket.get("user_id"):
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
        from services.email import is_email_configured, send_email, send_support_email, get_base_template
        if is_email_configured():
            number = ticket["ticket_number"]
            if is_admin:
                # Reach the reporter: an app user's address, or the external email sender.
                recipient = None
                if ticket.get("user_id"):
                    owner = await user_repository.find_by_id(ticket["user_id"])
                    recipient = owner.get("email") if owner else None
                recipient = recipient or ticket.get("reporter_email")
                if recipient:
                    inner = (
                        f"<p>Support replied to your ticket <strong>{number}</strong>.</p>"
                        f"<p>{_nl2br(body[:1500])}</p>"
                        f"<p>Reply to this email or open the app to respond.</p>"
                    )
                    await send_support_email(
                        recipient,
                        f"Reply on ticket {number}",
                        get_base_template(inner),
                        ticket_number=number,
                    )
            else:
                for owner in owner_emails():
                    await send_email(
                        owner,
                        f"[Laro] User reply on {number}",
                        f"<p>{user.get('email')} replied on {number}:</p><pre>{body[:1500]}</pre>",
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
        recipient = None
        if ticket.get("user_id"):
            recipient = await user_repository.find_by_id(ticket["user_id"])
        if not recipient and ticket.get("reporter_email"):
            recipient = {"email": ticket["reporter_email"], "name": ticket.get("reporter_name")}
        if recipient:
            await _notify_status_change(refreshed, recipient, old_status)

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
        reporter = await user_repository.find_by_id(t["user_id"]) if t.get("user_id") else None
        item["user"] = {
            "id": t.get("user_id"),
            "name": (reporter.get("name") if reporter else None) or t.get("reporter_name"),
            "email": (reporter.get("email") if reporter else None) or t.get("reporter_email"),
        }
        results.append(item)

    return {"tickets": results, "total": total, "limit": limit, "offset": offset}


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _nl2br(text: str) -> str:
    """HTML-escape user/admin text and turn newlines into <br> for email bodies."""
    return _html_escape(text or "").replace("\n", "<br>")


@router.post("/admin/message")
async def admin_send_message(
    data: AdminOutboundMessage,
    user: dict = Depends(get_current_user),
):
    """Staff-initiated email to any address (no prior ticket required).

    Opens a ticket and sends the first message, so the recipient's reply threads
    back in like any other ticket.
    """
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")

    to_addr = data.email.strip().lower()
    if not _EMAIL_RE.match(to_addr):
        raise HTTPException(status_code=400, detail="Invalid email address")

    subject = data.subject.strip()
    body = data.body.strip()
    if not subject or not body:
        raise HTTPException(status_code=400, detail="Subject and message are required")

    from services.email import is_email_configured, send_support_email, get_base_template
    inner = "<p>" + _nl2br(body) + "</p><p>Reply to this email to respond.</p>"

    # No ticket: just send a one-off email. Reply-To is the plain support address,
    # so if they DO reply, the inbound webhook opens a fresh ticket then.
    if not data.create_ticket:
        email_sent = False
        try:
            if is_email_configured():
                email_sent = await send_support_email(to_addr, subject, get_base_template(inner))
        except Exception as e:
            logger.warning(f"Outbound email (no ticket) failed: {e}")
        return {"ticket_created": False, "email_sent": email_sent}

    existing = await user_repository.find_by_email(to_addr)
    now = _now()
    ticket_id = str(uuid.uuid4())
    number = await _generate_ticket_number()
    ticket = {
        "id": ticket_id,
        "ticket_number": number,
        "user_id": existing["id"] if existing else None,
        "reporter_email": to_addr,
        "reporter_name": existing.get("name") if existing else None,
        "category": "support",
        "subject": subject[:300],
        "description": body[:10000],
        "status": "waiting_on_user",
        "priority": "normal",
        "app_version": None,
        "platform": "email-outbound",
        "device_info": None,
        "admin_notes": f"Opened by {user.get('email')} (outbound)",
        "resolution": None,
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    }
    await support_ticket_repository.insert(ticket)
    await support_ticket_message_repository.insert({
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "user_id": user["id"],
        "reporter_email": None,
        "is_staff": True,
        "body": body,
        "created_at": now,
    })

    email_sent = False
    try:
        if is_email_configured():
            # ticket_number sets Reply-To to the ticket alias so replies thread back.
            email_sent = await send_support_email(to_addr, subject, get_base_template(inner), ticket_number=number)
    except Exception as e:
        logger.warning(f"Outbound support email failed: {e}")

    payload = _serialize_ticket(ticket, include_private=True)
    payload["ticket_created"] = True
    payload["email_sent"] = email_sent
    return payload


# =============================================================================
# INBOUND EMAIL → TICKETS (Resend Receiving webhook)
# =============================================================================

# Matches a plus-address ticket token, e.g. app+LARO-AB12CD@inbound.laro.food
_TICKET_PLUS_RE = re.compile(r"\+((?:LARO-)?[A-Za-z0-9]+)@", re.IGNORECASE)


def _parse_email_address(raw: str) -> str:
    raw = (raw or "").strip()
    if "<" in raw and ">" in raw:
        m = re.search(r"<([^>]+)>", raw)
        if m:
            return m.group(1).strip().lower()
    return raw.lower()


def _parse_display_name(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    if "<" in raw:
        name = raw.split("<", 1)[0].strip().strip('"')
        return name or None
    return None


def _addresses_from_field(field) -> List[str]:
    """Normalise a Resend recipient/sender field to a list of raw address strings."""
    out: List[str] = []
    if not field:
        return out
    if isinstance(field, str):
        return [field]
    if isinstance(field, dict):
        field = [field]
    for item in field:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            out.append(item.get("email") or item.get("address") or "")
    return [a for a in out if a]


def _ticket_number_from_recipients(recipients: list) -> Optional[str]:
    for raw in recipients or []:
        addr = _parse_email_address(str(raw))
        m = _TICKET_PLUS_RE.search(addr)
        if not m:
            continue
        token = m.group(1).upper()
        return token if token.startswith("LARO-") else f"LARO-{token}"
    return None


def _plain_body_from_received(email: dict) -> str:
    text = (email.get("text") or "").strip()
    if text:
        return text[:8000]
    html = email.get("html") or ""
    if not html:
        return ""
    stripped = re.sub(r"<[^>]+>", " ", html)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped[:8000]


def _is_automated_sender(addr: str) -> bool:
    """Skip bounces, auto-responders and our own outbound so we don't loop or file junk."""
    addr = (addr or "").lower()
    if not addr or "@" not in addr:
        return True
    local = addr.split("@", 1)[0]
    if local in ("mailer-daemon", "postmaster", "no-reply", "noreply", "donotreply", "do-not-reply", "bounce", "bounces"):
        return True
    try:
        from services.email import SUPPORT_FROM_EMAIL, SMTP_FROM_EMAIL
        if addr in (SUPPORT_FROM_EMAIL.lower(), SMTP_FROM_EMAIL.lower()):
            return True
    except Exception:
        pass
    return False


# Cold sales / marketing senders that should never become tickets (no ticket, no
# auto-reply, no owner ping). Entries are full addresses or "@domain" (matches the
# domain and its subdomains). Extend in production with SUPPORT_BLOCKED_SENDERS
# (comma-separated) without a code change.
_DEFAULT_BLOCKED_SENDERS = ("@appfast.com",)


def _is_blocked_sender(addr: str) -> bool:
    addr = (addr or "").strip().lower()
    if "@" not in addr:
        return False
    domain = addr.split("@", 1)[1]
    extra = [e.strip().lower() for e in os.getenv("SUPPORT_BLOCKED_SENDERS", "").split(",") if e.strip()]
    for entry in (*_DEFAULT_BLOCKED_SENDERS, *extra):
        if entry.startswith("@"):
            d = entry[1:]
            if domain == d or domain.endswith("." + d):
                return True
        elif addr == entry:
            return True
    return False


async def _create_ticket_from_email(from_addr: str, from_name: Optional[str], subject: str, body: str) -> dict:
    """Create a new ticket from a cold inbound email (registered user or stranger)."""
    existing_user = await user_repository.find_by_email(from_addr)
    now = _now()
    ticket_id = str(uuid.uuid4())
    ticket_number = await _generate_ticket_number()
    ticket = {
        "id": ticket_id,
        "ticket_number": ticket_number,
        "user_id": existing_user["id"] if existing_user else None,
        "reporter_email": from_addr,
        "reporter_name": (existing_user.get("name") if existing_user else None) or from_name,
        "category": "support",
        "subject": (subject or "Support request")[:300],
        "description": body[:10000],
        "status": "open",
        "priority": "normal",
        "app_version": None,
        "platform": "email",
        "device_info": None,
        "admin_notes": None,
        "resolution": None,
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    }
    await support_ticket_repository.insert(ticket)
    await support_ticket_message_repository.insert({
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "user_id": existing_user["id"] if existing_user else None,
        "reporter_email": from_addr,
        "is_staff": False,
        "body": body[:8000],
        "created_at": now,
    })
    # Sends the auto-reply to the sender and the "new ticket" notice to owners.
    await _notify_ticket_created(ticket, existing_user)
    return ticket


@router.post("/inbound/resend")
async def resend_support_inbound(request: Request):
    """
    Resend `email.received` webhook.

    - Mail with a ticket token in the recipient (app+LARO-xxxx@) → appended to that ticket.
    - Any other inbound mail → a NEW ticket, with an auto-reply to the sender and an
      owner notification. This is how every email to the support address becomes a ticket.
    """
    raw = await request.body()

    # Verify the webhook is genuinely from Resend (svix signatures).
    secret = os.getenv("RESEND_WEBHOOK_SECRET", "").strip()
    if secret:
        try:
            from svix.webhooks import Webhook
            Webhook(secret).verify(
                raw.decode("utf-8"),
                {
                    "svix-id": request.headers.get("svix-id", ""),
                    "svix-timestamp": request.headers.get("svix-timestamp", ""),
                    "svix-signature": request.headers.get("svix-signature", ""),
                },
            )
        except Exception as exc:
            logger.warning("Resend inbound webhook verification failed: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid webhook signature") from exc
    elif os.getenv("ALLOW_INSECURE_WEBHOOKS", "false").lower() != "true":
        raise HTTPException(status_code=503, detail="RESEND_WEBHOOK_SECRET not configured")

    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    if event.get("type") != "email.received":
        return {"ok": True, "ignored": event.get("type")}

    data = event.get("data") or {}
    email_id = data.get("email_id") or data.get("id")

    from services.email import fetch_resend_received_email

    received = await fetch_resend_received_email(email_id) if email_id else None
    # Fall back to the webhook payload if the fetch API isn't available.
    src = received or data
    if not src:
        raise HTTPException(status_code=502, detail="Could not load received email")

    recipients = _addresses_from_field(src.get("to")) or _addresses_from_field(data.get("to"))
    from_raw = None
    for f in (src.get("from"), data.get("from")):
        if f:
            from_raw = f if isinstance(f, str) else _addresses_from_field(f)[:1]
            from_raw = from_raw[0] if isinstance(from_raw, list) and from_raw else (f if isinstance(f, str) else None)
            if from_raw:
                break
    from_addr = _parse_email_address(str(from_raw or ""))
    from_name = _parse_display_name(str(from_raw or ""))
    subject = (src.get("subject") or data.get("subject") or "").strip()
    # Take the body from whichever source actually has content (fetch can lag).
    body = _plain_body_from_received(received or {}) or _plain_body_from_received(data or {})

    if _is_automated_sender(from_addr):
        logger.info("Inbound email ignored (automated/own sender): %s", from_addr)
        return {"ok": True, "ignored": "automated_sender"}
    if _is_blocked_sender(from_addr):
        logger.info("Inbound email ignored (blocked sender): %s", from_addr)
        return {"ok": True, "ignored": "blocked_sender"}
    if not body and not subject:
        return {"ok": True, "ignored": "empty_message"}

    ticket_number = _ticket_number_from_recipients(recipients)

    # No ticket token → brand-new ticket from this email.
    if not ticket_number:
        ticket = await _create_ticket_from_email(from_addr, from_name, subject, body or subject)
        return {"ok": True, "created_ticket": ticket["ticket_number"]}

    # Token present → thread the reply onto the existing ticket.
    ticket = await support_ticket_repository.find_by_number(ticket_number.upper())
    if not ticket:
        logger.warning("Inbound email for unknown ticket %s — creating new", ticket_number)
        ticket = await _create_ticket_from_email(from_addr, from_name, subject, body or subject)
        return {"ok": True, "created_ticket": ticket["ticket_number"]}

    if not body:
        # Don't silently drop a reply to a real ticket — record it and log loudly.
        logger.warning("Inbound reply to %s had no extractable body; using subject", ticket_number)
        body = subject or "(reply had no text content)"

    # Authorise the sender: the ticket's reporter, or a staff admin account.
    reporter_email = (ticket.get("reporter_email") or "").lower()
    if not reporter_email and ticket.get("user_id"):
        reporter = await user_repository.find_by_id(ticket["user_id"])
        reporter_email = (reporter or {}).get("email", "").lower()
    sender_user = await user_repository.find_by_email(from_addr)
    is_reporter = bool(reporter_email) and from_addr == reporter_email
    # Reporter precedence: a reply from the ticket's own reporter is always the
    # reporter, even if that address also happens to be an admin account.
    is_staff = (not is_reporter) and bool(sender_user) and _is_admin(sender_user)

    if not is_staff and not is_reporter:
        logger.warning("Inbound reply rejected (sender %s not ticket owner or staff)", from_addr)
        return {"ok": True, "ignored": "unauthorized_sender"}

    now = _now()
    await support_ticket_message_repository.insert({
        "id": str(uuid.uuid4()),
        "ticket_id": ticket["id"],
        "user_id": (sender_user or {}).get("id") if (is_staff or sender_user) else ticket.get("user_id"),
        "reporter_email": from_addr,
        "is_staff": is_staff,
        "body": body,
        "created_at": now,
    })

    updates = {"updated_at": now}
    if is_staff:
        updates["status"] = "waiting_on_user"
    elif ticket.get("status") in ("waiting_on_user", "resolved", "closed"):
        # A reply from the reporter reopens a dormant/closed ticket so it resurfaces.
        updates["status"] = "open"
    await support_ticket_repository.update({"id": ticket["id"]}, updates)

    # Let you know a reply landed.
    if not is_staff:
        try:
            from services.email import is_email_configured, send_email, SUPPORT_NOTIFY_OWNERS
            if is_email_configured() and SUPPORT_NOTIFY_OWNERS:
                for owner in owner_emails():
                    try:
                        await send_email(
                            owner,
                            f"[Laro] Reply on {ticket['ticket_number']}",
                            f"<p>{from_addr} replied on {ticket['ticket_number']}:</p><pre>{body[:1500]}</pre>",
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Inbound reply owner-notify failed: {e}")

    return {"ok": True, "ticket_number": ticket["ticket_number"], "is_staff": is_staff}
