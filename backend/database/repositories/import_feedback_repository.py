"""Repository for recipe-import quality feedback from users."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .base_repository import BaseRepository


def _as_timestamp(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return datetime.now(timezone.utc).replace(tzinfo=None)
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ImportFeedbackRepository(BaseRepository):
    def __init__(self):
        super().__init__("import_feedback")

    async def create_feedback(
        self,
        *,
        user_id: str,
        rating: str,
        import_id: Optional[str] = None,
        source_url: Optional[str] = None,
        import_mode: Optional[str] = None,
        recipe_id: Optional[str] = None,
        note: str = "",
        original_recipe: Optional[dict] = None,
        corrected_recipe: Optional[dict] = None,
        platform: Optional[str] = None,
    ) -> dict[str, Any]:
        pool = await self._get_db()
        feedback_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        orig_json = json.dumps(original_recipe) if original_recipe is not None else None
        corr_json = json.dumps(corrected_recipe) if corrected_recipe is not None else None
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO import_feedback (
                    id, user_id, import_id, source_url, import_mode, recipe_id,
                    rating, note, original_recipe, corrected_recipe, platform, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6,
                    $7, $8, $9::jsonb, $10::jsonb, $11, $12
                )
                """,
                feedback_id,
                user_id,
                (import_id or "")[:64] or None,
                (source_url or "")[:2000] or None,
                (import_mode or "")[:40] or None,
                recipe_id,
                rating,
                (note or "")[:2000],
                orig_json,
                corr_json,
                (platform or "")[:40] or None,
                now,
            )
        return {
            "id": feedback_id,
            "user_id": user_id,
            "import_id": import_id,
            "rating": rating,
            "created_at": now.isoformat(),
        }

    async def recent(self, *, limit: int = 50) -> list[dict]:
        pool = await self._get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, import_id, source_url, import_mode, recipe_id,
                       rating, note, platform, created_at
                FROM import_feedback
                ORDER BY created_at DESC
                LIMIT $1
                """,
                max(1, min(int(limit), 200)),
            )
        return [dict(r) for r in rows]


import_feedback_repository = ImportFeedbackRepository()
