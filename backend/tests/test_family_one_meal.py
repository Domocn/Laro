"""Tests for family one-meal adult_boost on meal plan create/shape."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models import MealPlanCreate


@pytest.mark.asyncio
async def test_create_meal_plan_persists_adult_boost():
    from routers import meal_plans as mp

    user = {"id": "u1", "household_id": "h1"}
    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value=None)
    mock_recipe_repo = MagicMock()
    mock_recipe_repo.find_by_id = AsyncMock(
        return_value={"id": "r1", "title": "Mild Pasta"}
    )

    with (
        patch.object(mp, "meal_plan_repository", mock_repo),
        patch.object(mp, "recipe_repository", mock_recipe_repo),
        patch.object(mp, "log_action", AsyncMock()),
        patch.object(mp.ws_manager, "broadcast_to_household_or_user", AsyncMock()),
    ):
        result = await mp.create_meal_plan(
            plan=MealPlanCreate(
                date="2026-09-07",
                meal_type="Dinner",
                recipe_id="r1",
                adult_boost="For adults: Extra chili flakes",
            ),
            request=MagicMock(),
            user=user,
        )

    assert result.adult_boost == "Extra chili flakes"
    created = mock_repo.create.await_args.args[0]
    assert created["adult_boost"] == "Extra chili flakes"
    assert created["recipe_title"] == "Mild Pasta"


def test_normalize_adult_boost_strips_prefix():
    from routers.meal_plans import _normalize_adult_boost

    assert _normalize_adult_boost("For adults: chili oil") == "chili oil"
    assert _normalize_adult_boost("  Extra cheese  ") == "Extra cheese"
    assert _normalize_adult_boost("") == ""
    assert _normalize_adult_boost(None) == ""


def test_shape_plan_defaults_adult_boost():
    from routers.meal_plans import _shape_plan

    shaped = _shape_plan({"id": "1", "recipe_id": "r", "adult_boost": None})
    assert shaped["adult_boost"] == ""
    assert shaped["entry_type"] == "recipe"


def test_shape_plan_normalizes_date_and_null_notes():
    from datetime import datetime, timezone
    from routers.meal_plans import _shape_plan
    from models import MealPlanResponse

    shaped = _shape_plan({
        "id": "1",
        "date": datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc),
        "meal_type": "Dinner",
        "recipe_id": "r1",
        "recipe_title": None,
        "notes": None,
        "household_id": "h1",
        "created_at": datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
    })
    assert shaped["date"] == "2026-09-17"
    assert shaped["notes"] == ""
    assert shaped["recipe_title"] == ""

    response = MealPlanResponse(**shaped)
    assert response.date == "2026-09-17"
    assert response.notes == ""
    assert response.recipe_title == ""


def test_meal_plan_response_accepts_iso_datetime_date():
    from models import MealPlanResponse

    response = MealPlanResponse(
        id="1",
        date="2026-09-17T00:00:00",
        meal_type="Dinner",
        recipe_id="r1",
        recipe_title="Pasta",
        notes="ok",
        household_id="h1",
        created_at="2026-09-17T12:00:00",
    )
    assert response.date == "2026-09-17"
