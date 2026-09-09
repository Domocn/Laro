"""
AI chat memory — persist cooking-assistant conversations for review and bug reports.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from .base_repository import BaseRepository


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AiChatSessionRepository(BaseRepository):
    def __init__(self):
        super().__init__("ai_chat_sessions")

    async def find_by_id_for_user(self, session_id: str, user_id: str) -> Optional[dict]:
        row = await self.find_one({"id": session_id})
        if not row or row.get("user_id") != user_id:
            return None
        return row

    async def list_for_user(self, user_id: str, limit: int = 40) -> List[dict]:
        return await self.find_many(
            {"user_id": user_id},
            order_by="updated_at",
            order_dir="DESC",
            limit=limit,
        )

    async def create_session(self, user_id: str, title: str = "New chat") -> dict:
        now = _now()
        session = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": (title or "New chat")[:200],
            "created_at": now,
            "updated_at": now,
        }
        await self.insert(session)
        return session

    async def touch(
        self,
        session_id: str,
        *,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        updates = {"updated_at": _now()}
        if title:
            updates["title"] = title[:200]
        where = {"id": session_id}
        if user_id:
            where["user_id"] = user_id
        await self.update(where, updates)

    async def delete_for_user(self, session_id: str, user_id: str) -> bool:
        session = await self.find_by_id_for_user(session_id, user_id)
        if not session:
            return False
        await ai_chat_message_repository.delete({"session_id": session_id})
        deleted = await self.delete({"id": session_id, "user_id": user_id})
        return deleted > 0


class AiChatMessageRepository(BaseRepository):
    def __init__(self):
        super().__init__("ai_chat_messages")

    async def list_for_session(
        self,
        session_id: str,
        *,
        user_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[dict]:
        where = {"session_id": session_id}
        if user_id:
            where["user_id"] = user_id
        return await self.find_many(
            where,
            order_by="created_at",
            order_dir="ASC",
            limit=limit,
        )

    async def append(
        self,
        *,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
    ) -> dict:
        msg = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "role": role if role in ("user", "assistant", "system") else "user",
            "content": content or "",
            "created_at": _now(),
        }
        await self.insert(msg)
        return msg


ai_chat_session_repository = AiChatSessionRepository()
ai_chat_message_repository = AiChatMessageRepository()
