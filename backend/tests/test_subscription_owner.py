"""Tests for owner forever / subscription helpers."""
from datetime import datetime, timedelta, timezone

from utils.subscription import (
    is_app_owner,
    is_premium_user,
    subscription_snapshot,
    user_subscription_fields,
)


def test_owner_email_is_forever_pro(monkeypatch):
    monkeypatch.setenv("LARO_OWNER_EMAILS", "cowandom79@gmail.com")
    user = {
        "email": "cowandom79@gmail.com",
        "role": "user",
        "subscription_status": "free",
    }
    assert is_app_owner(user)
    assert is_premium_user(user)
    snap = subscription_snapshot(user)
    assert snap["is_active"] is True
    assert snap["is_lifetime"] is True
    assert snap["is_owner"] is True
    assert snap["status"] == "premium"


def test_super_admin_is_forever_pro():
    user = {
        "email": "someone@example.com",
        "role": "super_admin",
        "subscription_status": "free",
    }
    assert is_app_owner(user)
    assert is_premium_user(user)


def test_lifetime_premium_no_expiry():
    user = {
        "email": "paid@example.com",
        "role": "user",
        "subscription_status": "premium",
        "subscription_expires": None,
        "subscription_source": "admin",
    }
    assert is_premium_user(user)
    snap = subscription_snapshot(user)
    assert snap["is_lifetime"] is True
    assert snap["is_active"] is True


def test_expired_premium_not_active():
    user = {
        "email": "paid@example.com",
        "role": "user",
        "subscription_status": "premium",
        "subscription_expires": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    }
    assert is_premium_user(user) is False
    snap = subscription_snapshot(user)
    assert snap["is_active"] is False
    assert snap["status"] == "expired"


def test_active_trial():
    user = {
        "email": "trial@example.com",
        "role": "user",
        "subscription_status": "trial",
        "subscription_expires": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    }
    assert is_premium_user(user)
    snap = subscription_snapshot(user)
    assert snap["is_active"] is True


def test_user_subscription_fields_owner_seamless(monkeypatch):
    monkeypatch.setenv("LARO_OWNER_EMAILS", "cowandom79@gmail.com")
    fields = user_subscription_fields({
        "email": "cowandom79@gmail.com",
        "role": "user",
        "subscription_status": "free",
    })
    assert fields["is_pro"] is True
    assert fields["is_owner"] is True
    assert fields["is_lifetime"] is True
    assert fields["subscription_active"] is True
    assert fields["subscription_status"] == "premium"


def test_user_subscription_fields_free_user():
    fields = user_subscription_fields({
        "email": "free@example.com",
        "role": "user",
        "subscription_status": "free",
    })
    assert fields["is_pro"] is False
    assert fields["is_owner"] is False
    assert fields["subscription_active"] is False
    assert fields["subscription_status"] == "free"


def test_referral_trial_grants_pro():
    end = datetime.now(timezone.utc) + timedelta(days=14)
    user = {
        "email": "referred@example.com",
        "role": "user",
        "subscription_status": "free",
        "referral_trial_end": end,
    }
    assert is_premium_user(user) is True
    snap = subscription_snapshot(user)
    assert snap["is_active"] is True
    assert snap["status"] == "trial"
    assert snap["source"] == "referral"
    fields = user_subscription_fields(user)
    assert fields["is_pro"] is True


def test_expired_referral_trial_not_pro():
    end = datetime.now(timezone.utc) - timedelta(days=1)
    user = {
        "email": "referred@example.com",
        "role": "user",
        "subscription_status": "free",
        "referral_trial_end": end,
    }
    assert is_premium_user(user) is False
    snap = subscription_snapshot(user)
    assert snap["is_active"] is False
