"""Tests for the "what should I cook?" recommendations endpoint."""
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

import routers.recipe_recommendations as rec
from dependencies import get_current_user

USER = {"id": "u1", "household_id": "h1", "role": "user", "subscription_status": "premium"}
RECIPES = [
    {"id": "r1", "title": "Chickpea curry", "ingredients": [{"name": "chickpeas"}, {"name": "spinach"}],
     "tags": ["curry"], "dietary_tags": ["vegan"]},
    {"id": "r2", "title": "Chicken pie", "ingredients": [{"name": "chicken"}, {"name": "pastry"}],
     "tags": [], "dietary_tags": []},
    {"id": "r3", "title": "Spinach omelette", "ingredients": [{"name": "eggs"}, {"name": "spinach"}],
     "tags": [], "dietary_tags": ["vegetarian"]},
]


def _app():
    app = FastAPI()
    app.include_router(rec.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: USER
    app.state.http_client = object()
    return app


async def _post(body, llm=None, recipes=RECIPES):
    repo = AsyncMock()
    repo.find_by_household_or_author = AsyncMock(return_value=[dict(r) for r in recipes])
    with patch.object(rec, "recipe_repository", repo), \
         patch.object(rec, "require_ai_quota", AsyncMock()), \
         patch.object(rec, "consume_ai_quota", AsyncMock()), \
         patch.object(rec, "call_llm", llm or AsyncMock(return_value='{"recommendations": []}')):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app()), base_url="http://t") as c:
            return await c.post("/api/recommendations", json=body), repo


@pytest.mark.asyncio
async def test_returns_ai_picks_only_from_user_library():
    llm = AsyncMock(return_value=json.dumps({"recommendations": [
        {"id": "r1", "reason": "Uses your spinach", "missing_ingredients": ["coconut milk"]},
        {"id": "someone-elses-recipe", "reason": "hallucinated"},
        {"id": "r1", "reason": "duplicate"},
    ]}))
    resp, repo = await _post({"ingredients": ["spinach"], "dietary_needs": ["vegan"]}, llm)
    assert resp.status_code == 200
    body = resp.json()
    assert body["used_ai"] is True
    assert [r["recipe"]["id"] for r in body["recommendations"]] == ["r1"]
    assert body["recommendations"][0]["missing_ingredients"] == ["coconut milk"]
    repo.find_by_household_or_author.assert_awaited_once()
    assert repo.find_by_household_or_author.await_args.args[:2] == ("u1", "h1")
    prompt = llm.await_args.args[2]
    assert "vegan" in prompt and "Chickpea curry" in prompt


@pytest.mark.asyncio
async def test_requires_some_input():
    resp, _ = await _post({"description": "  ", "ingredients": []})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_empty_library_skips_ai():
    llm = AsyncMock()
    resp, _ = await _post({"ingredients": ["eggs"]}, llm, recipes=[])
    assert resp.json() == {"recommendations": [], "used_ai": False, "library_size": 0}
    llm.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_to_keyword_match_and_respects_diet_when_ai_fails():
    llm = AsyncMock(side_effect=httpx.ConnectError("ollama down"))
    resp, _ = await _post({"ingredients": ["spinach"], "dietary_needs": ["vegetarian"]}, llm)
    body = resp.json()
    assert body["used_ai"] is False
    assert [r["recipe"]["id"] for r in body["recommendations"]] == ["r3"]


@pytest.mark.asyncio
async def test_malformed_ai_json_returns_empty_not_500():
    resp, _ = await _post({"description": "something cosy"}, AsyncMock(return_value="not json"))
    assert resp.status_code == 200
    assert resp.json()["recommendations"] == []


def test_rank_candidates_prefers_overlap():
    ranked = rec.rank_candidates(RECIPES, rec._tokens("chicken pastry"), limit=2)
    assert ranked[0]["id"] == "r2"
