"""Import quota 402 message points users to Laro Pro (not chat-only)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from utils import ai_quota as aq


@pytest.mark.asyncio
async def test_require_ai_quota_message_mentions_laro_pro():
    free_user = {
        "id": "u1",
        "subscription_status": "free",
        "role": "user",
        "ai_bonus_uses": 0,
    }
    with patch.object(aq, "get_ai_usage", new=AsyncMock(return_value=99)), patch.object(
        aq, "free_ai_limit", return_value=3
    ), patch.object(aq, "is_premium_user", return_value=False):
        with pytest.raises(HTTPException) as exc:
            await aq.require_ai_quota(free_user)
    assert exc.value.status_code == 402
    detail = exc.value.detail
    assert detail["error"] == "ai_quota_exceeded"
    assert "Laro Pro" in detail["message"]
    assert "import" in detail["message"].lower()
