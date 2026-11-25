from datetime import datetime, timezone

from routers.meal_plans import _plan_date


def test_plan_date_iso_and_datetime():
    assert _plan_date("2026-09-17") == "2026-09-17"
    assert _plan_date("2026-09-17T19:00:00.000Z") == "2026-09-17"
    assert _plan_date(datetime(2026, 9, 17, 23, 59, tzinfo=timezone.utc)) == "2026-09-17"
    assert _plan_date(None) == ""
