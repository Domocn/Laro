from utils.recipe_fields import enrich_nutrition_from_ingredients


def test_enrich_keeps_complete_nutrition():
    nutrition = {"calories": 400, "protein": 30, "carbs": 20, "fat": 10}
    out = enrich_nutrition_from_ingredients(
        nutrition,
        [{"amount": "100", "unit": "g", "name": "chicken breast"}],
        servings=1,
    )
    assert out["calories"] == 400
    assert out["nutrition_estimated"] is False
    assert out["nutrition_source"] == "recipe"


def test_enrich_fills_missing_macros_from_ingredients():
    # Banana + yogurt should resolve in food DB; fill carbs/fat when absent
    out = enrich_nutrition_from_ingredients(
        {"calories": 250, "protein": 22, "carbs": None, "fat": None},
        [
            {"amount": "1", "unit": "", "name": "banana"},
            {"amount": "100", "unit": "g", "name": "greek yogurt"},
            {"amount": "1", "unit": "", "name": "egg"},
        ],
        servings=1,
    )
    assert out["calories"] == 250
    assert out["protein"] == 22
    # Filled from estimate when food DB matches
    assert out.get("carbs") is not None or out.get("fat") is not None
    assert out["nutrition_estimated"] is True
    assert out["nutrition_source"] == "mixed"


def test_enrich_preserves_estimated_flag_when_complete():
    out = enrich_nutrition_from_ingredients(
        {
            "calories": 250,
            "protein": 22,
            "carbs": 28,
            "fat": 16,
            "nutrition_estimated": True,
            "nutrition_source": "mixed",
        },
        [{"amount": "1", "unit": "", "name": "banana"}],
        servings=1,
    )
    assert out["nutrition_estimated"] is True
    assert out["nutrition_source"] == "mixed"
    assert out["calories"] == 250


def test_enrich_estimates_when_no_nutrition_given():
    out = enrich_nutrition_from_ingredients(
        None,
        [{"amount": "100", "unit": "g", "name": "chicken breast"}],
        servings=1,
    )
    assert out.get("calories") is not None
    assert out["nutrition_estimated"] is True
    assert out["nutrition_source"] == "estimated"

