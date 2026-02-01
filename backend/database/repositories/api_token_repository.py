"""
API Token Repository - Handles long-lived API tokens for integrations like Home Assistant
"""
import secrets
import hashlib
import logging
from typing import Optional, List
from datetime import datetime, timezone
from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


def generate_token() -> tuple[str, str]:
    """Generate a new API token and its hash.

    Returns:
        tuple: (plain_token, token_hash) - plain token is shown once, hash is stored
    """
    # Generate a secure random token
    plain_token = f"mise_{secrets.token_urlsafe(32)}"
    # Store the hash, not the plain token
    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
    return plain_token, token_hash


def hash_token(token: str) -> str:
    """Hash a token for comparison."""
    return hashlib.sha256(token.encode()).hexdigest()


class APITokenRepository(BaseRepository):
    """Repository for API tokens"""

    def __init__(self):
        super().__init__("api_tokens")

    async def create(self, token_data: dict) -> dict:
        """Create a new API token"""
        return await self.insert(token_data)

    async def find_by_hash(self, token_hash: str) -> Optional[dict]:
        """Find token by hash"""
        return await self.find_one({"token_hash": token_hash})

    async def find_by_user(self, user_id: str) -> List[dict]:
        """Find all tokens for a user"""
        return await self.find_many(
            {"user_id": user_id},
            order_by="created_at",
            order_dir="DESC"
        )

    async def find_by_id(self, token_id: str) -> Optional[dict]:
        """Find token by ID"""
        return await self.find_one({"id": token_id})

    async def delete_token(self, token_id: str, user_id: str) -> int:
        """Delete a token (must belong to user)"""
        return await self.delete({"id": token_id, "user_id": user_id})

    async def update_last_used(self, token_id: str) -> None:
        """Update last used timestamp"""
        pool = await self._get_db()
        # Use naive UTC datetime for PostgreSQL TIMESTAMP columns
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE api_tokens SET last_used_at = $1 WHERE id = $2",
                now, token_id
            )

    async def validate_token(self, plain_token: str) -> Optional[dict]:
        """Validate a token and return user info if valid"""
        token_hash = hash_token(plain_token)
        logger.info(f"Validating API token - hash prefix: {token_hash[:16]}...")
        token = await self.find_by_hash(token_hash)

        if not token:
            logger.warning(f"API token not found in database - hash prefix: {token_hash[:16]}...")
            return None

        logger.info(f"API token found - id: {token.get('id')}, user_id: {token.get('user_id')}, revoked: {token.get('revoked')}")

        # Check if token is expired
        expires_at = token.get("expires_at")
        if expires_at:
            # Handle string format (from JSON/API)
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            # Convert to naive UTC for comparison (PostgreSQL returns naive datetimes)
            if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=None)
            # Compare with naive UTC now
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if expires_at < now:
                return None

        # Check if token is revoked
        if token.get("revoked"):
            return None

        # Update last used
        await self.update_last_used(token["id"])

        return token

    async def revoke_token(self, token_id: str, user_id: str) -> int:
        """Revoke a token"""
        return await self.update(
            {"id": token_id, "user_id": user_id},
            {"revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}
        )


# Singleton instance
api_token_repository = APITokenRepository()
