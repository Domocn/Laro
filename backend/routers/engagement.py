"""Engagement: once-per-account UI flags and 'haven't seen you' feedback emails."""
import html
import json
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from database.connection import get_db
from database.repositories.user_repository import user_repository
from dependencies import get_current_user
from routers.admin import get_admin_user
from services import feedback_nudge as fn

router = APIRouter(tags=["Engagement"])

# Keys the web/Android apps may mark as seen (onboarding, guided tour, what's new release id).
SEEN_KEYS = {"onboarding", "tour", "whats_new"}


# ============================================================ seen flags
class SeenUpdate(BaseModel):
    key: str
    value: Optional[str] = None


def _parse_seen(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


@router.get("/me/seen")
async def get_seen(user: dict = Depends(get_current_user)):
    """What this account has already been shown (onboarding, tour, what's new)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        raw = await conn.fetchval("SELECT ui_seen FROM users WHERE id = $1", user["id"])
    return {"seen": _parse_seen(raw)}


@router.post("/me/seen")
async def mark_seen(data: SeenUpdate, user: dict = Depends(get_current_user)):
    if data.key not in SEEN_KEYS:
        raise HTTPException(status_code=400, detail="Unknown key")
    value = (data.value or "yes")[:40]
    pool = await get_db()
    async with pool.acquire() as conn:
        raw = await conn.fetchval("SELECT ui_seen FROM users WHERE id = $1", user["id"])
        seen = _parse_seen(raw)
        seen[data.key] = value
        await conn.execute("UPDATE users SET ui_seen = $1 WHERE id = $2", json.dumps(seen), user["id"])
    return {"seen": seen}


# ============================================================ feedback email pages
def _page(title: str, inner: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>{html.escape(title)} - Laro</title>
<style>
body{{margin:0;background:#f7f7f2;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1f2937}}
main{{max-width:480px;margin:40px auto;padding:28px;background:#fff;border-radius:20px;box-shadow:0 2px 12px rgba(0,0,0,.06)}}
h1{{font-size:22px;margin:0 0 12px}} p{{font-size:16px;line-height:1.5}}
label{{display:flex;gap:10px;align-items:center;padding:12px;border:1px solid #d1d5db;border-radius:12px;margin:8px 0;font-size:15px}}
textarea{{width:100%;box-sizing:border-box;min-height:110px;padding:12px;border:1px solid #d1d5db;border-radius:12px;font:inherit}}
button{{margin-top:14px;width:100%;padding:14px;border:0;border-radius:999px;background:#3d6a8a;color:#fff;font-size:16px;font-weight:600}}
a{{color:#3d6a8a}}
</style></head><body><main>{inner}</main></body></html>""")


@router.get("/feedback/nudge", response_class=HTMLResponse)
async def nudge_page(t: str = Query(...), r: Optional[str] = Query(None)):
    """Opened from the email. Shows the choice; nothing is saved until they press Send."""
    if not fn.read_token(t, "feedback"):
        return _page("Link expired", "<h1>That link doesn't work</h1><p>No problem. You can always reply to the email instead.</p>")
    options = "".join(
        f'<label><input type="radio" name="r" value="{k}"{" checked" if k == r else ""}> {html.escape(lbl)}</label>'
        for k, lbl in fn.REASONS
    )
    return _page("Your feedback", f"""<h1>Thanks for telling us</h1>
<p>What's stopping you from using Laro more often?</p>
<form method="post" action="/api/feedback/nudge">
<input type="hidden" name="t" value="{html.escape(t)}">
{options}
<p style="margin-top:18px">Anything else? (optional)</p>
<textarea name="comment" maxlength="4000" placeholder="What would make Laro more useful for you?"></textarea>
<button type="submit">Send feedback</button>
</form>""")


@router.post("/feedback/nudge", response_class=HTMLResponse)
async def nudge_submit(t: str = Form(...), r: Optional[str] = Form(None), comment: Optional[str] = Form(None)):
    user_id = fn.read_token(t, "feedback")
    if not user_id:
        return _page("Link expired", "<h1>That link doesn't work</h1><p>You can always reply to the email instead.</p>")
    await fn.record_response(user_id, r, comment)
    user = await user_repository.find_by_id(user_id)
    await fn.notify_owners(user, r, comment)
    return _page("Thank you", f"""<h1>Thank you</h1>
<p>That really helps. We read every answer.</p>
<p><a href="{fn.PUBLIC_URL}">Open Laro</a></p>""")


@router.get("/feedback/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_page(t: str = Query(...)):
    if not fn.read_token(t, "unsubscribe"):
        return _page("Link expired", "<h1>That link doesn't work</h1><p>Reply to the email and we'll take you off by hand.</p>")
    return _page("Stop these emails", f"""<h1>Stop these emails?</h1>
<p>We won't send you any more "what's stopping you" emails. Your account and everything in it stays as it is.</p>
<form method="post" action="/api/feedback/unsubscribe"><input type="hidden" name="t" value="{html.escape(t)}">
<button type="submit">Yes, stop them</button></form>""")


@router.post("/feedback/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_submit(t: str = Form(...)):
    user_id = fn.read_token(t, "unsubscribe")
    if not user_id:
        return _page("Link expired", "<h1>That link doesn't work</h1><p>Reply to the email and we'll take you off by hand.</p>")
    await fn.set_opt_out(user_id)
    return _page("Done", "<h1>Done</h1><p>You won't get these emails again.</p>")


# ============================================================ admin tools
@router.get("/admin/feedback-email/candidates")
async def feedback_candidates(admin: dict = Depends(get_admin_user)):
    """Dry run: who the daily job would email right now, and whether sending is switched on."""
    rows = await fn.find_candidates()
    return {
        "enabled": fn.ENABLED,
        "rules": {
            "inactive_days": fn.INACTIVE_DAYS, "max_inactive_days": fn.MAX_INACTIVE_DAYS,
            "gap_days": fn.GAP_DAYS, "max_per_user": fn.MAX_PER_USER, "daily_limit": fn.DAILY_LIMIT,
        },
        "candidates": [
            {"email": r["email"], "last_seen": str(r["seen"]), "emails_sent": r["sent_count"],
             "gets_winback_trial": fn.winback_eligible(r)} for r in rows
        ],
    }


@router.post("/admin/feedback-email/preview")
async def feedback_preview(admin: dict = Depends(get_admin_user)):
    """Send the email to yourself, exactly as users would get it. Not counted against you."""
    ok = await fn.send_one(admin, to=admin["email"], record=False, preview_winback=True)
    return {"sent": ok, "to": admin["email"]}


@router.get("/admin/feedback-email/responses")
async def feedback_responses(admin: dict = Depends(get_admin_user)):
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT f.created_at, f.reason, f.comment, u.email FROM feedback_responses f "
            "LEFT JOIN users u ON u.id = f.user_id ORDER BY f.created_at DESC LIMIT 200"
        )
    return {"responses": [
        {"at": str(r["created_at"]), "reason": fn.REASON_LABELS.get(r["reason"] or "", r["reason"]),
         "comment": r["comment"], "email": r["email"]} for r in rows
    ]}


# ============================================================ weekly plan email links (signed, no sign-in)
def _week_or_400(w: str):
    from datetime import date as _date
    try:
        return _date.fromisoformat(w[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad week")


@router.get("/meal-plan/week.ics")
async def weekly_plan_ics(t: str = Query(...), w: str = Query(...)):
    from fastapi.responses import Response
    from services import weekly_plan_email as wp

    user_id = wp.user_id_from_token(t)
    user = await user_repository.find_by_id(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=404, detail="Link not valid")
    week = _week_or_400(w)
    entries = await wp.week_entries(user, week)
    return Response(
        content=wp.build_ics(entries),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="laro-meals-{week.isoformat()}.ics"'},
    )


@router.get("/meal-plan/week", response_class=HTMLResponse)
async def weekly_plan_print(t: str = Query(...), w: str = Query(...)):
    from services import weekly_plan_email as wp

    user_id = wp.user_id_from_token(t)
    user = await user_repository.find_by_id(user_id) if user_id else None
    if not user:
        return _page("Link expired", "<h1>That link doesn't work</h1><p>Open Laro to see your meal plan.</p>")
    week = _week_or_400(w)
    return HTMLResponse(wp.build_print_page(user, week, await wp.week_entries(user, week)))


@router.post("/admin/weekly-plan-email/preview")
async def weekly_plan_preview(admin: dict = Depends(get_admin_user)):
    """Send yourself next week's plan email (even if the week is empty), to check how it looks."""
    from services import weekly_plan_email as wp
    from services.email import SUPPORT_FROM_EMAIL, send_email

    week = wp.next_monday()
    entries = await wp.week_entries(admin, week)
    subject, body, text = wp.build_email(admin, week, entries)
    ok = await send_email(to=admin["email"], subject=f"[PREVIEW] {subject}", html_body=body,
                          text_body=text, from_email=SUPPORT_FROM_EMAIL)
    return {"sent": ok, "to": admin["email"], "meals": len(entries)}
