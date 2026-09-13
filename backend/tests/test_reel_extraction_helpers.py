"""Tests for reel extraction helpers (ingredient normalize + caption macros)."""

from routers.ai import _attach_caption_nutrition, _normalize_reel_ingredients


def test_normalize_reel_ingredients_splits_measures():
    ings = _normalize_reel_ingredients(
        [
            "1 tbsp sweetener",
            {"amount": "", "unit": "", "name": "35 g flour"},
            {"amount": "3", "unit": "g", "name": "butter"},
            {"amount": "", "unit": "", "name": "sweetener to taste"},
        ]
    )
    assert ings[0]["unit"] in ("tbsp", "tablespoon") or "tbsp" in (ings[0]["unit"] or "")
    # food_db may normalize tbsp → tablespoon-ish; accept amount present
    assert ings[0]["amount"] in ("1", "1.0")
    assert "sweetener" in ings[0]["name"]
    assert ings[1]["amount"] in ("35", "35.0")
    assert ings[1]["unit"] == "g"
    assert "flour" in ings[1]["name"]
    assert ings[2] == {"amount": "3", "unit": "g", "name": "butter"}


def test_attach_caption_nutrition_from_macros_block():
    recipe = {"title": "Bowl", "ingredients": [], "instructions": []}
    caption = """Macros per bowl:
Calories: 380
Carbs: 38g
Protein: 32g
Fat: 11g
"""
    out = _attach_caption_nutrition(recipe, caption)
    nut = out.get("nutrition") or {}
    assert nut.get("calories") == 380
    assert nut.get("protein") == 32
    assert nut.get("carbs") == 38
    assert nut.get("fat") == 11
