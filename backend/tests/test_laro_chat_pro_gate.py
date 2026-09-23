"""Laro Chat endpoints require Pro; they do not consume free import quota."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from dependencies import get_current_user


def _free_user() -> dict:
    return {
        "id": "free-user-1",
        "email": "free@example.com",
        "household_id": None,
        "subscription_status": "free",
        "role": "user",
        "ai_uses_count": 0,
    }


def _pro_user() -> dict:
    return {
        "id": "pro-user-1",
        "email": "pro@example.com",
        "household_id": None,
        "subscription_status": "premium",
        "role": "user",
        "ai_uses_count": 0,
    }


@pytest.mark.asyncio
async def test_chat_rejects_free_user_with_pro_error():
    from routers import ai as ai_router

    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: _free_user()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/ai/chat",
            json={"message": "How do I sear steak?"},
        )

    assert res.status_code == 402
    detail = res.json()["detail"]
    assert detail["error"] == "laro_chat_pro_required"
    assert detail.get("upgrade_required") is True


@pytest.mark.asyncio
async def test_chat_allows_pro_user_without_burning_free_quota():
    from routers import ai as ai_router

    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: _pro_user()

    with patch(
        "routers.ai.call_llm_laro_chat",
        new=AsyncMock(return_value="Sear on high heat until browned."),
    ) as llm_mock, patch(
        "routers.ai._resolve_chat_session",
        new=AsyncMock(
            return_value={"id": "sess-1", "title": "New chat", "user_id": "pro-user-1"}
        ),
    ), patch(
        "routers.ai._persist_chat_turn",
        new=AsyncMock(),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/ai/chat",
                json={"message": "How do I sear steak?"},
            )

    assert res.status_code == 200
    assert res.json()["response"] == "Sear on high heat until browned."
    llm_mock.assert_awaited_once()
