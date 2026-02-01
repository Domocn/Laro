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
import secrets
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


def generate_share_code():
    """Generate a short, URL-safe share code"""
    return secrets.token_urlsafe(8)


@router.post("/create", response_model=ShareLinkResponse)
async def create_share_link(
    data: ShareLinkCreate,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Create a public share link for a recipe"""
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
    if data.expires_in_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)).isoformat()

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
    share_url = f"{base_url}/r/{share_code}"

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
            "share_url": f"{base_url}/r/{link['share_code']}",
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


@router.get("/recipe/{share_code}")
async def get_shared_recipe(
    share_code: str,
    request: Request
):
    """Get a recipe via its share code (public endpoint - no auth required)"""
    link = await recipe_share_repository.find_by_share_code(share_code)

    if not link or not link.get("is_active", True):
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    if link.get("expires_at"):
        expires_at = datetime.fromisoformat(link["expires_at"].replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
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

    return {
        "recipe": {
            "id": recipe.get("id"),
            "title": recipe.get("title"),
            "description": recipe.get("description"),
            "image_url": recipe.get("image_url"),
            "prep_time": recipe.get("prep_time"),
            "cook_time": recipe.get("cook_time"),
            "servings": recipe.get("servings"),
            "ingredients": recipe.get("ingredients", []),
            "instructions": recipe.get("instructions", []),
            "tags": recipe.get("tags", []),
            "category": recipe.get("category"),
            "cuisine": recipe.get("cuisine"),
            "difficulty": recipe.get("difficulty"),
            "nutrition": recipe.get("nutrition"),
        },
        "author": author_info,
        "allow_print": link.get("allow_print", True),
        "shared_at": link["created_at"],
        "include_links_in_share": sharing_settings.get("include_links_in_share", True),
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
