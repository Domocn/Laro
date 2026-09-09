"""Regression: null ingredient amount/unit must not 500 GET /recipes."""
from models import Ingredient, RecipeResponse
from utils.recipe_fields import normalize_ingredient, prepare_recipe_for_response


def test_normalize_ingredient_null_amount_and_unit():
    assert normalize_ingredient(
        {"name": "Paprika, garlic granules, salt and black pepper", "amount": None, "unit": None}
    ) == {
        "name": "Paprika, garlic granules, salt and black pepper",
        "amount": "",
        "unit": "",
    }


def test_normalize_ingredient_string_and_quantity_alias():
    assert normalize_ingredient("1 cup flour") == {
        "name": "1 cup flour",
        "amount": "",
        "unit": "",
    }
    assert normalize_ingredient({"name": "flour", "quantity": 1, "unit": "cup"}) == {
        "name": "flour",
        "amount": "1",
        "unit": "cup",
    }


def test_ingredient_model_coerces_none():
    ing = Ingredient(name="salt", amount=None, unit=None)
    assert ing.amount == ""
    assert ing.unit == ""


def test_prepare_recipe_for_response_accepts_null_ingredient_amount():
    """Cowandom PDF import stored seasoning with amount/unit null — list must still serialize."""
    row = {
        "id": "r1",
        "title": "Air-Fryer Chicken, Potatoes & Veg",
        "description": None,
        "ingredients": [
            {"name": "Chicken breast", "unit": "g", "amount": "140"},
            {"name": "Paprika, garlic granules, salt and black pepper", "unit": None, "amount": None},
        ],
        "instructions": ["Cook"],
        "prep_time": None,
        "cook_time": None,
        "servings": None,
        "category": "Dinner",
        "tags": ["needs-review", "imported-pdf"],
        "image_url": None,
        "author_id": "a286beb9-b7f4-4ef9-934b-7f4d121a03e2",
        "household_id": "a286beb9-b7f4-4ef9-934b-7f4d121a03e2",
        "created_at": "2026-09-05T00:00:00",
        "updated_at": "2026-09-05T00:00:00",
    }
    shaped = prepare_recipe_for_response(row)
    response = RecipeResponse(**shaped)
    assert response.title.startswith("Air-Fryer")
    assert len(response.ingredients) == 2
    assert response.ingredients[1].amount == ""
    assert response.ingredients[1].unit == ""
    assert response.description == ""
    assert response.category == "Dinner"
    assert response.servings == 4
