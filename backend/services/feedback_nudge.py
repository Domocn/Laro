"""'Haven't seen you for a while' feedback emails.

A daily job emails people who have not used Laro for a few days, asking what is
getting in the way. Answers land in feedback_responses (one tap on a reason, with
an optional comment) or as a support ticket if they simply reply to the email.

Safety:
- Off unless FEEDBACK_EMAILS_ENABLED=true. When off, the job only logs who it
  WOULD email (dry run).
- At most FEEDBACK_EMAIL_MAX_PER_USER emails per person ever (default 2), at least
  FEEDBACK_EMAIL_GAP_DAYS apart (default 45), never to opted-out or deleted users,
  never to the owners, at most FEEDBACK_EMAIL_DAILY_LIMIT per run.
- Every link opens a page first; nothing is recorded until the person presses a
  button there (mail scanners pre-open links).
"""
import base64
import hashlib
import hmac
import html
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from config import settings
from database.connection import get_db
from services.email import (
    APP_NAME,
    LOGO_URL,
    SUPPORT_FROM_EMAIL,
    send_email,
    support_inbound_domain,
    support_local_part,
)

logger = logging.getLogger(__name__)

ENABLED = os.environ.get("FEEDBACK_EMAILS_ENABLED", "false").lower() == "true"
INACTIVE_DAYS = int(os.environ.get("FEEDBACK_EMAIL_INACTIVE_DAYS", "5"))
MAX_INACTIVE_DAYS = int(os.environ.get("FEEDBACK_EMAIL_MAX_INACTIVE_DAYS", "90"))
GAP_DAYS = int(os.environ.get("FEEDBACK_EMAIL_GAP_DAYS", "45"))
MAX_PER_USER = int(os.environ.get("FEEDBACK_EMAIL_MAX_PER_USER", "2"))
DAILY_LIMIT = int(os.environ.get("FEEDBACK_EMAIL_DAILY_LIMIT", "25"))
PUBLIC_URL = os.environ.get("LARO_PUBLIC_URL", "https://laro.food").rstrip("/")

# (key, label) shown as buttons in the email. Keys are stored in feedback_responses.reason.
REASONS = [
    ("forgot", "I forgot about it"),
    ("broken", "Something didn't work"),
    ("missing", "It's missing something I need"),
    ("effort", "Too much effort to set up"),
    ("other_app", "I use something else"),
    ("other", "Something else"),
]
REASON_LABELS = dict(REASONS)


# Our own demo/test accounts. Never send them marketing or feedback emails.
INTERNAL_EMAIL_DOMAINS = {
    d.strip().lower().lstrip('@')
    for d in os.environ.get('LARO_INTERNAL_EMAIL_DOMAINS', 'laro.food').split(',')
    if d.strip()
}


def is_internal_email(email: Optional[str]) -> bool:
    domain = (email or '').rsplit('@', 1)[-1].strip().lower()
    return domain in INTERNAL_EMAIL_DOMAINS


def _owner_emails() -> set:
    raw = os.environ.get("LARO_OWNER_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


# ---------------------------------------------------------------- tokens
def make_token(user_id: str, purpose: str) -> str:
    """URL-safe signed token: base64(user_id).signature. No expiry (unsubscribe must keep working)."""
    uid = base64.urlsafe_b64encode(user_id.encode()).decode().rstrip("=")
    sig = hmac.new(settings.jwt_secret.encode(), f"{purpose}:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{uid}.{sig}"


def read_token(token: str, purpose: str) -> Optional[str]:
    try:
        uid_part, sig = token.split(".", 1)
        user_id = base64.urlsafe_b64decode(uid_part + "=" * (-len(uid_part) % 4)).decode()
    except Exception:
        return None
    expected = hmac.new(settings.jwt_secret.encode(), f"{purpose}:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]
    return user_id if hmac.compare_digest(sig, expected) else None


# ---------------------------------------------------------------- win-back trial
# People whose trial or subscription has FULLY run out get free Pro with the email,
# once per person ever. Never-paid free users and anyone currently Pro do not.
WINBACK_DAYS = int(os.environ.get("FEEDBACK_WINBACK_TRIAL_DAYS", "14"))


def winback_eligible(user: dict) -> bool:
    from utils.subscription import is_premium_user

    if WINBACK_DAYS <= 0 or user.get("winback_trial_granted_at"):
        return False
    if is_premium_user(user):
        return False
    status = (user.get("subscription_status") or "free").lower()
    had_pro = status in ("trial", "premium") or bool(user.get("referral_trial_end")) or bool(user.get("subscription_expires"))
    return had_pro


async def grant_winback(user_id: str, until: datetime) -> None:
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET subscription_status = 'trial', subscription_source = 'winback', "
            "subscription_expires = $1, winback_trial_granted_at = $2 WHERE id = $3",
            until.replace(tzinfo=None), datetime.now(timezone.utc).replace(tzinfo=None), user_id,
        )


# ---------------------------------------------------------------- email
def build_email(user: dict, winback_until: Optional[datetime] = None) -> tuple:
    """Return (subject, html, text) for one user."""
    first = html.escape(((user.get("name") or "").split(" ") or [""])[0]) or "there"
    gift_html = gift_text = ""
    if winback_until:
        day = f"{winback_until.day} {winback_until.strftime('%B')}"
        gift_html = (f'<p style="font-size:16px;background:#eef4f8;border-radius:12px;padding:12px 14px">'
                     f'We\'ve also switched <b>Laro Pro back on for you, free for {WINBACK_DAYS} days</b> '
                     f'(until {day}). No code and no card needed.</p>')
        gift_text = f"We've also switched Laro Pro back on for you, free for {WINBACK_DAYS} days (until {day}). No code and no card needed.\n\n"
    fb = make_token(user["id"], "feedback")
    unsub = make_token(user["id"], "unsubscribe")
    buttons = "".join(
        f'<a href="{PUBLIC_URL}/api/feedback/nudge?t={fb}&r={key}" '
        f'style="display:block;margin:8px 0;padding:12px 16px;border:1px solid #d1d5db;border-radius:12px;'
        f'color:#1f2937;text-decoration:none;font-size:15px">{html.escape(label)}</a>'
        for key, label in REASONS
    )
    unsub_url = f"{PUBLIC_URL}/api/feedback/unsubscribe?t={unsub}"
    subject = "Quick question about Laro"
    body = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#1f2937">
  <img src="{LOGO_URL}" alt="{APP_NAME}" style="height:36px;margin-bottom:16px">
  <p style="font-size:16px">Hi {first},</p>
  <p style="font-size:16px">We haven't seen you in Laro for a few days, and that's completely fine.
  We're a small team and we'd really like to know: <b>what's stopping you from using Laro more often?</b></p>
  {gift_html}
  <p style="font-size:15px;color:#4b5563">One tap is plenty:</p>
  {buttons}
  <p style="font-size:15px;color:#4b5563;margin-top:20px">Or just reply to this email. A real person reads every reply.</p>
  <p style="font-size:15px">Thanks,<br>The Laro team</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
  <p style="font-size:12px;color:#9ca3af">You're getting this because you have a Laro account. We send this at most twice.
  <a href="{unsub_url}" style="color:#9ca3af">Don't email me about this again</a>.</p>
</div>"""
    text = (
        f"Hi {first},\n\nWe haven't seen you in Laro for a few days, and that's completely fine. "
        "What's stopping you from using Laro more often?\n\n"
        + gift_text
        + "\n".join(f"- {label}: {PUBLIC_URL}/api/feedback/nudge?t={fb}&r={key}" for key, label in REASONS)
        + "\n\nOr just reply to this email. A real person reads every reply.\n\nThanks,\nThe Laro team\n\n"
        f"Don't email me about this again: {unsub_url}\n"
    )
    return subject, body, text


def reply_to_address() -> str:
    # A reply with no ticket token becomes a new support ticket (routers/support.py inbound).
    return f"{support_local_part()}@{support_inbound_domain()}"


# ---------------------------------------------------------------- selection + sending
async def find_candidates(limit: int = DAILY_LIMIT) -> List[dict]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *,
                   COALESCE(last_seen_at, last_login) AS seen,
                   COALESCE(feedback_email_count, 0) AS sent_count,
                   feedback_email_sent_at
            FROM users
            WHERE deleted_at IS NULL
              AND email LIKE '%@%'
              AND COALESCE(feedback_emails_opt_out, FALSE) = FALSE
              AND created_at < $1
              AND COALESCE(last_seen_at, last_login) IS NOT NULL
              AND COALESCE(last_seen_at, last_login) < $1
              AND COALESCE(last_seen_at, last_login) > $2
              AND COALESCE(feedback_email_count, 0) < $3
              AND (feedback_email_sent_at IS NULL OR feedback_email_sent_at < $4)
            ORDER BY COALESCE(last_seen_at, last_login) ASC
            LIMIT $5
            """,
            now - timedelta(days=INACTIVE_DAYS),
            now - timedelta(days=MAX_INACTIVE_DAYS),
            MAX_PER_USER,
            now - timedelta(days=GAP_DAYS),
            limit * 2,
        )
    owners = _owner_emails()
    out = [dict(r) for r in rows
           if (r["email"] or "").lower() not in owners and not is_internal_email(r["email"])]
    return out[:limit]


async def send_one(user: dict, to: Optional[str] = None, record: bool = True, preview_winback: bool = False) -> bool:
    winback_until = None
    if (record and winback_eligible(user)) or preview_winback:
        winback_until = datetime.now(timezone.utc) + timedelta(days=WINBACK_DAYS)
    subject, body, text = build_email(user, winback_until)
    ok = await send_email(
        to=to or user["email"],
        subject=subject,
        html_body=body,
        text_body=text,
        reply_to=reply_to_address(),
        from_email=SUPPORT_FROM_EMAIL,
    )
    if ok and record:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET feedback_email_sent_at = $1, "
                "feedback_email_count = COALESCE(feedback_email_count, 0) + 1 WHERE id = $2",
                datetime.now(timezone.utc).replace(tzinfo=None),
                user["id"],
            )
        if winback_until:
            # Only granted once the email has actually gone out, so the email never promises what didn't happen.
            await grant_winback(user["id"], winback_until)
    return ok


async def run_daily() -> dict:
    candidates = await find_candidates()
    if not ENABLED:
        logger.info(
            "Feedback emails OFF (dry run): would email %d user(s): %s",
            len(candidates), [c["id"] for c in candidates],
        )
        return {"enabled": False, "would_send": len(candidates)}
    sent = 0
    for user in candidates:
        try:
            if await send_one(user):
                sent += 1
        except Exception as e:
            logger.error("Feedback email to %s failed: %s", user["id"], e)
    logger.info("Feedback emails sent: %d of %d", sent, len(candidates))
    return {"enabled": True, "sent": sent, "candidates": len(candidates)}


# ---------------------------------------------------------------- responses
async def record_response(user_id: str, reason: Optional[str], comment: Optional[str], source: str = "email_nudge") -> None:
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO feedback_responses (id, user_id, source, reason, comment, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            str(uuid.uuid4()), user_id, source,
            reason if reason in REASON_LABELS else None,
            (comment or "").strip()[:4000] or None,
            datetime.now(timezone.utc).replace(tzinfo=None),
        )


async def notify_owners(user: Optional[dict], reason: Optional[str], comment: Optional[str]) -> None:
    owners = _owner_emails()
    if not owners:
        return
    who = html.escape((user or {}).get("email") or "unknown user")
    label = html.escape(REASON_LABELS.get(reason or "", reason or "no reason picked"))
    note = html.escape(comment or "").replace("\n", "<br>") or "<i>no comment</i>"
    body = f"<p><b>{who}</b> answered the feedback email.</p><p>Reason: <b>{label}</b></p><p>{note}</p>"
    for o in owners:
        try:
            await send_email(to=o, subject=f"Laro feedback: {label}", html_body=body)
        except Exception as e:
            logger.warning("Owner feedback notify failed: %s", e)


async def set_opt_out(user_id: str) -> None:
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET feedback_emails_opt_out = TRUE WHERE id = $1", user_id)
