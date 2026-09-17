"""Per-user recipe import attempts (in-progress + history) for Settings / Home."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from .base_repository import BaseRepository


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _dumps_result(result: Any) -> Optional[str]:
    if result is None:
        return None
    if isinstance(result, str):
        return result[:500_000] or None
    try:
        return json.dumps(result, ensure_ascii=False, default=str)[:500_000]
    except Exception:
        return None


def _loads_result(raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return None


class ImportAttemptRepository(BaseRepository):
    def __init__(self):
        super().__init__("import_attempts")

    async def start_attempt(
        self,
        *,
        import_id: str,
        user_id: str,
        kind: str,
        source_url: Optional[str] = None,
    ) -> None:
        if not import_id or not user_id or user_id == "unknown":
            return
        now = _naive_now()
        pool = await self._get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO import_attempts (
                    id, user_id, kind, source_url, status, title, error, recipe_id,
                    result_json, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, 'importing', NULL, NULL, NULL, NULL, $5, $5
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = CASE
                        WHEN import_attempts.status IN ('succeeded', 'failed')
                            THEN import_attempts.status
                        ELSE 'importing'
                    END,
                    source_url = COALESCE(EXCLUDED.source_url, import_attempts.source_url),
                    kind = EXCLUDED.kind,
                    result_json = CASE
                        WHEN import_attempts.status IN ('succeeded', 'failed')
                            THEN import_attempts.result_json
                        ELSE NULL
                    END,
                    error = CASE
                        WHEN import_attempts.status IN ('succeeded', 'failed')
                            THEN import_attempts.error
                        ELSE NULL
                    END,
                    updated_at = EXCLUDED.updated_at
                """,
                import_id[:64],
                user_id,
                (kind or "import")[:40],
                (source_url or "")[:2000] or None,
                now,
            )

    async def finish_attempt(
        self,
        *,
        import_id: str,
        status: str,
        title: Optional[str] = None,
        error: Optional[str] = None,
        recipe_id: Optional[str] = None,
        source_url: Optional[str] = None,
        user_id: Optional[str] = None,
        kind: Optional[str] = None,
        result: Any = None,
    ) -> None:
        if not import_id:
            return
        normalized = {
            "success": "succeeded",
            "succeeded": "succeeded",
            "error": "failed",
            "failed": "failed",
            "blocked": "failed",
            "importing": "importing",
            "started": "importing",
        }.get((status or "").lower(), (status or "failed")[:20])
        now = _naive_now()
        result_json = _dumps_result(result)
        pool = await self._get_db()
        async with pool.acquire() as conn:
            q = await conn.execute(
                """
                UPDATE import_attempts SET
                    status = $2,
                    title = COALESCE($3, title),
                    error = COALESCE($4, error),
                    recipe_id = COALESCE($5, recipe_id),
                    source_url = COALESCE($6, source_url),
                    result_json = COALESCE($7, result_json),
                    updated_at = $8
                WHERE id = $1
                """,
                import_id[:64],
                normalized,
                (title or "")[:300] or None,
                (error or "")[:2000] or None,
                recipe_id,
                (source_url or "")[:2000] or None,
                result_json,
                now,
            )
            if q.endswith("UPDATE 0") and user_id and user_id != "unknown":
                await conn.execute(
                    """
                    INSERT INTO import_attempts (
                        id, user_id, kind, source_url, status, title, error, recipe_id,
                        result_json, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $10
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        title = COALESCE(EXCLUDED.title, import_attempts.title),
                        error = COALESCE(EXCLUDED.error, import_attempts.error),
                        recipe_id = COALESCE(EXCLUDED.recipe_id, import_attempts.recipe_id),
                        result_json = COALESCE(EXCLUDED.result_json, import_attempts.result_json),
                        updated_at = EXCLUDED.updated_at
                    """,
                    import_id[:64],
                    user_id,
                    (kind or "import")[:40],
                    (source_url or "")[:2000] or None,
                    normalized,
                    (title or "")[:300] or None,
                    (error or "")[:2000] or None,
                    recipe_id,
                    result_json,
                    now,
                )

    def _row_to_dict(self, r, *, include_result: bool = False) -> dict[str, Any]:
        out = {
            "id": r["id"],
            "kind": r["kind"],
            "url": r["source_url"],
            "status": r["status"],
            "title": r["title"],
            "error": r["error"],
            "recipe_id": r["recipe_id"],
            "created_at": _iso(r["created_at"]),
            "updated_at": _iso(r["updated_at"]),
        }
        if include_result:
            result = _loads_result(r.get("result_json") if hasattr(r, "get") else r["result_json"])
            out["result"] = result
            if isinstance(result, dict) and "recipe" in result:
                out["recipe"] = result.get("recipe")
            elif isinstance(result, dict) and (
                result.get("title") or result.get("ingredients") or result.get("instructions")
            ):
                out["recipe"] = result
            else:
                out["recipe"] = None
            if isinstance(result, dict):
                out["used_ai"] = bool(result.get("used_ai", True))
        return out

    async def get_for_user(
        self,
        *,
        import_id: str,
        user_id: str,
        include_result: bool = True,
    ) -> Optional[dict[str, Any]]:
        if not import_id or not user_id:
            return None
        pool = await self._get_db()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, kind, source_url, status, title, error, recipe_id,
                       result_json, created_at, updated_at
                FROM import_attempts
                WHERE id = $1 AND user_id = $2
                """,
                import_id[:64],
                user_id,
            )
        if not row:
            return None
        return self._row_to_dict(row, include_result=include_result)

    async def list_for_user(
        self,
        *,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        pool = await self._get_db()
        limit = max(1, min(int(limit or 50), 100))
        offset = max(0, int(offset or 0))
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, kind, source_url, status, title, error, recipe_id,
                           created_at, updated_at
                    FROM import_attempts
                    WHERE user_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    LIMIT $3 OFFSET $4
                    """,
                    user_id,
                    status,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, kind, source_url, status, title, error, recipe_id,
                           created_at, updated_at
                    FROM import_attempts
                    WHERE user_id = $1
                    ORDER BY
                        CASE status WHEN 'importing' THEN 0 ELSE 1 END,
                        created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    user_id,
                    limit,
                    offset,
                )
        return [self._row_to_dict(r, include_result=False) for r in rows]


import_attempt_repository = ImportAttemptRepository()
