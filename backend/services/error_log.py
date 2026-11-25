"""
Error log: every server 500 and web-app crash is kept in Postgres (container logs are
wiped on each deploy), the owner is emailed when a new error appears or one starts
hitting several people, and a daily summary goes out each morning.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import traceback
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

APP_VERSION = os.getenv("APP_VERSION", "")

# A fingerprint seen this often in an hour, by this many people, triggers an instant alert.
SPIKE_COUNT = 5
SPIKE_USERS = 2
# Don't email about the same error more than once in this window.
ALERT_COOLDOWN = timedelta(hours=6)
# Drop events for one fingerprint beyond this many per hour (runaway loops).
MAX_PER_HOUR = 200

_ID_RE = re.compile(
    r"/(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{16,}|\d+)(?=/|$)",
    re.I,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalise_path(path: Optional[str]) -> str:
    """Replace ids in a path so /recipes/123 and /recipes/456 group together."""
    if not path:
        return ""
    # Web pages are hash routes ("#/recipes/123"): keep the route, drop the "#"
    path = path.lstrip("#")
    path = path.split("?", 1)[0].split("#", 1)[0]
    return _ID_RE.sub("/:id", path)[:300]


def fingerprint(source: str, error_type: str, path: str, where: str = "") -> str:
    raw = "|".join([source, error_type or "", normalise_path(path), where or ""])
    return hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()


def _app_frame(exc: BaseException) -> str:
    """Last stack frame inside our own code, e.g. routers/notifications.py:299."""
    frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    for fr in reversed(frames):
        if "/site-packages/" not in fr.filename and "/lib/python" not in fr.filename:
            return f"{fr.filename.replace('/app/', '')}:{fr.lineno}"
    return ""


def _unwrap(exc: BaseException) -> BaseException:
    """Starlette wraps route errors in ExceptionGroups; report the real one."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:  # type: ignore[name-defined]
        exc = exc.exceptions[0]
    return exc


def user_id_from_request(request) -> Optional[str]:
    """Best-effort user id from the bearer token, without touching the database."""
    try:
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return None
        token = auth.split(" ", 1)[1].strip()
        if token.startswith("laro_"):
            return "api-token"
        import jwt
        from config import settings

        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("user_id")
    except Exception:
        return None


async def record_server_exception(request, exc: BaseException, status: int = 500) -> None:
    exc = _unwrap(exc)
    where = _app_frame(exc)
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-6000:]
    await record_event(
        source="server",
        error_type=type(exc).__name__ if status == 500 else f"HTTP {status}",
        message=str(exc)[:2000],
        path=request.url.path,
        method=request.method,
        user_id=user_id_from_request(request),
        user_agent=(request.headers.get("user-agent") or "")[:300],
        app_version=APP_VERSION,
        detail=tb,
        where=where,
    )


async def record_event(
    *,
    source: str,
    error_type: str,
    message: str,
    path: str = "",
    method: str = "",
    user_id: Optional[str] = None,
    user_agent: str = "",
    app_version: str = "",
    detail: str = "",
    where: str = "",
    wait_for_alert: bool = False,
) -> None:
    """Store one error. Never raises: logging must not break the request.

    wait_for_alert: send any alert email before returning (background jobs, whose event
    loop ends as soon as this returns and would cancel a fire-and-forget alert).
    """
    try:
        from database.connection import get_db

        fp = fingerprint(source, error_type, path, where or message[:120])
        pool = await get_db()
        async with pool.acquire() as conn:
            recent = await conn.fetchval(
                "SELECT count(*) FROM error_events WHERE fingerprint = $1 AND created_at > $2",
                fp, _now() - timedelta(hours=1),
            )
            if recent and recent >= MAX_PER_HOUR:
                return
            await conn.execute(
                """INSERT INTO error_events
                   (created_at, source, fingerprint, error_type, message, path, method,
                    user_id, user_agent, app_version, detail, location)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                _now(), source, fp, (error_type or "")[:200], (message or "")[:2000],
                normalise_path(path), (method or "")[:10], user_id, (user_agent or "")[:300],
                (app_version or "")[:40], (detail or "")[:8000], (where or "")[:300],
            )
        if wait_for_alert:
            await _maybe_alert(fp)
        else:
            asyncio.create_task(_maybe_alert(fp))
    except Exception as e:  # pragma: no cover - best effort
        logger.warning("Could not record error event: %s", e)


async def record_task_failure(task_name: str, exc: BaseException, tb_text: str = "") -> None:
    """A Celery background job (reminders, imports, price sync, ...) raised."""
    exc = _unwrap(exc)
    where = _app_frame(exc)
    if not tb_text:
        tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    await record_event(
        source="worker",
        error_type=type(exc).__name__,
        message=str(exc)[:2000] or type(exc).__name__,
        path=task_name or "",
        method="TASK",
        app_version=APP_VERSION,
        detail=tb_text[-6000:],
        where=where,
        wait_for_alert=True,
    )


async def _maybe_alert(fp: str) -> None:
    """Email the owner for a brand-new error, or one that is hitting several people."""
    try:
        from database.connection import get_db

        pool = await get_db()
        async with pool.acquire() as conn:
            stats = await conn.fetchrow(
                """SELECT count(*) AS total,
                          count(*) FILTER (WHERE created_at > $2) AS hour_count,
                          count(DISTINCT user_id) FILTER (WHERE created_at > $2) AS hour_users
                   FROM error_events WHERE fingerprint = $1""",
                fp, _now() - timedelta(hours=1),
            )
            if not stats:
                return
            is_new = stats["total"] == 1
            is_spike = stats["hour_count"] >= SPIKE_COUNT and stats["hour_users"] >= SPIKE_USERS
            if not (is_new or is_spike):
                return
            last = await conn.fetchval(
                "SELECT last_sent_at FROM error_alerts WHERE fingerprint = $1", fp
            )
            if last and _now() - last < ALERT_COOLDOWN:
                return
            await conn.execute(
                """INSERT INTO error_alerts (fingerprint, last_sent_at) VALUES ($1, $2)
                   ON CONFLICT (fingerprint) DO UPDATE SET last_sent_at = EXCLUDED.last_sent_at""",
                fp, _now(),
            )
            sample = await conn.fetchrow(
                "SELECT * FROM error_events WHERE fingerprint = $1 ORDER BY created_at DESC LIMIT 1", fp
            )
        title = "New error in Laro" if is_new else (
            f"Error hitting {stats['hour_users']} people in the last hour"
        )
        await _email_owner(
            subject=f"[Laro] {title}: {sample['error_type']} on {sample['path'] or 'web'}",
            heading=title,
            body_html=_event_html(dict(sample), stats["hour_count"], stats["hour_users"]),
        )
    except Exception as e:  # pragma: no cover
        logger.warning("Error alert failed: %s", e)


def _event_html(ev: Dict[str, Any], hour_count: int = 0, hour_users: int = 0) -> str:
    who = "a signed-in user" if ev.get("user_id") and ev.get("user_id") != "api-token" else (
        "Home Assistant / API token" if ev.get("user_id") == "api-token" else "someone signed out"
    )
    return f"""
    <p style="margin:4px 0;"><strong>{escape(ev.get('error_type') or '')}</strong>
       on <code>{escape(ev.get('method') or '')} {escape(ev.get('path') or '')}</code> ({escape(ev.get('source') or '')})</p>
    <p style="margin:4px 0;">{escape((ev.get('message') or '')[:400])}</p>
    <p style="margin:4px 0;color:#6B7B6B;font-size:13px;">
      Where: {escape(ev.get('location') or 'n/a')} · Affected: {who}
      · Last hour: {hour_count} times, {hour_users} people · App {escape(ev.get('app_version') or '?')}
    </p>
    <p style="margin:12px 0 0;font-size:13px;">See Admin → Errors on laro.food for the full list.</p>
    """


async def _email_owner(subject: str, heading: str, body_html: str) -> int:
    from services.email import get_base_template, is_email_configured, send_email
    from utils.subscription import owner_emails

    if not is_email_configured():
        logger.info("Error email skipped (email not configured): %s", subject)
        return 0
    html = get_base_template(
        f'<h2 style="margin:0 0 12px 0;color:#2F3E2F;">{escape(heading)}</h2>{body_html}'
    )
    sent = 0
    for to in sorted(owner_emails()):
        if await send_email(to=to, subject=subject, html_body=html):
            sent += 1
    return sent


async def grouped_errors(conn, since: datetime, limit: int = 100) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """SELECT fingerprint,
                  max(error_type) AS error_type,
                  max(source) AS source,
                  max(path) AS path,
                  max(method) AS method,
                  max(location) AS location,
                  (array_agg(message ORDER BY created_at DESC))[1] AS message,
                  (array_agg(app_version ORDER BY created_at DESC))[1] AS app_version,
                  count(*) AS count,
                  count(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL AND user_id <> 'api-token') AS users,
                  min(created_at) AS first_seen,
                  max(created_at) AS last_seen,
                  (SELECT min(created_at) FROM error_events e2 WHERE e2.fingerprint = error_events.fingerprint) AS first_ever
           FROM error_events
           WHERE created_at > $1
           GROUP BY fingerprint
           ORDER BY count(DISTINCT user_id) DESC, count(*) DESC
           LIMIT $2""",
        since, limit,
    )
    out = []
    for r in rows:
        d = dict(r)
        for k in ("first_seen", "last_seen", "first_ever"):
            if d.get(k):
                d[k] = d[k].isoformat() + "Z"
        d["is_new"] = bool(r["first_ever"] and r["first_ever"] > since)
        out.append(d)
    return out


async def send_daily_summary() -> Dict[str, Any]:
    """Morning email: what broke in the last 24 hours (nothing sent when all is quiet)."""
    import asyncpg

    since = _now() - timedelta(hours=24)
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        groups = await grouped_errors(conn, since, limit=25)
    finally:
        await conn.close()
    if not groups:
        return {"sent": 0, "errors": 0}
    total = sum(g["count"] for g in groups)
    real = [g for g in groups if g["users"]]
    rows = "".join(
        f"<tr><td style='padding:4px 8px;'>{'NEW ' if g['is_new'] else ''}{escape(g['error_type'] or '')}</td>"
        f"<td style='padding:4px 8px;'><code>{escape(g['path'] or '')}</code></td>"
        f"<td style='padding:4px 8px;text-align:right;'>{g['count']}</td>"
        f"<td style='padding:4px 8px;text-align:right;'>{g['users']}</td></tr>"
        for g in groups
    )
    body = f"""
    <p style="margin:4px 0;">{total} error(s) in {len(groups)} kind(s) yesterday.
       {len(real)} affected real users.</p>
    <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;">
      <thead><tr style="background:#F3F6F3;text-align:left;">
        <th style="padding:6px 8px;">Error</th><th style="padding:6px 8px;">Where</th>
        <th style="padding:6px 8px;text-align:right;">Times</th><th style="padding:6px 8px;text-align:right;">People</th>
      </tr></thead><tbody>{rows}</tbody></table>
    <p style="margin:12px 0 0;font-size:13px;">Details: Admin → Errors on laro.food.</p>
    """
    sent = await _email_owner(
        subject=f"[Laro] Daily errors: {total} yesterday, {len(real)} affecting users",
        heading="Laro errors in the last 24 hours",
        body_html=body,
    )
    return {"sent": sent, "errors": total, "kinds": len(groups)}
