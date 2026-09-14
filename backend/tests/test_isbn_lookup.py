"""ISBN lookup: path alias + Open Library when Google fails."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from dependencies import get_current_user


@pytest.mark.asyncio
async def test_isbn_lookup_query_and_path_alias_use_open_library_when_google_errors():
    from routers import cookbooks as cookbooks_router

    user = {"id": "user-1", "household_id": "hh-1"}

    app = FastAPI()
    app.include_router(cookbooks_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    google = Response(403, json={"error": "quota"})
    ol = Response(
        200,
        json={
            "ISBN:9780143127550": {
                "title": "The Joy of Cooking",
                "authors": [{"name": "Irma S. Rombauer"}],
                "publishers": [{"name": "Scribner"}],
                "publish_date": "2019",
                "cover": {"medium": "https://covers.openlibrary.org/b/id/1-M.jpg"},
            }
        },
    )

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, timeout=None):
            if "googleapis.com" in url:
                return google
            if "openlibrary.org" in url:
                return ol
            raise AssertionError(f"unexpected url {url}")

    with patch.object(
        cookbooks_router.cookbook_repository,
        "find_by_isbn",
        AsyncMock(return_value=None),
    ), patch.object(cookbooks_router.httpx, "AsyncClient", FakeClient):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            q = await client.get("/api/cookbooks/lookup", params={"isbn": "978-0-14-312755-0"})
            p = await client.get("/api/cookbooks/isbn/9780143127550")

    assert q.status_code == 200, q.text
    assert p.status_code == 200, p.text
    assert q.json()["title"] == "The Joy of Cooking"
    assert p.json()["isbn"] == "9780143127550"
    assert q.json()["author"] == "Irma S. Rombauer"


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

    with patch.object(
        cookbooks_router, "assert_can_create_cookbook", AsyncMock(), create=True
    ), patch(
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
