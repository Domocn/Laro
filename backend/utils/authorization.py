"""
Authorization helpers for private user data (recipes, etc.).
"""
from __future__ import annotations

from fastapi import HTTPException


def user_can_view_recipe(user: dict, recipe: dict) -> bool:
    """
    True if the user may read this recipe's private content.

    Allowed:
    - Recipe author
    - Same household (recipe.household_id matches user.household_id)
    - admin / super_admin
    """
    if not user or not recipe:
        return False

    role = (user.get("role") or "").lower()
    if role in ("admin", "super_admin"):
        return True

    if recipe.get("author_id") == user.get("id"):
        return True

    recipe_hh = recipe.get("household_id")
    user_hh = user.get("household_id")
    if recipe_hh and user_hh and recipe_hh == user_hh:
        return True

    return False


def require_recipe_view(user: dict, recipe: dict) -> None:
    """
    Raise 404 if user cannot view recipe (same as missing — avoids IDOR existence leaks).
    Call only after confirming the recipe row exists.
    """
    if not user_can_view_recipe(user, recipe):
        raise HTTPException(status_code=404, detail="Recipe not found")


def require_recipe_edit(user: dict, recipe: dict) -> None:
    """
    Author, app admin, or household collaborator may mutate a recipe.

    Household members can edit recipes stamped with their household_id
    (RecipeSage / Mealie-style shared kitchen collaboration). Solo recipes
    without a household remain author-only.
    """
    role = (user.get("role") or "").lower()
    if role in ("admin", "super_admin"):
        return
    if recipe.get("author_id") == user.get("id"):
        return
    recipe_hh = recipe.get("household_id")
    user_hh = user.get("household_id")
    if recipe_hh and user_hh and str(recipe_hh) == str(user_hh):
        return
    raise HTTPException(status_code=403, detail="Not authorized")
