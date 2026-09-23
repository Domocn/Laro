"""Referral signup does not grant backend Pro when REFERRAL_TRIAL_DAYS=0."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from utils.subscription import REFERRAL_TRIAL_DAYS, is_premium_user


def test_referral_trial_days_default_zero(monkeypatch):
    monkeypatch.delenv("REFERRAL_TRIAL_DAYS", raising=False)
    import importlib
    import utils.subscription as sub

    importlib.reload(sub)
    assert sub.REFERRAL_TRIAL_DAYS == 0


def test_referral_trial_end_still_grants_pro_when_enabled():
    end = datetime.now(timezone.utc) + timedelta(days=7)
    user = {
        "email": "a@b.c",
        "role": "user",
        "subscription_status": "free",
        "referral_trial_end": end,
    }
    assert is_premium_user(user) is True


def test_no_referral_trial_end_means_free():
    user = {
        "email": "a@b.c",
        "role": "user",
        "subscription_status": "free",
        "referral_trial_end": None,
    }
    assert is_premium_user(user) is False
