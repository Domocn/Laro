"""Save a shared recipe copy into the recipient's account."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from dependencies import get_current_user


SOURCE_RECIPE = {
    "id": "src-1",
    "title": "Shared Pasta",
    "description": "Yummy",
    "ingredients": [{"name": "pasta", "amount": "200", "unit": "g"}],
    "instructions": ["Boil water", "Cook pasta"],
    "prep_time": 10,
    "cook_time": 12,
    "servings": 2,
    "category": "Dinner",
    "tags": ["italian"],
    "image_url": "/uploads/pasta.jpg",
    "author_id": "owner-1",
    "household_id": None,
    "dietary_tags": [],
    "difficulty": "easy",
    "nutrition_calories": 400,
    "nutrition_protein": 12,
    "nutrition_carbs": 60,
    "nutrition_fat": 8,
    "nutrition_fiber": None,
    "nutrition_sugar": None,
    "nutrition_sodium": None,
}


@pytest.mark.asyncio
async def test_save_shared_recipe_copies_into_account():
    recipient = {"id": "user-2", "email": "b@example.com", "household_id": "hh-2", "role": "user"}
    app.dependency_overrides[get_current_user] = lambda: recipient

    link = {
        "id": "link-1",
        "share_code": "Ab12Cd",
        "recipe_id": "src-1",
        "is_active": True,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "show_author": True,
        "allow_print": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    created = {}

    async def fake_create(doc):
        created.update(doc)
        return doc

    try:
        with patch("routers.sharing.recipe_share_repository") as share_repo, patch(
            "routers.sharing.recipe_repository"
        ) as recipe_repo, patch("routers.sharing.user_repository") as user_repo, patch(
            "routers.sharing.log_action", new_callable=AsyncMock
        ), patch(
            "utils.subscription.assert_can_create_recipes", new_callable=AsyncMock
        ) as assert_create:
            share_repo.find_by_share_code = AsyncMock(return_value=link)
            recipe_repo.find_by_id = AsyncMock(return_value=SOURCE_RECIPE)
            recipe_repo.find_one = AsyncMock(return_value=None)
            recipe_repo.create = AsyncMock(side_effect=fake_create)
            user_repo.find_by_id = AsyncMock(return_value={"id": "owner-1", "name": "Ada"})

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post("/api/share/recipe/Ab12Cd/save")

            assert res.status_code == 200, res.text
            body = res.json()
            assert body["already_saved"] is False
            assert body["already_owned"] is False
            assert body["recipe_id"] == created["id"]
            assert created["author_id"] == "user-2"
            assert created["household_id"] == "hh-2"
            assert created["title"] == "Shared Pasta"
            assert created["source_type"] == "shared"
            assert created["source_url"] == "/recipe/Ab12Cd"
            assert created["source_author"] == "Ada"
            assert created["image_url"] == "/uploads/pasta.jpg"
            assert created["ingredients"][0]["name"] == "pasta"
            assert_create.assert_awaited()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_save_shared_recipe_idempotent():
    recipient = {"id": "user-2", "email": "b@example.com", "role": "user"}
    app.dependency_overrides[get_current_user] = lambda: recipient
    existing = {**SOURCE_RECIPE, "id": "copy-9", "author_id": "user-2", "source_url": "/recipe/Ab12Cd"}
    link = {
        "id": "link-1",
        "share_code": "Ab12Cd",
        "recipe_id": "src-1",
        "is_active": True,
        "expires_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with patch("routers.sharing.recipe_share_repository") as share_repo, patch(
            "routers.sharing.recipe_repository"
        ) as recipe_repo, patch("routers.sharing.log_action", new_callable=AsyncMock):
            share_repo.find_by_share_code = AsyncMock(return_value=link)
            recipe_repo.find_by_id = AsyncMock(return_value=SOURCE_RECIPE)
            recipe_repo.find_one = AsyncMock(return_value=existing)
            recipe_repo.create = AsyncMock()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post("/api/share/recipe/Ab12Cd/save")

            assert res.status_code == 200, res.text
            body = res.json()
            assert body["already_saved"] is True
            assert body["recipe_id"] == "copy-9"
            recipe_repo.create.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
