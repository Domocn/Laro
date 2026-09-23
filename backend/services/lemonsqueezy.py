"""
Lemon Squeezy billing — checkout links, webhooks, customer portal.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

LEMONSQUEEZY_API_KEY = (os.getenv("LEMONSQUEEZY_API_KEY") or "").strip()
LEMONSQUEEZY_STORE_ID = (os.getenv("LEMONSQUEEZY_STORE_ID") or "").strip()
LEMONSQUEEZY_VARIANT_ID_WEEKLY = (os.getenv("LEMONSQUEEZY_VARIANT_ID_WEEKLY") or "").strip()
LEMONSQUEEZY_VARIANT_ID_MONTHLY = (os.getenv("LEMONSQUEEZY_VARIANT_ID_MONTHLY") or "").strip()
LEMONSQUEEZY_WEBHOOK_SECRET = (os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET") or "").strip()
LEMONSQUEEZY_CHECKOUT_REDIRECT_URL = (
    os.getenv("LEMONSQUEEZY_CHECKOUT_REDIRECT_URL") or "https://laro.food/settings?pro=success"
).strip()

API_BASE = "https://api.lemonsqueezy.com/v1"

PLAN_VARIANTS = {
    "weekly": LEMONSQUEEZY_VARIANT_ID_WEEKLY,
    "monthly": LEMONSQUEEZY_VARIANT_ID_MONTHLY,
}


def is_lemon_squeezy_enabled() -> bool:
    if not LEMONSQUEEZY_API_KEY or not LEMONSQUEEZY_STORE_ID:
        return False
    return bool(LEMONSQUEEZY_VARIANT_ID_WEEKLY or LEMONSQUEEZY_VARIANT_ID_MONTHLY)


def billing_plans_public() -> list[dict]:
    plans = []
    if LEMONSQUEEZY_VARIANT_ID_WEEKLY:
        plans.append({"id": "weekly", "label": "Weekly"})
    if LEMONSQUEEZY_VARIANT_ID_MONTHLY:
        plans.append({"id": "monthly", "label": "Monthly"})
    return plans


def verify_webhook_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    if not LEMONSQUEEZY_WEBHOOK_SECRET:
        allow_insecure = os.getenv("ALLOW_INSECURE_WEBHOOKS", "false").lower() == "true"
        if allow_insecure:
            logger.warning("Lemon Squeezy webhook not verified (ALLOW_INSECURE_WEBHOOKS=true)")
            return True
        return False
    if not signature_header:
        return False
    digest = hmac.new(
        LEMONSQUEEZY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, signature_header.strip())


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def subscription_expires_from_attributes(attrs: dict) -> Optional[datetime]:
    """Best-effort expiry for active/cancelled subs."""
    status = (attrs.get("status") or "").lower()
    renews_at = _parse_iso8601(attrs.get("renews_at"))
    ends_at = _parse_iso8601(attrs.get("ends_at"))
    if status in ("expired",):
        return ends_at or renews_at
    if status in ("cancelled", "paused"):
        return ends_at or renews_at
    if status in ("active", "on_trial", "past_due", "unpaid"):
        return renews_at or ends_at
    return ends_at or renews_at


def is_active_subscription_status(status: str) -> bool:
    return (status or "").lower() in ("active", "on_trial", "past_due")


async def create_checkout_url(
    *,
    plan: str,
    user_id: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
) -> str:
    variant_id = PLAN_VARIANTS.get(plan)
    if not variant_id:
        raise ValueError(f"Unknown or unconfigured plan: {plan}")

    checkout_data: dict[str, Any] = {
        "custom": {"user_id": str(user_id)},
    }
    if email:
        checkout_data["email"] = email
    if name:
        checkout_data["name"] = name

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_options": {"embed": False, "media": True, "logo": True},
                "checkout_data": checkout_data,
                "product_options": {
                    "redirect_url": LEMONSQUEEZY_CHECKOUT_REDIRECT_URL,
                },
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": str(LEMONSQUEEZY_STORE_ID)}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_BASE}/checkouts",
            json=payload,
            headers={
                "Authorization": f"Bearer {LEMONSQUEEZY_API_KEY}",
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json",
            },
        )
        resp.raise_for_status()
        body = resp.json()

    url = (body.get("data") or {}).get("attributes", {}).get("url")
    if not url:
        raise RuntimeError("Lemon Squeezy checkout response missing url")
    return url


async def fetch_subscription(subscription_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{API_BASE}/subscriptions/{subscription_id}",
            headers={
                "Authorization": f"Bearer {LEMONSQUEEZY_API_KEY}",
                "Accept": "application/vnd.api+json",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def customer_portal_url(subscription_id: str) -> Optional[str]:
    if not subscription_id or not LEMONSQUEEZY_API_KEY:
        return None
    try:
        body = await fetch_subscription(subscription_id)
        urls = (body.get("data") or {}).get("attributes", {}).get("urls") or {}
        return urls.get("customer_portal") or urls.get("update_payment_method")
    except Exception as exc:
        logger.warning("Lemon Squeezy portal lookup failed for %s: %s", subscription_id, exc)
        return None


def extract_user_id_from_webhook(payload: dict) -> Optional[str]:
    meta = payload.get("meta") or {}
    custom = meta.get("custom_data") or {}
    uid = custom.get("user_id") or custom.get("laro_user_id")
    if uid:
        return str(uid).strip()
    return None
