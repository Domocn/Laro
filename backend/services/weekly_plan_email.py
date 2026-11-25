"""Opt-in Sunday email: next week's meal plan, with 'Add to calendar' and 'Download / print'.

Users switch it on in Preferences (user_preferences."weeklyPlanEmail"). The job runs
on Sunday afternoon and emails next Monday to Sunday. Links are signed per user so
they work straight from the email without signing in:
  /api/meal-plan/week.ics?t=...&w=YYYY-MM-DD    (calendar file)
  /api/meal-plan/week?t=...&w=YYYY-MM-DD        (printable page)
"""
import html
import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from database.connection import get_db
from database.repositories.meal_plan_repository import meal_plan_repository
from services.email import APP_NAME, LOGO_URL, SUPPORT_FROM_EMAIL, send_email
from services.feedback_nudge import PUBLIC_URL, make_token, read_token

logger = logging.getLogger(__name__)

PURPOSE = "weekplan"
MEAL_ORDER = {"Breakfast": 0, "Lunch": 1, "Snack": 2, "Dinner": 3}
MEAL_TIMES = {"Breakfast": "0800", "Lunch": "1230", "Snack": "1500", "Dinner": "1800"}


def next_monday(today: Optional[date] = None) -> date:
    today = today or datetime.now(timezone.utc).date()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def _household(user: dict) -> str:
    return user.get("household_id") or user["id"]


async def week_entries(user: dict, week_start: date) -> List[dict]:
    end = week_start + timedelta(days=6)
    plans = await meal_plan_repository.find_by_household(
        _household(user), start_date=week_start.isoformat(), end_date=end.isoformat(), limit=200
    )
    plans = [p for p in plans if (p.get("recipe_title") or "").strip()]
    plans.sort(key=lambda p: (str(p.get("date")), MEAL_ORDER.get(p.get("meal_type"), 9)))
    return plans


def _day_label(d: str) -> str:
    try:
        return date.fromisoformat(str(d)[:10]).strftime("%A %d %B")
    except ValueError:
        return str(d)


def _group_by_day(entries: List[dict]) -> dict:
    days: dict = {}
    for e in entries:
        days.setdefault(str(e["date"])[:10], []).append(e)
    return days


def links(user: dict, week_start: date) -> dict:
    t = make_token(user["id"], PURPOSE)
    w = week_start.isoformat()
    return {
        "ics": f"{PUBLIC_URL}/api/meal-plan/week.ics?t={t}&w={w}",
        "print": f"{PUBLIC_URL}/api/meal-plan/week?t={t}&w={w}",
        "planner": f"{PUBLIC_URL}/meal-planner",
        "prefs": f"{PUBLIC_URL}/settings/preferences",
    }


# ---------------------------------------------------------------- calendar file
def _esc(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(entries: List[dict]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Laro//Meal Plan//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:Laro meal plan"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for e in entries:
        d = str(e["date"])[:10].replace("-", "")
        start = MEAL_TIMES.get(e.get("meal_type"), "1200")
        end_h = str(min(int(start[:2]) + 1, 23)).zfill(2)
        title = f"{e.get('meal_type') or 'Meal'}: {e.get('recipe_title')}"
        desc = "Planned in Laro"
        if e.get("recipe_id"):
            desc += f"\n{PUBLIC_URL}/#/recipes/{e['recipe_id']}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e.get('id')}@laro.food",  # stable: re-importing updates rather than duplicates
            f"DTSTAMP:{stamp}",
            f"DTSTART:{d}T{start}00",
            f"DTEND:{d}T{end_h}{start[2:]}00",
            f"SUMMARY:{_esc(title)}",
            f"DESCRIPTION:{_esc(desc)}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------- printable page
def build_print_page(user: dict, week_start: date, entries: List[dict]) -> str:
    end = week_start + timedelta(days=6)
    days = _group_by_day(entries)
    rows = ""
    for i in range(7):
        d = (week_start + timedelta(days=i)).isoformat()
        meals = days.get(d, [])
        items = "".join(
            f"<li><b>{html.escape(m.get('meal_type') or '')}</b> {html.escape(m.get('recipe_title') or '')}</li>"
            for m in meals
        ) or '<li class="none">Nothing planned</li>'
        rows += f"<section><h2>{html.escape(_day_label(d))}</h2><ul>{items}</ul></section>"
    title = f"Meal plan {week_start.strftime('%d %b')} to {end.strftime('%d %b %Y')}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>{html.escape(title)} - Laro</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1f2937;max-width:720px;margin:24px auto;padding:0 16px}}
h1{{font-size:22px}} h2{{font-size:16px;margin:18px 0 6px;border-bottom:1px solid #e5e7eb;padding-bottom:4px}}
ul{{margin:0;padding-left:18px}} li{{margin:4px 0}} .none{{color:#9ca3af;list-style:none;margin-left:-18px}}
.bar{{display:flex;gap:10px;margin:12px 0 4px}} .bar a,.bar button{{padding:10px 16px;border-radius:999px;border:1px solid #d1d5db;background:#fff;color:#1f2937;text-decoration:none;font:inherit;cursor:pointer}}
@media print{{.bar{{display:none}} body{{margin:0}}}}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="bar"><button onclick="window.print()">Print or save as PDF</button><a href="{html.escape(links(user, week_start)['ics'])}">Add to calendar</a></div>
{rows}
</body></html>"""


# ---------------------------------------------------------------- email
def build_email(user: dict, week_start: date, entries: List[dict]) -> tuple:
    first = html.escape(((user.get("name") or "").split(" ") or [""])[0]) or "there"
    end = week_start + timedelta(days=6)
    l = links(user, week_start)
    span = f"{week_start.strftime('%d %b')} to {end.strftime('%d %b')}"
    btn = ('display:inline-block;margin:6px 8px 6px 0;padding:12px 18px;border-radius:999px;'
           'text-decoration:none;font-size:15px;font-weight:600')
    if entries:
        days = _group_by_day(entries)
        plan_html = "".join(
            f'<p style="margin:14px 0 4px;font-weight:600">{html.escape(_day_label(d))}</p>'
            + "".join(
                f'<p style="margin:2px 0;color:#374151">{html.escape(m.get("meal_type") or "")}: '
                f'{html.escape(m.get("recipe_title") or "")}</p>' for m in meals)
            for d, meals in days.items()
        )
        subject = f"Your meals for {span}"
        intro = "Here's what's planned for next week."
        actions = (f'<a href="{l["ics"]}" style="{btn};background:#3d6a8a;color:#fff">Add to calendar</a>'
                   f'<a href="{l["print"]}" style="{btn};border:1px solid #d1d5db;color:#1f2937">Download or print</a>')
        text_plan = "\n".join(f"{_day_label(m['date'])} - {m.get('meal_type')}: {m.get('recipe_title')}" for m in entries)
    else:
        plan_html = '<p style="color:#4b5563">Nothing is planned for next week yet.</p>'
        subject = f"Plan your meals for {span}"
        intro = "Next week is still empty. A few minutes now saves the 6pm 'what's for dinner?'."
        actions = f'<a href="{l["planner"]}" style="{btn};background:#3d6a8a;color:#fff">Plan next week</a>'
        text_plan = "Nothing planned yet."
    body = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#1f2937">
  <img src="{LOGO_URL}" alt="{APP_NAME}" style="height:36px;margin-bottom:16px">
  <p style="font-size:16px">Hi {first},</p>
  <p style="font-size:16px">{intro}</p>
  {plan_html}
  <div style="margin-top:20px">{actions}</div>
  <p style="font-size:13px;color:#6b7280;margin-top:16px">"Add to calendar" opens a calendar file: your phone or Outlook/Google Calendar asks to add the meals.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
  <p style="font-size:12px;color:#9ca3af">You asked for this weekly email in Laro. <a href="{l['prefs']}" style="color:#9ca3af">Turn it off in Preferences</a>.</p>
</div>"""
    text = (f"Hi {first},\n\n{intro}\n\n{text_plan}\n\nAdd to calendar: {l['ics']}\n"
            f"Download or print: {l['print']}\n\nTurn this email off in Preferences: {l['prefs']}\n")
    return subject, body, text


# ---------------------------------------------------------------- job
async def run_weekly(today: Optional[date] = None) -> dict:
    week_start = next_monday(today)
    tag = week_start.isoformat()
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.* FROM users u
            JOIN user_preferences p ON p.user_id = u.id
            WHERE u.deleted_at IS NULL AND u.email LIKE '%@%'
              AND COALESCE(p."weeklyPlanEmail", FALSE) = TRUE
              AND COALESCE(u.weekly_plan_last_week, '') <> $1
            """,
            tag,
        )
    sent = 0
    for r in rows:
        user = dict(r)
        try:
            entries = await week_entries(user, week_start)
            if not entries:
                # The existing Sunday reminder (services/reminders.py) already nudges empty weeks;
                # don't send a second email about the same thing.
                continue
            subject, body, text = build_email(user, week_start, entries)
            ok = await send_email(to=user["email"], subject=subject, html_body=body, text_body=text,
                                  from_email=SUPPORT_FROM_EMAIL)
            if ok:
                sent += 1
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE users SET weekly_plan_last_week = $1 WHERE id = $2", tag, user["id"])
        except Exception as e:
            logger.error("Weekly plan email for %s failed: %s", user.get("id"), e)
    logger.info("Weekly plan emails for week %s: %d of %d", tag, sent, len(rows))
    return {"week": tag, "sent": sent, "subscribers": len(rows)}


def user_id_from_token(t: str) -> Optional[str]:
    return read_token(t, PURPOSE)
