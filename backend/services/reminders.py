"""
Scheduled meal / shopping / weekly-plan reminders.

Runs from:
  - in-process asyncio loop (FastAPI lifespan) — default, no Redis required
  - Celery beat tasks (workers/tasks.py) — production scale-out

Dedupes via reminder_dispatch_log so beat + in-process can coexist safely.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone, date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default local meal clock times (UTC). Mobile reminder_time overrides dinner.
DEFAULT_MEAL_HOURS = {
    "breakfast": (8, 0),
    "lunch": (12, 0),
    "dinner": (18, 0),
    "snack": (15, 0),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _already_sent(conn, user_id: str, kind: str, target_key: str) -> bool:
    row = await conn.fetchrow(
        """
        SELECT 1 FROM reminder_dispatch_log
        WHERE user_id = $1 AND kind = $2 AND target_key = $3
        """,
        user_id,
        kind,
        target_key,
    )
    return row is not None


async def _mark_sent(conn, user_id: str, kind: str, target_key: str) -> None:
    await conn.execute(
        """
        INSERT INTO reminder_dispatch_log (user_id, kind, target_key, sent_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, kind, target_key) DO NOTHING
        """,
        user_id,
        kind,
        target_key,
        _utcnow(),
    )


def _parse_hhmm(value: Optional[str], fallback: Tuple[int, int] = (18, 0)) -> Tuple[int, int]:
    if not value or not isinstance(value, str) or ":" not in value:
        return fallback
    try:
        parts = value.strip().split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return fallback


async def _eligible_users(conn) -> List[dict]:
    """
    Users who want reminders: web notification_settings.enabled,
    or mobile row with push_enabled + fcm_token.
    """
    rows = await conn.fetch(
        """
        SELECT
            u.id AS user_id,
            u.name,
            u.email,
            COALESCE(u.household_id, u.id) AS household_id,
            COALESCE(ns.enabled, FALSE) AS web_enabled,
            COALESCE(ns.meal_reminders, TRUE) AS meal_reminders,
            COALESCE(ns.shopping_reminders, TRUE) AS shopping_reminders,
            COALESCE(ns.weekly_plan_reminder, TRUE) AS weekly_plan_reminder,
            COALESCE(ns.reminder_time, 30) AS lead_minutes,
            mns.fcm_token,
            COALESCE(mns.push_enabled, TRUE) AS push_enabled,
            COALESCE(mns.meal_reminders, TRUE) AS mobile_meal_reminders,
            COALESCE(mns.shopping_reminders, TRUE) AS mobile_shopping_reminders,
            COALESCE(mns.weekly_plan_reminder, TRUE) AS mobile_weekly_plan_reminder,
            COALESCE(mns.reminder_time, '18:00') AS dinner_time
        FROM users u
        LEFT JOIN notification_settings ns ON ns.user_id = u.id
        LEFT JOIN mobile_notification_settings mns ON mns.user_id = u.id
        WHERE u.deleted_at IS NULL
          AND (
            COALESCE(ns.enabled, FALSE) = TRUE
            OR (mns.fcm_token IS NOT NULL AND COALESCE(mns.push_enabled, TRUE) = TRUE)
          )
        """
    )
    return [dict(r) for r in rows]


async def _send(user_id: str, notification_type, data: dict) -> Dict[str, Any]:
    from services.notifications import notify_user

    return await notify_user(user_id, notification_type, data=data)


async def process_meal_reminders(now: Optional[datetime] = None) -> Dict[str, int]:
    """Send meal reminders when (meal_time - lead_minutes) was crossed recently."""
    from database.connection import get_db
    from services.notifications import NotificationType

    now = now or _utcnow()
    today = now.date().isoformat()
    stats = {"checked": 0, "sent": 0, "skipped": 0, "errors": 0}

    pool = await get_db()
    async with pool.acquire() as conn:
        users = await _eligible_users(conn)
        for user in users:
            stats["checked"] += 1
            if user.get("web_enabled"):
                want_meal = bool(user.get("meal_reminders"))
            else:
                want_meal = bool(user.get("mobile_meal_reminders", True))
            if not want_meal:
                stats["skipped"] += 1
                continue

            lead = int(user.get("lead_minutes") or 30)
            # Web Settings uses "minutes before meal"; dinner defaults to 18:00.
            # Mobile stores an absolute dinner clock in reminder_time (HH:MM).
            if user.get("web_enabled"):
                dinner_h, dinner_m = DEFAULT_MEAL_HOURS["dinner"]
            else:
                dinner_h, dinner_m = _parse_hhmm(
                    user.get("dinner_time"), DEFAULT_MEAL_HOURS["dinner"]
                )

            meal_hours = dict(DEFAULT_MEAL_HOURS)
            meal_hours["dinner"] = (dinner_h, dinner_m)

            for meal_type, (hh, mm) in meal_hours.items():
                if meal_type == "snack":
                    continue
                meal_dt = datetime(now.year, now.month, now.day, hh, mm)
                target = meal_dt - timedelta(minutes=lead)
                # Fire within a 6-minute window after the target instant
                if not (target <= now < target + timedelta(minutes=6)):
                    continue

                plan = await conn.fetchrow(
                    """
                    SELECT recipe_title, notes, entry_type
                    FROM meal_plans
                    WHERE household_id = $1 AND date = $2
                      AND (LOWER(meal_type) = $3)
                    LIMIT 1
                    """,
                    user["household_id"],
                    today,
                    meal_type,
                )
                if not plan:
                    continue

                recipe_name = plan["recipe_title"] or plan["notes"] or meal_type.title()
                target_key = f"{today}:{meal_type}"
                if await _already_sent(conn, user["user_id"], "meal", target_key):
                    stats["skipped"] += 1
                    continue

                try:
                    result = await _send(
                        user["user_id"],
                        NotificationType.MEAL_REMINDER,
                        {"recipe_name": recipe_name, "meal_type": meal_type},
                    )
                    await _mark_sent(conn, user["user_id"], "meal", target_key)
                    if result.get("push_sent") or result.get("web_push_sent") or result.get("email_sent"):
                        stats["sent"] += 1
                    else:
                        # Still mark sent to avoid hammering users with no channel
                        stats["skipped"] += 1
                        logger.info(
                            "Meal reminder marked for %s but no channel delivered",
                            user["user_id"],
                        )
                except Exception as e:
                    stats["errors"] += 1
                    logger.exception("Meal reminder failed for %s: %s", user["user_id"], e)

    return stats


async def process_shopping_reminders(now: Optional[datetime] = None) -> Dict[str, int]:
    """Saturday ~10:00 UTC: remind if unchecked shopping items exist."""
    from database.connection import get_db
    from services.notifications import NotificationType

    now = now or _utcnow()
    stats = {"checked": 0, "sent": 0, "skipped": 0, "errors": 0}

    # Window: Saturday 10:00–10:06 UTC
    if now.weekday() != 5:  # Saturday
        return stats
    window_start = datetime(now.year, now.month, now.day, 10, 0)
    if not (window_start <= now < window_start + timedelta(minutes=6)):
        return stats

    week_key = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    pool = await get_db()
    async with pool.acquire() as conn:
        users = await _eligible_users(conn)
        for user in users:
            stats["checked"] += 1
            if user.get("web_enabled"):
                want = bool(user.get("shopping_reminders"))
            else:
                want = bool(user.get("mobile_shopping_reminders", True))
            if not want:
                stats["skipped"] += 1
                continue

            lists = await conn.fetch(
                "SELECT items FROM shopping_lists WHERE household_id = $1",
                user["household_id"],
            )
            unchecked = 0
            import json

            for row in lists:
                items = row["items"]
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                    except json.JSONDecodeError:
                        items = []
                if not items:
                    continue
                unchecked += sum(1 for i in items if isinstance(i, dict) and not i.get("checked"))

            if unchecked <= 0:
                stats["skipped"] += 1
                continue

            target_key = f"shopping:{week_key}"
            if await _already_sent(conn, user["user_id"], "shopping", target_key):
                stats["skipped"] += 1
                continue

            try:
                result = await _send(
                    user["user_id"],
                    NotificationType.SHOPPING_REMINDER,
                    {"item_count": unchecked},
                )
                await _mark_sent(conn, user["user_id"], "shopping", target_key)
                if result.get("push_sent") or result.get("web_push_sent") or result.get("email_sent"):
                    stats["sent"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                stats["errors"] += 1
                logger.exception("Shopping reminder failed for %s: %s", user["user_id"], e)

    return stats


async def process_weekly_plan_reminders(now: Optional[datetime] = None) -> Dict[str, int]:
    """Sunday ~16:00 UTC: nudge if next week has fewer than 3 planned meals."""
    from database.connection import get_db
    from services.notifications import NotificationType

    now = now or _utcnow()
    stats = {"checked": 0, "sent": 0, "skipped": 0, "errors": 0}

    if now.weekday() != 6:  # Sunday
        return stats
    window_start = datetime(now.year, now.month, now.day, 16, 0)
    if not (window_start <= now < window_start + timedelta(minutes=6)):
        return stats

    # Next Monday → Sunday
    days_until_monday = (7 - now.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = (now.date() + timedelta(days=days_until_monday))
    next_sunday = next_monday + timedelta(days=6)
    week_key = f"{next_monday.isocalendar().year}-W{next_monday.isocalendar().week:02d}"

    pool = await get_db()
    async with pool.acquire() as conn:
        users = await _eligible_users(conn)
        for user in users:
            stats["checked"] += 1
            if user.get("web_enabled"):
                want = bool(user.get("weekly_plan_reminder"))
            else:
                want = bool(user.get("mobile_weekly_plan_reminder", True))
            if not want:
                stats["skipped"] += 1
                continue

            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM meal_plans
                WHERE household_id = $1 AND date >= $2 AND date <= $3
                """,
                user["household_id"],
                next_monday.isoformat(),
                next_sunday.isoformat(),
            )
            if (count or 0) >= 3:
                stats["skipped"] += 1
                continue

            target_key = f"weekly:{week_key}"
            if await _already_sent(conn, user["user_id"], "weekly", target_key):
                stats["skipped"] += 1
                continue

            try:
                result = await _send(
                    user["user_id"],
                    NotificationType.WEEKLY_PLAN_REMINDER,
                    {"week_label": f"{next_monday.isoformat()} – {next_sunday.isoformat()}"},
                )
                await _mark_sent(conn, user["user_id"], "weekly", target_key)
                if result.get("push_sent") or result.get("web_push_sent") or result.get("email_sent"):
                    stats["sent"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                stats["errors"] += 1
                logger.exception("Weekly plan reminder failed for %s: %s", user["user_id"], e)

    return stats


async def run_all_reminder_sweeps(now: Optional[datetime] = None) -> Dict[str, Dict[str, int]]:
    """Run all reminder processors once."""
    meal = await process_meal_reminders(now)
    shopping = await process_shopping_reminders(now)
    weekly = await process_weekly_plan_reminders(now)
    logger.info("Reminder sweep: meal=%s shopping=%s weekly=%s", meal, shopping, weekly)
    return {"meal": meal, "shopping": shopping, "weekly": weekly}


async def reminder_scheduler_loop(interval_seconds: int = 60):
    """Background loop for in-process scheduling."""
    import asyncio

    logger.info("In-process reminder scheduler started (interval=%ss)", interval_seconds)
    # Small delay so DB is fully ready
    await asyncio.sleep(5)
    while True:
        try:
            await run_all_reminder_sweeps()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reminder sweep error")
        await asyncio.sleep(interval_seconds)
