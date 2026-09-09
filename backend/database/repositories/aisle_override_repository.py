"""
Aisle Override Repository — learned grocery aisle placements per household.
"""
from typing import Optional, Dict
from datetime import datetime, timezone
import uuid
from .base_repository import BaseRepository


class AisleOverrideRepository(BaseRepository):
    def __init__(self):
        super().__init__("aisle_overrides")

    async def get_map_for_household(self, household_id: str) -> Dict[str, str]:
        """Return {normalized_ingredient_key: aisle} for a household."""
        rows = await self.find_many({"household_id": household_id}, limit=2000)
        return {
            (r.get("ingredient_key") or "").lower(): r["aisle"]
            for r in rows
            if r.get("ingredient_key") and r.get("aisle")
        }

    async def upsert(self, household_id: str, ingredient_key: str, aisle: str) -> dict:
        key = (ingredient_key or "").lower().strip()
        if not key:
            raise ValueError("ingredient_key required")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pool = await self._get_db()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                """SELECT id FROM aisle_overrides
                   WHERE household_id = $1 AND ingredient_key = $2""",
                household_id, key,
            )
            if existing:
                await conn.execute(
                    """UPDATE aisle_overrides
                       SET aisle = $1, updated_at = $2
                       WHERE id = $3""",
                    aisle, now, existing["id"],
                )
                return {
                    "id": existing["id"],
                    "household_id": household_id,
                    "ingredient_key": key,
                    "aisle": aisle,
                    "updated_at": now.isoformat(),
                }
            oid = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO aisle_overrides
                   (id, household_id, ingredient_key, aisle, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $5)""",
                oid, household_id, key, aisle, now,
            )
            return {
                "id": oid,
                "household_id": household_id,
                "ingredient_key": key,
                "aisle": aisle,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }

    async def delete_override(self, household_id: str, ingredient_key: str) -> int:
        return await self.delete({
            "household_id": household_id,
            "ingredient_key": (ingredient_key or "").lower().strip(),
        })


aisle_override_repository = AisleOverrideRepository()
