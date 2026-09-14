"""
Owner usage digest — Ollama Cloud + Laro AI quotas.

Scheduled daily (default 08:00 UTC) to LARO_OWNER_EMAILS.
Also exposed via admin API for on-demand send.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DIGEST_USER_ID = "__usage_digest__"
DIGEST_KIND = "usage_digest"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digest_enabled() -> bool:
    return os.getenv("USAGE_DIGEST_ENABLED", "true").lower() in ("1", "true", "yes")


def digest_hour_utc() -> int:
    try:
        return max(0, min(23, int(os.getenv("USAGE_DIGEST_HOUR_UTC", "8"))))
    except ValueError:
        return 8


def digest_cadence() -> str:
    """daily | weekly (Mondays only)."""
    raw = (os.getenv("USAGE_DIGEST_CADENCE", "daily") or "daily").strip().lower()
    return raw if raw in ("daily", "weekly") else "daily"


async def fetch_ollama_usage() -> Dict[str, Any]:
    """Call ollama.com /api/usage + /api/me when an API key is configured."""
    from config import settings

    api_key = (getattr(settings, "ollama_api_key", None) or os.getenv("OLLAMA_API_KEY") or "").strip()
    base = (getattr(settings, "ollama_url", None) or os.getenv("OLLAMA_URL") or "https://ollama.com").rstrip("/")
    out: Dict[str, Any] = {
        "configured": bool(api_key),
        "cloud": "ollama.com" in base.lower(),
        "plan": None,
        "email": None,
        "activity_cost": None,
        "period": None,
        "models": [],
        "limits": {},
        "error": None,
    }
    if not api_key or "ollama.com" not in base.lower():
        out["error"] = "Ollama Cloud API key not configured (or not using ollama.com)"
        return out

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            me = await client.post(f"{base}/api/me", headers=headers, json={})
            if me.status_code == 200:
                body = me.json()
                out["plan"] = body.get("Plan") or body.get("plan")
                out["email"] = body.get("Email") or body.get("email")
            usage = await client.get(f"{base}/api/usage", headers=headers)
            if usage.status_code == 200:
                data = usage.json()
                activity = data.get("activity") or {}
                out["activity_cost"] = activity.get("cost")
                out["period"] = activity.get("period")
                out["models"] = activity.get("models") or []
                out["limits"] = data.get("limits") or {}
            else:
                out["error"] = f"usage HTTP {usage.status_code}"
    except Exception as e:
        out["error"] = str(e)
        logger.warning("Ollama usage fetch failed: %s", e)
    return out


async def fetch_laro_ai_stats() -> Dict[str, Any]:
    """Aggregate free-tier AI counters from the users table."""
    from database.connection import get_db
    from utils.ai_quota import free_ai_limit

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS user_count,
                COALESCE(SUM(COALESCE(ai_uses_count, 0)), 0) AS total_ai_uses,
                COUNT(*) FILTER (WHERE COALESCE(ai_uses_count, 0) > 0) AS users_with_ai,
                COUNT(*) FILTER (
                    WHERE COALESCE(ai_uses_count, 0) >= $1
                      AND LOWER(COALESCE(subscription_status, 'free')) NOT IN ('premium', 'active', 'pro')
                      AND LOWER(COALESCE(role, 'user')) NOT IN ('admin', 'super_admin')
                ) AS free_at_limit,
                COUNT(*) FILTER (
                    WHERE LOWER(COALESCE(subscription_status, '')) IN ('premium', 'active', 'pro')
                       OR LOWER(COALESCE(role, '')) = 'super_admin'
                ) AS premiumish_users
            FROM users
            WHERE deleted_at IS NULL
            """,
            free_ai_limit(),
        )
        top = await conn.fetch(
            """
            SELECT email, name, role, COALESCE(ai_uses_count, 0) AS ai_uses,
                   COALESCE(subscription_status, 'free') AS subscription_status
            FROM users
            WHERE deleted_at IS NULL AND COALESCE(ai_uses_count, 0) > 0
            ORDER BY ai_uses_count DESC
            LIMIT 10
            """
        )
    return {
        "free_ai_limit": free_ai_limit(),
        "user_count": int(row["user_count"] or 0),
        "total_ai_uses": int(row["total_ai_uses"] or 0),
        "users_with_ai": int(row["users_with_ai"] or 0),
        "free_at_limit": int(row["free_at_limit"] or 0),
        "premiumish_users": int(row["premiumish_users"] or 0),
        "top_users": [dict(r) for r in top],
    }


async def build_usage_report() -> Dict[str, Any]:
    ollama = await fetch_ollama_usage()
    laro = await fetch_laro_ai_stats()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ollama": ollama,
        "laro": laro,
    }


def _format_models(models: List[dict]) -> str:
    if not models:
        return "<em>None</em>"
    rows = []
    for m in models:
        name = m.get("name") or m.get("model") or "?"
        count = m.get("request_count") or m.get("count") or 0
        rows.append(f"<li><code>{name}</code> — {count} requests</li>")
    return "<ul style='margin:8px 0;padding-left:20px;'>" + "".join(rows) + "</ul>"


def _format_limits(limits: dict) -> str:
    if not limits:
        return "<em>n/a</em>"
    parts = []
    for key, val in limits.items():
        if not isinstance(val, dict):
            continue
        usage = val.get("usage")
        models = val.get("models") or []
        parts.append(
            f"<p style='margin:4px 0;'><strong>{key}</strong>: usage={usage} "
            f"({len(models)} model(s))</p>"
        )
        if models:
            parts.append(_format_models(models))
    return "".join(parts) or "<em>n/a</em>"


async def send_usage_digest_email(report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Email the digest to every LARO_OWNER_EMAILS address."""
    from services.email import get_base_template, is_email_configured, send_email
    from utils.subscription import owner_emails

    report = report or await build_usage_report()
    recipients = sorted(owner_emails())
    if not recipients:
        return {"sent": 0, "skipped": True, "reason": "no_owner_emails"}
    if not is_email_configured():
        logger.info("Usage digest skipped — email not configured. Report: %s", report)
        return {"sent": 0, "skipped": True, "reason": "email_not_configured", "report": report}

    ollama = report.get("ollama") or {}
    laro = report.get("laro") or {}
    top_rows = ""
    for u in laro.get("top_users") or []:
        top_rows += (
            f"<tr><td style='padding:4px 8px;'>{u.get('email')}</td>"
            f"<td style='padding:4px 8px;'>{u.get('role')}</td>"
            f"<td style='padding:4px 8px;'>{u.get('subscription_status')}</td>"
            f"<td style='padding:4px 8px;text-align:right;'>{u.get('ai_uses')}</td></tr>"
        )
    if not top_rows:
        top_rows = "<tr><td colspan='4' style='padding:8px;'><em>No AI usage yet</em></td></tr>"

    period = ollama.get("period") or {}
    period_label = ""
    if isinstance(period, dict) and period.get("type"):
        period_label = (
            f"{period.get('type')} "
            f"({period.get('starting_at', '?')[:10]} → {str(period.get('ending_at', '?'))[:10]})"
        )

    content = f"""
    <h2 style="margin:0 0 8px 0;color:#2F3E2F;">Laro AI usage digest</h2>
    <p style="color:#6B7B6B;font-size:13px;margin:0 0 20px 0;">
      Generated {report.get('generated_at')}
    </p>

    <h3 style="color:#2F3E2F;margin:16px 0 8px;">Ollama Cloud</h3>
    <p style="margin:4px 0;">Plan: <strong>{ollama.get('plan') or 'unknown'}</strong>
       ({ollama.get('email') or 'n/a'})</p>
    <p style="margin:4px 0;">Activity cost (period): <strong>{ollama.get('activity_cost') or '0'}</strong></p>
    <p style="margin:4px 0;font-size:13px;color:#6B7B6B;">{period_label or ''}</p>
    {"<p style='color:#B45309;'>Note: " + str(ollama.get('error')) + "</p>" if ollama.get("error") else ""}
    <p style="margin:12px 0 4px;"><strong>Limits</strong></p>
    {_format_limits(ollama.get("limits") or {})}

    <h3 style="color:#2F3E2F;margin:24px 0 8px;">Laro app AI quota</h3>
    <p style="margin:4px 0;">Users: <strong>{laro.get('user_count')}</strong>
       · Premium-ish: <strong>{laro.get('premiumish_users')}</strong></p>
    <p style="margin:4px 0;">Total free-tier AI uses recorded:
       <strong>{laro.get('total_ai_uses')}</strong>
       (limit per free user: {laro.get('free_ai_limit')})</p>
    <p style="margin:4px 0;">Users with any AI use: <strong>{laro.get('users_with_ai')}</strong>
       · Free users at limit: <strong>{laro.get('free_at_limit')}</strong></p>

    <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;">
      <thead>
        <tr style="background:#F3F6F3;text-align:left;">
          <th style="padding:6px 8px;">Email</th>
          <th style="padding:6px 8px;">Role</th>
          <th style="padding:6px 8px;">Sub</th>
          <th style="padding:6px 8px;text-align:right;">AI uses</th>
        </tr>
      </thead>
      <tbody>{top_rows}</tbody>
    </table>

    <p style="margin-top:24px;font-size:12px;color:#8B9B8B;">
      Cadence controlled by USAGE_DIGEST_CADENCE / USAGE_DIGEST_HOUR_UTC.
      Send now: POST /api/admin/ai-usage/send-digest
    </p>
    """

    subject = (
        f"Laro AI usage — Ollama {ollama.get('plan') or '?'} · "
        f"cost {ollama.get('activity_cost') or '0'} · "
        f"{laro.get('total_ai_uses')} app uses"
    )
    sent = 0
    errors = []
    for to in recipients:
        ok = await send_email(to=to, subject=subject, html_body=get_base_template(content))
        if ok:
            sent += 1
        else:
            errors.append(to)
    return {"sent": sent, "recipients": recipients, "errors": errors, "report": report}


async def _already_sent(conn, target_key: str) -> bool:
    row = await conn.fetchrow(
        """
        SELECT 1 FROM reminder_dispatch_log
        WHERE user_id = $1 AND kind = $2 AND target_key = $3
        """,
        DIGEST_USER_ID,
        DIGEST_KIND,
        target_key,
    )
    return row is not None


async def _mark_sent(conn, target_key: str) -> None:
    await conn.execute(
        """
        INSERT INTO reminder_dispatch_log (user_id, kind, target_key, sent_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, kind, target_key) DO NOTHING
        """,
        DIGEST_USER_ID,
        DIGEST_KIND,
        target_key,
        _utcnow(),
    )


async def process_usage_digest(now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Run once from the scheduler. Sends when:
    - USAGE_DIGEST_ENABLED
    - current UTC hour matches USAGE_DIGEST_HOUR_UTC
    - cadence: daily every day, or weekly on Monday
    - not already sent for this target_key
    """
    if not digest_enabled():
        return {"skipped": True, "reason": "disabled"}

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        # treat naive as UTC for hour checks
        hour = now.hour
        weekday = now.weekday()
        day_key = now.strftime("%Y-%m-%d")
    else:
        utc = now.astimezone(timezone.utc)
        hour = utc.hour
        weekday = utc.weekday()
        day_key = utc.strftime("%Y-%m-%d")

    if hour != digest_hour_utc():
        return {"skipped": True, "reason": "wrong_hour", "hour": hour}

    cadence = digest_cadence()
    if cadence == "weekly" and weekday != 0:  # Monday
        return {"skipped": True, "reason": "not_monday"}

    target_key = f"{cadence}:{day_key}"
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        if await _already_sent(conn, target_key):
            return {"skipped": True, "reason": "already_sent", "target_key": target_key}
        result = await send_usage_digest_email()
        # Mark once per day on successful send, or when email is not configured
        # (avoid retrying every minute and flooding logs).
        if result.get("sent", 0) > 0 or result.get("reason") == "email_not_configured":
            await _mark_sent(conn, target_key)
        result["target_key"] = target_key
        return result
