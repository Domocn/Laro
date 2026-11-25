"""Planned recipe versions + Low FODMAP swaps carry into the shopping list."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import GroceryGenerateRequest, MealPlanCreate, MealPlanResponse, MealPlanUpdate, RecipeSelection  # noqa: E402
from services.recipe_variants import (  # noqa: E402
    choice_label,
    clean_version_name,
    find_swap,
    ingredients_for_choice,
)

RECIPE = {
    "id": "r1",
    "title": "Pesto Pasta",
    "ingredients": [{"name": "pasta", "amount": "200", "unit": "g"}, {"name": "garlic clove", "amount": "2", "unit": ""}],
    "adaptations": json.dumps({
        "low_fodmap": {"swaps": [
            {"from": "garlic", "to": "garlic-infused oil"},
            {"from": "garlic clove", "to": "1 tbsp garlic-infused oil"},
        ], "notes": ""},
        "versions": [{
            "name": "Pomegranate",
            "ingredients": [{"name": "pasta"}, {"name": "pomegranate seeds"}, "garlic"],
            "instructions": ["Boil", "Scatter"],
        }],
    }),
}


def test_original_when_no_choice_or_unknown_version():
    assert ingredients_for_choice(RECIPE) == RECIPE["ingredients"]
    assert ingredients_for_choice(RECIPE, "Original") == RECIPE["ingredients"]
    assert ingredients_for_choice(RECIPE, "Not a version") == RECIPE["ingredients"]
    assert ingredients_for_choice({"ingredients": json.dumps([{"name": "x"}])}) == [{"name": "x"}]


def test_version_ingredients_case_insensitive():
    names = [i if isinstance(i, str) else i["name"] for i in ingredients_for_choice(RECIPE, "  pomegranate ")]
    assert names == ["pasta", "pomegranate seeds", "garlic"]


def test_low_fodmap_swaps_on_top_of_version():
    original = ingredients_for_choice(RECIPE, None, True)
    assert original[1] == {"name": "1 tbsp garlic-infused oil", "amount": "2", "unit": ""}  # longest match wins
    assert original[0]["name"] == "pasta"
    version = ingredients_for_choice(RECIPE, "Pomegranate", True)
    assert version[2]["name"] == "garlic-infused oil"  # string ingredient (normalised) swapped too
    # No swaps saved -> flag is a no-op
    assert ingredients_for_choice({"ingredients": [{"name": "garlic"}]}, None, True) == [{"name": "garlic"}]


def test_helpers():
    assert clean_version_name("  Chocolate   Orange ") == "Chocolate Orange"
    assert clean_version_name("original") is None
    assert clean_version_name(None) is None
    assert find_swap("Red onion", [{"from": "onion", "to": "leek"}])["to"] == "leek"
    assert find_swap("", [{"from": "onion", "to": "leek"}]) is None
    assert choice_label("Pesto Pasta", "Pomegranate", True) == "Pesto Pasta · Pomegranate · Low FODMAP"
    assert choice_label("Pesto Pasta") == "Pesto Pasta"


def test_meal_plan_models_round_trip_choice():
    sent = MealPlanCreate(date="2026-10-21", meal_type="Dinner", recipe_id="r1", recipe_version="Pomegranate", low_fodmap=True)
    assert (sent.recipe_version, sent.low_fodmap) == ("Pomegranate", True)
    legacy = MealPlanCreate(date="2026-10-21", meal_type="Dinner", recipe_id="r1")
    assert (legacy.recipe_version, legacy.low_fodmap) == (None, False)
    assert "recipe_version" not in MealPlanUpdate(notes="x").model_dump(exclude_unset=True)
    resp = MealPlanResponse(
        id="p1", date="2026-10-21", meal_type="Dinner", recipe_id="r1", recipe_title="Pesto Pasta",
        household_id="h1", created_at="2026-10-21T00:00:00", recipe_version="Pomegranate", low_fodmap=True,
    )
    assert resp.model_dump()["recipe_version"] == "Pomegranate"
    assert MealPlanResponse(id="p1", date="2026-10-21", meal_type="Dinner", household_id="h1",
                            created_at="x").low_fodmap is False


def test_shape_plan_handles_legacy_rows():
    from routers.meal_plans import _shape_plan

    shaped = _shape_plan({"id": "p1", "recipe_id": "r1", "date": "2026-10-21", "recipe_version": None, "low_fodmap": None})
    assert shaped["recipe_version"] is None and shaped["low_fodmap"] is False
    shaped = _shape_plan({"id": "p1", "recipe_id": "r1", "date": "2026-10-21", "recipe_version": " Pomegranate "})
    assert shaped["recipe_version"] == "Pomegranate"


def test_grocery_ingredient_sets_follow_selections():
    from routers.shopping_lists import _recipe_ingredient_sets

    other = {"id": "r2", "title": "Toast", "ingredients": [{"name": "bread"}]}
    sets = _recipe_ingredient_sets([RECIPE, other], [
        RecipeSelection(recipe_id="r1", recipe_version="Pomegranate", low_fodmap=True),
        RecipeSelection(recipe_id="r1"),
    ])
    assert [r["id"] for r, _ in sets] == ["r1", "r1", "r2"]
    assert sets[0][1][2]["name"] == "garlic-infused oil"
    assert sets[1][1] == RECIPE["ingredients"]
    assert sets[2][1] == [{"name": "bread"}]
    # No selections -> every recipe's Original, exactly as before
    assert _recipe_ingredient_sets([RECIPE], None) == [(RECIPE, RECIPE["ingredients"])]
    assert GroceryGenerateRequest(recipe_ids=["r1"]).selections is None
