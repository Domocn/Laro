"""
RevenueCat Secret API client — link Laro admin subscriptions ↔ RC entitlements.

Uses the project Secret API key (sk_…), not the Play public goog_ key.
Docs: https://www.revenuecat.com/docs/api-v1#tag/entitlements
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

REVENUECAT_SECRET_API_KEY = (os.getenv("REVENUECAT_SECRET_API_KEY") or "").strip()
REVENUECAT_ENTITLEMENT_ID = (os.getenv("REVENUECAT_ENTITLEMENT_ID") or "Laro Pro").strip()
REVENUECAT_API_BASE = (os.getenv("REVENUECAT_API_BASE") or "https://api.revenuecat.com/v1").rstrip("/")


def is_revenuecat_api_configured() -> bool:
    return bool(REVENUECAT_SECRET_API_KEY)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {REVENUECAT_SECRET_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _entitlement_path(entitlement_id: str) -> str:
    return quote(entitlement_id, safe="")


def _duration_for_days(days: int) -> Optional[str]:
    """Map day counts to RC promotional duration enums when exact end_time is unused."""
    if days <= 0:
        return "lifetime"
    if days <= 1:
        return "daily"
    if days <= 3:
        return "three_day"
    if days <= 7:
        return "weekly"
    if days <= 31:
        return "monthly"
    if days <= 62:
        return "two_month"
    if days <= 93:
        return "three_month"
    if days <= 186:
        return "six_month"
    if days <= 366:
        return "yearly"
    return "lifetime"


async def get_subscriber(app_user_id: str) -> dict[str, Any]:
    """Fetch RC subscriber snapshot. Returns {ok, …} without raising for 404."""
    if not is_revenuecat_api_configured():
        return {"ok": False, "configured": False, "error": "REVENUECAT_SECRET_API_KEY not set"}
    if not app_user_id:
        return {"ok": False, "configured": True, "error": "missing app_user_id"}

    url = f"{REVENUECAT_API_BASE}/subscribers/{quote(app_user_id, safe='')}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, headers=_headers())
        if r.status_code == 404:
            return {"ok": True, "configured": True, "exists": False, "entitlements": {}}
        if r.status_code >= 400:
            logger.warning("RevenueCat get_subscriber %s → %s %s", app_user_id, r.status_code, r.text[:300])
            return {
                "ok": False,
                "configured": True,
                "error": f"HTTP {r.status_code}",
                "detail": (r.text or "")[:300],
            }
        data = r.json() or {}
        subscriber = data.get("subscriber") or data
        entitlements = (subscriber.get("entitlements") or {})
        active = {}
        for eid, ent in entitlements.items():
            if not isinstance(ent, dict):
                continue
            expires = ent.get("expires_date")
            # null expires_date = lifetime
            is_active = True
            if expires:
                try:
                    exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    is_active = exp_dt > datetime.now(timezone.utc)
                except Exception:
                    is_active = True
            if is_active:
                active[eid] = {
                    "expires_date": expires,
                    "product_identifier": ent.get("product_identifier"),
                    "purchase_date": ent.get("purchase_date"),
                }
        return {
            "ok": True,
            "configured": True,
            "exists": True,
            "entitlements": active,
            "has_laro_pro": REVENUECAT_ENTITLEMENT_ID in active,
            "first_seen": subscriber.get("first_seen"),
            "management_url": subscriber.get("management_url"),
        }
    except Exception as e:
        logger.exception("RevenueCat get_subscriber failed for %s", app_user_id)
        return {"ok": False, "configured": True, "error": str(e)[:240]}


async def grant_promotional_entitlement(
    app_user_id: str,
    *,
    days: int = 30,
    entitlement_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Grant promotional entitlement so RC CustomerInfo matches admin-granted Pro.

    days=0 → lifetime. Otherwise uses end_time_ms for an exact window.
    """
    if not is_revenuecat_api_configured():
        return {"ok": False, "configured": False, "skipped": True, "error": "REVENUECAT_SECRET_API_KEY not set"}
    if not app_user_id:
        return {"ok": False, "configured": True, "error": "missing app_user_id"}

    eid = (entitlement_id or REVENUECAT_ENTITLEMENT_ID).strip() or "Laro Pro"
    url = f"{REVENUECAT_API_BASE}/subscribers/{quote(app_user_id, safe='')}/entitlements/{_entitlement_path(eid)}/promotional"

    if days <= 0:
        body: dict[str, Any] = {"duration": "lifetime"}
    else:
        end_ms = int((datetime.now(timezone.utc).timestamp() + days * 86400) * 1000)
        body = {"end_time_ms": end_ms}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, headers=_headers(), json=body)
        if r.status_code >= 400:
            # Fallback to duration enum if end_time_ms rejected
            if days > 0 and "end_time" in (r.text or "").lower():
                body = {"duration": _duration_for_days(days)}
                async with httpx.AsyncClient(timeout=20.0) as client:
                    r = await client.post(url, headers=_headers(), json=body)
            if r.status_code >= 400:
                logger.warning(
                    "RevenueCat grant promotional %s/%s → %s %s",
                    app_user_id,
                    eid,
                    r.status_code,
                    r.text[:300],
                )
                return {
                    "ok": False,
                    "configured": True,
                    "error": f"HTTP {r.status_code}",
                    "detail": (r.text or "")[:300],
                }
        logger.info("RevenueCat promotional granted user=%s entitlement=%s days=%s", app_user_id, eid, days)
        return {"ok": True, "configured": True, "entitlement": eid, "days": days, "body": body}
    except Exception as e:
        logger.exception("RevenueCat grant promotional failed for %s", app_user_id)
        return {"ok": False, "configured": True, "error": str(e)[:240]}


async def revoke_promotional_entitlements(app_user_id: str, *, entitlement_id: Optional[str] = None) -> dict[str, Any]:
    """Revoke promotional entitlements only (does not cancel Play Store purchases)."""
    if not is_revenuecat_api_configured():
        return {"ok": False, "configured": False, "skipped": True, "error": "REVENUECAT_SECRET_API_KEY not set"}
    if not app_user_id:
        return {"ok": False, "configured": True, "error": "missing app_user_id"}

    eid = (entitlement_id or REVENUECAT_ENTITLEMENT_ID).strip() or "Laro Pro"
    url = f"{REVENUECAT_API_BASE}/subscribers/{quote(app_user_id, safe='')}/entitlements/{_entitlement_path(eid)}/revoke_promotionals"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, headers=_headers())
        if r.status_code >= 400:
            logger.warning(
                "RevenueCat revoke promotional %s/%s → %s %s",
                app_user_id,
                eid,
                r.status_code,
                r.text[:300],
            )
            return {
                "ok": False,
                "configured": True,
                "error": f"HTTP {r.status_code}",
                "detail": (r.text or "")[:300],
            }
        logger.info("RevenueCat promotional revoked user=%s entitlement=%s", app_user_id, eid)
        return {"ok": True, "configured": True, "entitlement": eid}
    except Exception as e:
        logger.exception("RevenueCat revoke promotional failed for %s", app_user_id)
        return {"ok": False, "configured": True, "error": str(e)[:240]}
