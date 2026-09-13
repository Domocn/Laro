"""Unit + mocked API tests for store-meal recreate endpoint."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from dependencies import get_current_user
from models import RecreateStoreMealRequest
from routers import ai as ai_router


def test_recreate_store_meal_request_defaults():
    req = RecreateStoreMealRequest()
    assert req.mode == "recreate"
    assert req.images == []


def test_store_meal_modes_cover_mvp():
    for mode in (
        "recreate",
        "healthier",
        "higher_protein",
        "lower_calorie",
        "lower_carb",
        "custom",
    ):
        assert mode in ai_router.STORE_MEAL_MODES


def test_recreate_store_meal_route_registered():
    paths = {getattr(r, "path", None) for r in ai_router.router.routes}
    assert "/ai/recreate-store-meal" in paths


@pytest.mark.asyncio
async def test_recreate_store_meal_rejects_empty_payload():
    user = {
        "id": "user-1",
        "household_id": "hh-1",
        "subscription_status": "premium",
        "ai_uses_count": 0,
    }
    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    with patch.object(ai_router, "require_ai_quota", AsyncMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/ai/recreate-store-meal",
                json={"mode": "recreate", "images": []},
            )

    assert res.status_code == 400
    assert "photo" in res.json()["detail"].lower() or "product" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_recreate_store_meal_rejects_bad_mode():
    user = {
        "id": "user-1",
        "household_id": "hh-1",
        "subscription_status": "premium",
        "ai_uses_count": 0,
    }
    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    with patch.object(ai_router, "require_ai_quota", AsyncMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/ai/recreate-store-meal",
                json={
                    "mode": "deep_fry_everything",
                    "product_name": "Meal Deal",
                    "images": [],
                },
            )

    assert res.status_code == 400
    assert "mode" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_recreate_store_meal_text_only_mocked_llm():
    captured = {}

    async def fake_llm(client, system_prompt, user_prompt, user_id=None, **kwargs):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return json.dumps(
            {
                "title": "High-Protein Chicken Tikka Bowl",
                "description": "Home version with extra chicken and yoghurt",
                "original_product": "Tesco Chicken Tikka Masala",
                "changes_made": ["Doubled chicken", "Added Greek yoghurt"],
                "ingredients": [
                    {"name": "chicken breast", "amount": "400", "unit": "g"},
                    {"name": "basmati rice", "amount": "150", "unit": "g"},
                ],
                "instructions": ["Marinate", "Cook sauce", "Serve"],
                "prep_time": 15,
                "cook_time": 25,
                "servings": 2,
                "category": "Dinner",
                "tags": ["indian"],
                "nutrition": {
                    "calories": 520,
                    "protein": 48,
                    "carbs": 45,
                    "fat": 14,
                    "fiber": 4,
                    "sugar": 8,
                    "sodium": 600,
                },
            }
        )

    user = {
        "id": "user-1",
        "household_id": "hh-1",
        "subscription_status": "premium",
        "ai_uses_count": 0,
    }

    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    with patch.object(ai_router, "call_llm", side_effect=fake_llm), patch.object(
        ai_router, "require_ai_quota", AsyncMock()
    ), patch.object(ai_router, "consume_ai_quota", AsyncMock()), patch.object(
        ai_router, "is_premium_user", return_value=True
    ), patch(
        "utils.preference_context.load_user_prefs_and_food_context",
        AsyncMock(return_value="User likes mild spice"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/ai/recreate-store-meal",
                json={
                    "mode": "higher_protein",
                    "product_name": "Tesco Chicken Tikka Masala",
                    "description": "Mild tikka with rice",
                    "ingredients_text": "chicken, rice, cream, spices",
                    "nutrition_text": "650kcal, 28g protein",
                    "images": [],
                },
            )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["mode"] == "higher_protein"
    assert body["needs_review"] is True
    assert body["images_processed"] == 0
    recipe = body["recipe"]
    assert recipe["title"] == "High-Protein Chicken Tikka Bowl"
    assert "needs-review" in recipe["tags"]
    assert "store-meal" in recipe["tags"]
    assert "higher-protein" in recipe["tags"]
    assert recipe["source_type"] == "store_meal"
    assert recipe["transform_mode"] == "higher_protein"
    assert recipe["changes_made"] == ["Doubled chicken", "Added Greek yoghurt"]
    assert recipe["nutrition"]["protein"] == 48
    assert "higher protein" in captured["system"].lower() or "protein" in captured["system"].lower()
    assert "Tesco Chicken Tikka Masala" in captured["user"]


@pytest.mark.asyncio
async def test_recreate_store_meal_vision_path_mocked():
    captured = {}

    async def fake_vision(client, system_prompt, user_prompt, images, user_id=None, **kwargs):
        captured["images"] = images
        return json.dumps(
            {
                "title": "Healthier Ready Lasagne",
                "description": "Lighter home lasagne",
                "ingredients": [{"name": "courgette", "amount": "2", "unit": ""}],
                "instructions": ["Layer", "Bake"],
                "prep_time": 20,
                "cook_time": 40,
                "servings": 4,
                "category": "Dinner",
                "tags": [],
                "changes_made": ["More veg", "Less cheese"],
            }
        )

    user = {
        "id": "user-1",
        "household_id": "hh-1",
        "subscription_status": "premium",
        "ai_uses_count": 0,
    }
    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    with patch.object(ai_router, "call_llm_with_images", side_effect=fake_vision), patch.object(
        ai_router, "require_ai_quota", AsyncMock()
    ), patch.object(ai_router, "consume_ai_quota", AsyncMock()), patch.object(
        ai_router, "is_premium_user", return_value=True
    ), patch(
        "utils.preference_context.load_user_prefs_and_food_context",
        AsyncMock(return_value=""),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/ai/recreate-store-meal",
                json={
                    "mode": "healthier",
                    "images": ["data:image/jpeg;base64,abc123", "plainbase64"],
                },
            )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["images_processed"] == 2
    # data-URL prefix stripped
    assert captured["images"] == ["abc123", "plainbase64"]
    assert body["recipe"]["title"] == "Healthier Ready Lasagne"
    assert "healthier" in body["recipe"]["tags"]


@pytest.mark.asyncio
async def test_recreate_store_meal_demo_mock_env(monkeypatch):
    monkeypatch.setenv("STORE_MEAL_DEMO_MOCK", "1")
    user = {
        "id": "user-1",
        "household_id": "hh-1",
        "subscription_status": "premium",
        "ai_uses_count": 0,
    }
    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    with patch.object(ai_router, "require_ai_quota", AsyncMock()), patch.object(
        ai_router, "call_llm", AsyncMock(side_effect=AssertionError("LLM should not run"))
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/ai/recreate-store-meal",
                json={
                    "mode": "healthier",
                    "product_name": "Ready Lasagne",
                    "images": [],
                },
            )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["mode"] == "healthier"
    assert "Ready Lasagne" in body["recipe"]["title"]
    assert "demo-mock" in body["recipe"]["tags"]
