"""
Subscriptions Router - Handle subscription status and RevenueCat webhooks
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Header, BackgroundTasks
from dependencies import get_current_user, user_repository
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import logging
import hmac
import hashlib
import os

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


@router.get("/status")
async def get_subscription_status(user: dict = Depends(get_current_user)) -> SubscriptionStatus:
    """Get current user's subscription status"""
    status = user.get("subscription_status", "free")
    expires_str = user.get("subscription_expires")
    source = user.get("subscription_source")

    # Check if subscription has expired
    is_active = False
    if status in ["premium", "trial"]:
        if expires_str:
            try:
                expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                is_active = expires > datetime.now(timezone.utc)
                if not is_active:
                    status = "expired"
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse subscription expires date '{expires_str}': {e}")
                is_active = True  # If can't parse, assume active for safety
        else:
            is_active = True  # No expiry means lifetime

    return SubscriptionStatus(
        status=status,
        expires_at=expires_str,
        source=source,
        is_active=is_active
    )


class RevenueCatEvent(BaseModel):
    """RevenueCat webhook event structure"""
    event: dict
    api_version: str = "1.0"


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
        logger.info(f"Webhook auth debug: received='{auth_received[:4]}...{auth_received[-4:]}' (len={len(auth_received)}), expected='{auth_expected[:4]}...{auth_expected[-4:]}' (len={len(auth_expected)})")
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
        # No auth configured - log warning but allow (for development only)
        logger.warning("No webhook auth configured - webhook not verified!")

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

            await user_repository.update_user(user_id, {
                "subscription_status": "premium",
                "subscription_expires": expires_at.isoformat() if expires_at else None,
                "subscription_source": "revenuecat",
                "subscription_product_id": product_id,
                "subscription_store": store
            })
            logger.info(f"Granted premium to user {user_id} until {expires_at}")

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
                "subscription_product_id": product_id,
                "subscription_store": store
            })
            logger.info(f"Granted lifetime premium to user {user_id}")

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
                "subscription_product_id": product_id
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
    if data.is_active:
        await user_repository.update_user(user["id"], {
            "subscription_status": "premium",
            "subscription_expires": data.expires_at,
            "subscription_source": "revenuecat"
        })
        return {"status": "premium", "synced": True}
    else:
        # Check if current subscription is from revenuecat before downgrading
        if user.get("subscription_source") == "revenuecat":
            await user_repository.update_user(user["id"], {
                "subscription_status": "free",
                "subscription_expires": None
            })
        return {"status": "free", "synced": True}
