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
