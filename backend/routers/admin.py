"""
Admin Router - User Management, System Settings, Audit Logs, Backups, IP Access Control, Data Export
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Response, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from dependencies import (
    hash_password, get_current_user, create_token,
    user_repository, session_repository, totp_secret_repository, oauth_account_repository,
    system_settings_repository, llm_settings_repository, custom_prompts_repository,
    invite_code_repository, audit_log_repository, backup_repository, backup_settings_repository,
    recipe_repository, meal_plan_repository, shopping_list_repository,
    ip_allowlist_repository, ip_blocklist_repository, login_attempt_repository
)
from datetime import datetime, timezone, timedelta
import uuid
import secrets
import asyncio
import os
import json
import io
import zipfile

router = APIRouter(prefix="/admin", tags=["Admin"])

# =============================================================================
# MODELS
# =============================================================================

class UserListItem(BaseModel):
    id: str
    email: str
    name: str
    role: str
    status: str
    created_at: str
    last_login: Optional[str] = None
    household_id: Optional[str] = None

class UserListResponse(BaseModel):
    users: List[UserListItem]
    total: int
    page: int
    per_page: int

class AdminPasswordReset(BaseModel):
    new_password: str

class UserRoleUpdate(BaseModel):
    role: str  # 'admin' or 'user'

class UserStatusUpdate(BaseModel):
    status: str  # 'active', 'suspended'

class SystemSettingsUpdate(BaseModel):
    allow_registration: Optional[bool] = None
    allow_admin_registration: Optional[bool] = None
    require_invite_code: Optional[bool] = None
    password_min_length: Optional[int] = None
    password_require_uppercase: Optional[bool] = None
    password_require_number: Optional[bool] = None
    password_require_special: Optional[bool] = None
    max_login_attempts: Optional[int] = None
    lockout_duration_minutes: Optional[int] = None
    session_timeout_minutes: Optional[int] = None
    enable_ip_allowlist: Optional[bool] = None
    enable_ip_blocklist: Optional[bool] = None
    notify_new_login: Optional[bool] = None
    auto_backup_enabled: Optional[bool] = None
    auto_backup_interval_hours: Optional[int] = None
    # Sharing settings
    include_links_in_share: Optional[bool] = None  # Include share links in WhatsApp messages

class IPAccessRule(BaseModel):
    ip_pattern: str  # Can be exact IP, CIDR, or wildcard pattern
    description: Optional[str] = None

class InviteCodeCreate(BaseModel):
    max_uses: Optional[int] = 1
    expires_days: Optional[int] = 7
    grants_admin: Optional[bool] = False

class InviteCodeResponse(BaseModel):
    id: str
    code: str
    created_by: str
    max_uses: int
    uses: int
    grants_admin: bool
    expires_at: Optional[str]
    created_at: str

class AuditLogEntry(BaseModel):
    id: str
    user_id: str
    user_email: str
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    details: Optional[dict]
    ip_address: Optional[str]
    timestamp: str

class SystemHealthResponse(BaseModel):
    status: str
    database: dict
    storage: dict
    users: dict
    recipes: dict

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_admin_user(user: dict = Depends(get_current_user)):
    """Dependency to ensure user is admin or super_admin"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_super_admin_user(user: dict = Depends(get_current_user)):
    """Dependency to ensure user is super_admin (app owner)"""
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user

async def log_audit(
    user_id: str,
    user_email: str,
    action: str,
    target_type: str = None,
    target_id: str = None,
    details: dict = None,
    ip_address: str = None
):
    """Log an audit entry"""
    await audit_log_repository.create({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_email": user_email,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details": details,
        "ip_address": ip_address,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

async def get_system_settings():
    """Get current system settings or defaults"""
    return await system_settings_repository.get_settings("global")

# =============================================================================
# USER MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    admin: dict = Depends(get_admin_user)
):
    """List all users with pagination and filtering"""
    users_raw, total = await user_repository.list_users(
        page=page,
        per_page=per_page,
        search=search,
        role=role,
        status=status
    )

    users = []
    for u in users_raw:
        users.append(UserListItem(
            id=u["id"],
            email=u["email"],
            name=u["name"],
            role=u.get("role", "user"),
            status=u.get("status", "active"),
            created_at=u["created_at"],
            last_login=u.get("last_login"),
            household_id=u.get("household_id")
        ))

    return UserListResponse(
        users=users,
        total=total,
        page=page,
        per_page=per_page
    )

@router.get("/users/{user_id}")
async def get_user(user_id: str, admin: dict = Depends(get_admin_user)):
    """Get detailed user info"""
    user = await user_repository.find_by_id(user_id, exclude_password=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user stats
    recipe_count = await recipe_repository.count({"author_id": user_id})

    return {
        **user,
        "stats": {
            "recipes": recipe_count
        }
    }

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    data: UserRoleUpdate,
    admin: dict = Depends(get_admin_user)
):
    """Update user role"""
    valid_roles = ["admin", "user"]

    # Only super_admin can assign super_admin role
    if data.role == "super_admin":
        if admin.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Only super admin can assign super admin role")
        valid_roles.append("super_admin")

    if data.role not in valid_roles:
        raise HTTPException(status_code=400, detail="Invalid role")

    # Prevent self-demotion for last admin/super_admin
    if user_id == admin["id"] and data.role not in ["admin", "super_admin"]:
        admin_count = await user_repository.count({"role": "admin"})
        super_admin_count = await user_repository.count({"role": "super_admin"})
        if admin_count + super_admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove last admin")

    result = await user_repository.update_user(user_id, {"role": data.role})

    if result == 0:
        raise HTTPException(status_code=404, detail="User not found")

    # Log audit
    await log_audit(
        admin["id"], admin["email"], "user_role_change",
        "user", user_id, {"new_role": data.role}
    )

    return {"message": f"User role updated to {data.role}"}

@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    data: UserStatusUpdate,
    admin: dict = Depends(get_admin_user)
):
    """Suspend or activate a user"""
    if data.status not in ["active", "suspended"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Prevent self-suspension
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot change own status")

    result = await user_repository.update_user(user_id, {"status": data.status})

    if result == 0:
        raise HTTPException(status_code=404, detail="User not found")

    # Log audit
    await log_audit(
        admin["id"], admin["email"], f"user_{data.status}",
        "user", user_id
    )

    return {"message": f"User status updated to {data.status}"}

@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    data: AdminPasswordReset,
    admin: dict = Depends(get_admin_user)
):
    """Admin-initiated password reset"""
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = await user_repository.find_by_id(user_id, exclude_password=False)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Hash password in thread pool
    hashed = await asyncio.get_running_loop().run_in_executor(
        None, hash_password, data.new_password
    )

    await user_repository.update_user(user_id, {
        "password": hashed,
        "password_changed_at": datetime.now(timezone.utc).isoformat(),
        "force_password_change": 1
    })

    # Log audit
    await log_audit(
        admin["id"], admin["email"], "admin_password_reset",
        "user", user_id
    )

    return {"message": "Password reset successfully"}

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    permanent: bool = Query(False),
    admin: dict = Depends(get_admin_user)
):
    """Delete a user (soft or permanent)"""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete own account")

    user = await user_repository.find_by_id(user_id, exclude_password=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if permanent:
        # Permanent deletion - remove all user data
        await user_repository.delete_user(user_id)
        await recipe_repository.delete_by_author(user_id)
        await custom_prompts_repository.delete_by_user(user_id)
        await llm_settings_repository.delete_by_user(user_id)
        await session_repository.delete_by_user(user_id)
        await totp_secret_repository.delete_by_user(user_id)

        await log_audit(
            admin["id"], admin["email"], "user_deleted_permanent",
            "user", user_id, {"email": user["email"]}
        )

        return {"message": "User permanently deleted"}
    else:
        # Soft delete - mark as deleted
        await user_repository.update_user(user_id, {
            "status": "deleted",
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "deleted_by": admin["id"]
        })

        await log_audit(
            admin["id"], admin["email"], "user_deleted_soft",
            "user", user_id, {"email": user["email"]}
        )

        return {"message": "User marked as deleted"}

# =============================================================================
# SYSTEM SETTINGS ENDPOINTS
# =============================================================================

@router.get("/settings")
async def get_settings(admin: dict = Depends(get_admin_user)):
    """Get all system settings"""
    settings = await get_system_settings()
    return settings

@router.put("/settings")
async def update_settings(
    data: SystemSettingsUpdate,
    admin: dict = Depends(get_admin_user)
):
    """Update system settings"""
    update_data = {k: v for k, v in data.dict().items() if v is not None}

    if update_data:
        # Get current settings and merge
        current = await system_settings_repository.get_settings("global")
        merged = {**current, **update_data}
        await system_settings_repository.update_settings("global", merged)

        await log_audit(
            admin["id"], admin["email"], "settings_updated",
            "system", "settings", update_data
        )

    return await get_system_settings()

# =============================================================================
# INVITE CODE MANAGEMENT
# =============================================================================

@router.get("/invite-codes")
async def list_invite_codes(admin: dict = Depends(get_admin_user)):
    """List all invite codes"""
    codes = await invite_code_repository.list_all(limit=100)
    return {"codes": codes}

@router.post("/invite-codes")
async def create_invite_code(
    data: InviteCodeCreate,
    admin: dict = Depends(get_admin_user)
):
    """Create a new invite code"""
    code = secrets.token_urlsafe(8).upper()[:8]

    expires_at = None
    if data.expires_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=data.expires_days)).isoformat()

    invite = {
        "id": str(uuid.uuid4()),
        "code": code,
        "created_by": admin["id"],
        "max_uses": data.max_uses,
        "uses": 0,
        "grants_admin": 1 if data.grants_admin else 0,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await invite_code_repository.create(invite)

    await log_audit(
        admin["id"], admin["email"], "invite_code_created",
        "invite_code", invite["id"], {"code": code}
    )

    return invite

@router.delete("/invite-codes/{code_id}")
async def delete_invite_code(code_id: str, admin: dict = Depends(get_admin_user)):
    """Delete an invite code"""
    result = await invite_code_repository.delete_code(code_id)

    if result == 0:
        raise HTTPException(status_code=404, detail="Invite code not found")

    await log_audit(
        admin["id"], admin["email"], "invite_code_deleted",
        "invite_code", code_id
    )

    return {"message": "Invite code deleted"}

# =============================================================================
# AUDIT LOG ENDPOINTS
# =============================================================================

@router.get("/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    admin: dict = Depends(get_admin_user)
):
    """Get audit logs with filtering"""
    logs, total = await audit_log_repository.find_logs(
        user_id=user_id,
        action=action,
        page=page,
        per_page=per_page
    )

    return {
        "logs": logs,
        "total": total,
        "page": page,
        "per_page": per_page
    }

# =============================================================================
# SYSTEM HEALTH & STATS
# =============================================================================

@router.get("/system/health")
async def get_system_health(admin: dict = Depends(get_admin_user)):
    """Get system health and stats"""
    # Database stats - PostgreSQL connection and size check
    db_ok = True
    db_size_mb = 0
    try:
        # Connectivity check
        await user_repository.count({})

        # Get PostgreSQL database size
        from database.connection import get_db
        pool = await get_db()
        async with pool.acquire() as conn:
            result = await conn.fetchrow("SELECT pg_database_size(current_database()) as size")
            if result:
                db_size_mb = round(result['size'] / 1024 / 1024, 2)
    except Exception as e:
        logger.warning(f"Failed to get database statistics: {e}")
        db_ok = False

    # User stats
    total_users = await user_repository.count({})
    active_users = await user_repository.count({"status": {"$ne": "suspended"}})
    admin_users = await user_repository.count({"role": "admin"})

    # Recipe stats
    total_recipes = await recipe_repository.count({})

    # Storage stats
    upload_dir = os.environ.get("UPLOAD_DIR", "uploads")
    storage_used = 0
    try:
        for root, dirs, files in os.walk(upload_dir):
            for file in files:
                storage_used += os.path.getsize(os.path.join(root, file))
    except Exception as e:
        logger.debug(f"Failed to calculate storage usage: {e}")

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": {
            "connected": db_ok,
            "type": "PostgreSQL",
            "size_mb": db_size_mb
        },
        "storage": {
            "used_mb": round(storage_used / 1024 / 1024, 2)
        },
        "users": {
            "total": total_users,
            "active": active_users,
            "admins": admin_users
        },
        "recipes": {
            "total": total_recipes
        }
    }

# =============================================================================
# SUBSCRIPTION MANAGEMENT
# =============================================================================

class GrantSubscriptionRequest(BaseModel):
    user_id: str
    status: str = "premium"  # premium, trial, free
    days: int = 30  # Duration in days
    source: str = "admin"  # admin, revenuecat, stripe, etc.

@router.post("/subscriptions/grant")
async def grant_subscription(
    request: Request,
    data: GrantSubscriptionRequest,
    admin: dict = Depends(get_admin_user)
):
    """Grant premium subscription to a user"""
    from datetime import timedelta

    # Find the user
    user = await user_repository.find_by_id(data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate expiration
    expires_at = datetime.now(timezone.utc) + timedelta(days=data.days)

    # Update user subscription
    await user_repository.update_user(data.user_id, {
        "subscription_status": data.status,
        "subscription_expires": expires_at.isoformat(),
        "subscription_source": data.source
    })

    # Log the action
    await log_audit(
        admin["id"],
        admin["email"],
        "grant_subscription",
        "user",
        data.user_id,
        {"status": data.status, "days": data.days, "source": data.source},
        request.client.host if request.client else None
    )

    return {
        "success": True,
        "user_id": data.user_id,
        "subscription_status": data.status,
        "expires_at": expires_at.isoformat(),
        "source": data.source
    }

@router.post("/subscriptions/revoke/{user_id}")
async def revoke_subscription(
    request: Request,
    user_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Revoke premium subscription from a user"""
    user = await user_repository.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await user_repository.update_user(user_id, {
        "subscription_status": "free",
        "subscription_expires": None,
        "subscription_source": None
    })

    await log_audit(
        admin["id"],
        admin["email"],
        "revoke_subscription",
        "user",
        user_id,
        {},
        request.client.host if request.client else None
    )

    return {"success": True, "user_id": user_id, "subscription_status": "free"}

@router.get("/subscriptions")
async def list_subscriptions(
    admin: dict = Depends(get_admin_user),
    status: str = None
):
    """List all users with their subscription status"""
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                """SELECT id, email, name, subscription_status, subscription_expires, subscription_source
                   FROM users WHERE subscription_status = $1 ORDER BY subscription_expires DESC""",
                status
            )
        else:
            rows = await conn.fetch(
                """SELECT id, email, name, subscription_status, subscription_expires, subscription_source
                   FROM users WHERE subscription_status != 'free' ORDER BY subscription_expires DESC"""
            )

    return {
        "subscriptions": [
            {
                "user_id": row["id"],
                "email": row["email"],
                "name": row["name"],
                "status": row["subscription_status"],
                "expires": row["subscription_expires"].isoformat() if row["subscription_expires"] else None,
                "source": row["subscription_source"]
            }
            for row in rows
        ]
    }

# =============================================================================
# BACKUP ENDPOINTS
# =============================================================================

@router.post("/backup")
async def create_backup(
    background_tasks: BackgroundTasks,
    admin: dict = Depends(get_admin_user)
):
    """Create a database backup"""
    backup_id = str(uuid.uuid4())

    async def do_backup():
        try:
            backup_data = {
                "id": backup_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": admin["id"],
                "collections": {}
            }

            # Backup each table using repositories
            backup_data["collections"]["users"] = await user_repository.find_many(
                exclude_fields=["password"]
            )
            backup_data["collections"]["recipes"] = await recipe_repository.find_many()
            backup_data["collections"]["meal_plans"] = await meal_plan_repository.find_many()
            backup_data["collections"]["shopping_lists"] = await shopping_list_repository.find_many()
            backup_data["collections"]["custom_prompts"] = await custom_prompts_repository.find_many()

            # Store backup metadata
            await backup_repository.create({
                "id": backup_id,
                "created_at": backup_data["created_at"],
                "created_by": admin["id"],
                "size_bytes": len(json.dumps(backup_data)),
                "status": "completed"
            })

            await log_audit(
                admin["id"], admin["email"], "backup_created",
                "backup", backup_id
            )
        except Exception as e:
            await backup_repository.update_backup(
                backup_id,
                {"status": "failed", "error": str(e)}
            )

    # Start backup in background
    background_tasks.add_task(do_backup)

    return {"message": "Backup started", "backup_id": backup_id}

@router.get("/backups")
async def list_backups(admin: dict = Depends(get_admin_user)):
    """List all backups"""
    backups = await backup_repository.list_backups(limit=20)
    return {"backups": backups}

# =============================================================================
# IP ACCESS CONTROL
# =============================================================================

@router.get("/ip-rules")
async def get_ip_rules(admin: dict = Depends(get_admin_user)):
    """Get IP allowlist and blocklist"""
    allowlist = await ip_allowlist_repository.find_all(limit=100)
    blocklist = await ip_blocklist_repository.find_all(limit=100)

    return {
        "allowlist": allowlist,
        "blocklist": blocklist
    }

@router.post("/ip-rules/allowlist")
async def add_ip_allowlist(rule: IPAccessRule, admin: dict = Depends(get_admin_user)):
    """Add IP to allowlist"""
    doc = {
        "id": str(uuid.uuid4()),
        "ip_pattern": rule.ip_pattern,
        "description": rule.description,
        "created_by": admin["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await ip_allowlist_repository.create(doc)

    await log_audit(
        admin["id"], admin["email"], "ip_allowlist_add",
        "ip_rule", doc["id"], {"ip": rule.ip_pattern}
    )

    return doc

@router.post("/ip-rules/blocklist")
async def add_ip_blocklist(rule: IPAccessRule, admin: dict = Depends(get_admin_user)):
    """Add IP to blocklist"""
    doc = {
        "id": str(uuid.uuid4()),
        "ip_pattern": rule.ip_pattern,
        "description": rule.description,
        "created_by": admin["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await ip_blocklist_repository.create(doc)

    await log_audit(
        admin["id"], admin["email"], "ip_blocklist_add",
        "ip_rule", doc["id"], {"ip": rule.ip_pattern}
    )

    return doc

@router.delete("/ip-rules/allowlist/{rule_id}")
async def delete_ip_allowlist(rule_id: str, admin: dict = Depends(get_admin_user)):
    """Remove IP from allowlist"""
    result = await ip_allowlist_repository.delete_rule(rule_id)

    if result == 0:
        raise HTTPException(status_code=404, detail="Rule not found")

    await log_audit(
        admin["id"], admin["email"], "ip_allowlist_remove",
        "ip_rule", rule_id
    )

    return {"message": "IP removed from allowlist"}

@router.delete("/ip-rules/blocklist/{rule_id}")
async def delete_ip_blocklist(rule_id: str, admin: dict = Depends(get_admin_user)):
    """Remove IP from blocklist"""
    result = await ip_blocklist_repository.delete_rule(rule_id)

    if result == 0:
        raise HTTPException(status_code=404, detail="Rule not found")

    await log_audit(
        admin["id"], admin["email"], "ip_blocklist_remove",
        "ip_rule", rule_id
    )

    return {"message": "IP removed from blocklist"}

# =============================================================================
# USER DATA EXPORT (GDPR COMPLIANCE)
# =============================================================================

@router.get("/users/{user_id}/export")
async def export_user_data(user_id: str, admin: dict = Depends(get_admin_user)):
    """Export all data for a specific user (GDPR compliance)"""
    user = await user_repository.find_by_id(user_id, exclude_password=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Collect all user data
    export_data = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "user_info": user,
        "recipes": [],
        "favorites": [],
        "meal_plans": [],
        "shopping_lists": [],
        "sessions": [],
        "login_history": [],
        "oauth_accounts": []
    }

    # Get user's recipes
    recipes = await recipe_repository.find_by_author(user_id)
    export_data["recipes"] = recipes

    # Get favorites (stored in user document)
    export_data["favorites"] = user.get("favorites", [])

    # Get meal plans
    meal_plans = await meal_plan_repository.find_many({"user_id": user_id})
    export_data["meal_plans"] = meal_plans

    # Get shopping lists
    shopping_lists = await shopping_list_repository.find_many({"user_id": user_id})
    export_data["shopping_lists"] = shopping_lists

    # Get sessions (without token)
    sessions = await session_repository.find_by_user(user_id)
    export_data["sessions"] = [{k: v for k, v in s.items() if k != "token"} for s in sessions]

    # Get login history
    login_history = await login_attempt_repository.find_by_user(user_id, limit=100)
    export_data["login_history"] = login_history

    # Get OAuth accounts
    oauth_accounts = await oauth_account_repository.find_by_user(user_id)
    export_data["oauth_accounts"] = oauth_accounts

    await log_audit(
        admin["id"], admin["email"], "user_data_export",
        "user", user_id, {"email": user["email"]}
    )

    return export_data

@router.get("/users/{user_id}/export/download")
async def download_user_data(user_id: str, admin: dict = Depends(get_admin_user)):
    """Download user data as ZIP file"""
    user = await user_repository.find_by_id(user_id, exclude_password=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create in-memory ZIP file
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # User info
        zip_file.writestr("user_info.json", json.dumps(user, indent=2, default=str))

        # Recipes
        recipes = await recipe_repository.find_by_author(user_id)
        zip_file.writestr("recipes.json", json.dumps(recipes, indent=2, default=str))

        # Favorites
        favorites = user.get("favorites", [])
        zip_file.writestr("favorites.json", json.dumps(favorites, indent=2, default=str))

        # Meal plans
        meal_plans = await meal_plan_repository.find_many({"user_id": user_id})
        zip_file.writestr("meal_plans.json", json.dumps(meal_plans, indent=2, default=str))

        # Shopping lists
        shopping_lists = await shopping_list_repository.find_many({"user_id": user_id})
        zip_file.writestr("shopping_lists.json", json.dumps(shopping_lists, indent=2, default=str))

        # README
        readme = f"""# Data Export for {user['email']}

Generated: {datetime.now(timezone.utc).isoformat()}

## Contents
- user_info.json - Your account information
- recipes.json - All your recipes
- favorites.json - Your favorited recipes
- meal_plans.json - Your meal plans
- shopping_lists.json - Your shopping lists

This export contains all your personal data stored in Laro.
"""
        zip_file.writestr("README.md", readme)

    zip_buffer.seek(0)

    await log_audit(
        admin["id"], admin["email"], "user_data_download",
        "user", user_id, {"email": user["email"]}
    )

    filename = f"mise_export_{user['email'].replace('@', '_')}_{datetime.now().strftime('%Y%m%d')}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# =============================================================================
# SCHEDULED BACKUP SETTINGS
# =============================================================================

@router.get("/backup-settings")
async def get_backup_settings(admin: dict = Depends(get_admin_user)):
    """Get automatic backup settings"""
    settings = await backup_settings_repository.get_settings()
    return settings

@router.put("/backup-settings")
async def update_backup_settings(
    enabled: bool = Query(...),
    interval_hours: int = Query(24, ge=1, le=168),
    max_backups: int = Query(7, ge=1, le=30),
    admin: dict = Depends(get_admin_user)
):
    """Update automatic backup settings"""
    next_scheduled = None
    if enabled:
        next_scheduled = (datetime.now(timezone.utc) + timedelta(hours=interval_hours)).isoformat()

    await backup_settings_repository.update_settings({
        "auto_backup_enabled": 1 if enabled else 0,
        "interval_hours": interval_hours,
        "max_backups_to_keep": max_backups,
        "next_scheduled": next_scheduled
    })

    await log_audit(
        admin["id"], admin["email"], "backup_settings_updated",
        "system", "backup_settings",
        {"enabled": enabled, "interval_hours": interval_hours}
    )

    return {"message": "Backup settings updated", "next_scheduled": next_scheduled}
