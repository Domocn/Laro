"""Unit tests for curated food DB + AI prompt injection helpers."""
from utils.food_db import (
    FOOD_DATABASE,
    build_ai_food_context,
    estimate_nutrition_from_foods,
    find_food,
    format_food_db_prompt_block,
    resolve_nutrition_goals,
    retrieve_foods_for_ai,
)
from utils.preference_context import format_preference_context


def test_food_db_has_high_protein_anchors():
    for name in (
        "chicken breast",
        "greek yogurt",
        "cottage cheese",
        "egg",
        "tofu",
        "lentils",
        "tuna",
        "whey protein powder",
    ):
        assert name in FOOD_DATABASE
        assert FOOD_DATABASE[name]["protein"] > 0


def test_find_food_fuzzy_match():
    match = find_food("fresh skinless chicken breast fillets")
    assert match is not None
    assert match[0] == "chicken breast"
    assert match[1]["protein"] == 31


def test_resolve_goals_defaults_for_high_protein():
    goals = resolve_nutrition_goals({"dietaryRestrictions": ["high-protein"]})
    assert goals["daily_protein_g"] == 140
    assert goals["daily_calories"] == 2200
    assert goals["protein_per_meal_g"] == 35.0
    assert goals["high_protein"] is True


def test_resolve_goals_explicit_overrides():
    goals = resolve_nutrition_goals(
        {
            "dietaryRestrictions": ["high-protein"],
            "dailyProteinTarget": 180,
            "dailyCalorieTarget": 2500,
        }
    )
    assert goals["daily_protein_g"] == 180
    assert goals["daily_calories"] == 2500
    assert goals["protein_per_meal_g"] == 45.0


def test_resolve_goals_empty_without_high_protein():
    goals = resolve_nutrition_goals({})
    assert goals["daily_protein_g"] is None
    assert goals["daily_calories"] is None
    assert goals["high_protein"] is False


def test_retrieve_prioritises_high_protein_and_pantry():
    foods = retrieve_foods_for_ai(
        {"dietaryRestrictions": ["high-protein"]},
        pantry_items=["greek yogurt", "spinach", "oats"],
        limit=12,
        seed="test-a",
    )
    names = [f["name"] for f in foods]
    assert any("yogurt" in n or "chicken" in n or "cottage" in n or "egg" in n for n in names)
    assert any(n in names for n in ("greek yogurt", "spinach", "oats"))
    # Uniqueness via seed: different seeds can reshuffle scores
    foods_b = retrieve_foods_for_ai(
        {"dietaryRestrictions": ["high-protein"]},
        pantry_items=["greek yogurt", "spinach", "oats"],
        limit=12,
        seed="test-b",
    )
    assert [f["name"] for f in foods] != [f["name"] for f in foods_b] or len(foods) >= 8


def test_retrieve_respects_vegan_filter():
    foods = retrieve_foods_for_ai(
        {"dietaryRestrictions": ["vegan", "high-protein"]},
        limit=15,
        seed="vegan",
    )
    names = {f["name"] for f in foods}
    assert "chicken breast" not in names
    assert "egg" not in names
    assert any(n in names for n in ("firm tofu", "tempeh", "lentils", "pea protein powder", "edamame"))


def test_format_food_db_prompt_block_includes_macros_and_goals():
    foods = retrieve_foods_for_ai(
        {"dietaryRestrictions": ["high-protein"]},
        limit=5,
        seed="prompt",
    )
    goals = resolve_nutrition_goals({"dietaryRestrictions": ["high-protein"]})
    block = format_food_db_prompt_block(foods, goals)
    assert "Food database building blocks" in block
    assert "protein" in block.lower()
    assert "140" in block
    assert "UNIQUE" in block
    assert "not medical" in block.lower()


def test_build_ai_food_context_for_high_protein():
    ctx = build_ai_food_context(
        {"dietaryRestrictions": ["high-protein"], "dailyProteinTarget": 160},
        pantry_items=["tuna", "rice"],
        query="high protein dinner ideas",
        seed="ctx1",
    )
    assert "Food database" in ctx
    assert "160" in ctx
    assert "tuna" in ctx or "rice" in ctx


def test_build_ai_food_context_skips_when_no_goals():
    ctx = build_ai_food_context({}, query="hello")
    assert ctx == ""


def test_estimate_nutrition_from_foods():
    result = estimate_nutrition_from_foods(
        ["200g chicken breast", "100g greek yogurt", "mystery spice blend"],
        servings=2,
    )
    assert result["source"] == "food_db"
    assert result["totals"]["protein"] > 50
    assert "mystery spice blend" in result["unknown_ingredients"]
    assert result["per_serving"]["protein"] == round(result["totals"]["protein"] / 2, 1)


def test_preference_context_includes_nutrition_goals():
    ctx = format_preference_context(
        {
            "dietaryRestrictions": ["high-protein"],
            "dailyProteinTarget": 150,
            "dailyCalorieTarget": 2100,
        }
    )
    assert "Nutrition goals" in ctx
    assert "150" in ctx
    assert "2100" in ctx


def test_retrieve_foods_excludes_adult_veto():
    foods = retrieve_foods_for_ai(
        {"dislikedIngredients": ["mushrooms", "olive oil"]},
        limit=40,
        seed="veto-adult",
    )
    names = {f["name"] for f in foods}
    assert "mushroom" not in names
    assert "olive oil" not in names


def test_retrieve_foods_excludes_kid_veto_when_kid_friendly():
    from utils.food_db import _active_veto_set

    on = _active_veto_set(
        {
            "hasChildren": True,
            "kidFriendlyMeals": True,
            "dislikedIngredients": ["liver"],
            "kidVetoIngredients": ["tofu"],
        }
    )
    assert "liver" in on
    assert "tofu" in on

    off = _active_veto_set(
        {
            "hasChildren": True,
            "kidFriendlyMeals": False,
            "dislikedIngredients": ["liver"],
            "kidVetoIngredients": ["tofu"],
        }
    )
    assert "liver" in off
    assert "tofu" not in off

    foods = retrieve_foods_for_ai(
        {
            "hasChildren": True,
            "kidFriendlyMeals": True,
            "kidVetoIngredients": ["tofu"],
        },
        query="tofu",
        limit=20,
        seed="veto-kid",
    )
    assert "tofu" not in {f["name"] for f in foods}
