"""
Subscriptions Router - Handle subscription status and RevenueCat webhooks
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Header
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

# RevenueCat webhook secret (set in environment)
REVENUECAT_WEBHOOK_SECRET = os.getenv("REVENUECAT_WEBHOOK_SECRET", "")


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
            except:
                is_active = True  # If can't parse, assume active
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
    x_revenuecat_signature: Optional[str] = Header(None, alias="X-RevenueCat-Signature")
):
    """
    Handle RevenueCat webhook events

    Events handled:
    - INITIAL_PURCHASE: New subscription
    - RENEWAL: Subscription renewed
    - CANCELLATION: Subscription cancelled
    - EXPIRATION: Subscription expired
    - BILLING_ISSUE: Payment failed
    """
    body = await request.body()

    # Verify webhook signature if secret is configured
    if REVENUECAT_WEBHOOK_SECRET and x_revenuecat_signature:
        expected_sig = hmac.new(
            REVENUECAT_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, x_revenuecat_signature):
            logger.warning("Invalid RevenueCat webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = await request.json()
        event = data.get("event", {})
        event_type = event.get("type", "")
        app_user_id = event.get("app_user_id", "")

        logger.info(f"RevenueCat webhook: {event_type} for user {app_user_id}")

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

        # Handle different event types
        if event_type in ["INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION"]:
            # Grant premium access
            expiration = event.get("expiration_at_ms")
            expires_at = None
            if expiration:
                expires_at = datetime.fromtimestamp(expiration / 1000, tz=timezone.utc)

            await user_repository.update_user(user_id, {
                "subscription_status": "premium",
                "subscription_expires": expires_at.isoformat() if expires_at else None,
                "subscription_source": "revenuecat"
            })
            logger.info(f"Granted premium to user {user_id} until {expires_at}")

        elif event_type in ["EXPIRATION", "BILLING_ISSUE"]:
            # Subscription expired or payment failed
            await user_repository.update_user(user_id, {
                "subscription_status": "expired",
                "subscription_source": "revenuecat"
            })
            logger.info(f"Subscription expired for user {user_id}")

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
                else:
                    await user_repository.update_user(user_id, {
                        "subscription_status": "free",
                        "subscription_expires": None
                    })
            logger.info(f"Subscription cancelled for user {user_id}")

        return {"status": "ok"}

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
