"""
API Tokens Router - Manage long-lived API tokens for integrations
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid

from dependencies import get_current_user
from database.repositories.api_token_repository import (
    api_token_repository,
    generate_token,
)
from utils.activity_logger import log_action

router = APIRouter(prefix="/api-tokens", tags=["API Tokens"])


class CreateTokenRequest(BaseModel):
    name: str
    expires_in_days: Optional[int] = None  # None = never expires


class TokenResponse(BaseModel):
    id: str
    name: str
    created_at: str
    last_used_at: Optional[str]
    expires_at: Optional[str]
    revoked: bool


class CreateTokenResponse(BaseModel):
    token: str  # Only shown once!
    id: str
    name: str
    expires_at: Optional[str]
    message: str = "Save this token - it won't be shown again!"


@router.post("", response_model=CreateTokenResponse)
async def create_api_token(
    request: CreateTokenRequest,
    req: Request,
    user: dict = Depends(get_current_user)
):
    """Create a new API token for integrations like Home Assistant."""
    # Generate token
    plain_token, token_hash = generate_token()

    # Calculate expiry - use naive UTC datetime for PostgreSQL TIMESTAMP columns
    expires_at = None
    if request.expires_in_days:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)
        ).replace(tzinfo=None)

    # Create token record with naive UTC datetimes for PostgreSQL
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    token_data = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": request.name,
        "token_hash": token_hash,
        "scopes": '["read", "write"]',
        "expires_at": expires_at,
        "created_at": now,
        "revoked": False,
    }

    await api_token_repository.create(token_data)

    # Log token creation
    await log_action(
        user, "api_token_created", req,
        target_type="api_token",
        target_id=token_data["id"],
        details={"name": request.name}
    )

    return CreateTokenResponse(
        token=plain_token,
        id=token_data["id"],
        name=request.name,
        expires_at=expires_at.isoformat() if expires_at else None,
    )


@router.get("", response_model=List[TokenResponse])
async def list_api_tokens(user: dict = Depends(get_current_user)):
    """List all API tokens for the current user."""
    tokens = await api_token_repository.find_by_user(user["id"])

    def to_str(val):
        """Convert datetime to ISO string if needed"""
        if val is None:
            return None
        if hasattr(val, 'isoformat'):
            return val.isoformat()
        return str(val)

    return [
        TokenResponse(
            id=t["id"],
            name=t["name"],
            created_at=to_str(t["created_at"]),
            last_used_at=to_str(t.get("last_used_at")),
            expires_at=to_str(t.get("expires_at")),
            revoked=t.get("revoked", False),
        )
        for t in tokens
    ]


@router.delete("/{token_id}")
async def delete_api_token(
    token_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Delete an API token."""
    deleted = await api_token_repository.delete_token(token_id, user["id"])
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Token not found")

    # Log token deletion
    await log_action(
        user, "api_token_deleted", request,
        target_type="api_token",
        target_id=token_id
    )

    return {"message": "Token deleted"}


@router.post("/{token_id}/revoke")
async def revoke_api_token(
    token_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Revoke an API token (keeps record but invalidates it)."""
    updated = await api_token_repository.revoke_token(token_id, user["id"])
    if updated == 0:
        raise HTTPException(status_code=404, detail="Token not found")

    # Log token revocation
    await log_action(
        user, "api_token_revoked", request,
        target_type="api_token",
        target_id=token_id
    )

    return {"message": "Token revoked"}
