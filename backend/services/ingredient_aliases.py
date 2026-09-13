"""
Ingredient alias / rename — Tandoor-style merge across household recipes.

Stores from_key → to_key mappings per household (or user when solo) and can
rewrite recipe ingredient JSON in bulk.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


def normalize_ingredient_key(name: str) -> str:
    text = (name or "").lower().strip()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120]


class IngredientAliasRepository(BaseRepository):
    def __init__(self):
        super().__init__("ingredient_aliases")

    async def list_for_scope(self, *, household_id: Optional[str], user_id: str) -> List[dict]:
        if household_id:
            return await self.find_many({"household_id": household_id}, limit=2000)
        # BaseRepository treats None as "= $n", which never matches SQL NULL.
        pool = await self._get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM ingredient_aliases
                   WHERE user_id = $1 AND household_id IS NULL
                   LIMIT 2000""",
                user_id,
            )
        from database.connection import rows_to_dicts

        return rows_to_dicts(rows)

    async def get_map(self, *, household_id: Optional[str], user_id: str) -> Dict[str, str]:
        rows = await self.list_for_scope(household_id=household_id, user_id=user_id)
        return {
            (r.get("from_key") or "").lower(): r.get("to_key")
            for r in rows
            if r.get("from_key") and r.get("to_key")
        }

    async def upsert_alias(
        self,
        *,
        household_id: Optional[str],
        user_id: str,
        from_key: str,
        to_key: str,
    ) -> dict:
        frm = normalize_ingredient_key(from_key)
        to = normalize_ingredient_key(to_key)
        if not frm or not to or frm == to:
            raise ValueError("from_key and to_key required and must differ")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pool = await self._get_db()
        async with pool.acquire() as conn:
            if household_id:
                existing = await conn.fetchrow(
                    """SELECT id FROM ingredient_aliases
                       WHERE household_id = $1 AND from_key = $2""",
                    household_id,
                    frm,
                )
            else:
                existing = await conn.fetchrow(
                    """SELECT id FROM ingredient_aliases
                       WHERE user_id = $1 AND household_id IS NULL AND from_key = $2""",
                    user_id,
                    frm,
                )
            if existing:
                await conn.execute(
                    """UPDATE ingredient_aliases
                       SET to_key = $1, updated_at = $2 WHERE id = $3""",
                    to,
                    now,
                    existing["id"],
                )
                return {
                    "id": existing["id"],
                    "from_key": frm,
                    "to_key": to,
                    "household_id": household_id,
                    "user_id": user_id,
                }
            oid = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO ingredient_aliases
                   (id, household_id, user_id, from_key, to_key, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $6)""",
                oid,
                household_id,
                user_id,
                frm,
                to,
                now,
            )
            return {
                "id": oid,
                "from_key": frm,
                "to_key": to,
                "household_id": household_id,
                "user_id": user_id,
            }

    async def delete_alias(
        self, *, household_id: Optional[str], user_id: str, from_key: str
    ) -> int:
        frm = normalize_ingredient_key(from_key)
        if household_id:
            return await self.delete({"household_id": household_id, "from_key": frm})
        pool = await self._get_db()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """DELETE FROM ingredient_aliases
                   WHERE user_id = $1 AND household_id IS NULL AND from_key = $2""",
                user_id,
                frm,
            )
        # asyncpg returns e.g. "DELETE 1"
        try:
            return int(str(result).split()[-1])
        except (ValueError, IndexError):
            return 0


ingredient_alias_repository = IngredientAliasRepository()


def apply_alias_to_ingredient(ing: Any, alias_map: Dict[str, str]) -> Tuple[Any, bool]:
    """Return (ingredient, changed)."""
    if not alias_map:
        return ing, False
    if isinstance(ing, str):
        text = ing.strip()
        key = normalize_ingredient_key(text)
        if key in alias_map:
            return alias_map[key], True
        # Try amount/unit prefix: "2 cups scallions" → alias the name tail
        m = re.match(r"^([\d\./\s½⅓⅔¼¾]+\s*[a-zA-Z%]*)\s+(.+)$", text)
        if m:
            name_key = normalize_ingredient_key(m.group(2))
            if name_key in alias_map:
                return f"{m.group(1).strip()} {alias_map[name_key]}", True
        return ing, False
    if isinstance(ing, dict):
        name = ing.get("name") or ing.get("ingredient") or ""
        key = normalize_ingredient_key(str(name))
        if key in alias_map:
            updated = dict(ing)
            updated["name"] = alias_map[key]
            return updated, True
        return ing, False
    return ing, False


async def rename_across_recipes(
    *,
    recipes: List[dict],
    from_name: str,
    to_name: str,
    recipe_repository,
) -> Dict[str, Any]:
    """Rewrite ingredient names across recipe rows. Returns stats."""
    frm = normalize_ingredient_key(from_name)
    to = normalize_ingredient_key(to_name)
    alias_map = {frm: to}
    touched = 0
    replacements = 0
    for recipe in recipes:
        ingredients = recipe.get("ingredients") or []
        new_ings = []
        changed = False
        for ing in ingredients:
            updated, did = apply_alias_to_ingredient(ing, alias_map)
            new_ings.append(updated)
            if did:
                changed = True
                replacements += 1
        if changed:
            await recipe_repository.update_recipe(
                recipe["id"],
                {"ingredients": new_ings},
            )
            touched += 1
    return {
        "from_key": frm,
        "to_key": to,
        "recipes_updated": touched,
        "replacements": replacements,
    }
