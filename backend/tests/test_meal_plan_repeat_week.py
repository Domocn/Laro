"""Tests for meal-plan repeat-week + idempotent delete (E-MP003)."""
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel


class _User(dict):
    pass


@pytest.mark.asyncio
async def test_delete_meal_plan_missing_is_success():
    from routers import meal_plans as mp

    user = {"id": "u1", "household_id": None}
    mock_repo = MagicMock()
    mock_repo.find_by_id = AsyncMock(return_value=None)

    with patch.object(mp, "meal_plan_repository", mock_repo):
        # Call the underlying coroutine by invoking endpoint function directly
        result = await mp.delete_meal_plan(
            plan_id="gone-id",
            request=MagicMock(),
            user=user,
        )
    assert result["already_gone"] is True
    mock_repo.delete_plan.assert_not_called()


@pytest.mark.asyncio
async def test_repeat_week_copies_and_clears_destination():
    from routers import meal_plans as mp

    user = {"id": "u1", "household_id": "h1"}
    start = date(2026, 9, 7)
    end = start + timedelta(days=6)
    source = [
        {
            "id": "m1",
            "date": start.isoformat(),
            "meal_type": "Dinner",
            "entry_type": "recipe",
            "recipe_id": "r1",
            "recipe_title": "Steak",
            "notes": "",
            "household_id": "h1",
        },
        {
            "id": "m2",
            "date": (start + timedelta(days=1)).isoformat(),
            "meal_type": "Lunch",
            "entry_type": "note",
            "recipe_id": None,
            "recipe_title": "Out",
            "notes": "cafe",
            "household_id": "h1",
        },
    ]

    mock_repo = MagicMock()
    mock_repo.find_by_household = AsyncMock(return_value=source)
    mock_repo.delete_in_date_range = AsyncMock(return_value=2)
    mock_repo.create = AsyncMock(return_value=None)

    with (
        patch.object(mp, "meal_plan_repository", mock_repo),
        patch.object(mp, "log_action", AsyncMock()),
        patch.object(mp.ws_manager, "broadcast_to_household_or_user", AsyncMock()),
    ):
        result = await mp.repeat_week(
            data=mp.RepeatWeekRequest(
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                day_offset=7,
            ),
            request=MagicMock(),
            user=user,
        )

    assert result["created"] == 2
    assert result["replaced"] == 2
    assert result["dest_start"] == (start + timedelta(days=7)).isoformat()
    assert mock_repo.create.await_count == 2
    created_dates = {call.args[0]["date"] for call in mock_repo.create.await_args_list}
    assert (start + timedelta(days=7)).isoformat() in created_dates
    assert (start + timedelta(days=8)).isoformat() in created_dates
