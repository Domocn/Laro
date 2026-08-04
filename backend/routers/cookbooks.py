"""
Cookbooks Router - CRUD operations for cookbook management
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from models import CookbookCreate, CookbookUpdate, CookbookResponse, ISBNLookupResponse
from dependencies import get_current_user, cookbook_repository, recipe_repository
from database.websocket_manager import ws_manager, EventType
from utils.activity_logger import log_action
from utils.security import sanitize_error_message
import uuid
import httpx
from datetime import datetime, timezone
from typing import List, Optional

router = APIRouter(prefix="/cookbooks", tags=["Cookbooks"])


@router.get("", response_model=List[CookbookResponse])
async def get_cookbooks(
    search: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get all cookbooks for the current user/household"""
    if search:
        cookbooks = await cookbook_repository.search(
            user_id=user["id"],
            household_id=user.get("household_id"),
            search_term=search
        )
    else:
        cookbooks = await cookbook_repository.find_by_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id")
        )

    return [CookbookResponse(**c) for c in cookbooks]


@router.post("", response_model=CookbookResponse)
async def create_cookbook(
    cookbook: CookbookCreate,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Create a new cookbook"""
    cookbook_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    cookbook_doc = {
        "id": cookbook_id,
        "user_id": user["id"],
        "household_id": user.get("household_id"),
        "title": cookbook.title,
        "author": cookbook.author,
        "isbn": cookbook.isbn,
        "publisher": cookbook.publisher,
        "year": cookbook.year,
        "cover_image_url": cookbook.cover_image_url,
        "notes": cookbook.notes,
        "created_at": now,
        "updated_at": now
    }

    await cookbook_repository.create(cookbook_doc)

    # Log cookbook creation
    await log_action(
        user, "cookbook_created", request,
        target_type="cookbook",
        target_id=cookbook_id,
        details={"title": cookbook.title, "author": cookbook.author}
    )

    # Broadcast to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.DATA_SYNC,
        data={"type": "cookbook_created", "cookbook": cookbook_doc}
    )

    return CookbookResponse(**cookbook_doc)


@router.get("/lookup", response_model=ISBNLookupResponse)
async def lookup_isbn(
    isbn: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Look up cookbook information by ISBN using Google Books API"""
    # Clean ISBN (remove dashes, spaces)
    clean_isbn = isbn.replace("-", "").replace(" ", "")

    # Check if we already have this cookbook
    existing = await cookbook_repository.find_by_isbn(
        isbn=clean_isbn,
        user_id=user["id"],
        household_id=user.get("household_id")
    )
    if existing:
        return ISBNLookupResponse(
            title=existing["title"],
            author=existing.get("author"),
            publisher=existing.get("publisher"),
            year=existing.get("year"),
            cover_image_url=existing.get("cover_image_url"),
            isbn=clean_isbn
        )

    # Look up via Google Books API
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://www.googleapis.com/books/v1/volumes",
                params={"q": f"isbn:{clean_isbn}"},
                timeout=10.0
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=404,
                    detail="Could not find book information for this ISBN"
                )

            data = response.json()
            if data.get("totalItems", 0) == 0:
                # Try Open Library as fallback
                ol_response = await client.get(
                    f"https://openlibrary.org/api/books",
                    params={"bibkeys": f"ISBN:{clean_isbn}", "format": "json", "jscmd": "data"},
                    timeout=10.0
                )

                if ol_response.status_code == 200:
                    ol_data = ol_response.json()
                    book_key = f"ISBN:{clean_isbn}"
                    if book_key in ol_data:
                        book = ol_data[book_key]
                        authors = book.get("authors", [])
                        author_names = ", ".join([a.get("name", "") for a in authors])
                        publishers = book.get("publishers", [])
                        publisher = publishers[0].get("name") if publishers else None

                        cover_url = None
                        if "cover" in book:
                            cover_url = book["cover"].get("large") or book["cover"].get("medium")

                        return ISBNLookupResponse(
                            title=book.get("title", "Unknown"),
                            author=author_names or None,
                            publisher=publisher,
                            year=int(book.get("publish_date", "")[:4]) if book.get("publish_date", "")[:4].isdigit() else None,
                            cover_image_url=cover_url,
                            isbn=clean_isbn
                        )

                raise HTTPException(
                    status_code=404,
                    detail="Book not found. Try entering details manually."
                )

            # Parse Google Books response
            book = data["items"][0]["volumeInfo"]

            # Get cover image (prefer large, fall back to thumbnail)
            cover_url = None
            if "imageLinks" in book:
                cover_url = book["imageLinks"].get("large") or book["imageLinks"].get("thumbnail")
                # Convert to HTTPS and remove zoom parameter for better quality
                if cover_url:
                    cover_url = cover_url.replace("http://", "https://")
                    cover_url = cover_url.replace("&edge=curl", "")

            # Parse publication year
            year = None
            if "publishedDate" in book:
                try:
                    year = int(book["publishedDate"][:4])
                except (ValueError, IndexError):
                    pass

            return ISBNLookupResponse(
                title=book.get("title", "Unknown"),
                author=", ".join(book.get("authors", [])) or None,
                publisher=book.get("publisher"),
                year=year,
                cover_image_url=cover_url,
                isbn=clean_isbn
            )

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to book lookup service: {sanitize_error_message(e)}"
            )


@router.get("/{cookbook_id}", response_model=CookbookResponse)
async def get_cookbook(
    cookbook_id: str,
    user: dict = Depends(get_current_user)
):
    """Get a specific cookbook"""
    cookbook = await cookbook_repository.find_by_id(cookbook_id)
    if not cookbook:
        raise HTTPException(status_code=404, detail="Cookbook not found")

    # Verify access
    if cookbook["user_id"] != user["id"]:
        if not user.get("household_id") or cookbook.get("household_id") != user["household_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view this cookbook")

    return CookbookResponse(**cookbook)


@router.put("/{cookbook_id}", response_model=CookbookResponse)
async def update_cookbook(
    cookbook_id: str,
    cookbook_update: CookbookUpdate,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Update a cookbook"""
    existing = await cookbook_repository.find_by_id(cookbook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cookbook not found")

    # Verify ownership
    if existing["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this cookbook")

    # Build update data (only include non-None fields)
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field, value in cookbook_update.model_dump().items():
        if value is not None:
            update_data[field] = value

    await cookbook_repository.update_cookbook(cookbook_id, update_data)
    updated = await cookbook_repository.find_by_id(cookbook_id)

    # Log cookbook update
    await log_action(
        user, "cookbook_updated", request,
        target_type="cookbook",
        target_id=cookbook_id,
        details={"title": updated.get("title")}
    )

    # Broadcast update
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.DATA_SYNC,
        data={"type": "cookbook_updated", "cookbook": updated}
    )

    return CookbookResponse(**updated)


@router.delete("/{cookbook_id}")
async def delete_cookbook(
    cookbook_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Delete a cookbook"""
    existing = await cookbook_repository.find_by_id(cookbook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cookbook not found")

    # Verify ownership
    if existing["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this cookbook")

    cookbook_title = existing.get("title", "Unknown")

    await cookbook_repository.delete_cookbook(cookbook_id)

    # Log cookbook deletion
    await log_action(
        user, "cookbook_deleted", request,
        target_type="cookbook",
        target_id=cookbook_id,
        details={"title": cookbook_title}
    )

    # Broadcast deletion
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.DATA_SYNC,
        data={"type": "cookbook_deleted", "id": cookbook_id}
    )

    return {"message": "Cookbook deleted"}


@router.get("/{cookbook_id}/recipes")
async def get_cookbook_recipes(
    cookbook_id: str,
    user: dict = Depends(get_current_user)
):
    """Get all recipes from a specific cookbook"""
    cookbook = await cookbook_repository.find_by_id(cookbook_id)
    if not cookbook:
        raise HTTPException(status_code=404, detail="Cookbook not found")

    # Verify access
    if cookbook["user_id"] != user["id"]:
        if not user.get("household_id") or cookbook.get("household_id") != user["household_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view this cookbook")

    # Get recipes linked to this cookbook
    recipes = await recipe_repository.find_by_cookbook(cookbook_id)

    return {
        "cookbook": CookbookResponse(**cookbook),
        "recipes": recipes,
        "recipe_count": len(recipes)
    }
