"""
Security Router - Password Reset, 2FA (TOTP), OAuth, Session Management
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from dependencies import (
    hash_password, verify_password, create_token, get_current_user,
    user_repository, session_repository, totp_secret_repository, login_attempt_repository
)
from utils.activity_logger import log_action, log_user_activity
from datetime import datetime, timezone, timedelta
import uuid
import secrets
import asyncio
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
import os

# Import email service
try:
    from services.email import (
        send_password_reset_email,
        send_password_changed_notification,
        send_2fa_enabled_notification,
        send_2fa_disabled_notification,
        is_email_configured
    )
except ImportError:
    # Fallback if email service not available
    async def send_password_reset_email(*args, **kwargs): return False
    async def send_password_changed_notification(*args, **kwargs): return False
    async def send_2fa_enabled_notification(*args, **kwargs): return False
    async def send_2fa_disabled_notification(*args, **kwargs): return False
    def is_email_configured(): return False

router = APIRouter(prefix="/security", tags=["Security"])

# =============================================================================
# MODELS
# =============================================================================

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: List[str]

class TOTPVerify(BaseModel):
    code: str

class TOTPDisable(BaseModel):
    password: str
    code: str

class SessionInfo(BaseModel):
    id: str
    user_agent: str
    ip_address: str
    created_at: str
    last_active: str
    is_current: bool

# =============================================================================
# PASSWORD RESET (EMAIL-BASED)
# =============================================================================

# Note: Password reset tokens would need their own repository
# For now, we'll use a simple in-memory approach or the session repository
# In production, you'd create a password_reset_token_repository

@router.post("/password-reset/request")
async def request_password_reset(data: PasswordResetRequest, background_tasks: BackgroundTasks):
    """Request a password reset email"""
    user = await user_repository.find_by_email(data.email)

    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If the email exists, a reset link has been sent"}

    # Generate token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    # Store reset token in user record (simplified approach)
    # In production, use a dedicated password_reset_tokens table/repository
    await user_repository.update_user(user["id"], {
        "password_reset_token": token,
        "password_reset_expires": expires_at.isoformat()
    })

    # Send email if configured
    if is_email_configured():
        background_tasks.add_task(send_password_reset_email, user["email"], token)
        return {"message": "If the email exists, a reset link has been sent"}
    else:
        # Development mode - return token directly
        return {
            "message": "Password reset token generated",
            "token": token,
            "note": "Email is disabled. In production, this token would be sent via email."
        }

@router.post("/password-reset/confirm")
async def confirm_password_reset(data: PasswordResetConfirm):
    """Confirm password reset with token"""
    # Find user with matching token
    # This is a simplified approach - in production, use a dedicated tokens table
    from database.connection import get_db, dict_from_row

    pool = await get_db()
    async with pool.acquire() as conn:
        query = """
            SELECT * FROM users
            WHERE password_reset_token = $1
            AND password_reset_expires > $2
        """
        row = await conn.fetchrow(query, data.token, datetime.now(timezone.utc).isoformat())

    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = dict_from_row(row)

    # Validate password
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Hash new password
    hashed = await asyncio.get_running_loop().run_in_executor(
        None, hash_password, data.new_password
    )

    # Update user password and clear reset token
    await user_repository.update_user(user["id"], {
        "password": hashed,
        "password_changed_at": datetime.now(timezone.utc).isoformat(),
        "password_reset_token": None,
        "password_reset_expires": None
    })

    # Invalidate all sessions for this user
    await session_repository.delete_by_user(user["id"])

    return {"message": "Password reset successfully"}

@router.post("/password/change")
async def change_password(data: ChangePassword, request: Request, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Change password for logged-in user"""
    # Verify current password
    db_user = await user_repository.find_by_id(user["id"], exclude_password=False)

    is_valid = await asyncio.get_running_loop().run_in_executor(
        None, verify_password, data.current_password, db_user["password"]
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Validate new password
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Hash and update
    hashed = await asyncio.get_running_loop().run_in_executor(
        None, hash_password, data.new_password
    )

    await user_repository.update_user(user["id"], {
        "password": hashed,
        "password_changed_at": datetime.now(timezone.utc).isoformat(),
        "force_password_change": False
    })

    # Log password change
    await log_action(user, "password_changed", request)

    # Send notification email
    if is_email_configured():
        background_tasks.add_task(send_password_changed_notification, db_user["email"])

    return {"message": "Password changed successfully"}

# =============================================================================
# TOTP 2FA
# =============================================================================

@router.post("/2fa/setup")
async def setup_totp(user: dict = Depends(get_current_user)):
    """Setup TOTP 2FA"""
    # Check if already enabled
    existing = await totp_secret_repository.find_by_user(user["id"], verified_only=True)
    if existing:
        raise HTTPException(status_code=400, detail="2FA is already enabled")

    # Generate secret
    secret = pyotp.random_base32()

    # Generate QR code
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(user["email"], issuer_name="Laro")

    # Create QR code as SVG
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Generate backup codes
    backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
    hashed_backup_codes = [
        await asyncio.get_running_loop().run_in_executor(None, hash_password, code)
        for code in backup_codes
    ]

    # Delete any pending unverified setups
    await totp_secret_repository.delete_by_user(user["id"])

    # Store pending 2FA setup
    await totp_secret_repository.create({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "secret": secret,
        "backup_codes": hashed_backup_codes,
        "verified": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    return TOTPSetupResponse(
        secret=secret,
        qr_code=f"data:image/png;base64,{qr_base64}",
        backup_codes=backup_codes
    )

@router.post("/2fa/verify")
async def verify_totp_setup(data: TOTPVerify, request: Request, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Verify TOTP setup with a code"""
    # Get pending setup
    setup = await totp_secret_repository.find_by_user(user["id"], verified_only=False)
    if not setup or setup.get("verified"):
        raise HTTPException(status_code=400, detail="No pending 2FA setup")

    # Verify code
    totp = pyotp.TOTP(setup["secret"])
    if not totp.verify(data.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Mark as verified
    await totp_secret_repository.update_totp(setup["id"], {
        "verified": True,
        "verified_at": datetime.now(timezone.utc).isoformat()
    })

    # Update user
    await user_repository.update_user(user["id"], {"totp_enabled": True})

    # Log 2FA enabled
    await log_action(user, "2fa_enabled", request)

    # Send notification email
    if is_email_configured():
        background_tasks.add_task(send_2fa_enabled_notification, user["email"])

    return {"message": "2FA enabled successfully"}

@router.post("/2fa/disable")
async def disable_totp(data: TOTPDisable, request: Request, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Disable TOTP 2FA"""
    # Verify password
    db_user = await user_repository.find_by_id(user["id"], exclude_password=False)

    is_valid = await asyncio.get_running_loop().run_in_executor(
        None, verify_password, data.password, db_user["password"]
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid password")

    # Verify TOTP code
    totp_doc = await totp_secret_repository.find_by_user(user["id"], verified_only=True)
    if not totp_doc:
        raise HTTPException(status_code=400, detail="2FA is not enabled")

    totp = pyotp.TOTP(totp_doc["secret"])
    if not totp.verify(data.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    # Remove 2FA
    await totp_secret_repository.delete_by_user(user["id"])
    await user_repository.update_user(user["id"], {"totp_enabled": False})

    # Log 2FA disabled
    await log_action(user, "2fa_disabled", request)

    # Send notification email
    if is_email_configured():
        background_tasks.add_task(send_2fa_disabled_notification, db_user["email"])

    return {"message": "2FA disabled successfully"}

@router.get("/2fa/status")
async def get_totp_status(user: dict = Depends(get_current_user)):
    """Get 2FA status"""
    totp_doc = await totp_secret_repository.find_by_user(user["id"], verified_only=True)

    backup_codes_remaining = 0
    if totp_doc:
        backup_codes = totp_doc.get("backup_codes", [])
        if isinstance(backup_codes, list):
            backup_codes_remaining = len([c for c in backup_codes if c])

    return {
        "enabled": bool(totp_doc),
        "backup_codes_remaining": backup_codes_remaining
    }

@router.post("/2fa/regenerate-backup-codes")
async def regenerate_backup_codes(data: TOTPVerify, user: dict = Depends(get_current_user)):
    """Regenerate backup codes"""
    totp_doc = await totp_secret_repository.find_by_user(user["id"], verified_only=True)
    if not totp_doc:
        raise HTTPException(status_code=400, detail="2FA is not enabled")

    # Verify code
    totp = pyotp.TOTP(totp_doc["secret"])
    if not totp.verify(data.code):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    # Generate new backup codes
    backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
    hashed_backup_codes = [
        await asyncio.get_running_loop().run_in_executor(None, hash_password, code)
        for code in backup_codes
    ]

    await totp_secret_repository.update_totp(totp_doc["id"], {
        "backup_codes": hashed_backup_codes
    })

    return {"backup_codes": backup_codes}

# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

@router.get("/sessions")
async def list_sessions(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """List all active sessions for current user"""
    sessions = await session_repository.find_by_user(user["id"])

    # Get current session token from header
    current_token = request.headers.get("Authorization", "").replace("Bearer ", "")

    result = []
    for s in sessions:
        result.append(SessionInfo(
            id=s["id"],
            user_agent=s.get("user_agent", "Unknown"),
            ip_address=s.get("ip_address", "Unknown"),
            created_at=s["created_at"],
            last_active=s.get("last_active", s["created_at"]),
            is_current=s.get("token", "") == current_token
        ))

    return {"sessions": result}

@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, user: dict = Depends(get_current_user)):
    """Revoke a specific session"""
    # Verify session belongs to user
    session = await session_repository.find_by_id(session_id)
    if not session or session.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await session_repository.delete_session(session_id)

    if result == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session revoked"}

@router.delete("/sessions")
async def revoke_all_sessions(
    request: Request,
    keep_current: bool = Query(True),
    user: dict = Depends(get_current_user)
):
    """Revoke all sessions (optionally keeping current)"""
    if keep_current:
        current_token = request.headers.get("Authorization", "").replace("Bearer ", "")
        # Get all sessions and delete non-current ones
        sessions = await session_repository.find_by_user(user["id"])
        for session in sessions:
            if session.get("token") != current_token:
                await session_repository.delete_session(session["id"])
    else:
        await session_repository.delete_by_user(user["id"])

    return {"message": "Sessions revoked"}

# =============================================================================
# ACCOUNT LOCKOUT TRACKING
# =============================================================================

@router.get("/login-attempts")
async def get_login_attempts(user: dict = Depends(get_current_user)):
    """Get recent failed login attempts for current user"""
    attempts = await login_attempt_repository.find_by_user(user["id"], limit=10)
    return {"attempts": attempts}
