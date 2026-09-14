"""
Home Assistant API endpoint unit tests (meal-type casing, recipe titles, AI quota).
"""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.mark.asyncio
async def test_today_next_meal_uses_lowercase_meal_types():
    """DB stores lowercase meal_type; /today must still pick next_meal."""
    from routers import homeassistant as ha

    plans = [
        {
            "id": "1",
            "date": "2026-09-06",
            "meal_type": "breakfast",
            "recipe_title": "Oats",
        },
        {
            "id": "2",
            "date": "2026-09-06",
            "meal_type": "dinner",
            "recipe_title": "Pasta",
        },
    ]
    user = {"id": "u1", "household_id": "h1"}

    mock_now = datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc)

    with (
        patch.object(
            ha.meal_plan_repository,
            "find_by_household",
            new=AsyncMock(return_value=plans),
        ),
        patch.object(ha, "datetime") as mock_dt,
    ):
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        result = await ha.homeassistant_today(user)

    assert result["count"] == 2
    assert result["next_meal"] is not None
    assert result["next_meal"]["meal_type"] == "dinner"
    assert result["next_meal"]["recipe_title"] == "Pasta"
    assert "Oats" in result["summary"]


@pytest.mark.asyncio
async def test_recipes_endpoint_exposes_title_as_name():
    from routers import homeassistant as ha

    recipes = [
        {
            "id": "r1",
            "title": "Tomato Soup",
            "description": "A cozy bowl",
            "prep_time": 10,
            "cook_time": 20,
            "servings": 4,
        }
    ]
    user = {"id": "u1", "household_id": "h1"}

    with patch.object(
        ha.recipe_repository,
        "find_by_household_or_author",
        new=AsyncMock(return_value=recipes),
    ):
        result = await ha.homeassistant_recipes(user, limit=10)

    assert result["count"] == 1
    assert result["recipes"][0]["name"] == "Tomato Soup"
    assert result["recipes"][0]["title"] == "Tomato Soup"


@pytest.mark.asyncio
async def test_all_endpoint_includes_ai_quota():
    from routers import homeassistant as ha

    user = {
        "id": "u1",
        "household_id": "h1",
        "email": "a@b.com",
        "name": "Ada",
        "favorites": "[]",
    }

    with (
        patch.object(
            ha.recipe_repository,
            "find_by_household_or_author",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(
            ha.meal_plan_repository,
            "find_by_household",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(
            ha.shopping_list_repository,
            "find_by_household",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "utils.ai_quota.get_quota_status",
            new=AsyncMock(
                return_value={
                    "premium": False,
                    "used": 1,
                    "limit": 3,
                    "bonus": 0,
                    "remaining": 2,
                    "unlimited": False,
                }
            ),
        ),
    ):
        result = await ha.homeassistant_all(user)

    assert result["ai_remaining"] == 2
    assert result["ai_unlimited"] is False
    assert result["ai_quota"]["remaining"] == 2
