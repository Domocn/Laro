"""
Subscriptions Router - status, Lemon Squeezy checkout/webhooks, RevenueCat legacy webhooks
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Header, BackgroundTasks
from dependencies import get_current_user, user_repository
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone, timedelta
import logging
import hmac
import hashlib
import os
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

# RevenueCat webhook authentication (set in environment)
# Use REVENUECAT_WEBHOOK_AUTH for Authorization header (e.g., "Bearer your_secret")
# Or REVENUECAT_WEBHOOK_SECRET for HMAC signature verification
REVENUECAT_WEBHOOK_AUTH = os.getenv("REVENUECAT_WEBHOOK_AUTH", "")
REVENUECAT_WEBHOOK_SECRET = os.getenv("REVENUECAT_WEBHOOK_SECRET", "")

# Unified notification service
try:
    from services.notifications import notify_user, NotificationType
    NOTIFICATIONS_ENABLED = True
except ImportError:
    NOTIFICATIONS_ENABLED = False
    async def notify_user(*args, **kwargs):
        return {"email_sent": False, "push_sent": False}


class SubscriptionStatus(BaseModel):
    status: str  # free, trial, premium, expired
    expires_at: Optional[str] = None
    source: Optional[str] = None
    is_active: bool = False
    is_lifetime: bool = False
    is_owner: bool = False


def _billing_provider_preference() -> str:
    return (os.getenv("LARO_BILLING_PROVIDER") or "revenuecat").strip().lower()


@router.get("/billing-config")
async def get_billing_config(user: dict = Depends(get_current_user)):
    """
    Checkout provider for the web app.
    Default: RevenueCat Web (configure Paddle or RC Billing in the RC dashboard).
    Optional: LARO_BILLING_PROVIDER=lemonsqueezy for direct Lemon Squeezy checkout.
    """
    from services import lemonsqueezy as ls
    from services.lemonsqueezy import is_lemon_squeezy_enabled

    pref = _billing_provider_preference()
    if pref == "lemonsqueezy" and is_lemon_squeezy_enabled():
        return {
            "provider": "lemonsqueezy",
            "plans": ls.billing_plans_public(),
        }

    engine = (os.getenv("LARO_RC_WEB_BILLING_ENGINE") or "paddle").strip().lower()
    if engine not in ("paddle", "rc_billing", "stripe"):
        engine = "paddle"

    return {
        "provider": "revenuecat",
        "engine": engine,
        "plans": [
            {"id": "weekly", "label": "Weekly"},
            {"id": "monthly", "label": "Monthly"},
        ],
    }


class CheckoutRequest(BaseModel):
    plan: Literal["weekly", "monthly"] = Field(..., description="Laro Pro plan id")


@router.post("/checkout")
async def create_billing_checkout(
    body: CheckoutRequest,
    user: dict = Depends(get_current_user),
):
    """Create a Lemon Squeezy checkout URL bound to the logged-in Laro user."""
    from services.lemonsqueezy import create_checkout_url, is_lemon_squeezy_enabled

    if not is_lemon_squeezy_enabled():
        raise HTTPException(status_code=503, detail="Lemon Squeezy billing is not configured")
    try:
        url = await create_checkout_url(
            plan=body.plan,
            user_id=str(user["id"]),
            email=user.get("email"),
            name=user.get("name"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Lemon Squeezy checkout failed")
        raise HTTPException(status_code=502, detail="Could not create checkout") from e
    return {"url": url, "provider": "lemonsqueezy"}


@router.get("/customer-portal")
async def get_customer_portal(user: dict = Depends(get_current_user)):
    """Lemon Squeezy customer portal for manage/cancel (when subscribed via LS)."""
    from services.lemonsqueezy import customer_portal_url, is_lemon_squeezy_enabled

    if not is_lemon_squeezy_enabled():
        raise HTTPException(status_code=503, detail="Billing portal is not configured")
    sub_id = user.get("billing_subscription_id")
    if not sub_id:
        raise HTTPException(status_code=404, detail="No Lemon Squeezy subscription on this account")
    url = await customer_portal_url(str(sub_id))
    if not url:
        raise HTTPException(status_code=502, detail="Could not load billing portal")
    return {"url": url}


@router.get("/status")
async def get_subscription_status(user: dict = Depends(get_current_user)) -> SubscriptionStatus:
    """Get current user's subscription status (includes owner forever Pro)."""
    from utils.subscription import subscription_snapshot

    snap = subscription_snapshot(user)
    return SubscriptionStatus(
        status=snap["status"],
        expires_at=snap["expires_at"],
        source=snap["source"],
        is_active=snap["is_active"],
        is_lifetime=snap["is_lifetime"],
        is_owner=snap["is_owner"],
    )


class RevenueCatEvent(BaseModel):
    """RevenueCat webhook event structure"""
    event: dict
    api_version: str = "1.0"


@router.get("/webhook/revenuecat")
@router.head("/webhook/revenuecat")
async def revenuecat_webhook_health():
    """
    Browser / URL-check probe. RevenueCat delivers events with POST only.
    Opening this URL in a browser used to return 405 Method Not Allowed.
    """
    return {
        "status": "ok",
        "service": "revenuecat-webhook",
        "method": "POST required for events",
        "hint": "Configure RevenueCat → Integrations → Webhooks to POST here with Authorization",
    }


@router.post("/webhook/revenuecat")
async def revenuecat_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    x_revenuecat_signature: Optional[str] = Header(None, alias="X-RevenueCat-Signature")
):
    """
    Handle RevenueCat webhook events

    Events handled:
    - INITIAL_PURCHASE: New subscription
    - RENEWAL: Subscription renewed
    - CANCELLATION: Subscription cancelled (still active until expiry)
    - EXPIRATION: Subscription expired
    - BILLING_ISSUE: Payment failed
    - UNCANCELLATION: User re-enabled auto-renew
    - PRODUCT_CHANGE: User changed subscription tier
    - SUBSCRIBER_ALIAS: Anonymous user identified
    - NON_RENEWING_PURCHASE: One-time purchase (lifetime)
    """
    body = await request.body()

    # Verify webhook - check Authorization header first (RevenueCat UI method)
    if REVENUECAT_WEBHOOK_AUTH:
        if not authorization:
            logger.warning("RevenueCat webhook missing Authorization header")
            raise HTTPException(status_code=401, detail="Missing authorization")
        auth_received = authorization.strip()
        auth_expected = REVENUECAT_WEBHOOK_AUTH.strip()
        if not hmac.compare_digest(auth_received, auth_expected):
            logger.warning("Invalid RevenueCat webhook authorization")
            raise HTTPException(status_code=401, detail="Invalid authorization")
        logger.debug("RevenueCat webhook authorized via Authorization header")
    # Fall back to HMAC signature verification
    elif REVENUECAT_WEBHOOK_SECRET:
        if not x_revenuecat_signature:
            logger.warning("RevenueCat webhook missing signature header")
            raise HTTPException(status_code=401, detail="Missing signature")
        expected_sig = hmac.new(
            REVENUECAT_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, x_revenuecat_signature):
            logger.warning("Invalid RevenueCat webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        # Fail closed outside explicit local insecure mode
        allow_insecure = os.getenv("ALLOW_INSECURE_WEBHOOKS", "false").lower() == "true"
        is_production = bool(
            os.getenv("RAILWAY_ENVIRONMENT")
            or os.getenv("IS_CLOUD", "").lower() == "true"
            or os.getenv("LARO_ENV", "").lower() == "production"
            or not allow_insecure
        )
        if is_production:
            logger.error("RevenueCat webhook rejected: no REVENUECAT_WEBHOOK_AUTH or SECRET configured")
            raise HTTPException(
                status_code=503,
                detail="Webhook authentication is not configured",
            )
        logger.warning("No webhook auth configured - webhook not verified (ALLOW_INSECURE_WEBHOOKS=true)!")

    try:
        data = await request.json()
        event = data.get("event", {})
        event_type = event.get("type", "")
        app_user_id = event.get("app_user_id", "")
        product_id = event.get("product_id", "")

        # Extract additional useful data
        original_app_user_id = event.get("original_app_user_id")  # For alias events
        price_in_purchased_currency = event.get("price_in_purchased_currency")
        currency = event.get("currency")
        store = event.get("store")  # APP_STORE, PLAY_STORE, etc.

        logger.info(f"RevenueCat webhook: {event_type} for user {app_user_id} (product: {product_id})")

        if not app_user_id:
            return {"status": "ok", "message": "No user ID"}

        # Find user by ID (RevenueCat app_user_id should match our user ID)
        user = await user_repository.find_by_id(app_user_id)
        if not user:
            # Try to find by Supabase ID
            user = await user_repository.find_by_supabase_id(app_user_id)

        if not user:
            logger.warning(f"RevenueCat webhook: User not found: {app_user_id}")
            return {"status": "ok", "message": "User not found"}

        user_id = user["id"]
        user_email = user.get("email")
        user_name = user.get("name", "there")

        # Handle different event types
        if event_type == "INITIAL_PURCHASE":
            # New subscription - grant premium access
            expiration = event.get("expiration_at_ms")
            expires_at = None
            if expiration:
                expires_at = datetime.fromtimestamp(expiration / 1000, tz=timezone.utc)

            # Only write columns that exist on users (product_id/store historically
            # caused webhook 500s and left purchases undetected).
            await user_repository.update_user(user_id, {
                "subscription_status": "premium",
                "subscription_expires": expires_at.isoformat() if expires_at else None,
                "subscription_source": "revenuecat",
            })
            logger.info(
                f"Granted premium to user {user_id} until {expires_at} "
                f"(product={product_id}, store={store})"
            )

            try:
                from routers.friends import grant_referrer_reward_for_subscriber
                refreshed = await user_repository.find_by_id(user_id)
                if refreshed:
                    await grant_referrer_reward_for_subscriber(refreshed)
            except Exception as reward_err:
                logger.warning(f"Referral reward failed for {user_id}: {reward_err}")

            # Send welcome notification (email + push)
            if NOTIFICATIONS_ENABLED:
                background_tasks.add_task(
                    notify_user,
                    user_id=user_id,
                    notification_type=NotificationType.SUBSCRIPTION_WELCOME
                )

        elif event_type == "NON_RENEWING_PURCHASE":
            # Lifetime purchase - no expiration
            await user_repository.update_user(user_id, {
                "subscription_status": "premium",
                "subscription_expires": None,  # Lifetime = no expiry
                "subscription_source": "revenuecat",
            })
            logger.info(
                f"Granted lifetime premium to user {user_id} "
                f"(product={product_id}, store={store})"
            )
            try:
                from routers.friends import grant_referrer_reward_for_subscriber
                refreshed = await user_repository.find_by_id(user_id)
                if refreshed:
                    await grant_referrer_reward_for_subscriber(refreshed)
            except Exception as reward_err:
                logger.warning(f"Referral reward failed for {user_id}: {reward_err}")

        elif event_type in ["RENEWAL", "UNCANCELLATION"]:
            # Subscription renewed or re-enabled
            expiration = event.get("expiration_at_ms")
            expires_at = None
            if expiration:
                expires_at = datetime.fromtimestamp(expiration / 1000, tz=timezone.utc)

            await user_repository.update_user(user_id, {
                "subscription_status": "premium",
                "subscription_expires": expires_at.isoformat() if expires_at else None,
                "subscription_source": "revenuecat"
            })
            logger.info(f"Renewed premium for user {user_id} until {expires_at}")

        elif event_type == "PRODUCT_CHANGE":
            # User changed subscription tier (upgrade/downgrade)
            expiration = event.get("expiration_at_ms")
            expires_at = None
            if expiration:
                expires_at = datetime.fromtimestamp(expiration / 1000, tz=timezone.utc)

            await user_repository.update_user(user_id, {
                "subscription_status": "premium",
                "subscription_expires": expires_at.isoformat() if expires_at else None,
                "subscription_source": "revenuecat",
            })
            logger.info(f"User {user_id} changed to product {product_id}")

        elif event_type == "BILLING_ISSUE":
            # Payment failed - notify user but don't immediately revoke
            logger.warning(f"Billing issue for user {user_id}")

            # Send billing issue notification (email + push)
            if NOTIFICATIONS_ENABLED:
                background_tasks.add_task(
                    notify_user,
                    user_id=user_id,
                    notification_type=NotificationType.BILLING_ISSUE
                )

        elif event_type == "EXPIRATION":
            # Subscription expired
            await user_repository.update_user(user_id, {
                "subscription_status": "expired",
                "subscription_source": "revenuecat"
            })
            logger.info(f"Subscription expired for user {user_id}")

            # Send win-back notification (email + push)
            if NOTIFICATIONS_ENABLED:
                background_tasks.add_task(
                    notify_user,
                    user_id=user_id,
                    notification_type=NotificationType.SUBSCRIPTION_EXPIRED
                )

        elif event_type == "CANCELLATION":
            # User cancelled but may still have access until expiry
            expiration = event.get("expiration_at_ms")
            if expiration:
                expires_at = datetime.fromtimestamp(expiration / 1000, tz=timezone.utc)
                if expires_at > datetime.now(timezone.utc):
                    # Still active until expiry
                    await user_repository.update_user(user_id, {
                        "subscription_expires": expires_at.isoformat()
                    })
                    logger.info(f"User {user_id} cancelled, access until {expires_at}")
                else:
                    await user_repository.update_user(user_id, {
                        "subscription_status": "free",
                        "subscription_expires": None
                    })
            else:
                logger.info(f"Subscription cancelled for user {user_id}")

        elif event_type == "SUBSCRIBER_ALIAS":
            # Anonymous user was identified - merge if needed
            if original_app_user_id and original_app_user_id != app_user_id:
                logger.info(f"User alias: {original_app_user_id} -> {app_user_id}")
                # Could merge purchase history here if needed

        return {"status": "ok", "event_type": event_type}

    except Exception as e:
        logger.error(f"RevenueCat webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SyncSubscriptionRequest(BaseModel):
    """Request to sync subscription from RevenueCat"""
    revenuecat_user_id: str
    product_id: Optional[str] = None
    is_active: bool
    expires_at: Optional[str] = None


@router.post("/sync")
async def sync_subscription(
    data: SyncSubscriptionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Sync subscription status from Android/iOS app
    Called by the app after RevenueCat purchase verification
    """
    from utils.subscription import is_app_owner, subscription_snapshot

    # Never overwrite owner forever / admin grants via a free RC sync
    if is_app_owner(user):
        snap = subscription_snapshot(user)
        return {"status": snap["status"], "synced": True, "is_owner": True}

    if data.is_active:
        await user_repository.update_user(user["id"], {
            "subscription_status": "premium",
            "subscription_expires": data.expires_at,
            "subscription_source": "revenuecat"
        })
        try:
            from routers.friends import grant_referrer_reward_for_subscriber
            refreshed = await user_repository.find_by_id(user["id"])
            if refreshed:
                await grant_referrer_reward_for_subscriber(refreshed)
        except Exception as reward_err:
            logger.warning(f"Referral reward failed for {user['id']}: {reward_err}")
        return {"status": "premium", "synced": True}
    else:
        # Only downgrade RevenueCat-sourced subs — preserve admin/owner lifetime
        source = (user.get("subscription_source") or "").lower()
        if source in ("revenuecat", "lemonsqueezy"):
            await user_repository.update_user(user["id"], {
                "subscription_status": "free",
                "subscription_expires": None
            })
            return {"status": "free", "synced": True}
        snap = subscription_snapshot(user)
        return {"status": snap["status"], "synced": True, "preserved": True}


async def _resolve_user_for_lemon_webhook(payload: dict) -> Optional[dict]:
    user_id = None
    try:
        from services.lemonsqueezy import extract_user_id_from_webhook

        user_id = extract_user_id_from_webhook(payload)
    except Exception:
        user_id = None
    if user_id:
        user = await user_repository.find_by_id(user_id)
        if user:
            return user
    attrs = (payload.get("data") or {}).get("attributes") or {}
    email = (attrs.get("user_email") or attrs.get("customer_email") or "").strip().lower()
    if email:
        user = await user_repository.find_by_email(email)
        if user:
            return user
    return None


async def _apply_lemon_subscription(user_id: str, payload: dict, *, grant_referral: bool) -> None:
    from services.lemonsqueezy import (
        is_active_subscription_status,
        subscription_expires_from_attributes,
    )

    data = payload.get("data") or {}
    sub_id = str(data.get("id") or "")
    attrs = data.get("attributes") or {}
    status = (attrs.get("status") or "").lower()
    expires_dt = subscription_expires_from_attributes(attrs)
    expires_iso = expires_dt.isoformat() if expires_dt else None

    if is_active_subscription_status(status):
        await user_repository.update_user(
            user_id,
            {
                "subscription_status": "premium",
                "subscription_expires": expires_iso,
                "subscription_source": "lemonsqueezy",
                "billing_subscription_id": sub_id or None,
            },
        )
        if grant_referral:
            try:
                from routers.friends import grant_referrer_reward_for_subscriber

                refreshed = await user_repository.find_by_id(user_id)
                if refreshed:
                    await grant_referrer_reward_for_subscriber(refreshed)
            except Exception as reward_err:
                logger.warning("Referral reward failed for %s: %s", user_id, reward_err)
        return

    if status == "cancelled" and expires_dt and expires_dt > datetime.now(timezone.utc):
        await user_repository.update_user(
            user_id,
            {
                "subscription_expires": expires_iso,
                "billing_subscription_id": sub_id or None,
                "subscription_source": "lemonsqueezy",
            },
        )
        return

    await user_repository.update_user(
        user_id,
        {
            "subscription_status": "expired" if status == "expired" else "free",
            "subscription_expires": expires_iso,
            "subscription_source": "lemonsqueezy",
            "billing_subscription_id": sub_id or None,
        },
    )


@router.get("/webhook/lemonsqueezy")
@router.head("/webhook/lemonsqueezy")
async def lemonsqueezy_webhook_health():
    return {
        "status": "ok",
        "service": "lemonsqueezy-webhook",
        "method": "POST required for events",
    }


@router.post("/webhook/lemonsqueezy")
async def lemonsqueezy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
):
    from services.lemonsqueezy import verify_webhook_signature

    raw = await request.body()
    if not verify_webhook_signature(raw, x_signature):
        logger.warning("Lemon Squeezy webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON") from e

    event_name = (payload.get("meta") or {}).get("event_name") or ""
    logger.info("Lemon Squeezy webhook: %s", event_name)

    user = await _resolve_user_for_lemon_webhook(payload)
    if not user:
        logger.warning("Lemon Squeezy webhook: user not found for event %s", event_name)
        return {"status": "ok", "message": "User not found"}

    user_id = user["id"]
    grant_events = {
        "subscription_created",
        "subscription_resumed",
        "subscription_unpaused",
        "subscription_payment_success",
        "subscription_payment_recovered",
    }
    update_events = grant_events | {
        "subscription_updated",
        "subscription_cancelled",
        "subscription_expired",
        "subscription_paused",
        "subscription_payment_failed",
    }

    if event_name in update_events:
        await _apply_lemon_subscription(
            user_id,
            payload,
            grant_referral=event_name in grant_events,
        )

        if event_name == "subscription_payment_failed" and NOTIFICATIONS_ENABLED:
            background_tasks.add_task(
                notify_user,
                user_id=user_id,
                notification_type=NotificationType.BILLING_ISSUE,
            )
        if event_name == "subscription_created" and NOTIFICATIONS_ENABLED:
            background_tasks.add_task(
                notify_user,
                user_id=user_id,
                notification_type=NotificationType.SUBSCRIPTION_WELCOME,
            )
        if event_name == "subscription_expired" and NOTIFICATIONS_ENABLED:
            background_tasks.add_task(
                notify_user,
                user_id=user_id,
                notification_type=NotificationType.SUBSCRIPTION_EXPIRED,
            )

    return {"status": "ok", "event": event_name}
