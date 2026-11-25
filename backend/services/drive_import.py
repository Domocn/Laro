"""
Big-file import from a Google Drive share link.

Phones and Cloudflare cap uploads (~95 MB here), but cookbooks are often
hundreds of MB. The user pastes a Drive link instead; the server downloads the
file itself and works through it as a background job the client polls.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

DRIVE_MAX_BYTES = int(os.environ.get("DRIVE_IMPORT_MAX_MB", "600")) * 1024 * 1024
JOB_TTL_SECONDS = 2 * 24 * 3600

_ID_PATTERNS = (
    re.compile(r"/file/d/([A-Za-z0-9_-]{20,})"),
    re.compile(r"[?&]id=([A-Za-z0-9_-]{20,})"),
)
_DRIVE_HOSTS = ("drive.google.com", "docs.google.com", "drive.usercontent.google.com")


class DriveImportError(Exception):
    """Plain-language problem to show the user."""


def drive_file_id(url: str) -> str:
    """Pull the file id out of a Google Drive share link; reject anything else."""
    url = (url or "").strip()
    m = re.match(r"^https?://([^/]+)/", url + "/")
    if not m or m.group(1).lower() not in _DRIVE_HOSTS:
        raise DriveImportError("That isn't a Google Drive link. In Drive, use Share → Copy link.")
    for pat in _ID_PATTERNS:
        found = pat.search(url)
        if found:
            return found.group(1)
    raise DriveImportError("Couldn't find the file in that Drive link. In Drive, use Share → Copy link.")


async def download_drive_file(file_id: str, dest_path: str, *, max_bytes: int = DRIVE_MAX_BYTES) -> int:
    """Stream a publicly shared Drive file to disk. Returns its size in bytes."""
    url = "https://drive.usercontent.google.com/download"
    params = {"id": file_id, "export": "download", "confirm": "t"}
    size = 0
    timeout = httpx.Timeout(30.0, read=120.0)
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        async with client.stream("GET", url, params=params) as resp:
            ctype = resp.headers.get("content-type", "")
            if resp.status_code in (401, 403, 404) or "text/html" in ctype:
                raise DriveImportError(
                    "Laro can't open that file. In Google Drive, set sharing to "
                    "\"Anyone with the link\" and try again."
                )
            if resp.status_code != 200:
                raise DriveImportError(f"Google Drive didn't send the file (error {resp.status_code}). Try again shortly.")
            declared = int(resp.headers.get("content-length") or 0)
            if declared > max_bytes:
                raise DriveImportError(f"That file is too big (max {max_bytes // (1024 * 1024)} MB).")
            with open(dest_path, "wb") as fh:
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise DriveImportError(f"That file is too big (max {max_bytes // (1024 * 1024)} MB).")
                    fh.write(chunk)
    with open(dest_path, "rb") as fh:
        if fh.read(5) != b"%PDF-":
            raise DriveImportError("That file isn't a PDF. Share a PDF cookbook or recipe file.")
    return size


# ── Job status (Redis so any API worker can answer the poll; memory fallback for self-host) ──

_memory_jobs: Dict[str, Dict[str, Any]] = {}
_redis = None


async def _redis_client():
    global _redis
    if _redis is None:
        try:
            import redis.asyncio as redis
            from config import settings

            client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
            await client.ping()
            _redis = client
        except Exception as e:  # pragma: no cover - depends on deployment
            logger.info("Drive import jobs using in-memory store (%s)", e)
            _redis = False
    return _redis or None


def _key(job_id: str) -> str:
    return f"laro:import_job:{job_id}"


async def save_job(job: Dict[str, Any]) -> None:
    job["updated_at"] = time.time()
    client = await _redis_client()
    if client:
        await client.set(_key(job["id"]), json.dumps(job), ex=JOB_TTL_SECONDS)
    else:
        _memory_jobs[job["id"]] = dict(job)


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    client = await _redis_client()
    if client:
        raw = await client.get(_key(job_id))
        return json.loads(raw) if raw else None
    return _memory_jobs.get(job_id)


_ACTIVE_STALE_SECONDS = 10 * 60  # no progress for 10 min = the worker died; allow a fresh start


def _active_key(user_id: str, file_id: str) -> str:
    return f"laro:import_active:{user_id}:{file_id}"


async def mark_running(job: Dict[str, Any]) -> None:
    client = await _redis_client()
    key = _active_key(job["user_id"], job["file_id"])
    if client:
        await client.set(key, job["id"], ex=JOB_TTL_SECONDS)
    else:
        _memory_jobs[key] = {"id": job["id"]}


async def find_running_job(user_id: str, file_id: str) -> Optional[Dict[str, Any]]:
    """The unfinished, still-progressing import of this file for this user, if any."""
    client = await _redis_client()
    key = _active_key(user_id, file_id)
    job_id = await client.get(key) if client else (_memory_jobs.get(key) or {}).get("id")
    job = await get_job(job_id) if job_id else None
    if not job or job.get("status") in ("done", "failed"):
        return None
    if time.time() - float(job.get("updated_at") or 0) > _ACTIVE_STALE_SECONDS:
        return None
    return job


def new_job(user_id: str, file_id: str) -> Dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "file_id": file_id,
        "status": "queued",  # queued → downloading → reading → importing → done | failed
        "message": "Starting…",
        "part": 0,
        "parts": 0,
        "recipe_count": 0,
        "skipped_count": 0,
        "created_at": time.time(),
    }
