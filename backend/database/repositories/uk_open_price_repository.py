"""
UK Open Prices repository — local offline copy of Open Food Facts Open Prices (GBP).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_repository import BaseRepository


class UkOpenPriceRepository(BaseRepository):
    """Persisted GBP Open Prices catalog for offline cost estimates."""

    def __init__(self):
        super().__init__("uk_open_prices")

    async def count_all(self) -> int:
        pool = await self._get_db()
        async with pool.acquire() as conn:
            return int(await conn.fetchval("SELECT COUNT(*) FROM uk_open_prices") or 0)

    async def latest_synced_at(self) -> Optional[datetime]:
        pool = await self._get_db()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT MAX(synced_at) FROM uk_open_prices")

    async def replace_catalog(self, entries: List[Dict[str, Any]]) -> int:
        """Replace the whole catalog in one transaction (daily sync).

        Caller must not pass an empty list unless intentionally wiping —
        sync_uk_open_prices refuses empty downloads before calling this.
        """
        if not entries:
            return 0
        pool = await self._get_db()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM uk_open_prices")
                # Extra safety: unique by id in case caller forgot to dedupe
                seen = set()
                rows = []
                for e in entries:
                    eid = e.get("id") or str(uuid.uuid4())
                    if eid in seen:
                        continue
                    seen.add(eid)
                    rows.append(
                        (
                            eid,
                            e.get("name") or "",
                            e.get("name_norm") or "",
                            float(e.get("price") or 0),
                            e.get("currency") or "GBP",
                            e.get("store"),
                            e.get("observed_date") or e.get("date"),
                            e.get("product_code"),
                            e.get("quantity"),
                            e.get("quantity_unit"),
                            e.get("price_per"),
                            e.get("per_kg"),
                            e.get("entry_type") or e.get("type") or "PRODUCT",
                            now,
                        )
                    )
                if not rows:
                    return 0
                await conn.executemany(
                    """
                    INSERT INTO uk_open_prices (
                        id, name, name_norm, price, currency, store, observed_date,
                        product_code, quantity, quantity_unit, price_per, per_kg,
                        entry_type, synced_at
                    ) VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14
                    )
                    """,
                    rows,
                )
                return len(rows)

    async def find_all(self, limit: int = 5000) -> List[dict]:
        return await self.find_many({}, order_by="name", order_dir="ASC", limit=limit)

    async def search_by_name(self, name_norm: str, limit: int = 50) -> List[dict]:
        """Substring search on normalized name for offline matching.

        Only matches catalog names containing the query (not the reverse),
        so short tokens like 'oil' / 'ham' do not latch onto unrelated products.
        """
        pool = await self._get_db()
        # Escape LIKE metacharacters in user/query text
        safe = (
            (name_norm or "")
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = f"%{safe}%"
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM uk_open_prices
                WHERE name_norm LIKE $1 ESCAPE '\\'
                ORDER BY observed_date DESC NULLS LAST
                LIMIT $2
                """,
                pattern,
                limit,
            )
        from ..connection import rows_to_dicts

        return rows_to_dicts(rows)


uk_open_price_repository = UkOpenPriceRepository()
