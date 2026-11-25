"""
Fill recipe macros after the response (saves and imports never wait on the AI).

``schedule_recipe_macros(ids, user)`` starts a background task that, per recipe, estimates any
uncached ingredient lines, writes totals / badges / version macros, and pushes the updated
recipe to the household so open pages refresh.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

_TASKS: set = set()


async def fill_recipe_macros(recipe_id: str, user: Optional[dict] = None) -> bool:
    """Compute (with AI) and save one recipe's macros. True when something was written."""
    from dependencies import recipe_repository
    from services.version_macros import refresh_recipe_macros

    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        return False
    result = await refresh_recipe_macros(recipe, recipe.get("adaptations"), allow_ai=True, fill_weights=True)
    fields = _changed(recipe, result["fields"])
    if not fields:
        return False
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()  # synced clients pick it up
    await recipe_repository.update_recipe(recipe_id, fields)
    if user:
        await _broadcast(recipe_id, user)
    return True


def _changed(recipe: dict, fields: dict) -> dict:
    import json

    from utils.recipe_fields import normalize_adaptations

    out = {}
    for key, value in fields.items():
        have = recipe.get(key)
        if key == "adaptations":
            have = normalize_adaptations(have)
        elif key == "ingredient_macros" and isinstance(have, str):
            try:
                have = json.loads(have)
            except (TypeError, ValueError):
                have = None
        if have != value:
            out[key] = value
    return out


async def _broadcast(recipe_id: str, user: dict) -> None:
    try:
        from database.websocket_manager import EventType, ws_manager
        from dependencies import recipe_repository
        from utils.recipe_fields import prepare_recipe_for_response

        updated = await recipe_repository.find_by_id(recipe_id)
        if updated:
            await ws_manager.broadcast_to_household_or_user(
                user_id=user["id"],
                household_id=user.get("household_id"),
                event_type=EventType.RECIPE_UPDATED,
                data=prepare_recipe_for_response(updated),
            )
    except Exception:
        logger.debug("Macro broadcast failed for %s", recipe_id, exc_info=True)


async def _run(recipe_ids: list, user: Optional[dict]) -> None:
    for rid in recipe_ids:
        try:
            await fill_recipe_macros(rid, user)
        except Exception:
            logger.warning("Background macros failed for recipe %s", rid, exc_info=True)


def schedule_recipe_macros(recipe_ids: Iterable[str], user: Optional[dict] = None) -> Optional[asyncio.Task]:
    """Fire-and-forget macro fill for these recipes (no-op outside a running event loop)."""
    ids = [r for r in dict.fromkeys(recipe_ids) if r]
    if not ids:
        return None
    try:
        task = asyncio.get_running_loop().create_task(_run(ids, user))
    except RuntimeError:
        return None
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task
