"""
Cookbooks Router - CRUD operations for cookbook management
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from models import (
    CookbookCreate,
    CookbookUpdate,
    CookbookResponse,
    ISBNLookupResponse,
    CookbookBuyLink,
    CookbookBuySearchResult,
    CookbookBuySearchResponse,
)
from dependencies import get_current_user, cookbook_repository, recipe_repository
from database.websocket_manager import ws_manager, EventType
from utils.activity_logger import log_action
from utils.security import sanitize_error_message
import os
import re
import uuid
import httpx
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import quote_plus

router = APIRouter(prefix="/cookbooks", tags=["Cookbooks"])

# Blocklist: never emit outbound links to known pirate / shadow libraries.
_PIRATE_HOST_RE = re.compile(
    r"(zlib|z-library|libgen|librarygenesis|sci-hub|annas-archive|annasarchive|"
    r"oceanofpdf|pdfdrive|ebookee|freebook|torrent)",
    re.IGNORECASE,
)


def _safe_outbound_url(url: Optional[str]) -> Optional[str]:
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url.startswith(("https://", "http://")):
        return None
    if _PIRATE_HOST_RE.search(url):
        return None
    return url


def _pick_isbn(isbns: Optional[list]) -> Optional[str]:
    if not isbns:
        return None
    # Prefer ISBN-13 (starts with 978/979) when present
    for candidate in isbns:
        clean = re.sub(r"[^0-9Xx]", "", str(candidate))
        if len(clean) == 13 and clean.startswith(("978", "979")):
            return clean
    for candidate in isbns:
        clean = re.sub(r"[^0-9Xx]", "", str(candidate))
        if len(clean) in (10, 13):
            return clean
    return None


def _build_buy_links(
    *,
    title: str,
    author: Optional[str],
    isbn: Optional[str],
    publisher: Optional[str],
    open_library_key: Optional[str],
    archive_id: Optional[str] = None,
) -> List[CookbookBuyLink]:
    """Legal purchase / borrow / storefront search links only (no filetype:pdf pirate bait)."""
    links: List[CookbookBuyLink] = []
    search_bits = " ".join(p for p in [title, author] if p).strip() or title
    encoded_q = quote_plus(search_bits)

    # Amazon product/search — affiliate tag only if already configured in env
    amazon_tag = (os.getenv("AMAZON_AFFILIATE_TAG") or "").strip()
    if isbn:
        amazon_url = f"https://www.amazon.com/s?k={quote_plus(isbn)}"
    else:
        amazon_url = f"https://www.amazon.com/s?k={encoded_q}"
    if amazon_tag:
        sep = "&" if "?" in amazon_url else "?"
        amazon_url = f"{amazon_url}{sep}tag={quote_plus(amazon_tag)}"
    links.append(CookbookBuyLink(label="Amazon", url=amazon_url, kind="amazon"))

    # Bookshop.org (supports indie bookstores; ISBN when available)
    if isbn:
        bookshop_url = f"https://bookshop.org/book/{isbn}"
    else:
        bookshop_url = f"https://bookshop.org/search?keywords={encoded_q}"
    links.append(CookbookBuyLink(label="Bookshop.org", url=bookshop_url, kind="bookshop"))

    # Open Library work/edition page
    if open_library_key:
        ol_path = open_library_key if open_library_key.startswith("/") else f"/{open_library_key}"
        ol_url = _safe_outbound_url(f"https://openlibrary.org{ol_path}")
        if ol_url:
            links.append(CookbookBuyLink(label="Open Library", url=ol_url, kind="open_library"))

    # Internet Archive borrow when we have an identifier
    if archive_id:
        ia_url = _safe_outbound_url(f"https://archive.org/details/{quote_plus(archive_id)}")
        if ia_url:
            links.append(CookbookBuyLink(label="Internet Archive", url=ia_url, kind="archive"))

    # Publisher web search (when known) — helps find official DRM-free storefronts
    if publisher:
        pub_q = quote_plus(f"{publisher} {title} cookbook")
        links.append(
            CookbookBuyLink(
                label="Publisher search",
                url=f"https://www.google.com/search?q={pub_q}",
                kind="publisher",
            )
        )

    # DRM-free storefront search — explicit "buy", never filetype:pdf
    title_quoted = f'"{title}"' if title else "cookbook"
    author_part = author or ""
    drm_q = quote_plus(f"{title_quoted} {author_part} cookbook PDF buy".strip())
    links.append(
        CookbookBuyLink(
            label="Search DRM-free stores",
            url=f"https://www.google.com/search?q={drm_q}",
            kind="drm_free_search",
        )
    )

    return links


def _cover_from_open_library(cover_i: Optional[int], isbn: Optional[str]) -> Optional[str]:
    if cover_i:
        return f"https://covers.openlibrary.org/b/id/{cover_i}-M.jpg"
    if isbn:
        return f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
    return None


async def _search_open_library(client: httpx.AsyncClient, query: str, limit: int) -> List[CookbookBuySearchResult]:
    # Prefer subject bias toward cookbooks without poisoning the title match.
    q = query.strip()
    params = {
        "q": q,
        "limit": limit,
        "fields": "key,title,author_name,first_publish_year,isbn,cover_i,publisher,edition_key,ia,subject",
    }
    # Soft subject boost when query doesn't already say cookbook
    if "cookbook" not in q.lower() and "cook book" not in q.lower():
        params["q"] = f"({q}) OR subject:cookbooks {q}"

    response = await client.get("https://openlibrary.org/search.json", params=params, timeout=12.0)
    if response.status_code != 200:
        return []

    docs = response.json().get("docs") or []
    results: List[CookbookBuySearchResult] = []
    for doc in docs[:limit]:
        title = (doc.get("title") or "").strip()
        if not title:
            continue
        authors = doc.get("author_name") or []
        author = ", ".join(authors) if authors else None
        isbn = _pick_isbn(doc.get("isbn"))
        publishers = doc.get("publisher") or []
        publisher = publishers[0] if publishers else None
        year = doc.get("first_publish_year")
        if year is not None:
            try:
                year = int(year)
            except (TypeError, ValueError):
                year = None
        ol_key = doc.get("key")
        ia_list = doc.get("ia") or []
        archive_id = ia_list[0] if ia_list else None
        cover = _cover_from_open_library(doc.get("cover_i"), isbn)
        results.append(
            CookbookBuySearchResult(
                title=title,
                author=author,
                isbn=isbn,
                publisher=publisher,
                year=year,
                cover_image_url=cover,
                open_library_key=ol_key,
                source="open_library",
                buy_links=_build_buy_links(
                    title=title,
                    author=author,
                    isbn=isbn,
                    publisher=publisher,
                    open_library_key=ol_key,
                    archive_id=archive_id,
                ),
            )
        )
    return results


async def _search_google_books(client: httpx.AsyncClient, query: str, limit: int) -> List[CookbookBuySearchResult]:
    """Optional Google Books volumes API (metadata only). Works without a key; uses key if set."""
    params = {"q": query, "maxResults": min(limit, 20), "printType": "books"}
    api_key = (os.getenv("GOOGLE_BOOKS_API_KEY") or "").strip()
    if api_key:
        params["key"] = api_key

    response = await client.get(
        "https://www.googleapis.com/books/v1/volumes",
        params=params,
        timeout=12.0,
    )
    if response.status_code != 200:
        return []

    items = response.json().get("items") or []
    results: List[CookbookBuySearchResult] = []
    for item in items[:limit]:
        info = item.get("volumeInfo") or {}
        title = (info.get("title") or "").strip()
        if not title:
            continue
        authors = info.get("authors") or []
        author = ", ".join(authors) if authors else None
        publisher = info.get("publisher")
        year = None
        if info.get("publishedDate"):
            try:
                year = int(str(info["publishedDate"])[:4])
            except (ValueError, TypeError):
                year = None
        isbn = None
        for ident in info.get("industryIdentifiers") or []:
            if ident.get("type") in ("ISBN_13", "ISBN_10"):
                isbn = _pick_isbn([ident.get("identifier")]) or isbn
        cover = None
        image_links = info.get("imageLinks") or {}
        cover = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        if cover:
            cover = cover.replace("http://", "https://")

        results.append(
            CookbookBuySearchResult(
                title=title,
                author=author,
                isbn=isbn,
                publisher=publisher,
                year=year,
                cover_image_url=cover,
                open_library_key=None,
                source="google_books",
                buy_links=_build_buy_links(
                    title=title,
                    author=author,
                    isbn=isbn,
                    publisher=publisher,
                    open_library_key=None,
                ),
            )
        )
    return results


def _dedupe_results(results: List[CookbookBuySearchResult], limit: int) -> List[CookbookBuySearchResult]:
    seen = set()
    out: List[CookbookBuySearchResult] = []
    for r in results:
        key = (r.isbn or "", (r.title or "").lower(), (r.author or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= limit:
            break
    return out


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
    from utils.free_limits import assert_can_create_cookbook
    await assert_can_create_cookbook(user, cookbook_repository)

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


@router.get("/search-buy", response_model=CookbookBuySearchResponse)
async def search_cookbooks_to_buy(
    q: str = Query(..., min_length=2, max_length=200, description="Title, author, or ISBN"),
    limit: int = Query(12, ge=1, le=30),
    user: dict = Depends(get_current_user),
):
    """
    Search bibliographic catalogs for cookbooks to buy legally, then import a DRM-free PDF.

    Uses Open Library (primary) and optionally Google Books volumes API (metadata only).
    Returns outbound purchase / borrow / storefront search links — never scrapes or hosts PDFs.
    """
    query = (q or "").strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Search query too short")

    results: List[CookbookBuySearchResult] = []
    async with httpx.AsyncClient() as client:
        try:
            results.extend(await _search_open_library(client, query, limit))
        except httpx.RequestError:
            pass

        # Fill remaining slots from Google Books when OL is thin or as supplement
        remaining = max(limit - len(results), min(6, limit))
        if remaining > 0:
            try:
                results.extend(await _search_google_books(client, query, remaining))
            except httpx.RequestError:
                pass

    # Soft empty is fine — UI shows helper copy (never scrape/host PDFs)
    return CookbookBuySearchResponse(
        query=query,
        results=_dedupe_results(results, limit),
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
