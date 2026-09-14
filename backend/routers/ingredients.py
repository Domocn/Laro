"""
Ingredient aliases — merge/rename foods across household recipes (Tandoor-style).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dependencies import get_current_user, recipe_repository
from services.ingredient_aliases import (
    ingredient_alias_repository,
    normalize_ingredient_key,
    rename_across_recipes,
)

router = APIRouter(prefix="/ingredients", tags=["Ingredients"])


class AliasBody(BaseModel):
    from_name: str = Field(..., min_length=1, max_length=200)
    to_name: str = Field(..., min_length=1, max_length=200)
    apply_to_recipes: bool = True


def _scope(user: dict):
    return user.get("household_id"), user["id"]


@router.get("/aliases")
async def list_aliases(user: dict = Depends(get_current_user)):
    household_id, user_id = _scope(user)
    rows = await ingredient_alias_repository.list_for_scope(
        household_id=household_id, user_id=user_id
    )
    return {
        "aliases": [
            {
                "id": r.get("id"),
                "from_key": r.get("from_key"),
                "to_key": r.get("to_key"),
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.put("/aliases")
async def upsert_alias(data: AliasBody, user: dict = Depends(get_current_user)):
    household_id, user_id = _scope(user)
    try:
        alias = await ingredient_alias_repository.upsert_alias(
            household_id=household_id,
            user_id=user_id,
            from_key=data.from_name,
            to_key=data.to_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stats = {"recipes_updated": 0, "replacements": 0}
    if data.apply_to_recipes:
        recipes = await recipe_repository.find_by_household_or_author(
            author_id=user_id,
            household_id=household_id,
            limit=2000,
        )
        stats = await rename_across_recipes(
            recipes=recipes,
            from_name=data.from_name,
            to_name=data.to_name,
            recipe_repository=recipe_repository,
        )
    return {"alias": alias, **stats}


@router.delete("/aliases/{from_key}")
async def delete_alias(from_key: str, user: dict = Depends(get_current_user)):
    household_id, user_id = _scope(user)
    deleted = await ingredient_alias_repository.delete_alias(
        household_id=household_id,
        user_id=user_id,
        from_key=from_key,
    )
    return {"deleted": deleted, "from_key": normalize_ingredient_key(from_key)}


@router.post("/rename")
async def rename_ingredient(data: AliasBody, user: dict = Depends(get_current_user)):
    """
    Save alias + rewrite matching ingredients across recipes in one call.
    """
    return await upsert_alias(data, user)
