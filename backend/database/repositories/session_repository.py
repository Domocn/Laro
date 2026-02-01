"""
Session Repository - Handles session and authentication-related database operations
"""
import json
from typing import Optional, List
from .base_repository import BaseRepository


class SessionRepository(BaseRepository):
    """Repository for session operations"""

    def __init__(self):
        super().__init__("sessions")

    async def find_by_id(self, session_id: str) -> Optional[dict]:
        """Find session by ID"""
        return await self.find_one({"id": session_id})

    async def find_by_token(self, token: str) -> Optional[dict]:
        """Find session by token"""
        return await self.find_one({"token": token})

    async def find_by_user_and_token(self, user_id: str, token: str) -> Optional[dict]:
        """Find session by user ID and token"""
        return await self.find_one({"user_id": user_id, "token": token})

    async def create(self, session_data: dict) -> dict:
        """Create a new session"""
        return await self.insert(session_data)

    async def update_session(self, session_id: str, data: dict) -> int:
        """Update session data"""
        return await self.update({"id": session_id}, data)

    async def delete_session(self, session_id: str) -> int:
        """Delete a session"""
        return await self.delete({"id": session_id})

    async def delete_by_user_and_token(self, user_id: str, token: str) -> int:
        """Delete session by user ID and token"""
        pool = await self._get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM sessions WHERE user_id = $1 AND token = $2",
                user_id, token
            )
        # Parse rowcount from result string (e.g., "DELETE 1")
        rowcount = int(result.split()[-1]) if result else 0
        return rowcount

    async def find_by_user(self, user_id: str) -> List[dict]:
        """Find all sessions for a user"""
        return await self.find_many(
            {"user_id": user_id},
            order_by="created_at",
            order_dir="DESC"
        )

    async def delete_by_user(self, user_id: str) -> int:
        """Delete all sessions for a user"""
        return await self.delete({"user_id": user_id})

    async def find_existing_session(
        self,
        user_id: str,
        user_agent: str = None,
        ip_address: str = None
    ) -> Optional[dict]:
        """Find existing session matching device/IP"""
        pool = await self._get_db()

        if user_agent and ip_address:
            query = """
                SELECT * FROM sessions
                WHERE user_id = $1 AND (user_agent = $2 OR ip_address = $3)
                LIMIT 1
            """
            values = [user_id, user_agent, ip_address]
        elif user_agent:
            query = """
                SELECT * FROM sessions
                WHERE user_id = $1 AND user_agent = $2
                LIMIT 1
            """
            values = [user_id, user_agent]
        elif ip_address:
            query = """
                SELECT * FROM sessions
                WHERE user_id = $1 AND ip_address = $2
                LIMIT 1
            """
            values = [user_id, ip_address]
        else:
            return None

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)

        if row:
            from ..connection import dict_from_row
            return dict_from_row(row)
        return None


class LoginAttemptRepository(BaseRepository):
    """Repository for login attempt tracking"""

    def __init__(self):
        super().__init__("login_attempts")

    async def create(self, attempt_data: dict) -> dict:
        """Record a login attempt"""
        return await self.insert(attempt_data)

    async def count_recent_failures(self, email: str, since: str) -> int:
        """Count failed login attempts since a specific time"""
        pool = await self._get_db()

        query = """
            SELECT COUNT(*) FROM login_attempts
            WHERE email = $1 AND success = FALSE AND timestamp >= $2
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, email, since)

        return row[0] if row else 0

    async def cleanup_old_attempts(self, before: str) -> int:
        """Delete login attempts older than the specified time"""
        pool = await self._get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM login_attempts WHERE timestamp < $1",
                before
            )
        # Parse rowcount from result string (e.g., "DELETE 1")
        rowcount = int(result.split()[-1]) if result else 0
        return rowcount

    async def find_by_user(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[dict]:
        """Find login attempts for a user"""
        return await self.find_many(
            {"user_id": user_id},
            order_by="timestamp",
            order_dir="DESC",
            limit=limit
        )


class TotpSecretRepository(BaseRepository):
    """Repository for TOTP secrets"""

    JSON_FIELDS = ["backup_codes"]

    def __init__(self):
        super().__init__("totp_secrets")

    async def find_by_user(self, user_id: str, verified_only: bool = False) -> Optional[dict]:
        """Find TOTP secret for a user"""
        conditions = {"user_id": user_id}
        if verified_only:
            conditions["verified"] = True

        return await self.find_one(conditions, json_fields=self.JSON_FIELDS)

    async def create(self, totp_data: dict) -> dict:
        """Create a new TOTP secret"""
        return await self.insert(totp_data, json_fields=self.JSON_FIELDS)

    async def update_totp(self, totp_id: str, data: dict) -> int:
        """Update TOTP data"""
        return await self.update({"id": totp_id}, data, json_fields=self.JSON_FIELDS)

    async def delete_by_user(self, user_id: str) -> int:
        """Delete TOTP secret for a user"""
        return await self.delete({"user_id": user_id})


class OAuthAccountRepository(BaseRepository):
    """Repository for OAuth account links"""

    def __init__(self):
        super().__init__("oauth_accounts")

    async def find_by_provider(
        self,
        provider: str,
        provider_id: str
    ) -> Optional[dict]:
        """Find OAuth account by provider and provider ID"""
        return await self.find_one({
            "provider": provider,
            "provider_id": provider_id
        })

    async def find_by_user(self, user_id: str) -> List[dict]:
        """Find all OAuth accounts for a user"""
        return await self.find_many({"user_id": user_id})

    async def create(self, oauth_data: dict) -> dict:
        """Create a new OAuth account link"""
        return await self.insert(oauth_data)

    async def delete_by_user(self, user_id: str) -> int:
        """Delete all OAuth accounts for a user"""
        return await self.delete({"user_id": user_id})

    async def count_by_user(self, user_id: str) -> int:
        """Count OAuth accounts for a user"""
        return await self.count({"user_id": user_id})

    async def delete_by_user_and_provider(self, user_id: str, provider: str) -> bool:
        """Delete OAuth account by user and provider"""
        count = await self.delete({
            "user_id": user_id,
            "provider": provider
        })
        return count > 0


class TrustedDeviceRepository(BaseRepository):
    """Repository for trusted devices"""

    def __init__(self):
        super().__init__("trusted_devices")

    async def find_by_token(self, device_token: str) -> Optional[dict]:
        """Find trusted device by token"""
        return await self.find_one({"device_token": device_token})

    async def find_by_user(self, user_id: str) -> List[dict]:
        """Find all trusted devices for a user"""
        return await self.find_many(
            {"user_id": user_id},
            order_by="last_used",
            order_dir="DESC"
        )

    async def create(self, device_data: dict) -> dict:
        """Create a new trusted device"""
        return await self.insert(device_data)

    async def update_device(self, device_id: str, data: dict) -> int:
        """Update trusted device data"""
        return await self.update({"id": device_id}, data)

    async def delete_device(self, device_id: str) -> int:
        """Delete a trusted device"""
        return await self.delete({"id": device_id})

    async def delete_by_user(self, user_id: str) -> int:
        """Delete all trusted devices for a user"""
        return await self.delete({"user_id": user_id})


class OAuthStateRepository(BaseRepository):
    """Repository for OAuth state tokens (CSRF protection)"""

    def __init__(self):
        super().__init__("oauth_states")

    async def create(self, state_data: dict) -> dict:
        """Create an OAuth state token"""
        return await self.insert(state_data)

    async def find_and_delete(self, state: str) -> Optional[dict]:
        """Find and delete an OAuth state (for one-time use)"""
        result = await self.find_one({"state": state})
        if result:
            await self.delete({"state": state})
        return result

    async def cleanup_expired(self, before: str) -> int:
        """Delete expired OAuth states"""
        pool = await self._get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM oauth_states WHERE created_at < $1",
                before
            )
        # Parse rowcount from result string (e.g., "DELETE 1")
        rowcount = int(result.split()[-1]) if result else 0
        return rowcount


# Singleton instances
session_repository = SessionRepository()
login_attempt_repository = LoginAttemptRepository()
totp_secret_repository = TotpSecretRepository()
oauth_account_repository = OAuthAccountRepository()
trusted_device_repository = TrustedDeviceRepository()
oauth_state_repository = OAuthStateRepository()
