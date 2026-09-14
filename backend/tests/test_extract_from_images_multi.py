"""Ensure extract-from-images handles multi-page / multi-recipe cookbook photos."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from dependencies import get_current_user, prepare_vision_images


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
                "recipes": [
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
                ]
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
    ), patch.object(
        ai_router.recipe_repository,
        "find_by_household_or_author",
        AsyncMock(return_value=[]),
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
    assert body["recipe"]["title"] == "Two-Page Stew"
    assert body["recipe_count"] == 1
    assert len(body["recipes"]) == 1
    assert "needs-review" in body["recipe"]["tags"]
    assert "imported-photo" in body["recipe"]["tags"]
    assert body["needs_review"] is True


@pytest.mark.asyncio
async def test_extract_from_images_accepts_bare_recipe_list():
    """Root cause of cookbook photo failures: vision returns a JSON array of recipes."""
    from routers import ai as ai_router

    async def fake_vision(client, system_prompt, user_prompt, images, user_id=None):
        # Model often returns a bare list when multiple dishes are photographed
        return json.dumps(
            [
                {
                    "title": "Southwest Turkey & Egg Scramble",
                    "ingredients": [{"name": "turkey", "amount": "8", "unit": "oz"}],
                    "instructions": ["Scramble"],
                    "prep_time": 5,
                    "cook_time": 10,
                    "servings": 2,
                    "category": "Breakfast",
                    "tags": [],
                },
                {
                    "title": "Smoked Salmon Bowl",
                    "ingredients": [{"name": "salmon", "amount": "4", "unit": "oz"}],
                    "instructions": ["Assemble"],
                    "prep_time": 10,
                    "cook_time": 0,
                    "servings": 1,
                    "category": "Breakfast",
                    "tags": [],
                },
            ]
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
    ), patch.object(
        ai_router, "_resolve_cookbook_for_user", AsyncMock(return_value=None)
    ), patch.object(
        ai_router.recipe_repository,
        "find_by_household_or_author",
        AsyncMock(return_value=[]),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/ai/extract-from-images",
                json={"images": ["img1", "img2"]},
            )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["recipe_count"] == 2
    titles = [r["title"] for r in body["recipes"]]
    assert "Southwest Turkey & Egg Scramble" in titles
    assert "Smoked Salmon Bowl" in titles
    # Older clients that only read `.recipe` still get the first dish
    assert body["recipe"]["title"] == titles[0]


@pytest.mark.asyncio
async def test_extract_from_images_batches_large_uploads():
    """Uploads above PHOTO_EXTRACT_BATCH_SIZE are split across vision calls."""
    from routers import ai as ai_router

    calls = []

    async def fake_vision(client, system_prompt, user_prompt, images, user_id=None):
        calls.append(list(images))
        recipes = [
            {
                "title": f"Dish {img}",
                "ingredients": [{"name": "egg", "amount": "1", "unit": ""}],
                "instructions": ["Cook"],
                "category": "Breakfast",
                "tags": [],
            }
            for img in images
        ]
        return json.dumps({"recipes": recipes})

    user = {
        "id": "user-1",
        "household_id": None,
        "subscription_status": "premium",
        "ai_uses_count": 0,
    }
    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user

    # 7 images with batch size 5 → 2 vision calls
    imgs = [f"p{i}" for i in range(7)]
    with patch.object(ai_router, "call_llm_with_images", side_effect=fake_vision), patch.object(
        ai_router, "require_ai_quota", AsyncMock()
    ), patch.object(ai_router, "consume_ai_quota", AsyncMock()), patch.object(
        ai_router, "is_premium_user", return_value=True
    ), patch.object(
        ai_router, "_resolve_cookbook_for_user", AsyncMock(return_value=None)
    ), patch.object(
        ai_router.recipe_repository,
        "find_by_household_or_author",
        AsyncMock(return_value=[]),
    ), patch(
        "services.recipe_pdf_import.PHOTO_EXTRACT_BATCH_SIZE", 5
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/ai/extract-from-images",
                json={"images": imgs},
            )

    assert res.status_code == 200, res.text
    assert len(calls) == 2
    assert calls[0] == imgs[:5]
    assert calls[1] == imgs[5:]
    assert res.json()["recipe_count"] == 7


def test_extract_from_images_source_uses_all_images():
    """Static guard: endpoint must not hard-code images[0] for the vision call."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "routers" / "ai.py"
    text = src.read_text()
    start = text.index("async def extract_recipe_from_images")
    fn = text[start : start + 5500]
    assert "data.images[0]" not in fn
    assert "call_llm_with_images" in fn
    assert "parse_llm_recipes_payload" in fn
    assert "MULTI_RECIPE_IMAGES_PROMPT" in fn
    assert "prepare_vision_images" in fn


def test_prepare_vision_images_downscales_large_jpeg(tmp_path):
    """Phone-camera photos are re-encoded so multi-page bodies stay under limits."""
    import base64
    import io

    from PIL import Image

    im = Image.new("RGB", (4000, 3000), color=(240, 240, 230))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=95)
    raw_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    data_url = f"data:image/jpeg;base64,{raw_b64}"

    out = prepare_vision_images([data_url], max_side=1600, quality=80)
    assert len(out) == 1
    decoded = base64.b64decode(out[0])
    with Image.open(io.BytesIO(decoded)) as got:
        assert max(got.size) <= 1600
        assert got.format == "JPEG"
    assert len(out[0]) < len(raw_b64)
