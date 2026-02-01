"""
Trusted Devices Router - Allow 2FA bypass for trusted devices
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from dependencies import get_current_user, trusted_device_repository, totp_secret_repository
from utils.activity_logger import log_action
from datetime import datetime, timezone, timedelta
import uuid
import hashlib
import secrets

router = APIRouter(prefix="/trusted-devices", tags=["Trusted Devices"])

# =============================================================================
# CONFIGURATION
# =============================================================================

TRUST_DURATION_DAYS = 30  # How long a device remains trusted

# =============================================================================
# MODELS
# =============================================================================

class TrustDeviceRequest(BaseModel):
    device_name: Optional[str] = None

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_device_token() -> str:
    """Generate a secure device trust token"""
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    """Hash a token for storage"""
    return hashlib.sha256(token.encode()).hexdigest()

def get_device_fingerprint(request: Request) -> str:
    """Generate a device fingerprint from request headers"""
    user_agent = request.headers.get("user-agent", "")
    # Combine user agent with some stable identifier
    fingerprint = hashlib.md5(user_agent.encode()).hexdigest()[:16]
    return fingerprint

async def is_device_trusted(user_id: str, device_token: str) -> bool:
    """Check if a device is trusted for 2FA bypass"""
    if not device_token:
        return False

    token_hash = hash_token(device_token)

    device = await trusted_device_repository.find_one({
        "user_id": user_id,
        "token_hash": token_hash,
        "is_active": 1
    })

    if not device:
        return False

    # Check expiration
    expires_at = datetime.fromisoformat(device["expires_at"].replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        # Device trust expired
        await trusted_device_repository.update_device(device["id"], {"is_active": 0})
        return False

    # Update last used
    await trusted_device_repository.update_device(
        device["id"],
        {"last_used": datetime.now(timezone.utc).isoformat()}
    )

    return True

async def create_trusted_device(
    user_id: str,
    request: Request,
    device_name: Optional[str] = None
) -> str:
    """Create a new trusted device entry and return the token"""
    token = generate_device_token()
    token_hash = hash_token(token)

    user_agent = request.headers.get("user-agent", "Unknown")
    ip_address = request.client.host if request.client else "Unknown"
    fingerprint = get_device_fingerprint(request)

    # Auto-generate device name if not provided
    if not device_name:
        if "iPhone" in user_agent or "iPad" in user_agent:
            device_name = "iOS Device"
        elif "Android" in user_agent:
            device_name = "Android Device"
        elif "Mac" in user_agent:
            device_name = "Mac"
        elif "Windows" in user_agent:
            device_name = "Windows PC"
        elif "Linux" in user_agent:
            device_name = "Linux Device"
        else:
            device_name = "Unknown Device"

    device_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "token_hash": token_hash,
        "device_name": device_name,
        "device_fingerprint": fingerprint,
        "user_agent": user_agent[:500],  # Limit length
        "ip_address": ip_address,
        "is_active": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=TRUST_DURATION_DAYS)).isoformat(),
        "last_used": datetime.now(timezone.utc).isoformat()
    }

    await trusted_device_repository.create(device_doc)

    return token

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("")
async def list_trusted_devices(user: dict = Depends(get_current_user)):
    """List all trusted devices for the current user"""
    devices = await trusted_device_repository.find_by_user(user["id"])

    # Check for expired devices and filter
    now = datetime.now(timezone.utc)
    active_devices = []
    for device in devices:
        if not device.get("is_active"):
            continue
        expires_at = datetime.fromisoformat(device["expires_at"].replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at > now:
            device["days_remaining"] = (expires_at - now).days
            # Remove sensitive field
            device.pop("token_hash", None)
            active_devices.append(device)

    return {"devices": active_devices}

@router.post("")
async def trust_current_device(
    request: Request,
    data: TrustDeviceRequest = None,
    user: dict = Depends(get_current_user)
):
    """Trust the current device for 2FA bypass"""
    # Check if user has 2FA enabled
    totp_secret = await totp_secret_repository.find_by_user(user["id"])

    if not totp_secret or not totp_secret.get("verified"):
        raise HTTPException(
            status_code=400,
            detail="2FA must be enabled to trust devices"
        )

    device_name = data.device_name if data else None
    token = await create_trusted_device(user["id"], request, device_name)

    # Log device trust
    await log_action(
        user, "device_trusted", request,
        details={"device_name": device_name or "Auto-detected"}
    )

    return {
        "message": "Device trusted successfully",
        "trust_token": token,
        "expires_in_days": TRUST_DURATION_DAYS
    }

@router.delete("/{device_id}")
async def revoke_trusted_device(
    device_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Revoke trust for a specific device"""
    device = await trusted_device_repository.find_one({"id": device_id, "user_id": user["id"]})
    if not device:
        raise HTTPException(status_code=404, detail="Trusted device not found")

    device_name = device.get("device_name", "Unknown")

    await trusted_device_repository.update_device(
        device_id,
        {"is_active": 0, "revoked_at": datetime.now(timezone.utc).isoformat()}
    )

    # Log device revocation
    await log_action(
        user, "device_trust_revoked", request,
        target_type="trusted_device",
        target_id=device_id,
        details={"device_name": device_name}
    )

    return {"message": "Device trust revoked"}

@router.delete("")
async def revoke_all_trusted_devices(request: Request, user: dict = Depends(get_current_user)):
    """Revoke trust for all devices"""
    devices = await trusted_device_repository.find_by_user(user["id"])
    revoked_count = 0

    now = datetime.now(timezone.utc).isoformat()
    for device in devices:
        if device.get("is_active"):
            await trusted_device_repository.update_device(
                device["id"],
                {"is_active": 0, "revoked_at": now}
            )
            revoked_count += 1

    # Log bulk revocation
    if revoked_count > 0:
        await log_action(
            user, "all_devices_trust_revoked", request,
            details={"revoked_count": revoked_count}
        )

    return {"message": f"Revoked {revoked_count} trusted device(s)"}

@router.get("/check")
async def check_device_trusted(
    request: Request,
    trust_token: str = None,
    user: dict = Depends(get_current_user)
):
    """Check if the current request has a valid trust token"""
    # Get token from query or header
    if not trust_token:
        trust_token = request.headers.get("X-Device-Trust-Token")

    is_trusted = await is_device_trusted(user["id"], trust_token)

    return {"is_trusted": is_trusted}
