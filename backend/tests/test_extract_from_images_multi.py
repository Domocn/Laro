"""Ensure extract-from-images passes every uploaded page to vision (not just [0])."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from dependencies import get_current_user


@pytest.mark.asyncio
async def test_extract_from_images_sends_all_pages():
    """Regression: previously only data.images[0] was passed to call_llm_with_image."""
    from routers import ai as ai_router

    captured = {}

    async def fake_vision(client, system_prompt, user_prompt, images, user_id=None):
        captured["images"] = images
        captured["user_prompt"] = user_prompt
        return json.dumps(
            {
                "title": "Two-Page Stew",
                "description": "Combined",
                "ingredients": [{"name": "beef", "amount": "1", "unit": "lb"}],
                "instructions": ["Brown", "Simmer"],
                "prep_time": 10,
                "cook_time": 60,
                "servings": 4,
                "category": "Dinner",
                "tags": ["stew"],
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
        ai_router, "call_llm_with_image", side_effect=fake_vision
    ), patch.object(ai_router, "require_ai_quota", AsyncMock()), patch.object(
        ai_router, "consume_ai_quota", AsyncMock()
    ), patch.object(ai_router, "is_premium_user", return_value=True), patch.object(
        ai_router, "_resolve_cookbook_for_user", AsyncMock(return_value=None)
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "images": ["aaa", "bbb", "ccc"],
                "cookbook_id": None,
                "cookbook_page": 12,
            }
            res = await client.post("/api/ai/extract-from-images", json=payload)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["images_processed"] == 3
    assert captured["images"] == ["aaa", "bbb", "ccc"]
    assert "3" in captured["user_prompt"]
    assert body["recipe"]["title"] == "Two-Page Stew"
    assert "needs-review" in body["recipe"]["tags"]
    assert body["needs_review"] is True


def test_extract_from_images_source_uses_all_images():
    """Static guard: endpoint must not hard-code images[0] for the vision call."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "routers" / "ai.py"
    text = src.read_text()
    # Isolate the extract_recipe_from_images function body roughly
    start = text.index("async def extract_recipe_from_images")
    end = text.index("\n@router.", start + 1) if "\n@router." in text[start + 1 :] else len(text)
    # If no next router, take until end of file chunk
    fn = text[start : start + 3500]
    assert "data.images[0]" not in fn
    assert "call_llm_with_images" in fn
    assert "data.images" in fn
