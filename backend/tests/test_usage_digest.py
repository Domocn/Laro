"""Tests for owner AI / Ollama usage digest."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from services import usage_digest as ud


def test_digest_hour_and_cadence_defaults(monkeypatch):
    monkeypatch.delenv("USAGE_DIGEST_HOUR_UTC", raising=False)
    monkeypatch.delenv("USAGE_DIGEST_CADENCE", raising=False)
    assert ud.digest_hour_utc() == 8
    assert ud.digest_cadence() == "daily"


def test_digest_cadence_weekly(monkeypatch):
    monkeypatch.setenv("USAGE_DIGEST_CADENCE", "weekly")
    assert ud.digest_cadence() == "weekly"


@pytest.mark.asyncio
async def test_process_usage_digest_skips_wrong_hour(monkeypatch):
    monkeypatch.setenv("USAGE_DIGEST_ENABLED", "true")
    monkeypatch.setenv("USAGE_DIGEST_HOUR_UTC", "8")
    now = datetime(2026, 9, 10, 14, 0, 0, tzinfo=timezone.utc)
    result = await ud.process_usage_digest(now)
    assert result["skipped"] is True
    assert result["reason"] == "wrong_hour"


@pytest.mark.asyncio
async def test_process_usage_digest_weekly_skips_non_monday(monkeypatch):
    monkeypatch.setenv("USAGE_DIGEST_ENABLED", "true")
    monkeypatch.setenv("USAGE_DIGEST_CADENCE", "weekly")
    monkeypatch.setenv("USAGE_DIGEST_HOUR_UTC", "8")
    # 2026-09-10 is Thursday
    now = datetime(2026, 9, 10, 8, 0, 0, tzinfo=timezone.utc)
    result = await ud.process_usage_digest(now)
    assert result["skipped"] is True
    assert result["reason"] == "not_monday"


@pytest.mark.asyncio
async def test_send_usage_digest_email_builds_report(monkeypatch):
    monkeypatch.setenv("LARO_OWNER_EMAILS", "owner@example.com")
    report = {
        "generated_at": "2026-09-10T12:00:00+00:00",
        "ollama": {
            "plan": "pro",
            "email": "owner@example.com",
            "activity_cost": "0.00000",
            "period": {"type": "last_4_weeks", "starting_at": "2026-08-17", "ending_at": "2026-09-10"},
            "limits": {"monthly": {"usage": 0, "models": []}},
            "error": None,
        },
        "laro": {
            "free_ai_limit": 3,
            "user_count": 21,
            "total_ai_uses": 7,
            "users_with_ai": 4,
            "free_at_limit": 0,
            "premiumish_users": 2,
            "top_users": [
                {"email": "a@b.com", "role": "user", "subscription_status": "free", "ai_uses": 2}
            ],
        },
    }
    with patch.object(ud, "build_usage_report", AsyncMock(return_value=report)), patch(
        "services.email.is_email_configured", return_value=True
    ), patch("services.email.send_email", AsyncMock(return_value=True)) as send, patch(
        "services.email.get_base_template", side_effect=lambda c: c
    ):
        result = await ud.send_usage_digest_email()

    assert result["sent"] == 1
    assert result["recipients"] == ["owner@example.com"]
    assert send.await_count == 1
    subject = send.await_args.kwargs.get("subject") or send.await_args.args[1]
    assert "pro" in subject.lower() or "Pro" in subject or "usage" in subject.lower()


@pytest.mark.asyncio
async def test_fetch_ollama_usage_reports_missing_cloud_key(monkeypatch):
    class S:
        ollama_api_key = ""
        ollama_url = "http://localhost:11434"

    with patch.dict("sys.modules", {}), patch("config.settings", S(), create=True):
        # Patch inside function imports
        with patch.object(ud, "fetch_ollama_usage", wraps=ud.fetch_ollama_usage):
            pass
    # Direct unit: empty key + local URL
    with patch("config.settings", S()):
        out = await ud.fetch_ollama_usage()
    assert out["configured"] is False or out.get("error")
    assert out.get("cloud") is False or out.get("error")
