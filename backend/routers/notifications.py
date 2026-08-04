from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from dependencies import get_current_user, push_subscription_repository, notification_settings_repository
from models import MobileNotificationSettingsUpdate, MobileNotificationSettingsResponse
from datetime import datetime, timezone
import uuid

# Import for mobile notification settings
from database.connection import get_db

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.post("/subscribe")
async def subscribe_push(subscription: dict, user: dict = Depends(get_current_user)):
    """Subscribe to push notifications"""
    sub_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "subscription": subscription,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # Upsert - update if exists, insert if not
    await push_subscription_repository.upsert(
        {"user_id": user["id"]},
        sub_doc
    )

    return {"message": "Subscribed to notifications"}

@router.get("/settings")
async def get_notification_settings(user: dict = Depends(get_current_user)):
    """Get notification preferences"""
    settings = await notification_settings_repository.find_by_user(user["id"])

    if not settings:
        settings = {
            "enabled": False,
            "meal_reminders": True,
            "reminder_time": 30,  # minutes before meal
            "shopping_reminders": True,
            "weekly_plan_reminder": True
        }

    # Remove internal fields
    settings.pop("user_id", None)
    return settings

@router.put("/settings")
async def update_notification_settings(settings: dict, user: dict = Depends(get_current_user)):
    """Update notification preferences"""
    # Remove user_id if passed in settings to avoid overwriting
    settings.pop("user_id", None)

    await notification_settings_repository.upsert_settings(user["id"], settings)

    return {"message": "Settings updated"}


# =============================================================================
# MOBILE NOTIFICATION SETTINGS (FCM/APNs)
# =============================================================================

@router.get("/mobile", response_model=MobileNotificationSettingsResponse)
async def get_mobile_notification_settings(user: dict = Depends(get_current_user)):
    """Get mobile push notification settings including all notification preferences"""
    pool = await get_db()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mobile_notification_settings WHERE user_id = $1",
            user["id"]
        )

    if not row:
        # Return defaults if no settings exist (all notifications enabled)
        return MobileNotificationSettingsResponse(
            user_id=user["id"],
            fcm_token=None,
            apns_token=None,
            reminder_time="17:00",
            push_enabled=True,
            email_enabled=True,
            subscription_alerts=True,
            weekly_digest=True,
            streak_notifications=True,
            milestone_notifications=True,
            household_updates=True,
            recipe_shared=True,
            cookbook_updates=True,
            shopping_list_updates=True,
            shopping_reminders=True,
            meal_reminders=True,
            expiry_alerts=True,
            import_complete=True,
            ai_complete=True,
            security_alerts=True,
            updated_at=None
        )

    data = dict(row)
    return MobileNotificationSettingsResponse(
        user_id=data["user_id"],
        fcm_token=data.get("fcm_token"),
        apns_token=data.get("apns_token"),
        reminder_time=data.get("reminder_time", "17:00"),
        # Master toggles
        push_enabled=data.get("push_enabled", True),
        email_enabled=data.get("email_enabled", True),
        # Subscription
        subscription_alerts=data.get("subscription_alerts", True),
        # Engagement
        weekly_digest=data.get("weekly_digest", True),
        streak_notifications=data.get("streak_notifications", True),
        milestone_notifications=data.get("milestone_notifications", True),
        # Social
        household_updates=data.get("household_updates", True),
        recipe_shared=data.get("recipe_shared", True),
        cookbook_updates=data.get("cookbook_updates", True),
        # Shopping
        shopping_list_updates=data.get("shopping_list_updates", True),
        shopping_reminders=data.get("shopping_reminders", True),
        # App
        meal_reminders=data.get("meal_reminders", True),
        expiry_alerts=data.get("expiry_alerts", True),
        import_complete=data.get("import_complete", True),
        ai_complete=data.get("ai_complete", True),
        # Security
        security_alerts=data.get("security_alerts", True),
        updated_at=str(data.get("updated_at")) if data.get("updated_at") else None
    )


@router.put("/mobile", response_model=MobileNotificationSettingsResponse)
async def update_mobile_notification_settings(
    settings: MobileNotificationSettingsUpdate,
    user: dict = Depends(get_current_user)
):
    """Update mobile push notification settings (including FCM token)"""
    pool = await get_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Build update data
    update_fields = {"updated_at": now}
    for field, value in settings.model_dump().items():
        if value is not None:
            update_fields[field] = value

    async with pool.acquire() as conn:
        # Check if settings exist
        existing = await conn.fetchrow(
            "SELECT user_id FROM mobile_notification_settings WHERE user_id = $1",
            user["id"]
        )

        if existing:
            # Update existing settings
            set_clauses = []
            values = []
            param_count = 1

            for field, value in update_fields.items():
                set_clauses.append(f"{field} = ${param_count}")
                values.append(value)
                param_count += 1

            values.append(user["id"])
            query = f"""
                UPDATE mobile_notification_settings
                SET {', '.join(set_clauses)}
                WHERE user_id = ${param_count}
            """
            await conn.execute(query, *values)
        else:
            # Insert new settings
            update_fields["user_id"] = user["id"]
            columns = ", ".join(update_fields.keys())
            placeholders = ", ".join([f"${i+1}" for i in range(len(update_fields))])
            values = list(update_fields.values())

            query = f"""
                INSERT INTO mobile_notification_settings ({columns})
                VALUES ({placeholders})
            """
            await conn.execute(query, *values)

    return await get_mobile_notification_settings(user)


class FcmTokenRequest(BaseModel):
    token: str

@router.post("/fcm-token")
async def register_fcm_token(
    body: FcmTokenRequest,
    user: dict = Depends(get_current_user)
):
    """Register or update FCM token for push notifications."""
    fcm_token = body.token

    pool = await get_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT user_id FROM mobile_notification_settings WHERE user_id = $1",
            user["id"]
        )

        if existing:
            await conn.execute(
                "UPDATE mobile_notification_settings SET fcm_token = $1, updated_at = $2 WHERE user_id = $3",
                fcm_token, now, user["id"]
            )
        else:
            await conn.execute(
                """INSERT INTO mobile_notification_settings
                   (user_id, fcm_token, meal_reminders, expiry_alerts, shopping_list_updates, import_complete, reminder_time, updated_at)
                   VALUES ($1, $2, true, true, true, true, '17:00', $3)""",
                user["id"], fcm_token, now
            )

    return {"message": "FCM token registered", "user_id": user["id"]}


@router.delete("/fcm-token")
async def remove_fcm_token(user: dict = Depends(get_current_user)):
    """Remove FCM token (disable push notifications for this device)"""
    pool = await get_db()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE mobile_notification_settings SET fcm_token = NULL, updated_at = $1 WHERE user_id = $2",
            now, user["id"]
        )

    return {"message": "FCM token removed"}
