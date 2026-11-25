"""Black Friday 2026: free Pro extension for founding users + a thank-you email.

Run inside the backend container on the VPS:

  # 1. See exactly what would happen (changes nothing, sends nothing)
  docker exec laro-backend python scripts/black_friday_2026.py --weeks 12 --dry-run

  # 2. Email ONLY the preview address (both versions), change no accounts
  docker exec laro-backend python scripts/black_friday_2026.py --weeks 12 --preview-to you@example.com

  # 3. Do it for real: extend + email everyone (safe to re-run; done users are skipped)
  docker exec laro-backend python scripts/black_friday_2026.py --weeks 12 --apply

Who gets what:
- Not currently Pro (expired trial, or free): Pro trial until max(now, old end) + N weeks,
  and the "extension" email.
- Already Pro with no end date (lifetime / paid / admin-granted): no change, and a
  thank-you email without the extension wording.
- Owners (LARO_OWNER_EMAILS / super_admin) and internal addresses
  (LARO_INTERNAL_EMAIL_DOMAINS, default laro.food) are skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import html
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import close_db, get_db, init_db  # noqa: E402
from services.email import APP_NAME, LOGO_URL, SUPPORT_FROM_EMAIL, send_email  # noqa: E402
from services.feedback_nudge import PUBLIC_URL, is_internal_email, reply_to_address  # noqa: E402
from utils.subscription import is_app_owner, is_premium_user, parse_expires  # noqa: E402

CAMPAIGN = "black_friday_2026"

PRO_PERKS = [
    "Unlimited recipes and cookbooks",
    "Unlimited AI imports: websites, videos, photos and PDFs",
    "A macro breakdown for every ingredient",
    "Room for more friends and household members",
]
NEW_LATELY = [
    'Recipe sections, like "For the sauce"',
    "Recipe versions, with a Low FODMAP switch",
    "UK food data for more accurate macros",
    "Import a whole cookbook from a Google Drive link",
    "A weekly email with next week's meals, ready for your calendar (switch it on in Preferences)",
]


def _ul(items):
    return "".join(f'<li style="margin:4px 0">{html.escape(i)}</li>' for i in items)


def _day(d: datetime) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


def build_email(user: dict, weeks: int, until: datetime | None) -> tuple[str, str, str]:
    first = html.escape(((user.get("name") or "").split(" ") or [""])[0]) or "there"
    btn = ("display:inline-block;margin-top:8px;padding:12px 20px;border-radius:999px;background:#3d6a8a;"
           "color:#fff;text-decoration:none;font-weight:600")
    if until:
        subject = f"A Black Friday thank you: {weeks} more weeks of Laro Pro"
        gift = (f"<p style=\"font-size:16px\">As a Black Friday thank you to our founding users, we've added "
                f"<b>{weeks} weeks of Laro Pro</b> to your account, free. It's already switched on: no code and no "
                f"card needed. <b>Your Pro now runs until {_day(until)}.</b></p>"
                f"<p style=\"font-size:16px;margin-bottom:4px\">With Pro you get:</p><ul>{_ul(PRO_PERKS)}</ul>")
        gift_text = (f"As a Black Friday thank you to our founding users, we've added {weeks} weeks of Laro Pro "
                     f"to your account, free. It's already switched on: no code and no card needed. "
                     f"Your Pro now runs until {_day(until)}.\n\nWith Pro you get:\n"
                     + "\n".join(f"- {p}" for p in PRO_PERKS) + "\n\n")
    else:
        subject = "A Black Friday thank you from Laro"
        gift = ("<p style=\"font-size:16px\">This Black Friday we're saying thank you to our founding users. "
                "You already have Laro Pro, so there's nothing you need to do: we just wanted to say it.</p>")
        gift_text = ("This Black Friday we're saying thank you to our founding users. You already have Laro Pro, "
                     "so there's nothing you need to do: we just wanted to say it.\n\n")
    body = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#1f2937">
  <img src="{LOGO_URL}" alt="{APP_NAME}" style="height:36px;margin-bottom:16px">
  <p style="font-size:16px">Hi {first},</p>
  <p style="font-size:16px">You were one of the first people to use Laro, and we're really grateful.</p>
  {gift}
  <p style="font-size:16px;margin-bottom:4px">New in Laro lately:</p>
  <ul>{_ul(NEW_LATELY)}</ul>
  <a href="{PUBLIC_URL}" style="{btn}">Open Laro</a>
  <p style="font-size:16px;margin-top:20px">Thanks for being here early. If anything isn't working for you, just reply: a real person reads every message.</p>
  <p style="font-size:16px">The Laro team</p>
</div>"""
    text = (f"Hi {first},\n\nYou were one of the first people to use Laro, and we're really grateful.\n\n"
            + gift_text + "New in Laro lately:\n" + "\n".join(f"- {n}" for n in NEW_LATELY)
            + f"\n\nOpen Laro: {PUBLIC_URL}\n\nThanks for being here early. If anything isn't working for you, "
            "just reply: a real person reads every message.\n\nThe Laro team\n")
    return subject, body, text


def plan_for(user: dict, weeks: int, now: datetime) -> tuple[str, datetime | None]:
    """Return (action, new_end). action: extend | thank | skip-owner."""
    if is_app_owner(user):
        return "skip-owner", None
    if is_internal_email(user.get("email")):
        return "skip-internal", None
    if is_premium_user(user):
        status = (user.get("subscription_status") or "").lower()
        if status == "premium" and not user.get("subscription_expires"):
            return "thank", None  # lifetime / paid / admin-granted with no end
    ends = [now]
    for col in ("subscription_expires", "referral_trial_end"):
        d = parse_expires(user.get(col))
        if d:
            ends.append(d if d.tzinfo else d.replace(tzinfo=timezone.utc))
    return "extend", max(ends) + timedelta(weeks=weeks)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--preview-to")
    mode.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    await init_db()
    pool = await get_db()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS campaign_sends (campaign VARCHAR(80) NOT NULL, user_id VARCHAR(255) NOT NULL, "
            "sent_at TIMESTAMP NOT NULL, PRIMARY KEY (campaign, user_id))"
        )
        users = [dict(r) for r in await conn.fetch(
            "SELECT * FROM users WHERE deleted_at IS NULL AND email LIKE '%@%' ORDER BY created_at")]
        done = {r["user_id"] for r in await conn.fetch(
            "SELECT user_id FROM campaign_sends WHERE campaign = $1", CAMPAIGN)}

    if args.preview_to:
        sample = {"name": "Preview", "id": "preview"}
        for until in (now + timedelta(weeks=args.weeks), None):
            subject, body, text = build_email(sample, args.weeks, until)
            ok = await send_email(to=args.preview_to, subject=f"[PREVIEW] {subject}", html_body=body,
                                  text_body=text, reply_to=reply_to_address(), from_email=SUPPORT_FROM_EMAIL)
            print(f"preview {'sent' if ok else 'FAILED'}: {subject}")
        await close_db()
        return

    sent = 0
    for u in users:
        action, until = plan_for(u, args.weeks, now)
        who = (u["email"] or "")[:3] + "***"
        if u["id"] in done:
            print(f"{who}: already done, skipped")
            continue
        print(f"{who}: {action}" + (f" until {until.date()}" if until else ""))
        if args.dry_run or action.startswith("skip-"):
            continue
        async with pool.acquire() as conn:
            if action == "extend":
                await conn.execute(
                    "UPDATE users SET subscription_status = 'trial', subscription_source = $1, "
                    "subscription_expires = $2 WHERE id = $3",
                    CAMPAIGN, until.replace(tzinfo=None), u["id"])
        subject, body, text = build_email(u, args.weeks, until)
        ok = await send_email(to=u["email"], subject=subject, html_body=body, text_body=text,
                              reply_to=reply_to_address(), from_email=SUPPORT_FROM_EMAIL)
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO campaign_sends (campaign, user_id, sent_at) VALUES ($1, $2, $3) "
                "ON CONFLICT DO NOTHING", CAMPAIGN, u["id"], now.replace(tzinfo=None))
        sent += ok
        print(f"   email {'sent' if ok else 'FAILED (account already extended; re-run will not resend)'}")
    print(f"done: {sent} email(s) sent" + (" (dry run, nothing changed)" if args.dry_run else ""))
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
