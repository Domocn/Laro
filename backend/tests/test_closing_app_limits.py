from datetime import datetime, timezone

from utils.free_limits import (
    CLOSING_APP_RECIPE_ALLOWANCE,
    closing_app_recipe_limit,
    closing_app_window_open,
    recipe_limit,
)


def test_closing_window_open_before_deadline():
    assert closing_app_window_open(datetime(2026, 10, 21, tzinfo=timezone.utc)) is True
    assert closing_app_window_open(datetime(2026, 11, 16, tzinfo=timezone.utc)) is False


def test_free_user_gets_migration_allowance_in_window():
    user = {"id": "u1", "subscription_status": "free"}
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert recipe_limit(user) == 50
    assert closing_app_recipe_limit(user, now) == CLOSING_APP_RECIPE_ALLOWANCE
    assert CLOSING_APP_RECIPE_ALLOWANCE == 500


def test_free_user_returns_to_normal_cap_after_window():
    user = {"id": "u1", "subscription_status": "free"}
    later = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert closing_app_recipe_limit(user, later) == 50
