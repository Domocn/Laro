"""Users can only list/load/delete their own AI chat sessions."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from dependencies import get_current_user


def _user(uid: str) -> dict:
    return {
        "id": uid,
        "email": f"{uid}@example.com",
        "household_id": None,
        "subscription_status": "premium",
        "ai_uses_count": 0,
    }


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_chat_session():
    from routers import ai as ai_router

    owner = _user("owner-1")
    stranger = _user("stranger-2")
    session = {
        "id": "sess-owned",
        "user_id": owner["id"],
        "title": "Pasta tips",
        "created_at": None,
        "updated_at": None,
    }

    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")

    # Stranger is authenticated
    app.dependency_overrides[get_current_user] = lambda: stranger

    with patch(
        "database.repositories.ai_chat_repository.ai_chat_session_repository.find_by_id_for_user",
        new=AsyncMock(return_value=None),
    ) as find_mock:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/ai/chat-sessions/sess-owned")

    assert res.status_code == 404
    find_mock.assert_awaited()
    # Must look up with the stranger's id (not the owner's)
    assert find_mock.await_args.args[0] == "sess-owned"
    assert find_mock.await_args.args[1] == stranger["id"]


@pytest.mark.asyncio
async def test_list_chat_sessions_scoped_to_current_user():
    from routers import ai as ai_router

    me = _user("me-1")
    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: me

    with patch(
        "database.repositories.ai_chat_repository.ai_chat_session_repository.list_for_user",
        new=AsyncMock(
            return_value=[
                {
                    "id": "s1",
                    "user_id": me["id"],
                    "title": "My soup chat",
                    "created_at": None,
                    "updated_at": None,
                }
            ]
        ),
    ) as list_mock:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/ai/chat-sessions")

    assert res.status_code == 200
    body = res.json()
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["title"] == "My soup chat"
    list_mock.assert_awaited_once_with(me["id"])


@pytest.mark.asyncio
async def test_report_chat_accepts_client_transcript_when_db_empty():
    from routers import ai as ai_router

    me = _user("reporter-1")
    session = {
        "id": "sess-report",
        "user_id": me["id"],
        "title": "Brownie chat",
        "created_at": None,
        "updated_at": None,
    }
    app = FastAPI()
    app.include_router(ai_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: me

    append_mock = AsyncMock(
        return_value={"id": "m1", "role": "assistant", "content": "Hi"}
    )
    list_messages_mock = AsyncMock(side_effect=[[], [{"role": "assistant", "content": "Hi there"}]])
    insert_ticket_mock = AsyncMock()
    insert_msg_mock = AsyncMock()

    with (
        patch(
            "database.repositories.ai_chat_repository.ai_chat_session_repository.find_by_id_for_user",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "database.repositories.ai_chat_repository.ai_chat_message_repository.list_for_session",
            new=list_messages_mock,
        ),
        patch(
            "database.repositories.ai_chat_repository.ai_chat_message_repository.append",
            new=append_mock,
        ),
        patch(
            "database.repositories.support_ticket_repository.support_ticket_repository.insert",
            new=insert_ticket_mock,
        ),
        patch(
            "database.repositories.support_ticket_repository.support_ticket_message_repository.insert",
            new=insert_msg_mock,
        ),
        patch("routers.support._generate_ticket_number", new=AsyncMock(return_value="T-100")),
        patch("routers.support._notify_ticket_created", new=AsyncMock()),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/ai/chat-sessions/sess-report/report",
                json={
                    "transcript": [{"role": "assistant", "content": "Hi there"}],
                    "recipe_title": "High Protein Brownie",
                    "platform": "web",
                },
            )

    assert res.status_code == 200
    assert res.json().get("status") == "reported"
    append_mock.assert_awaited()
    insert_ticket_mock.assert_awaited()
