import hashlib
import hmac
import json
import os

import pytest

from services.lemonsqueezy import (
    is_active_subscription_status,
    subscription_expires_from_attributes,
    verify_webhook_signature,
    extract_user_id_from_webhook,
)


def test_verify_webhook_signature_valid(monkeypatch):
    secret = "test-secret-6chars"
    body = b'{"meta":{"event_name":"subscription_created"}}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    import services.lemonsqueezy as ls

    monkeypatch.setattr(ls, "LEMONSQUEEZY_WEBHOOK_SECRET", secret)
    assert ls.verify_webhook_signature(body, sig) is True
    assert ls.verify_webhook_signature(body, "bad") is False


def test_extract_user_id_from_webhook():
    payload = {"meta": {"custom_data": {"user_id": "user-abc"}}}
    assert extract_user_id_from_webhook(payload) == "user-abc"


def test_subscription_expires_prefers_renews_for_active():
    attrs = {
        "status": "active",
        "renews_at": "2026-10-01T12:00:00.000000Z",
        "ends_at": None,
    }
    dt = subscription_expires_from_attributes(attrs)
    assert dt is not None
    assert dt.year == 2026


def test_is_active_subscription_status():
    assert is_active_subscription_status("active") is True
    assert is_active_subscription_status("on_trial") is True
    assert is_active_subscription_status("expired") is False
