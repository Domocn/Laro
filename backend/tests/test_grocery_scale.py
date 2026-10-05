from utils.grocery_scale import ingredients_for_slot, scale_factor_for_servings


def test_scale_factor():
    assert scale_factor_for_servings(4, 8) == 2.0
    assert scale_factor_for_servings(4, 2) == 0.5


def test_ingredients_for_slot_doubles():
    recipe = {
        "servings": 4,
        "ingredients": [{"name": "flour", "amount": "2", "unit": "cup"}],
    }
    scaled = ingredients_for_slot(recipe, 8)
    assert scaled[0]["amount"] == "4"
