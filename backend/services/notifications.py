"""
Unified Notification Service - Handles both Email and Push notifications

Usage:
    from services.notifications import notify_user, NotificationType

    await notify_user(
        user_id="abc123",
        notification_type=NotificationType.TRIAL_ENDING,
        data={"days_left": 3}
    )
"""
import os
import logging
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)

# Firebase Cloud Messaging v1 API
FCM_PROJECT_ID = "laro-be102"
FCM_V1_URL = f"https://fcm.googleapis.com/v1/projects/{FCM_PROJECT_ID}/messages:send"
FCM_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]

# Load service account credentials for FCM v1 API
_fcm_credentials = None
_fcm_load_error = None  # Store last load error for diagnostics

def _normalize_pem_key(raw: str) -> str:
    """Rebuild a clean PEM private key from potentially mangled input.

    Env var systems can mangle the key in many ways: literal \\n instead of
    newlines, stripped newlines, extra whitespace, \\r\\n line endings, etc.
    This extracts the raw base64 and rebuilds a properly formatted PEM.
    """
    import re
    if not raw or not raw.strip():
        return raw

    # Replace literal \n / \r text and actual \r with nothing/newlines
    cleaned = raw.replace("\\n", "\n").replace("\\r", "").replace("\r", "")

    # Strip PEM header/footer and all whitespace to get pure base64
    cleaned = cleaned.replace("-----BEGIN PRIVATE KEY-----", "")
    cleaned = cleaned.replace("-----END PRIVATE KEY-----", "")
    cleaned = re.sub(r'\s+', '', cleaned)

    if not cleaned:
        logger.warning("Firebase private_key was empty after stripping PEM headers")
        return raw

    # Rebuild PEM with proper 64-char line wrapping
    lines = [cleaned[i:i+64] for i in range(0, len(cleaned), 64)]
    pem = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
    logger.info(f"Firebase private_key normalized ({len(cleaned)} base64 chars)")
    return pem


def _get_fcm_credentials():
    """Load and cache Firebase service account credentials."""
    global _fcm_credentials, _fcm_load_error
    if _fcm_credentials is not None:
        return _fcm_credentials

    try:
        from google.oauth2 import service_account
        import json

        # Try file first (most reliable), then env var as fallback
        sa_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        if not sa_path:
            for candidate in [
                Path(__file__).parent.parent / "firebase-service-account.json",
                Path("/data/firebase-service-account.json"),  # Docker/HA addon
            ]:
                if candidate.exists():
                    sa_path = str(candidate)
                    break

        if sa_path and Path(sa_path).exists():
            _fcm_credentials = service_account.Credentials.from_service_account_file(
                sa_path, scopes=FCM_SCOPES
            )
            logger.info(f"Firebase service account loaded from file: {sa_path}")
            return _fcm_credentials

        # Fallback: JSON content passed as env var
        sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if sa_json:
            _fcm_load_error = None
            # Strip surrounding quotes/whitespace that Railway may add
            sa_json = sa_json.strip().strip("'").strip('"').strip()
            logger.debug(f"Firebase env var first 20 chars: {repr(sa_json[:20])}")
            try:
                info = json.loads(sa_json)
            except json.JSONDecodeError:
                # Try fixing escaped newlines
                sa_json_fixed = sa_json.replace('\n', '\\n').replace('\r', '\\r')
                try:
                    info = json.loads(sa_json_fixed)
                except json.JSONDecodeError:
                    # Last resort: try treating as single-quoted JSON (replace ' with ")
                    sa_json_fixed2 = sa_json.replace("'", '"')
                    info = json.loads(sa_json_fixed2)

            info["private_key"] = _normalize_pem_key(info.get("private_key", ""))

            _fcm_credentials = service_account.Credentials.from_service_account_info(
                info, scopes=FCM_SCOPES
            )
            logger.info("Firebase service account loaded from env var")
            return _fcm_credentials

        _fcm_load_error = "No service account file found and FIREBASE_SERVICE_ACCOUNT_JSON env var not set"
        logger.warning("Firebase service account not found — push notifications disabled")
    except Exception as e:
        _fcm_load_error = f"{type(e).__name__}: {e}"
        logger.error(f"Failed to load Firebase credentials: {e}")

    return _fcm_credentials


def get_fcm_diagnostics() -> dict:
    """Return diagnostic info about FCM credential loading."""
    import json as _json
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    diag = {
        "fcm_code_version": 3,  # bump this to confirm deployment
        "env_var_set": sa_json is not None,
        "env_var_length": len(sa_json) if sa_json else 0,
        "credentials_loaded": _fcm_credentials is not None,
        "load_error": _fcm_load_error,
    }
    # Add private key format hints for debugging PEM errors
    if sa_json:
        try:
            info = _json.loads(sa_json)
            pk = info.get("private_key", "")
            diag["pk_starts_with"] = pk[:30] + "..." if len(pk) > 30 else pk
            diag["pk_has_literal_backslash_n"] = "\\n" in pk
            diag["pk_has_real_newlines"] = "\n" in pk and "\\n" not in pk
            diag["pk_length"] = len(pk)
        except Exception:
            diag["pk_parse_error"] = True
    return diag


def _get_fcm_access_token() -> Optional[str]:
    """Get a valid OAuth2 access token for FCM v1 API."""
    creds = _get_fcm_credentials()
    if not creds:
        return None

    try:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        return creds.token
    except Exception as e:
        logger.error(f"Failed to refresh FCM access token: {e}")
        return None

# Import email functions
try:
    from services.email import (
        send_subscription_welcome_email,
        send_billing_issue_email,
        send_subscription_expired_email,
        send_subscription_cancelled_email,
        is_email_configured
    )
    EMAIL_ENABLED = is_email_configured()
except ImportError:
    EMAIL_ENABLED = False


class NotificationType(str, Enum):
    # Subscription
    SUBSCRIPTION_WELCOME = "subscription_welcome"
    TRIAL_ENDING = "trial_ending"
    BILLING_ISSUE = "billing_issue"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    RENEWAL_REMINDER = "renewal_reminder"

    # Engagement
    INACTIVE_USER = "inactive_user"
    WEEKLY_DIGEST = "weekly_digest"
    MILESTONE = "milestone"
    STREAK = "streak"  # Cooking streak

    # Social
    REFERRAL_SUCCESS = "referral_success"
    HOUSEHOLD_INVITE = "household_invite"
    HOUSEHOLD_JOINED = "household_joined"  # Someone joined your household
    RECIPE_SHARED = "recipe_shared"
    COOKBOOK_UPDATED = "cookbook_updated"  # New recipe in shared cookbook

    # Shopping
    SHOPPING_LIST_UPDATED = "shopping_list_updated"  # Household member added items
    SHOPPING_REMINDER = "shopping_reminder"  # Reminder to shop

    # App
    IMPORT_COMPLETE = "import_complete"
    MEAL_REMINDER = "meal_reminder"
    EXPIRY_ALERT = "expiry_alert"
    AI_COMPLETE = "ai_complete"  # AI task finished (meal plan, etc.)

    # Security
    NEW_LOGIN = "new_login"
    PASSWORD_CHANGED = "password_changed"

    # Custom (for admin testing)
    CUSTOM = "custom"


# Notification templates - defines what each notification type sends
NOTIFICATION_TEMPLATES = {
    NotificationType.SUBSCRIPTION_WELCOME: {
        "title": "Welcome to Laro Pro! 🎉",
        "body": "You now have access to all premium features. Start cooking!",
        "email_func": "send_subscription_welcome_email",
        "push": True,
        "email": True
    },
    NotificationType.TRIAL_ENDING: {
        "title": "Your trial ends in {days_left} days",
        "body": "Subscribe now to keep your premium features!",
        "email_func": None,  # TODO: implement
        "push": True,
        "email": True
    },
    NotificationType.BILLING_ISSUE: {
        "title": "Payment issue ⚠️",
        "body": "Please update your payment method to keep Pro features.",
        "email_func": "send_billing_issue_email",
        "push": True,
        "email": True
    },
    NotificationType.SUBSCRIPTION_EXPIRED: {
        "title": "Your Pro subscription has ended",
        "body": "We miss you! Resubscribe to get premium features back.",
        "email_func": "send_subscription_expired_email",
        "push": True,
        "email": True
    },
    NotificationType.SUBSCRIPTION_CANCELLED: {
        "title": "Subscription cancelled",
        "body": "You can resubscribe anytime in the app.",
        "email_func": "send_subscription_cancelled_email",
        "push": False,  # Don't push for cancellation
        "email": True
    },
    NotificationType.RENEWAL_REMINDER: {
        "title": "Subscription renewing soon",
        "body": "Your Pro subscription renews in {days_left} days.",
        "email_func": None,
        "push": True,
        "email": True
    },
    NotificationType.INACTIVE_USER: {
        "title": "We miss you! 💚",
        "body": "You have {recipe_count} recipes waiting. Come back and cook something delicious!",
        "email_func": None,
        "push": True,
        "email": True
    },
    NotificationType.WEEKLY_DIGEST: {
        "title": "Your weekly meal inspiration 🍽️",
        "body": "Check out this week's recipe suggestions!",
        "email_func": None,
        "push": True,
        "email": True
    },
    NotificationType.MILESTONE: {
        "title": "Milestone reached! 🏆",
        "body": "You've saved {count} recipes! Keep cooking!",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.REFERRAL_SUCCESS: {
        "title": "Your friend joined! 🎉",
        "body": "{friend_name} just signed up using your referral code!",
        "email_func": None,
        "push": True,
        "email": True
    },
    NotificationType.HOUSEHOLD_INVITE: {
        "title": "You've been invited!",
        "body": "{inviter_name} invited you to join their household.",
        "email_func": None,
        "push": True,
        "email": True
    },
    NotificationType.RECIPE_SHARED: {
        "title": "New recipe shared with you",
        "body": "{sharer_name} shared '{recipe_name}' with you!",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.IMPORT_COMPLETE: {
        "title": "Recipe imported! ✅",
        "body": "'{recipe_name}' has been added to your collection.",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.MEAL_REMINDER: {
        "title": "Time to cook! 🍳",
        "body": "'{recipe_name}' is on your meal plan for today.",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.EXPIRY_ALERT: {
        "title": "Ingredient expiring soon",
        "body": "{item_name} expires in {days_left} days. Time to use it!",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.STREAK: {
        "title": "🔥 {streak_days} day streak!",
        "body": "You've been cooking for {streak_days} days in a row. Keep it up!",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.HOUSEHOLD_JOINED: {
        "title": "New household member!",
        "body": "{member_name} just joined your household.",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.COOKBOOK_UPDATED: {
        "title": "New recipe in {cookbook_name}",
        "body": "{sharer_name} added '{recipe_name}' to {cookbook_name}.",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.SHOPPING_LIST_UPDATED: {
        "title": "Shopping list updated",
        "body": "{member_name} added {item_count} items to the shopping list.",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.SHOPPING_REMINDER: {
        "title": "Time to shop! 🛒",
        "body": "You have {item_count} items on your shopping list.",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.AI_COMPLETE: {
        "title": "✨ {task_type} ready!",
        "body": "Your {task_type} has been generated and is ready to view.",
        "email_func": None,
        "push": True,
        "email": False
    },
    NotificationType.NEW_LOGIN: {
        "title": "New login detected",
        "body": "New login from {device} in {location}.",
        "email_func": None,
        "push": True,
        "email": True
    },
    NotificationType.PASSWORD_CHANGED: {
        "title": "Password changed",
        "body": "Your password was changed. If this wasn't you, contact support.",
        "email_func": None,
        "push": True,
        "email": True
    },
    NotificationType.CUSTOM: {
        "title": "{title}",
        "body": "{body}",
        "email_func": None,
        "push": True,
        "email": False
    }
}


async def send_push_notification(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None
) -> bool:
    """Send a push notification via Firebase Cloud Messaging v1 API"""
    if not fcm_token:
        return False

    access_token = _get_fcm_access_token()
    if not access_token:
        logger.warning("No FCM access token available — push not sent")
        return False

    # FCM v1 API payload format
    # Data values must all be strings
    str_data = {k: str(v) for k, v in (data or {}).items()}

    payload = {
        "message": {
            "token": fcm_token,
            "notification": {
                "title": title,
                "body": body
            },
            "data": str_data,
            "android": {
                "notification": {
                    "sound": "default",
                    "channel_id": "laro_notifications"
                }
            }
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(FCM_V1_URL, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"Push sent: {title}")
                return True
            else:
                error_body = response.text
                logger.error(f"FCM v1 error {response.status_code}: {error_body}")
                return False
    except Exception as e:
        logger.error(f"Push notification error: {e}")
        return False


# Map notification types to user preference fields
NOTIFICATION_PREFERENCE_MAP = {
    # Subscription
    NotificationType.SUBSCRIPTION_WELCOME: "subscription_alerts",
    NotificationType.TRIAL_ENDING: "subscription_alerts",
    NotificationType.BILLING_ISSUE: "subscription_alerts",
    NotificationType.SUBSCRIPTION_EXPIRED: "subscription_alerts",
    NotificationType.SUBSCRIPTION_CANCELLED: "subscription_alerts",
    NotificationType.RENEWAL_REMINDER: "subscription_alerts",

    # Engagement
    NotificationType.INACTIVE_USER: "weekly_digest",
    NotificationType.WEEKLY_DIGEST: "weekly_digest",
    NotificationType.MILESTONE: "milestone_notifications",
    NotificationType.STREAK: "streak_notifications",

    # Social
    NotificationType.REFERRAL_SUCCESS: "household_updates",
    NotificationType.HOUSEHOLD_INVITE: "household_updates",
    NotificationType.HOUSEHOLD_JOINED: "household_updates",
    NotificationType.RECIPE_SHARED: "recipe_shared",
    NotificationType.COOKBOOK_UPDATED: "cookbook_updates",

    # Shopping
    NotificationType.SHOPPING_LIST_UPDATED: "shopping_list_updates",
    NotificationType.SHOPPING_REMINDER: "shopping_reminders",

    # App
    NotificationType.IMPORT_COMPLETE: "import_complete",
    NotificationType.MEAL_REMINDER: "meal_reminders",
    NotificationType.EXPIRY_ALERT: "expiry_alerts",
    NotificationType.AI_COMPLETE: "ai_complete",

    # Security (always on by default)
    NotificationType.NEW_LOGIN: "security_alerts",
    NotificationType.PASSWORD_CHANGED: "security_alerts",

    # Custom (always allowed)
    NotificationType.CUSTOM: None
}


async def get_user_notification_preferences(user_id: str) -> Dict[str, bool]:
    """Get user's notification preferences from database"""
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mobile_notification_settings WHERE user_id = $1",
            user_id
        )

    if not row:
        # Return defaults (all enabled)
        return {
            "push_enabled": True,
            "email_enabled": True,
            "subscription_alerts": True,
            "weekly_digest": True,
            "streak_notifications": True,
            "milestone_notifications": True,
            "household_updates": True,
            "recipe_shared": True,
            "cookbook_updates": True,
            "shopping_list_updates": True,
            "shopping_reminders": True,
            "meal_reminders": True,
            "expiry_alerts": True,
            "import_complete": True,
            "ai_complete": True,
            "security_alerts": True,
            "fcm_token": None
        }

    return dict(row)


async def notify_user(
    user_id: str,
    notification_type: NotificationType,
    data: Optional[Dict[str, Any]] = None,
    force_email: bool = False,
    force_push: bool = False,
    ignore_preferences: bool = False
) -> Dict[str, bool]:
    """
    Send a notification to a user via appropriate channels.

    Args:
        user_id: The user's ID
        notification_type: Type of notification to send
        data: Dynamic data for the notification (e.g., {"days_left": 3})
        force_email: Send email even if template says not to
        force_push: Send push even if template says not to
        ignore_preferences: Bypass user preferences (for critical notifications)

    Returns:
        Dict with "email_sent" and "push_sent" booleans
    """
    from dependencies import user_repository
    from database.connection import get_db

    result = {"email_sent": False, "push_sent": False, "skipped_preference": False}
    data = data or {}

    # Get template
    template = NOTIFICATION_TEMPLATES.get(notification_type)
    if not template:
        logger.error(f"Unknown notification type: {notification_type}")
        return result

    # Get user info
    user = await user_repository.find_by_id(user_id)
    if not user:
        logger.error(f"User not found: {user_id}")
        return result

    user_email = user.get("email")
    user_name = user.get("name", "there")

    # Get user preferences
    prefs = await get_user_notification_preferences(user_id)

    # Check if user has disabled this notification type
    pref_field = NOTIFICATION_PREFERENCE_MAP.get(notification_type)
    if pref_field and not ignore_preferences:
        if not prefs.get(pref_field, True):
            logger.info(f"User {user_id} has disabled {pref_field}, skipping {notification_type}")
            result["skipped_preference"] = True
            return result

    # Format title and body with data
    try:
        title = template["title"].format(**data) if data else template["title"]
        body = template["body"].format(**data) if data else template["body"]
    except KeyError as e:
        logger.error(f"Missing data for notification template: {e}")
        title = template["title"]
        body = template["body"]

    # Check master email toggle
    email_allowed = prefs.get("email_enabled", True) or force_email or ignore_preferences

    # Send email if enabled for this notification type
    if (template["email"] or force_email) and EMAIL_ENABLED and user_email and email_allowed:
        email_func_name = template.get("email_func")
        if email_func_name:
            # Use specific email function
            email_func = globals().get(email_func_name)
            if email_func:
                try:
                    await email_func(to=user_email, name=user_name, **data)
                    result["email_sent"] = True
                except Exception as e:
                    logger.error(f"Email send error: {e}")
        else:
            # TODO: Generic email template
            logger.info(f"No email function for {notification_type}, skipping email")

    # Check master push toggle
    push_allowed = prefs.get("push_enabled", True) or force_push or ignore_preferences

    # Send push if enabled for this notification type
    if (template["push"] or force_push) and push_allowed:
        fcm_token = prefs.get("fcm_token")

        if fcm_token:
            push_result = await send_push_notification(
                fcm_token=fcm_token,
                title=title,
                body=body,
                data={"type": notification_type.value, **data}
            )
            result["push_sent"] = push_result

    logger.info(f"Notification {notification_type} to {user_id}: email={result['email_sent']}, push={result['push_sent']}")
    return result


async def notify_users_bulk(
    user_ids: list,
    notification_type: NotificationType,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, int]:
    """Send notification to multiple users"""
    results = {"total": len(user_ids), "email_sent": 0, "push_sent": 0, "failed": 0}

    for user_id in user_ids:
        try:
            result = await notify_user(user_id, notification_type, data)
            if result["email_sent"]:
                results["email_sent"] += 1
            if result["push_sent"]:
                results["push_sent"] += 1
        except Exception as e:
            logger.error(f"Failed to notify {user_id}: {e}")
            results["failed"] += 1

    return results
