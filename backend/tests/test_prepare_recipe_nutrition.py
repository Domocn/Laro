from utils.recipe_fields import prepare_recipe_for_response


def _base_row(**overrides):
    row = {
        "id": "r1",
        "title": "Test Bowl",
        "description": "",
        "ingredients": [
            {"amount": "100", "unit": "g", "name": "chicken breast"},
            {"amount": "1", "unit": "", "name": "banana"},
        ],
        "instructions": ["Mix"],
        "prep_time": 5,
        "cook_time": 0,
        "servings": 1,
        "category": "Breakfast",
        "tags": [],
        "image_url": "",
        "author_id": "u1",
        "household_id": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "nutrition_calories": None,
        "nutrition_protein": None,
        "nutrition_carbs": None,
        "nutrition_fat": None,
        "nutrition_fiber": None,
        "nutrition_sugar": None,
        "nutrition_sodium": None,
    }
    row.update(overrides)
    return row


def test_prepare_estimates_missing_macros():
    shaped = prepare_recipe_for_response(_base_row())
    n = shaped.get("nutrition") or {}
    assert n.get("calories") is not None
    assert n.get("protein") is not None
    assert n.get("nutrition_estimated") is True
    assert n.get("nutrition_source") == "estimated"


def test_prepare_keeps_author_macros():
    shaped = prepare_recipe_for_response(
        _base_row(
            nutrition_calories=400,
            nutrition_protein=40,
            nutrition_carbs=10,
            nutrition_fat=12,
        )
    )
    n = shaped.get("nutrition") or {}
    assert n["calories"] == 400
    assert n["protein"] == 40
    assert n.get("nutrition_estimated") in (None, False)


def test_prepare_can_skip_estimate():
    shaped = prepare_recipe_for_response(
        _base_row(),
        estimate_missing_nutrition=False,
    )
    assert shaped.get("nutrition") is None
