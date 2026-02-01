"""
Authentication Router - Registration, login, profile management
"""
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from models import UserCreate, UserLogin, UserResponse, UserUpdate
from dependencies import (
    get_current_user, hash_password, verify_password, create_token,
    user_repository, session_repository, login_attempt_repository,
    totp_secret_repository, oauth_account_repository, system_settings_repository,
    invite_code_repository, custom_prompts_repository, llm_settings_repository,
    ip_allowlist_repository, ip_blocklist_repository, household_repository,
    recipe_repository, user_preferences_repository, meal_plan_repository,
    shopping_list_repository,
)
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional
import ipaddress
import re

logger = logging.getLogger(__name__)

# Import activity logger
from utils.activity_logger import log_user_activity

# Import debug utilities
try:
    from utils.debug import Loggers, log_auth_event
    _debug_available = True
except ImportError:
    _debug_available = False

# Import email service
try:
    from services.email import (
        send_new_login_notification,
        send_account_locked_notification,
        is_email_configured
    )
except ImportError:
    async def send_new_login_notification(*args, **kwargs): return False
    async def send_account_locked_notification(*args, **kwargs): return False
    def is_email_configured(): return False

router = APIRouter(prefix="/auth", tags=["Auth"])


# Extended models
class UserCreateExtended(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Optional[str] = None
    invite_code: Optional[str] = None
    referral_code: Optional[str] = None  # Friend code for 1st month free


class LoginWithTOTP(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None


def ip_matches_pattern(ip: str, pattern: str) -> bool:
    """Check if IP matches a pattern (exact, CIDR, or wildcard)"""
    try:
        if ip == pattern:
            return True

        if '/' in pattern:
            try:
                network = ipaddress.ip_network(pattern, strict=False)
                return ipaddress.ip_address(ip) in network
            except ValueError:
                return False

        if '*' in pattern:
            regex_pattern = pattern.replace('.', r'\.').replace('*', r'\d+')
            return bool(re.match(f'^{regex_pattern}$', ip))

        return False
    except Exception as e:
        logger.debug(f"Error matching IP pattern '{pattern}' against '{ip}': {e}")
        return False


async def check_ip_access(ip: str) -> tuple:
    """Check if IP is allowed access. Returns (allowed, reason)"""
    settings = await system_settings_repository.get_settings()

    # Check blocklist first
    if settings.get("enable_ip_blocklist", False):
        blocklist = await ip_blocklist_repository.find_all()
        for rule in blocklist:
            if ip_matches_pattern(ip, rule["ip_pattern"]):
                return False, "IP is blocked"

    # Check allowlist if enabled
    if settings.get("enable_ip_allowlist", False):
        allowlist = await ip_allowlist_repository.find_all()
        if not allowlist:
            return True, ""

        for rule in allowlist:
            if ip_matches_pattern(ip, rule["ip_pattern"]):
                return True, ""

        return False, "IP not in allowlist"

    return True, ""


async def is_new_device(user_id: str, user_agent: str, ip: str) -> bool:
    """Check if this is a new device/IP combination for the user"""
    existing = await session_repository.find_existing_session(user_id, user_agent, ip)
    return existing is None


async def check_account_lockout(email: str) -> bool:
    """Check if account is locked due to failed attempts"""
    settings = await system_settings_repository.get_settings()
    max_attempts = settings.get("max_login_attempts", 5)
    lockout_minutes = settings.get("lockout_duration_minutes", 15)

    # Use naive UTC datetime for PostgreSQL TIMESTAMP columns
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=lockout_minutes)).replace(tzinfo=None)
    failed_count = await login_attempt_repository.count_recent_failures(email, cutoff)

    return failed_count >= max_attempts


async def record_login_attempt(email: str, success: bool, ip_address: str = None, user_id: str = None):
    """Record a login attempt"""
    # Use naive UTC datetime for PostgreSQL TIMESTAMP columns
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await login_attempt_repository.create({
        "id": str(uuid.uuid4()),
        "email": email,
        "user_id": user_id,
        "success": success,
        "ip_address": ip_address,
        "timestamp": now
    })

    # Clean up old records - use naive UTC datetime
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).replace(tzinfo=None)
    await login_attempt_repository.cleanup_old_attempts(cutoff)


async def validate_password(password: str) -> tuple:
    """Validate password against policy"""
    settings = await system_settings_repository.get_settings()

    min_length = settings.get("password_min_length", 8)
    require_uppercase = settings.get("password_require_uppercase", False)
    require_number = settings.get("password_require_number", False)
    require_special = settings.get("password_require_special", False)

    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters"

    if require_uppercase and not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if require_number and not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"

    if require_special and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"

    return True, ""


@router.post("/register", response_model=dict)
async def register(user: UserCreateExtended, request: Request, background_tasks: BackgroundTasks):
    ip_address = request.client.host if request.client else None
    if _debug_available:
        Loggers.auth.info("Registration attempt", email=user.email[:3] + "***", ip=ip_address)

    # Check IP access
    if ip_address:
        ip_allowed, ip_reason = await check_ip_access(ip_address)
        if not ip_allowed:
            if _debug_available:
                log_auth_event("REGISTER_BLOCKED", ip_address=ip_address, success=False, reason=ip_reason)
            raise HTTPException(status_code=403, detail=ip_reason)

    settings = await system_settings_repository.get_settings()

    # Check if registration is allowed
    if not settings.get("allow_registration", True):
        raise HTTPException(status_code=403, detail="Registration is currently disabled")

    # Check if invite code is required
    invite_doc = None
    if settings.get("require_invite_code", False):
        if not user.invite_code:
            raise HTTPException(status_code=400, detail="Invite code is required")

        # Use naive UTC datetime for PostgreSQL TIMESTAMP columns
        current_time = datetime.now(timezone.utc).replace(tzinfo=None)
        invite_doc = await invite_code_repository.find_valid_code(user.invite_code, current_time)

        if not invite_doc:
            raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    # Check if email exists
    existing = await user_repository.find_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate password
    is_valid, error_msg = await validate_password(user.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Determine role
    user_count = await user_repository.count({})

    if user_count == 0:
        role = "admin"
    elif invite_doc and invite_doc.get("grants_admin"):
        role = "admin"
    elif user.role == "admin" and settings.get("allow_admin_registration", False):
        role = "admin"
    else:
        role = "user"

    user_id = str(uuid.uuid4())

    # Hash password in a thread pool
    hashed_password = await asyncio.get_running_loop().run_in_executor(
        None, hash_password, user.password
    )

    # Handle referral code - gives 1st month free to new user
    # Referrer gets their free month only when referred user subscribes
    referred_by = None
    referral_trial_end = None
    if user.referral_code:
        referrer = await user_repository.find_by_friend_code(user.referral_code.strip().upper())
        if referrer:
            referred_by = referrer["id"]
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

            # Grant 30-day trial for the new user immediately
            referral_trial_end = now_utc + timedelta(days=30)

            # Track pending referral reward for the referrer
            # They'll get their free month when this user subscribes
            pending_rewards = referrer.get("pending_referral_rewards", [])
            pending_rewards.append({
                "referred_user_id": user_id,
                "created_at": now_utc.isoformat()
            })

            await user_repository.update_user(referrer["id"], {
                "pending_referral_rewards": pending_rewards
            })

    # Use naive UTC datetime for PostgreSQL TIMESTAMP columns
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user_doc = {
        "id": user_id,
        "email": user.email,
        "password": hashed_password,
        "name": user.name,
        "role": role,
        "status": "active",
        "household_id": None,
        "favorites": [],
        "allergies": [],
        "referred_by": referred_by,
        "referral_trial_end": referral_trial_end,
        "referral_count": 0,
        "created_at": now,
        "last_login": now
    }
    await user_repository.create(user_doc)

    # Log registration activity
    await log_user_activity(
        user_id=user_id,
        user_email=user.email,
        action="register",
        details={"role": role, "invite_used": bool(invite_doc)},
        ip_address=ip_address
    )

    # Update invite code usage
    if invite_doc:
        await invite_code_repository.increment_uses(invite_doc["id"])

    token = create_token(user_id)

    # Create session
    await session_repository.create({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "token": token,
        "user_agent": request.headers.get("User-Agent", "Unknown"),
        "ip_address": ip_address or "Unknown",
        "created_at": now,
        "last_active": now
    })

    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": user.email,
            "name": user.name,
            "role": role,
            "household_id": None,
            "household_name": None,
            "household_role": None,
            "created_at": now.isoformat(),
            "referral_trial_end": referral_trial_end.isoformat() if referral_trial_end else None,
            "has_referral_trial": referral_trial_end is not None
        }
    }


@router.post("/login", response_model=dict)
async def login(user: LoginWithTOTP, request: Request, background_tasks: BackgroundTasks):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent", "Unknown")
    if _debug_available:
        Loggers.auth.info("Login attempt", email=user.email[:3] + "***", ip=ip_address)

    # Check IP access
    if ip_address:
        ip_allowed, ip_reason = await check_ip_access(ip_address)
        if not ip_allowed:
            if _debug_available:
                log_auth_event("LOGIN_BLOCKED", ip_address=ip_address, success=False, reason=ip_reason)
            raise HTTPException(status_code=403, detail=ip_reason)

    settings = await system_settings_repository.get_settings()

    # Check account lockout
    if await check_account_lockout(user.email):
        if _debug_available:
            log_auth_event("LOGIN_LOCKED", email=user.email, ip_address=ip_address, success=False, reason="account_locked")
        if is_email_configured():
            lockout_minutes = settings.get("lockout_duration_minutes", 15)
            background_tasks.add_task(send_account_locked_notification, user.email, lockout_minutes)

        raise HTTPException(
            status_code=429,
            detail="Account temporarily locked due to too many failed attempts. Please try again later."
        )

    db_user = await user_repository.find_by_email(user.email, include_password=True)
    if not db_user:
        await record_login_attempt(user.email, False, ip_address)
        await log_user_activity(
            user_id="unknown",
            user_email=user.email,
            action="login_failed",
            details={"reason": "user_not_found"},
            ip_address=ip_address
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if account is suspended
    if db_user.get("status") == "suspended":
        raise HTTPException(status_code=403, detail="Account is suspended")

    if db_user.get("status") == "deleted":
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if OAuth-only account
    if db_user.get("oauth_only") and not db_user.get("password"):
        raise HTTPException(
            status_code=400,
            detail="This account uses social login. Please sign in with Google or GitHub."
        )

    # Check if password exists in database
    if not db_user.get("password"):
        logger.error(f"User {user.email} has no password hash stored in database")
        raise HTTPException(status_code=401, detail="Invalid credentials - please contact admin")

    # Verify password in a thread pool
    try:
        is_valid = await asyncio.get_running_loop().run_in_executor(
            None, verify_password, user.password, db_user["password"]
        )
    except Exception as e:
        logger.error(f"Password verification error for {user.email}: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not is_valid:
        await record_login_attempt(user.email, False, ip_address, db_user["id"])
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check 2FA if enabled
    if db_user.get("totp_enabled"):
        if not user.totp_code:
            return {
                "requires_2fa": True,
                "message": "Please provide your 2FA code"
            }

        # Verify TOTP
        import pyotp
        totp_doc = await totp_secret_repository.find_by_user(db_user["id"], verified_only=True)

        if totp_doc:
            totp = pyotp.TOTP(totp_doc["secret"])
            if not totp.verify(user.totp_code):
                # Check backup codes
                backup_valid = False
                backup_codes = totp_doc.get("backup_codes", [])
                for i, hashed_code in enumerate(backup_codes):
                    if hashed_code:
                        code_matches = await asyncio.get_running_loop().run_in_executor(
                            None, verify_password, user.totp_code, hashed_code
                        )
                        if code_matches:
                            backup_codes[i] = None
                            await totp_secret_repository.update_totp(
                                totp_doc["id"],
                                {"backup_codes": backup_codes}
                            )
                            backup_valid = True
                            break

                if not backup_valid:
                    await record_login_attempt(user.email, False, ip_address, db_user["id"])
                    raise HTTPException(status_code=401, detail="Invalid 2FA code")

    # Record successful login
    await record_login_attempt(user.email, True, ip_address, db_user["id"])

    # Log login activity
    await log_user_activity(
        user_id=db_user["id"],
        user_email=db_user["email"],
        action="login",
        details={"user_agent": user_agent[:100]},
        ip_address=ip_address
    )

    # Check if this is a new device and send notification
    if settings.get("notify_new_login", False) and is_email_configured():
        is_new = await is_new_device(db_user["id"], user_agent, ip_address)
        if is_new:
            device_name = "Unknown Browser"
            if "Chrome" in user_agent:
                device_name = "Chrome"
            elif "Firefox" in user_agent:
                device_name = "Firefox"
            elif "Safari" in user_agent:
                device_name = "Safari"
            elif "Edge" in user_agent:
                device_name = "Edge"

            background_tasks.add_task(
                send_new_login_notification,
                db_user["email"],
                device_name,
                ip_address or "Unknown",
                "Unknown",
                datetime.now(timezone.utc)
            )

    # Update last login - use naive UTC datetime for PostgreSQL
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await user_repository.update_user(
        db_user["id"],
        {"last_login": now}
    )

    token = create_token(db_user["id"])

    # Create session with naive UTC datetimes
    await session_repository.create({
        "id": str(uuid.uuid4()),
        "user_id": db_user["id"],
        "token": token,
        "user_agent": user_agent,
        "ip_address": ip_address,
        "created_at": now,
        "last_active": now
    })

    # Fetch household info if user belongs to one
    household_name = None
    household_role = None
    user_household_id = db_user.get("household_id")
    if user_household_id:
        household = await household_repository.find_by_id(user_household_id)
        if household:
            household_name = household.get("name")
            household_role = "owner" if household.get("owner_id") == db_user["id"] else "member"

    # Check if user has active referral trial
    referral_trial_end = db_user.get("referral_trial_end")
    has_referral_trial = False
    if referral_trial_end:
        if hasattr(referral_trial_end, 'replace'):
            # It's a datetime, compare with now
            has_referral_trial = referral_trial_end > now
        referral_trial_end = referral_trial_end.isoformat() if hasattr(referral_trial_end, 'isoformat') else referral_trial_end

    return {
        "token": token,
        "user": {
            "id": db_user["id"],
            "email": db_user["email"],
            "name": db_user["name"],
            "role": db_user.get("role", "user"),
            "household_id": user_household_id,
            "household_name": household_name,
            "household_role": household_role,
            "created_at": db_user["created_at"],
            "totp_enabled": db_user.get("totp_enabled", False),
            "force_password_change": db_user.get("force_password_change", False),
            "referral_trial_end": referral_trial_end,
            "has_referral_trial": has_referral_trial,
            "referral_count": db_user.get("referral_count", 0)
        }
    }


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    created_at = user["created_at"]
    if hasattr(created_at, 'isoformat'):
        created_at = created_at.isoformat()

    # Fetch household info if user belongs to one
    household_name = None
    household_role = None
    user_household_id = user.get("household_id")
    if user_household_id:
        household = await household_repository.find_by_id(user_household_id)
        if household:
            household_name = household.get("name")
            household_role = "owner" if household.get("owner_id") == user["id"] else "member"

    # Check referral trial status
    referral_trial_end = user.get("referral_trial_end")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    has_referral_trial = False
    if referral_trial_end:
        if hasattr(referral_trial_end, 'replace'):
            has_referral_trial = referral_trial_end > now
        referral_trial_end = referral_trial_end.isoformat() if hasattr(referral_trial_end, 'isoformat') else referral_trial_end

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user.get("role", "user"),
        "household_id": user_household_id,
        "household_name": household_name,
        "household_role": household_role,
        "allergies": user.get("allergies", []),
        "created_at": created_at,
        "referral_trial_end": referral_trial_end,
        "has_referral_trial": has_referral_trial,
        "referral_count": user.get("referral_count", 0)
    }


@router.get("/me/extended")
async def get_me_extended(user: dict = Depends(get_current_user)):
    """Get extended user info including role and security settings"""
    oauth_accounts = await oauth_account_repository.find_by_user(user["id"])
    linked_providers = [acc["provider"] for acc in oauth_accounts]

    # Fetch household info if user belongs to one
    household_name = None
    household_role = None
    user_household_id = user.get("household_id")
    if user_household_id:
        household = await household_repository.find_by_id(user_household_id)
        if household:
            household_name = household.get("name")
            household_role = "owner" if household.get("owner_id") == user["id"] else "member"

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user.get("role", "user"),
        "status": user.get("status", "active"),
        "household_id": user_household_id,
        "household_name": household_name,
        "household_role": household_role,
        "allergies": user.get("allergies", []),
        "created_at": user["created_at"],
        "last_login": user.get("last_login"),
        "totp_enabled": user.get("totp_enabled", False),
        "oauth_only": user.get("oauth_only", False),
        "linked_oauth": linked_providers,
        "force_password_change": user.get("force_password_change", False)
    }


@router.put("/me")
async def update_profile(data: UserUpdate, user: dict = Depends(get_current_user)):
    update_data = {}

    if data.name is not None:
        update_data["name"] = data.name

    if data.email is not None and data.email != user["email"]:
        existing = await user_repository.find_by_email(data.email)
        if existing and existing["id"] != user["id"]:
            raise HTTPException(status_code=400, detail="Email already in use")
        update_data["email"] = data.email

    if data.allergies is not None:
        update_data["allergies"] = data.allergies

    if update_data:
        await user_repository.update_user(user["id"], update_data)

    updated_user = await user_repository.find_by_id(user["id"])

    # Fetch household info if user belongs to one
    household_name = None
    household_role = None
    user_household_id = updated_user.get("household_id")
    if user_household_id:
        household = await household_repository.find_by_id(user_household_id)
        if household:
            household_name = household.get("name")
            household_role = "owner" if household.get("owner_id") == updated_user["id"] else "member"

    created_at = updated_user["created_at"]
    if hasattr(created_at, 'isoformat'):
        created_at = created_at.isoformat()

    return {
        "id": updated_user["id"],
        "email": updated_user["email"],
        "name": updated_user["name"],
        "household_id": user_household_id,
        "household_name": household_name,
        "household_role": household_role,
        "allergies": updated_user.get("allergies", []),
        "created_at": created_at
    }


@router.delete("/me")
async def delete_account(request: Request, user: dict = Depends(get_current_user)):
    """Delete user account and all associated data"""
    import logging
    logger = logging.getLogger(__name__)

    user_id = user["id"]
    user_email = user.get("email", "unknown")
    household_id = user.get("household_id")
    ip_address = request.client.host if request.client else None

    try:
        # If user owns a household, delete or transfer it
        if household_id:
            household = await household_repository.find_by_id(household_id)
            if household and household["owner_id"] == user_id:
                member_ids = household.get("member_ids", [])
                if len(member_ids) <= 1:
                    await household_repository.delete_household(household_id)
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Transfer household ownership before deleting account"
                    )
            elif household:
                await household_repository.remove_member(household_id, user_id)

        # Delete user's meal plans FIRST (they reference recipes via foreign key)
        if not household_id:
            try:
                await meal_plan_repository.delete_by_user(user_id)
            except Exception as e:
                logger.warning(f"Failed to delete meal plans for user {user_id}: {e}")

        # Delete meal plans that reference user's recipes (to avoid FK constraint)
        try:
            user_recipes = await recipe_repository.find_by_author(user_id)
            recipe_ids = [r["id"] for r in user_recipes if r.get("household_id") is None]
            if recipe_ids:
                await meal_plan_repository.delete_by_recipe_ids(recipe_ids)
        except Exception as e:
            logger.warning(f"Failed to delete meal plans referencing user recipes {user_id}: {e}")

        # Delete user's recipes (not shared with household)
        try:
            await recipe_repository.delete_by_author(user_id, household_id=None)
        except Exception as e:
            logger.warning(f"Failed to delete recipes for user {user_id}: {e}")

        # Delete user's shopping lists (if no household)
        if not household_id:
            try:
                await shopping_list_repository.delete_by_user(user_id)
            except Exception as e:
                logger.warning(f"Failed to delete shopping lists for user {user_id}: {e}")

        # Delete user's custom prompts
        try:
            await custom_prompts_repository.delete_by_user(user_id)
        except Exception as e:
            logger.warning(f"Failed to delete custom prompts for user {user_id}: {e}")

        # Delete user's LLM settings
        try:
            await llm_settings_repository.delete_by_user(user_id)
        except Exception as e:
            logger.warning(f"Failed to delete LLM settings for user {user_id}: {e}")

        # Delete user's sessions
        try:
            await session_repository.delete_by_user(user_id)
        except Exception as e:
            logger.warning(f"Failed to delete sessions for user {user_id}: {e}")

        # Delete user's TOTP secrets
        try:
            await totp_secret_repository.delete_by_user(user_id)
        except Exception as e:
            logger.warning(f"Failed to delete TOTP secrets for user {user_id}: {e}")

        # Delete OAuth links
        try:
            await oauth_account_repository.delete_by_user(user_id)
        except Exception as e:
            logger.warning(f"Failed to delete OAuth accounts for user {user_id}: {e}")

        # Delete user preferences
        try:
            await user_preferences_repository.delete_by_user(user_id)
        except Exception as e:
            logger.warning(f"Failed to delete user preferences for user {user_id}: {e}")

        # Log account deletion before deleting
        try:
            await log_user_activity(
                user_id=user_id,
                user_email=user_email,
                action="account_deleted",
                details={"had_household": bool(household_id)},
                ip_address=ip_address
            )
        except Exception as e:
            logger.warning(f"Failed to log account deletion for user {user_id}: {e}")

        # Delete user account
        await user_repository.delete_user(user_id)

        return {"message": "Account deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete account for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")


@router.post("/logout")
async def logout(request: Request, user: dict = Depends(get_current_user)):
    """Logout and invalidate current session"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    ip_address = request.client.host if request.client else None

    await session_repository.delete_by_user_and_token(user["id"], token)

    # Log logout activity
    await log_user_activity(
        user_id=user["id"],
        user_email=user.get("email", "unknown"),
        action="logout",
        ip_address=ip_address
    )

    return {"message": "Logged out successfully"}


@router.get("/debug/user-status")
async def debug_user_status(email: str, user: dict = Depends(get_current_user)):
    """Debug endpoint to check user status (admin only).
    Returns basic info about whether user exists and has password set.
    Does NOT return sensitive data like password hashes.
    """
    # Require admin role
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    target_user = await user_repository.find_by_email(email, include_password=True)

    if not target_user:
        return {
            "exists": False,
            "message": "No user found with this email"
        }

    return {
        "exists": True,
        "id": target_user["id"],
        "email": target_user["email"],
        "name": target_user["name"],
        "role": target_user.get("role", "user"),
        "status": target_user.get("status", "active"),
        "has_password": bool(target_user.get("password")),
        "oauth_only": target_user.get("oauth_only", False),
        "totp_enabled": target_user.get("totp_enabled", False),
        "created_at": target_user.get("created_at"),
        "last_login": target_user.get("last_login")
    }
