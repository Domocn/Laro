"""Unit tests for RevenueCat admin link helpers."""
import os
from unittest.mock import AsyncMock, patch

import pytest

from services import revenuecat as rc


def test_duration_mapping():
    assert rc._duration_for_days(0) == "lifetime"
    assert rc._duration_for_days(1) == "daily"
    assert rc._duration_for_days(7) == "weekly"
    assert rc._duration_for_days(30) == "monthly"
    assert rc._duration_for_days(365) == "yearly"


@pytest.mark.asyncio
async def test_grant_skipped_without_secret(monkeypatch):
    monkeypatch.setattr(rc, "REVENUECAT_SECRET_API_KEY", "")
    out = await rc.grant_promotional_entitlement("user-1", days=7)
    assert out["skipped"] is True
    assert out["configured"] is False


@pytest.mark.asyncio
async def test_grant_posts_end_time(monkeypatch):
    monkeypatch.setattr(rc, "REVENUECAT_SECRET_API_KEY", "sk_test")
    monkeypatch.setattr(rc, "REVENUECAT_ENTITLEMENT_ID", "Laro Pro")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "{}"
    mock_response.json = lambda: {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            assert "promotional" in url
            assert "Laro%20Pro" in url or "Laro Pro" in url or "entitlements/Laro" in url
            assert "end_time_ms" in json
            return mock_response

    with patch("httpx.AsyncClient", FakeClient):
        out = await rc.grant_promotional_entitlement("user-1", days=14)
    assert out["ok"] is True
    assert out["days"] == 14


@pytest.mark.asyncio
async def test_get_subscriber_active_entitlement(monkeypatch):
    monkeypatch.setattr(rc, "REVENUECAT_SECRET_API_KEY", "sk_test")
    monkeypatch.setattr(rc, "REVENUECAT_ENTITLEMENT_ID", "Laro Pro")

    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {
                "subscriber": {
                    "entitlements": {
                        "Laro Pro": {
                            "expires_date": None,
                            "product_identifier": "laro_pro_monthly",
                            "purchase_date": "2026-01-01T00:00:00Z",
                        }
                    }
                }
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            return FakeResp()

    with patch("httpx.AsyncClient", FakeClient):
        out = await rc.get_subscriber("user-1")
    assert out["ok"] is True
    assert out["has_laro_pro"] is True
