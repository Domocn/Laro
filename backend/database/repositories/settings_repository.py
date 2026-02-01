"""
Settings Repository - Handles system settings, user preferences, and LLM settings
"""
import json
from typing import Optional, List
from .base_repository import BaseRepository


class SystemSettingsRepository(BaseRepository):
    """Repository for system settings"""

    JSON_FIELDS = ["settings"]

    DEFAULT_SETTINGS = {
        "allow_registration": True,
        "allow_admin_registration": False,
        "require_invite_code": False,
        "password_min_length": 8,
        "password_require_uppercase": False,
        "password_require_number": False,
        "password_require_special": False,
        "max_login_attempts": 5,
        "lockout_duration_minutes": 15,
        "session_timeout_minutes": 1440,
        "enable_ip_allowlist": False,
        "enable_ip_blocklist": False,
        "notify_new_login": False,
        "include_links_in_share": False,
    }

    def __init__(self):
        super().__init__("system_settings")

    async def get_settings(self, settings_type: str = "global") -> dict:
        """Get system settings, creating defaults if not exists"""
        pool = await self._get_db()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT settings FROM system_settings WHERE type = $1",
                settings_type
            )

        if row:
            settings = json.loads(row[0]) if row[0] else {}
            # Merge with defaults to ensure all fields are present
            result = {**self.DEFAULT_SETTINGS, **settings}
            return result

        # Create defaults
        await self.update_settings(settings_type, self.DEFAULT_SETTINGS)
        return {**self.DEFAULT_SETTINGS}

    async def update_settings(self, settings_type: str, settings: dict) -> dict:
        """Update system settings"""
        pool = await self._get_db()

        settings_json = json.dumps(settings)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO system_settings (type, settings)
                VALUES ($1, $2)
                ON CONFLICT(type) DO UPDATE SET settings = $2
                """,
                settings_type, settings_json
            )

        return settings

    async def get_setup_status(self) -> dict:
        """Get setup wizard status"""
        settings = await self.get_settings("setup")
        return {"complete": settings.get("complete", False)}

    async def mark_setup_complete(self, completed_at: str) -> dict:
        """Mark setup as complete"""
        return await self.update_settings("setup", {
            "complete": True,
            "completed_at": completed_at
        })


class LLMSettingsRepository(BaseRepository):
    """Repository for per-user LLM settings"""

    def __init__(self):
        super().__init__("llm_settings")

    async def find_by_user(self, user_id: str) -> Optional[dict]:
        """Get LLM settings for a user"""
        return await self.find_one({"user_id": user_id})

    async def upsert_settings(self, user_id: str, settings: dict) -> dict:
        """Create or update LLM settings for a user"""
        return await self.upsert(
            {"user_id": user_id},
            settings
        )

    async def delete_by_user(self, user_id: str) -> int:
        """Delete LLM settings for a user"""
        return await self.delete({"user_id": user_id})


class LLMCacheRepository(BaseRepository):
    """Repository for LLM response caching"""

    def __init__(self):
        super().__init__("llm_cache")

    async def find_by_hash(self, hash: str) -> Optional[dict]:
        """Find cached response by hash"""
        return await self.find_one({"hash": hash})

    async def cache_response(
        self,
        hash: str,
        response: str,
        created_at: float,
        provider: str,
        model: str
    ) -> dict:
        """Cache an LLM response"""
        pool = await self._get_db()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_cache (hash, response, created_at, provider, model)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT(hash) DO UPDATE SET
                    response = $2,
                    created_at = $3,
                    provider = $4,
                    model = $5
                """,
                hash, response, created_at, provider, model
            )

        return {
            "hash": hash,
            "response": response,
            "created_at": created_at,
            "provider": provider,
            "model": model
        }


class CustomPromptsRepository(BaseRepository):
    """Repository for custom AI prompts"""

    def __init__(self):
        super().__init__("custom_prompts")

    async def find_by_user(self, user_id: str) -> Optional[dict]:
        """Get custom prompts for a user"""
        return await self.find_one({"user_id": user_id})

    async def upsert_prompts(self, user_id: str, prompts: dict) -> dict:
        """Create or update custom prompts for a user"""
        return await self.upsert(
            {"user_id": user_id},
            prompts
        )

    async def delete_by_user(self, user_id: str) -> int:
        """Delete custom prompts for a user"""
        return await self.delete({"user_id": user_id})


class UserPreferencesRepository(BaseRepository):
    """Repository for user preferences"""

    JSON_FIELDS = ["dietary", "dietaryRestrictions"]

    def __init__(self):
        super().__init__("user_preferences")

    async def find_by_user(self, user_id: str) -> Optional[dict]:
        """Get preferences for a user"""
        return await self.find_one(
            {"user_id": user_id},
            json_fields=self.JSON_FIELDS
        )

    async def upsert_preferences(self, user_id: str, preferences: dict) -> dict:
        """Create or update preferences for a user"""
        return await self.upsert(
            {"user_id": user_id},
            preferences,
            json_fields=self.JSON_FIELDS
        )

    async def delete_by_user(self, user_id: str) -> int:
        """Delete preferences for a user"""
        return await self.delete({"user_id": user_id})


class InviteCodeRepository(BaseRepository):
    """Repository for invite codes"""

    def __init__(self):
        super().__init__("invite_codes")

    async def find_by_code(self, code: str) -> Optional[dict]:
        """Find invite code by code"""
        return await self.find_one({"code": code})

    async def find_by_id(self, code_id: str) -> Optional[dict]:
        """Find invite code by ID"""
        return await self.find_one({"id": code_id})

    async def create(self, invite_data: dict) -> dict:
        """Create a new invite code"""
        return await self.insert(invite_data)

    async def increment_uses(self, code_id: str) -> int:
        """Increment the uses count for an invite code"""
        pool = await self._get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE invite_codes SET uses = uses + 1 WHERE id = $1",
                code_id
            )
        # Parse rowcount from result string (e.g., "UPDATE 1")
        rowcount = int(result.split()[-1]) if result else 0
        return rowcount

    async def delete_code(self, code_id: str) -> int:
        """Delete an invite code"""
        return await self.delete({"id": code_id})

    async def list_all(self, limit: int = 100) -> List[dict]:
        """List all invite codes"""
        return await self.find_many(
            order_by="created_at",
            order_dir="DESC",
            limit=limit
        )

    async def find_valid_code(self, code: str, current_time: str) -> Optional[dict]:
        """Find a valid (non-expired, uses remaining) invite code"""
        pool = await self._get_db()

        query = """
            SELECT * FROM invite_codes
            WHERE code = $1
            AND (expires_at IS NULL OR expires_at > $2)
            AND uses < max_uses
            LIMIT 1
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, code, current_time)

        if row:
            from ..connection import dict_from_row
            return dict_from_row(row)
        return None


class AuditLogRepository(BaseRepository):
    """Repository for audit logs"""

    JSON_FIELDS = ["details"]

    def __init__(self):
        super().__init__("audit_logs")

    async def create(self, log_data: dict) -> dict:
        """Create an audit log entry"""
        return await self.insert(log_data, json_fields=self.JSON_FIELDS)

    async def find_logs(
        self,
        user_id: str = None,
        action: str = None,
        page: int = 1,
        per_page: int = 50
    ) -> tuple[List[dict], int]:
        """Find audit logs with filtering and pagination"""
        pool = await self._get_db()

        conditions = []
        values = []
        param_count = 1

        if user_id:
            conditions.append(f"user_id = ${param_count}")
            values.append(user_id)
            param_count += 1

        if action:
            conditions.append(f"action LIKE ${param_count}")
            values.append(f"%{action}%")
            param_count += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with pool.acquire() as conn:
            # Count total
            count_query = f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}"
            row = await conn.fetchrow(count_query, *values)
            total = row[0] if row else 0

            # Get paginated results
            offset = (page - 1) * per_page
            query = f"""
                SELECT * FROM audit_logs
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
            """
            final_values = values + [per_page, offset]

            rows = await conn.fetch(query, *final_values)

        from ..connection import rows_to_dicts
        logs = rows_to_dicts(rows)

        # Deserialize JSON fields
        for log in logs:
            if log.get("details"):
                try:
                    log["details"] = json.loads(log["details"])
                except (json.JSONDecodeError, TypeError):
                    pass

        return logs, total


class BackupRepository(BaseRepository):
    """Repository for backups"""

    def __init__(self):
        super().__init__("backups")

    async def create(self, backup_data: dict) -> dict:
        """Create a backup record"""
        return await self.insert(backup_data)

    async def update_backup(self, backup_id: str, data: dict) -> int:
        """Update backup status"""
        return await self.update({"id": backup_id}, data)

    async def list_backups(self, limit: int = 20) -> List[dict]:
        """List recent backups"""
        return await self.find_many(
            order_by="created_at",
            order_dir="DESC",
            limit=limit
        )


class BackupSettingsRepository(BaseRepository):
    """Repository for backup settings"""

    def __init__(self):
        super().__init__("backup_settings")

    async def get_settings(self) -> dict:
        """Get backup settings"""
        settings = await self.find_one({"type": "global"})
        if not settings:
            return {
                "type": "global",
                "auto_backup_enabled": False,
                "interval_hours": 24,
                "max_backups_to_keep": 7,
                "last_backup": None,
                "next_scheduled": None
            }
        return settings

    async def update_settings(self, data: dict) -> dict:
        """Update backup settings"""
        return await self.upsert({"type": "global"}, data)


class CustomRoleRepository(BaseRepository):
    """Repository for custom user roles"""

    JSON_FIELDS = ["permissions"]

    def __init__(self):
        super().__init__("custom_roles")

    async def find_by_id(self, role_id: str) -> Optional[dict]:
        """Find role by ID"""
        return await self.find_one({"id": role_id}, json_fields=self.JSON_FIELDS)

    async def find_by_name(self, name: str) -> Optional[dict]:
        """Find role by name"""
        return await self.find_one({"name": name}, json_fields=self.JSON_FIELDS)

    async def create(self, role_data: dict) -> dict:
        """Create a new custom role"""
        return await self.insert(role_data, json_fields=self.JSON_FIELDS)

    async def update_role(self, role_id: str, data: dict) -> int:
        """Update a custom role"""
        return await self.update({"id": role_id}, data, json_fields=self.JSON_FIELDS)

    async def delete_role(self, role_id: str) -> int:
        """Delete a custom role"""
        return await self.delete({"id": role_id})

    async def list_all(self, limit: int = 100) -> List[dict]:
        """List all custom roles"""
        return await self.find_many(
            json_fields=self.JSON_FIELDS,
            order_by="created_at",
            order_dir="DESC",
            limit=limit
        )


class VoiceSettingsRepository(BaseRepository):
    """Repository for user voice cooking settings"""

    def __init__(self):
        super().__init__("voice_settings")

    async def find_by_user(self, user_id: str) -> Optional[dict]:
        """Get voice settings for a user"""
        return await self.find_one({"user_id": user_id})

    async def upsert_settings(self, user_id: str, settings: dict) -> dict:
        """Create or update voice settings for a user"""
        return await self.upsert({"user_id": user_id}, settings)


class CustomIngredientRepository(BaseRepository):
    """Repository for user-defined custom ingredients (nutrition)"""

    def __init__(self):
        super().__init__("custom_ingredients")

    async def find_by_user(self, user_id: str) -> List[dict]:
        """Get custom ingredients for a user"""
        return await self.find_many(
            {"user_id": user_id},
            order_by="name",
            order_dir="ASC"
        )

    async def find_by_name(self, user_id: str, name: str) -> Optional[dict]:
        """Find custom ingredient by name for a user"""
        return await self.find_one({"user_id": user_id, "name": name})

    async def create(self, ingredient_data: dict) -> dict:
        """Create a custom ingredient"""
        return await self.insert(ingredient_data)


class ShareLinkRepository(BaseRepository):
    """Repository for recipe share links (advanced sharing)"""

    def __init__(self):
        super().__init__("share_links")

    async def find_by_code(self, share_code: str) -> Optional[dict]:
        """Find share link by code"""
        return await self.find_one({"share_code": share_code})

    async def find_by_id(self, link_id: str) -> Optional[dict]:
        """Find share link by ID"""
        return await self.find_one({"id": link_id})

    async def create(self, link_data: dict) -> dict:
        """Create a new share link"""
        return await self.insert(link_data)

    async def update_link(self, link_id: str, data: dict) -> int:
        """Update a share link"""
        return await self.update({"id": link_id}, data)

    async def find_by_user(self, user_id: str, active_only: bool = True) -> List[dict]:
        """Find all share links for a user"""
        conditions = {"user_id": user_id}
        if active_only:
            conditions["is_active"] = True
        return await self.find_many(
            conditions,
            order_by="created_at",
            order_dir="DESC"
        )

    async def increment_views(self, link_id: str) -> int:
        """Increment view count for a share link"""
        pool = await self._get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE share_links SET view_count = view_count + 1 WHERE id = $1",
                link_id
            )
        # Parse rowcount from result string (e.g., "UPDATE 1")
        rowcount = int(result.split()[-1]) if result else 0
        return rowcount


# Singleton instances
system_settings_repository = SystemSettingsRepository()
llm_settings_repository = LLMSettingsRepository()
llm_cache_repository = LLMCacheRepository()
custom_prompts_repository = CustomPromptsRepository()
user_preferences_repository = UserPreferencesRepository()
invite_code_repository = InviteCodeRepository()
audit_log_repository = AuditLogRepository()
backup_repository = BackupRepository()
backup_settings_repository = BackupSettingsRepository()
custom_role_repository = CustomRoleRepository()
voice_settings_repository = VoiceSettingsRepository()
custom_ingredient_repository = CustomIngredientRepository()
share_link_repository = ShareLinkRepository()
