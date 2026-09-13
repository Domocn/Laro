"""Tests for adult/kid veto matching and replacement suggestions."""
from utils.veto_replacements import (
    CURATED_SWAPS,
    check_ingredients_for_vetoes,
    match_veto_token,
    suggest_replacements,
)


def test_match_veto_fuzzy_substring_and_plural():
    assert match_veto_token("fresh mushrooms", ["mushroom"]) == "mushroom"
    assert match_veto_token("cilantro leaves", ["cilantro"]) == "cilantro"
    assert match_veto_token("chicken breast", ["mushroom"]) is None
    # Short tokens (<4) only match exact / both-short — avoid "egg" → "eggplant"
    assert match_veto_token("eggplant", ["egg"]) is None
    assert match_veto_token("egg", ["egg"]) == "egg"


def test_adult_hit_with_curated_swap():
    prefs = {"dislikedIngredients": ["mushrooms", "cilantro"]}
    result = check_ingredients_for_vetoes(
        [
            {"name": "chicken breast", "amount": "400", "unit": "g"},
            {"name": "sliced mushrooms", "amount": "200", "unit": "g"},
            {"name": "fresh cilantro", "amount": "1", "unit": "bunch"},
        ],
        prefs,
    )
    assert result["has_hits"] is True
    assert len(result["hits"]) == 2
    lists = {h["list"] for h in result["hits"]}
    assert lists == {"adult"}

    mush = next(r for r in result["replacements"] if "mushroom" in r["ingredient"].lower())
    names = [s["name"].lower() for s in mush["suggestions"]]
    assert any(n in names for n in ("zucchini", "eggplant", "bell pepper"))
    assert all(s.get("source") in ("curated", "food_db") for s in mush["suggestions"])


def test_kid_veto_only_when_kid_friendly_active():
    ingredients = [
        {"name": "broccoli florets", "amount": "2", "unit": "cups"},
        {"name": "rice", "amount": "1", "unit": "cup"},
    ]
    prefs_off = {
        "hasChildren": True,
        "familyOneMeal": False,
        "kidFriendlyMeals": False,
        "kidVetoIngredients": ["broccoli"],
        "dislikedIngredients": [],
    }
    off = check_ingredients_for_vetoes(ingredients, prefs_off)
    assert off["has_hits"] is False

    prefs_on = {
        "hasChildren": True,
        "familyOneMeal": False,
        "kidFriendlyMeals": True,
        "kidVetoIngredients": ["broccoli"],
        "dislikedIngredients": [],
    }
    on = check_ingredients_for_vetoes(ingredients, prefs_on)
    assert on["has_hits"] is True
    assert on["hits"][0]["list"] == "kid"
    assert on["hits"][0]["matched_veto"] == "broccoli"
    suggestions = [s["name"].lower() for s in on["replacements"][0]["suggestions"]]
    assert any("bean" in n or "zucchini" in n or "carrot" in n for n in suggestions)


def test_both_adult_and_kid_lists_reported():
    prefs = {
        "hasChildren": True,
        "kidFriendlyMeals": True,
        "dislikedIngredients": ["olives"],
        "kidVetoIngredients": ["olives", "peas"],
    }
    result = check_ingredients_for_vetoes(
        [{"name": "black olives", "amount": "50", "unit": "g"}],
        prefs,
    )
    assert result["has_hits"]
    hit = result["hits"][0]
    assert "adult" in hit["lists"]
    assert "kid" in hit["lists"]


def test_suggest_replacements_skips_other_vetoes():
    prefs = {
        "dislikedIngredients": ["mushroom", "zucchini"],
    }
    suggestions = suggest_replacements(
        "portobello mushrooms",
        matched_veto="mushroom",
        prefs=prefs,
        limit=5,
    )
    names = [s["name"].lower() for s in suggestions]
    assert "zucchini" not in names
    assert names  # still suggests something else


def test_open_substitutions_for_butter():
    from utils.veto_replacements import suggest_ingredient_substitutions

    result = suggest_ingredient_substitutions("butter", {}, limit=5)
    assert result["ingredient"] == "butter"
    names = [s["name"].lower() for s in result["suggestions"]]
    assert any("oil" in n or "ghee" in n for n in names)


def test_banana_substitutions_use_binder_function():
    """Mashed banana should swap by function (applesauce), not random fruit."""
    from utils.veto_replacements import suggest_ingredient_substitutions

    for name in ("banana", "mashed banana"):
        result = suggest_ingredient_substitutions(name, {}, limit=5)
        names = [s["name"].lower() for s in result["suggestions"]]
        assert "applesauce" in names or "apple sauce" in names, names
        assert "binder" in (result.get("roles") or [])
        # Should not lead with unrelated citrus just because category=fruit
        assert names[0] not in ("lemon", "orange", "blueberry", "strawberry")


def test_curated_map_covers_common_vetoes():
    for key in ("mushroom", "cilantro", "olive", "anchovy", "liver", "broccoli", "butter", "banana"):
        assert key in CURATED_SWAPS
        assert len(CURATED_SWAPS[key]) >= 2


def test_empty_ingredients_no_hits():
    assert check_ingredients_for_vetoes([], {"dislikedIngredients": ["x"]})["has_hits"] is False
    assert check_ingredients_for_vetoes([{"name": "salt"}], {})["has_hits"] is False


def test_string_ingredients_supported():
    result = check_ingredients_for_vetoes(
        ["200g mushrooms", "salt"],
        {"dislikedIngredients": ["mushroom"]},
    )
    # "200g mushrooms" as whole string — normalize may not strip amount, but substring match should hit
    assert result["has_hits"] is True
