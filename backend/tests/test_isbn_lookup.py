"""ISBN lookup: Open Library search.json primary + resilient fallbacks."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from dependencies import get_current_user


@pytest.mark.asyncio
async def test_isbn_lookup_uses_open_library_search_when_google_quota_and_books_api_down():
    """Prod failure mode: Google 429 + /api/books ConnectError → search.json still works."""
    from routers import cookbooks as cookbooks_router

    user = {"id": "user-1", "household_id": "hh-1"}
    app = FastAPI()
    app.include_router(cookbooks_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, timeout=None, **kwargs):
            if "googleapis.com" in url:
                return Response(429, json={"error": {"code": 429}})
            if "/api/books" in url:
                raise cookbooks_router.httpx.ConnectError("simulated")
            if "search.json" in url:
                return Response(
                    200,
                    json={
                        "numFound": 1,
                        "docs": [
                            {
                                "title": "The Alchemist",
                                "author_name": ["Paulo Coelho"],
                                "publisher": ["HarperCollins"],
                                "first_publish_year": 2014,
                                "cover_i": 15091614,
                            }
                        ],
                    },
                )
            raise AssertionError(f"unexpected url {url}")

    with patch.object(
        cookbooks_router.cookbook_repository,
        "find_by_isbn",
        AsyncMock(return_value=None),
    ), patch.object(cookbooks_router.httpx, "AsyncClient", FakeClient):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/cookbooks/lookup", params={"isbn": "978-0-06-231500-7"}
            )
            path = await client.get("/api/cookbooks/isbn/9780062315007")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["title"] == "The Alchemist"
    assert body["author"] == "Paulo Coelho"
    assert body["year"] == 2014
    assert "15091614" in (body.get("cover_image_url") or "")
    assert path.status_code == 200
    assert path.json()["isbn"] == "9780062315007"


@pytest.mark.asyncio
async def test_isbn_lookup_404_when_catalogs_empty():
    from routers import cookbooks as cookbooks_router

    user = {"id": "user-1", "household_id": None}
    app = FastAPI()
    app.include_router(cookbooks_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, timeout=None, **kwargs):
            if "search.json" in url:
                return Response(200, json={"numFound": 0, "docs": []})
            if "/api/books" in url:
                return Response(200, json={})
            if "googleapis.com" in url:
                return Response(200, json={"totalItems": 0, "items": []})
            raise AssertionError(url)

    with patch.object(
        cookbooks_router.cookbook_repository,
        "find_by_isbn",
        AsyncMock(return_value=None),
    ), patch.object(cookbooks_router.httpx, "AsyncClient", FakeClient):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/cookbooks/lookup", params={"isbn": "0000000000"})

    assert res.status_code == 404
    assert "manually" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_cookbook_accepts_android_published_year_alias():
    from routers import cookbooks as cookbooks_router

    user = {"id": "user-1", "household_id": None}
    app = FastAPI()
    app.include_router(cookbooks_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    created = {}

    async def fake_create(doc):
        created.update(doc)
        return doc

    with patch(
        "utils.free_limits.assert_can_create_cookbook", AsyncMock()
    ), patch.object(
        cookbooks_router.cookbook_repository, "create", side_effect=fake_create
    ), patch.object(
        cookbooks_router, "log_action", AsyncMock()
    ), patch.object(
        cookbooks_router.ws_manager,
        "broadcast_to_household_or_user",
        AsyncMock(),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/cookbooks",
                json={
                    "title": "Test Book",
                    "author": "A",
                    "isbn": "123",
                    "published_year": 2020,
                    "description": "Notes from Android",
                },
            )

    assert res.status_code == 200, res.text
    assert created.get("year") == 2020
    assert created.get("notes") == "Notes from Android"
