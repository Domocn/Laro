"""
Security Repository - Handles IP allowlist/blocklist
OAuth repositories are in session_repository.py
"""
from typing import Optional, List
from .base_repository import BaseRepository


class IPAllowlistRepository(BaseRepository):
    """Repository for IP allowlist"""

    def __init__(self):
        super().__init__("ip_allowlist")

    async def find_all(self, limit: int = 100) -> List[dict]:
        """Get all allowlist entries"""
        return await self.find_many(limit=limit)

    async def find_by_id(self, rule_id: str) -> Optional[dict]:
        """Find rule by ID"""
        return await self.find_one({"id": rule_id})

    async def create(self, rule_data: dict) -> dict:
        """Create a new allowlist rule"""
        return await self.insert(rule_data)

    async def delete_rule(self, rule_id: str) -> int:
        """Delete an allowlist rule"""
        return await self.delete({"id": rule_id})


class IPBlocklistRepository(BaseRepository):
    """Repository for IP blocklist"""

    def __init__(self):
        super().__init__("ip_blocklist")

    async def find_all(self, limit: int = 100) -> List[dict]:
        """Get all blocklist entries"""
        return await self.find_many(limit=limit)

    async def find_by_id(self, rule_id: str) -> Optional[dict]:
        """Find rule by ID"""
        return await self.find_one({"id": rule_id})

    async def create(self, rule_data: dict) -> dict:
        """Create a new blocklist rule"""
        return await self.insert(rule_data)

    async def delete_rule(self, rule_id: str) -> int:
        """Delete a blocklist rule"""
        return await self.delete({"id": rule_id})


# Singleton instances
ip_allowlist_repository = IPAllowlistRepository()
ip_blocklist_repository = IPBlocklistRepository()
