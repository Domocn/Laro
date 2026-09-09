"""
Recipe Sharing Router
Allows users to create public share links for individual recipes.
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from dependencies import get_current_user, recipe_repository, recipe_share_repository, user_repository, system_settings_repository
from utils.activity_logger import log_action
from utils.share_links import generate_share_code, parse_share_expiry, public_share_path
import os
import uuid

router = APIRouter(prefix="/share", tags=["sharing"])


class ShareLinkCreate(BaseModel):
    recipe_id: str
    expires_in_days: Optional[int] = None
    allow_print: bool = True
    show_author: bool = True


class ShareLinkResponse(BaseModel):
    id: str
    share_code: str
    share_url: str
    recipe_id: str
    created_at: str
    expires_at: Optional[str]
    view_count: int
    allow_print: bool
    show_author: bool


@router.post("/create", response_model=ShareLinkResponse)
async def create_share_link(
    data: ShareLinkCreate,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Create a public share link for a recipe"""
    from utils.free_limits import assert_can_share
    await assert_can_share(user)

    recipe = await recipe_repository.find_by_id(data.recipe_id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe_user_id = str(recipe.get("user_id") or recipe.get("author_id", ""))
    user_id = str(user.get("id", ""))
    if recipe_user_id != user_id and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You can only share your own recipes")

    share_code = generate_share_code()
    existing = await recipe_share_repository.find_by_share_code(share_code)
    while existing:
        share_code = generate_share_code()
        existing = await recipe_share_repository.find_by_share_code(share_code)

    expires_at = None
    # Require finite expiry — never-expiring public links leak private recipes forever
    days = data.expires_in_days
    if days is None or days <= 0:
        days = 30  # default 30 days
    if days > 90:
        days = 90  # hard cap
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    share_link_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    share_link = {
        "id": share_link_id,
        "share_code": share_code,
        "recipe_id": data.recipe_id,
        "user_id": user["id"],
        "created_at": now,
        "expires_at": expires_at,
        "view_count": 0,
        "allow_print": data.allow_print,
        "show_author": data.show_author,
        "is_active": True,
    }

    await recipe_share_repository.create(share_link)

    # Log share link creation
    await log_action(
        user, "share_link_created", request,
        target_type="share_link",
        target_id=share_link_id,
        details={"recipe_id": data.recipe_id, "share_code": share_code}
    )

    base_url = os.environ.get("OAUTH_REDIRECT_BASE_URL", str(request.base_url).rstrip('/'))
    share_url = f"{base_url}{public_share_path(share_code)}"

    return ShareLinkResponse(
        id=share_link_id,
        share_code=share_code,
        share_url=share_url,
        recipe_id=data.recipe_id,
        created_at=now,
        expires_at=expires_at,
        view_count=0,
        allow_print=data.allow_print,
        show_author=data.show_author,
    )


@router.get("/my-links")
async def get_my_share_links(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Get all share links created by the current user"""
    links = await recipe_share_repository.find_by_user(user["id"], active_only=True)

    base_url = os.environ.get("OAUTH_REDIRECT_BASE_URL", str(request.base_url).rstrip('/'))

    result = []
    for link in links:
        recipe = await recipe_repository.find_by_id(link["recipe_id"])

        result.append({
            "id": link["id"],
            "share_code": link["share_code"],
            "share_url": f"{base_url}{public_share_path(link['share_code'])}",
            "recipe_id": link["recipe_id"],
            "recipe_title": recipe.get("title", "Unknown") if recipe else "Deleted Recipe",
            "recipe_image": recipe.get("image_url") if recipe else None,
            "created_at": link["created_at"],
            "expires_at": link.get("expires_at"),
            "view_count": link.get("view_count", 0),
            "allow_print": link.get("allow_print", True),
            "show_author": link.get("show_author", True),
        })

    return {"links": result, "total": len(result)}


async def get_sharing_settings():
    """Get sharing-related system settings"""
    settings = await system_settings_repository.get_settings("global")
    return {
        "include_links_in_share": settings.get("include_links_in_share", False) if settings else False,
    }


@router.get("/settings")
async def get_share_settings():
    """Get sharing settings (public endpoint - no auth required)"""
    return await get_sharing_settings()


@router.get("/substitutions")
async def public_ingredient_substitutions(
    ingredient: str,
    limit: int = 5,
    share_code: Optional[str] = None,
):
    """
    Public peek at substitution ideas (no auth).
    When share_code is provided, Laro AI ranks swaps for that shared recipe.
    Guests can browse; applying swaps requires an account.
    """
    from utils.veto_replacements import suggest_ingredient_substitutions

    name = (ingredient or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Ingredient is required")
    limit = max(1, min(int(limit or 5), 8))
    local = suggest_ingredient_substitutions(name, {}, limit=limit)
    suggestions = list(local.get("suggestions") or [])
    ai_used = False
    source = "local"

    recipe_title = ""
    recipe_description = ""
    ingredients: list = []
    instructions: list = []
    if share_code:
        link = await recipe_share_repository.find_by_share_code(share_code.strip())
        if link and link.get("is_active", True):
            expires_at = parse_share_expiry(link.get("expires_at"))
            if not expires_at or expires_at >= datetime.now(timezone.utc):
                recipe = await recipe_repository.find_by_id(link["recipe_id"])
                if recipe:
                    recipe_title = recipe.get("title") or ""
                    recipe_description = recipe.get("description") or ""
                    ingredients = list(recipe.get("ingredients") or [])
                    instructions = list(recipe.get("instructions") or [])

    if recipe_title or ingredients:
        from utils.ai_substitutions import ai_rank_substitutions

        ai_result = await ai_rank_substitutions(
            name,
            recipe_title=recipe_title,
            recipe_description=recipe_description,
            ingredients=ingredients,
            instructions=instructions,
            seed_suggestions=suggestions,
            diet_notes="",
            limit=limit,
            user=None,
            meter_quota=False,
        )
        if ai_result.get("suggestions"):
            suggestions = ai_result["suggestions"]
            ai_used = True
            source = "ai"

    return {
        "ingredient": name,
        "suggestions": suggestions,
        "category": local.get("category"),
        "roles": local.get("roles"),
        "ai_used": ai_used,
        "source": source,
    }


@router.post("/substitutions")
async def public_ingredient_substitutions_with_context(body: dict):
    """
    Public AI substitutions with client-supplied recipe context (share page).
    No auth / no quota — responses are LLM-cached. Apply still requires signup.
    """
    from utils.veto_replacements import suggest_ingredient_substitutions
    from utils.ai_substitutions import ai_rank_substitutions

    name = str((body or {}).get("ingredient") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Ingredient is required")
    limit = max(1, min(int((body or {}).get("limit") or 5), 8))
    local = suggest_ingredient_substitutions(name, {}, limit=limit)
    suggestions = list(local.get("suggestions") or [])

    recipe_title = str((body or {}).get("recipe_title") or "").strip()
    recipe_description = str((body or {}).get("recipe_description") or "").strip()
    ingredients = list((body or {}).get("ingredients") or [])
    instructions = list((body or {}).get("instructions") or [])
    share_code = str((body or {}).get("share_code") or "").strip()

    if share_code and (not recipe_title or not ingredients):
        link = await recipe_share_repository.find_by_share_code(share_code)
        if link and link.get("is_active", True):
            recipe = await recipe_repository.find_by_id(link["recipe_id"])
            if recipe:
                recipe_title = recipe_title or (recipe.get("title") or "")
                recipe_description = recipe_description or (recipe.get("description") or "")
                if not ingredients:
                    ingredients = list(recipe.get("ingredients") or [])
                if not instructions:
                    instructions = list(recipe.get("instructions") or [])

    ai_used = False
    source = "local"
    if recipe_title or ingredients:
        ai_result = await ai_rank_substitutions(
            name,
            recipe_title=recipe_title,
            recipe_description=recipe_description,
            ingredients=ingredients,
            instructions=instructions,
            seed_suggestions=suggestions,
            diet_notes="",
            limit=limit,
            user=None,
            meter_quota=False,
        )
        if ai_result.get("suggestions"):
            suggestions = ai_result["suggestions"]
            ai_used = True
            source = "ai"

    return {
        "ingredient": name,
        "suggestions": suggestions,
        "category": local.get("category"),
        "roles": local.get("roles"),
        "ai_used": ai_used,
        "source": source,
    }


@router.get("/recipe/{share_code}")
async def get_shared_recipe(
    share_code: str,
    request: Request
):
    """Get a recipe via its share code (public endpoint - no auth required)"""
    link = await recipe_share_repository.find_by_share_code(share_code)

    if not link or not link.get("is_active", True):
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    expires_at = parse_share_expiry(link.get("expires_at"))
    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This share link has expired")

    recipe = await recipe_repository.find_by_id(link["recipe_id"])

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe no longer exists")

    await recipe_share_repository.increment_view_count(link["id"])

    author_info = None
    if link.get("show_author", True):
        author_id = recipe.get("user_id") or recipe.get("author_id")
        if author_id:
            author = await user_repository.find_by_id(author_id)
            if author:
                author_info = {
                    "name": author.get("name", "Anonymous"),
                    "avatar_url": author.get("avatar_url"),
                }

    sharing_settings = await get_sharing_settings()

    from utils.recipe_fields import prepare_recipe_for_response
    shaped = prepare_recipe_for_response(recipe, share_mode=True)
    nutrition = shaped.get("nutrition") or {}

    return {
        "recipe": {
            "id": shaped.get("id"),
            "title": shaped.get("title"),
            "description": shaped.get("description"),
            "image_url": shaped.get("image_url"),
            "prep_time": shaped.get("prep_time"),
            "cook_time": shaped.get("cook_time"),
            "servings": shaped.get("servings"),
            "ingredients": shaped.get("ingredients", []),
            "instructions": shaped.get("instructions", []),
            "tags": shaped.get("tags", []),
            "category": shaped.get("category"),
            "cuisine": shaped.get("cuisine"),
            "difficulty": shaped.get("difficulty"),
            "nutrition": nutrition,
        },
        "author": author_info,
        "allow_print": link.get("allow_print", True),
        "shared_at": link["created_at"],
        "include_links_in_share": sharing_settings.get("include_links_in_share", True),
        "nutrition_estimated": bool(nutrition.get("nutrition_estimated")),
    }


@router.delete("/{link_id}")
async def revoke_share_link(
    link_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Revoke (delete) a share link"""
    link = await recipe_share_repository.find_by_id(link_id)

    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")

    user_id = str(user.get("id"))
    if str(link["user_id"]) != user_id and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You can only revoke your own share links")

    await recipe_share_repository.update(link_id, {"is_active": False})

    # Log share link revocation
    await log_action(
        user, "share_link_revoked", request,
        target_type="share_link",
        target_id=link_id,
        details={"share_code": link.get("share_code")}
    )

    return {"success": True, "message": "Share link revoked"}


@router.get("/stats/{link_id}")
async def get_share_link_stats(
    link_id: str,
    user: dict = Depends(get_current_user)
):
    """Get statistics for a share link"""
    link = await recipe_share_repository.find_by_id(link_id)

    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")

    user_id = str(user.get("id"))
    if str(link["user_id"]) != user_id and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You can only view stats for your own share links")

    return {
        "id": link["id"],
        "share_code": link["share_code"],
        "view_count": link.get("view_count", 0),
        "created_at": link["created_at"],
        "expires_at": link.get("expires_at"),
        "is_active": link.get("is_active", True),
    }
