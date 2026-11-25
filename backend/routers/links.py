"""
Links Router - counts where web visits come from, report for Admin → Links
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from database.connection import get_db
from routers.admin import get_admin_user
from services.link_tracking import (
    clean_source, is_bot, link_report, record_visit, source_from_user_agent,
)

router = APIRouter(tags=["Links"])

# Light per-IP cap so the public endpoint can't be used to flood the table
_recent: dict = {}
_MAX_PER_HOUR = 30


def _allowed(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _recent.get(ip, []) if now - t < 3600]
    if len(hits) >= _MAX_PER_HOUR:
        _recent[ip] = hits
        return False
    hits.append(now)
    _recent[ip] = hits
    if len(_recent) > 5000:
        _recent.clear()
    return True


class VisitReport(BaseModel):
    source: Optional[str] = Field(None, max_length=100)
    campaign: Optional[str] = Field(None, max_length=100)
    landing: Optional[str] = Field(None, max_length=200)
    referrer_host: Optional[str] = Field(None, max_length=200)


@router.post("/track/visit", status_code=204)
async def track_visit(report: VisitReport, request: Request):
    """One call per browser session from the web app. No sign-in, no personal data."""
    # Behind Cloudflare + Caddy the socket address is the proxy, so use the original client
    forwarded = request.headers.get("cf-connecting-ip") or (request.headers.get("x-forwarded-for") or "").split(",")[0]
    ip = forwarded.strip() or (request.client.host if request.client else "?")
    if not _allowed(ip):
        return None
    user_agent = request.headers.get("user-agent") or ""
    if is_bot(user_agent):
        return None
    source =clean_source(report.source) or source_from_user_agent(user_agent) or "direct"
    pool = await get_db()
    async with pool.acquire() as conn:
        await record_visit(
            conn,
            source=source,
            campaign=report.campaign,
            landing=report.landing,
            referrer_host=report.referrer_host,
            user_agent=user_agent,
        )
    return None


@router.get("/admin/links")
async def links_report(
    days: int = Query(7, ge=1, le=365),
    _admin: dict = Depends(get_admin_user),
):
    """Visits and sign-ups per source."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    pool = await get_db()
    async with pool.acquire() as conn:
        report = await link_report(conn, since)
    return {"days": days, **report}
