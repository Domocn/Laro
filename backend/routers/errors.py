"""
Errors Router - web-app crash reports in, grouped error list out (admin)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from database.connection import get_db
from routers.admin import get_admin_user
from services.error_log import grouped_errors, record_event, user_id_from_request
from services.link_tracking import is_bot

router = APIRouter(tags=["Errors"])


class ClientErrorReport(BaseModel):
    message: str = Field(..., max_length=2000)
    error_type: Optional[str] = Field(None, max_length=200)
    stack: Optional[str] = Field(None, max_length=6000)
    component_stack: Optional[str] = Field(None, max_length=4000)
    page: Optional[str] = Field(None, max_length=500)
    app_version: Optional[str] = Field(None, max_length=40)
    platform: Optional[str] = Field(None, max_length=20)


@router.post("/errors/client", status_code=204)
async def report_client_error(report: ClientErrorReport, request: Request):
    """Web and Android crash reports. Sign-in optional so login-screen crashes are caught too."""
    # Search crawlers often fail to load page chunks; that's not a bug real people hit
    if is_bot(request.headers.get("user-agent") or ""):
        return None
    stack = report.stack or ""
    source = "android" if (report.platform or "").lower() == "android" else "web"
    # First line of our own code in the stack groups repeats of the same crash
    where = ""
    for line in stack.splitlines()[1:]:
        if "/assets/" in line or "/src/" in line or "com.laro.app" in line:
            where = line.strip()[:200]
            break
    await record_event(
        source=source,
        error_type=report.error_type or "Error",
        message=report.message,
        path=report.page or "",
        method="",
        user_id=user_id_from_request(request),
        user_agent=(request.headers.get("user-agent") or "")[:300],
        app_version=report.app_version or "",
        detail="\n\n".join(s for s in (stack, report.component_stack or "") if s),
        where=where or report.message[:120],
    )
    return None


@router.get("/admin/errors")
async def list_errors(
    days: int = Query(7, ge=1, le=90),
    _admin: dict = Depends(get_admin_user),
):
    """Errors grouped by kind, most people affected first."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    pool = await get_db()
    async with pool.acquire() as conn:
        groups = await grouped_errors(conn, since, limit=200)
    return {"days": days, "groups": groups}


@router.get("/admin/errors/{fingerprint}")
async def error_samples(fingerprint: str, _admin: dict = Depends(get_admin_user)):
    """Latest occurrences of one error, with stack traces."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT created_at, source, error_type, message, path, method, location,
                      user_id, user_agent, app_version, detail
               FROM error_events WHERE fingerprint = $1 ORDER BY created_at DESC LIMIT 20""",
            fingerprint,
        )
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat() + "Z"
        out.append(d)
    return {"fingerprint": fingerprint, "events": out}
