"""Unit tests for auto meal-plan day normalization (1-based AI → week dates)."""
from datetime import date

from routers.ai import _attach_auto_meal_plan_dates, _normalize_auto_meal_plan_days


def test_normalize_shifts_one_based_days():
    plan = [{"day": d, "meals": []} for d in range(1, 8)]
    out = _normalize_auto_meal_plan_days(plan, 7)
    assert [p["day"] for p in out] == list(range(7))


def test_normalize_keeps_zero_based_days():
    plan = [{"day": i, "meals": []} for i in range(7)]
    out = _normalize_auto_meal_plan_days(plan, 7)
    assert [p["day"] for p in out] == list(range(7))


def test_attach_dates_uses_week_start_not_today():
    plan = [{"day": i, "meals": []} for i in range(7)]
    start = date(2026, 8, 17)  # Monday
    out = _attach_auto_meal_plan_dates(
        _normalize_auto_meal_plan_days(plan, 7), start
    )
    assert out[0]["date"] == "2026-08-17"
    assert out[6]["date"] == "2026-08-23"
