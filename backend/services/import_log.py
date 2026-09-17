"""
Persistent, structured logs for recipe imports (URL / reel / video / text).

Each import gets an `import_id`. Steps are:
  1. Emitted to logger `laro.import` (docker/Portainer)
  2. Appended as JSON lines under uploads/import-logs/YYYY-MM-DD.jsonl

Search:  grep import_id=imp_xxx  or  jq on the jsonl file.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("laro.import")

_lock = threading.Lock()


def _logs_dir() -> Path:
    base = os.getenv("IMPORT_LOG_DIR", "").strip()
    if base:
        path = Path(base)
    else:
        # Prefer mounted uploads so logs survive container recreate
        path = Path(os.getenv("UPLOAD_DIR", "uploads")) / "import-logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


class ImportTrace:
    """Correlate one import attempt across SocialFetch / yt-dlp / vision / LLM."""

    def __init__(
        self,
        kind: str,
        *,
        user_id: Optional[str] = None,
        url: Optional[str] = None,
        extra: Optional[dict] = None,
    ):
        self.import_id = f"imp_{uuid.uuid4().hex[:12]}"
        self.kind = kind
        self.user_id = user_id or "unknown"
        self.url = url
        self.started = time.time()
        self.steps: list[dict] = []
        self.status = "started"
        self._start(
            {
                "kind": kind,
                "user_id": self.user_id,
                "url": url,
                **(extra or {}),
            }
        )
        _schedule_persist_start(self)

    def _start(self, payload: dict) -> None:
        self.step("start", **payload)

    def step(self, name: str, level: str = "info", **data: Any) -> None:
        elapsed_ms = int((time.time() - self.started) * 1000)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "import_id": self.import_id,
            "kind": self.kind,
            "user_id": self.user_id,
            "step": name,
            "elapsed_ms": elapsed_ms,
            "data": _json_safe(data),
        }
        self.steps.append(record)
        msg = (
            f"[import_id={self.import_id}] kind={self.kind} step={name} "
            f"elapsed_ms={elapsed_ms} {_compact(data)}"
        )
        log_fn = getattr(logger, level if level in ("debug", "info", "warning", "error") else "info")
        log_fn(msg)
        _append_jsonl(record)

    def finish(self, status: str, **data: Any) -> dict:
        self.status = status
        elapsed_ms = int((time.time() - self.started) * 1000)
        self.step(
            "finish",
            level="info" if status == "success" else "warning",
            status=status,
            total_elapsed_ms=elapsed_ms,
            step_count=len(self.steps),
            **data,
        )
        _schedule_persist_finish(self, status, data)
        return {
            "import_id": self.import_id,
            "status": status,
            "elapsed_ms": elapsed_ms,
        }


def _schedule(coro) -> None:
    """Best-effort schedule for FastAPI request handlers (running event loop)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    try:
        loop.create_task(coro)
    except Exception:
        logger.debug("import attempt persist schedule failed", exc_info=True)


def _schedule_persist_start(trace: "ImportTrace") -> None:
    async def _run():
        try:
            from database.repositories.import_attempt_repository import import_attempt_repository

            await import_attempt_repository.start_attempt(
                import_id=trace.import_id,
                user_id=trace.user_id,
                kind=trace.kind,
                source_url=trace.url,
            )
        except Exception:
            logger.debug("import attempt start persist failed", exc_info=True)

    _schedule(_run())


def _schedule_persist_finish(trace: "ImportTrace", status: str, data: dict) -> None:
    title = data.get("title") or data.get("recipe_title")
    if not title and isinstance(data.get("recipe"), dict):
        title = data["recipe"].get("title")
    error = data.get("error") or data.get("detail") or data.get("reason")
    if error is not None:
        error = str(error)[:2000]
    recipe_id = data.get("recipe_id")
    # Persist extracted recipe so clients can poll after Cloudflare/proxy timeouts.
    result_payload = None
    if isinstance(data.get("recipe"), dict):
        result_payload = {
            "recipe": data["recipe"],
            "used_ai": bool(data.get("used_ai", True)),
        }
    elif data.get("store_result") and isinstance(data.get("result"), dict):
        result_payload = data["result"]

    async def _run():
        try:
            from database.repositories.import_attempt_repository import import_attempt_repository

            await import_attempt_repository.finish_attempt(
                import_id=trace.import_id,
                status=status,
                title=str(title)[:300] if title else None,
                error=error,
                recipe_id=str(recipe_id) if recipe_id else None,
                source_url=trace.url,
                user_id=trace.user_id,
                kind=trace.kind,
                result=result_payload,
            )
        except Exception:
            logger.debug("import attempt finish persist failed", exc_info=True)

    _schedule(_run())


def _compact(data: dict, limit: int = 240) -> str:
    if not data:
        return ""
    try:
        s = json.dumps(_json_safe(data), ensure_ascii=False, separators=(",", ":"))
    except Exception:
        s = str(data)
    if len(s) > limit:
        return s[: limit - 3] + "..."
    return s


def _append_jsonl(record: dict) -> None:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = _logs_dir() / f"{day}.jsonl"
    line = json.dumps(record, ensure_ascii=False) + "\n"
    try:
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception as e:
        logger.warning("Failed to write import log file %s: %s", path, e)


def recipe_summary(recipe: Optional[dict]) -> dict:
    if not recipe or not isinstance(recipe, dict):
        return {"empty": True}
    ings = recipe.get("ingredients") or []
    insts = recipe.get("instructions") or []
    return {
        "title": (recipe.get("title") or "")[:120],
        "ingredients": len(ings) if isinstance(ings, list) else 0,
        "instructions": len(insts) if isinstance(insts, list) else 0,
        "has_nutrition": bool(recipe.get("nutrition")),
    }
