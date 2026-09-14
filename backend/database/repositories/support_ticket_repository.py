"""
Support ticket repository — user-facing issue reporting and tracking.
"""
from typing import Optional, List, Any
from .base_repository import BaseRepository


class SupportTicketRepository(BaseRepository):
    def __init__(self):
        super().__init__("support_tickets")

    async def find_by_id(self, ticket_id: str) -> Optional[dict]:
        return await self.find_one({"id": ticket_id})

    async def find_by_number(self, ticket_number: str) -> Optional[dict]:
        return await self.find_one({"ticket_number": ticket_number})

    async def find_by_user(self, user_id: str, limit: int = 50) -> List[dict]:
        return await self.find_many(
            {"user_id": user_id},
            order_by="created_at",
            order_dir="DESC",
            limit=limit,
        )

    async def list_all(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[dict]:
        conditions: dict[str, Any] = {}
        if status:
            conditions["status"] = status
        return await self.find_many(
            conditions,
            order_by="updated_at",
            order_dir="DESC",
            limit=limit,
            offset=offset,
        )

    async def count_all(self, status: Optional[str] = None) -> int:
        conditions: dict[str, Any] = {}
        if status:
            conditions["status"] = status
        return await self.count(conditions)


class SupportTicketMessageRepository(BaseRepository):
    def __init__(self):
        super().__init__("support_ticket_messages")

    async def find_by_ticket(self, ticket_id: str) -> List[dict]:
        return await self.find_many(
            {"ticket_id": ticket_id},
            order_by="created_at",
            order_dir="ASC",
        )


support_ticket_repository = SupportTicketRepository()
support_ticket_message_repository = SupportTicketMessageRepository()
