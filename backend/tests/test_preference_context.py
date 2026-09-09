"""Unit tests for preference context used in AI recipe-idea prompts."""
from datetime import date

from utils.preference_context import (
    adult_veto_ingredients,
    format_lifestyle_context,
    format_preference_context,
    format_veto_exclusion_lines,
    kid_veto_ingredients,
    merge_preferences_into_free_text,
    normalize_preferred_recipe_sites,
    normalize_recipe_site,
    normalize_wfh_days,
    wants_family_one_meal,
    wants_kid_friendly,
    wfh_day_indices_for_plan,
)


def test_normalize_recipe_site_strips_scheme_and_www():
    assert normalize_recipe_site("https://www.BBCGoodFood.com/recipes/foo") == "bbcgoodfood.com"
    assert normalize_recipe_site("nytimes.com") == "nytimes.com"
    assert normalize_recipe_site("not a domain") is None
    assert normalize_recipe_site("") is None


def test_normalize_preferred_recipe_sites_dedupes_and_caps():
    sites = normalize_preferred_recipe_sites(
        [
            "https://www.bbcgoodfood.com/x",
            "bbcgoodfood.com",
            "https://www.seriouseats.com",
            "",
            "nope",
        ]
    )
    assert sites == ["bbcgoodfood.com", "seriouseats.com"]


def test_format_preference_context_high_protein_and_sites():
    ctx = format_preference_context(
        {
            "dietaryRestrictions": ["high-protein", "gluten-free"],
            "preferredRecipeSites": ["https://www.bbcgoodfood.com"],
            "allergens": ["peanuts"],
        }
    )
    assert "high-protein" in ctx.lower()
    assert "protein-forward" in ctx.lower()
    assert "gluten-free" in ctx
    assert "bbcgoodfood.com" in ctx
    assert "peanuts" in ctx


def test_format_preference_context_empty():
    assert format_preference_context({}) == ""
    assert format_preference_context(None) == ""


def test_merge_preferences_into_free_text():
    merged = merge_preferences_into_free_text(
        "quick weeknight dinners",
        {"dietaryRestrictions": ["high-protein"]},
    )
    assert "quick weeknight dinners" in merged
    assert "high-protein" in merged.lower()

    assert merge_preferences_into_free_text(None, None) == "balanced variety"


def test_normalize_wfh_days_names_and_ints():
    assert normalize_wfh_days(["Monday", "wed", 4, "friday"]) == ["mon", "wed", "fri"]
    assert normalize_wfh_days([0, 1, 1, 6]) == ["mon", "tue", "sun"]
    assert normalize_wfh_days("tue, thu") == ["tue", "thu"]
    assert normalize_wfh_days([]) == []
    assert normalize_wfh_days(None) == []


def test_wfh_day_indices_maps_relative_to_start():
    # 2026-09-07 is a Monday
    prefs = {
        "worksFromHome": True,
        "wfhDays": ["mon", "wed", "fri"],
    }
    idxs = wfh_day_indices_for_plan(prefs, start_date=date(2026, 9, 7), days=7)
    assert idxs == [0, 2, 4]

    # Start on Wednesday → WFH offsets shift
    idxs2 = wfh_day_indices_for_plan(prefs, start_date=date(2026, 9, 9), days=7)
    assert idxs2 == [0, 2, 5]  # wed, fri, mon


def test_wfh_day_indices_requires_works_from_home():
    prefs = {"worksFromHome": False, "wfhDays": ["mon", "tue"]}
    assert wfh_day_indices_for_plan(prefs, start_date=date(2026, 9, 7), days=7) == []


def test_wants_kid_friendly_defaults():
    assert wants_kid_friendly({"hasChildren": True}) is True
    assert wants_kid_friendly({"hasChildren": True, "kidFriendlyMeals": False, "familyOneMeal": False}) is False
    assert wants_kid_friendly({"hasChildren": False, "kidFriendlyMeals": True}) is True
    assert wants_kid_friendly({}) is False


def test_wants_family_one_meal_defaults():
    assert wants_family_one_meal({"hasChildren": True}) is True
    assert wants_family_one_meal({"hasChildren": True, "familyOneMeal": False}) is False
    assert wants_family_one_meal({"hasChildren": False, "familyOneMeal": True}) is True
    assert wants_family_one_meal({}) is False
    # Family one-meal implies kid-friendly
    assert wants_kid_friendly({"hasChildren": True, "kidFriendlyMeals": False, "familyOneMeal": True}) is True


def test_preference_context_includes_kids_wfh_and_targets():
    ctx = format_preference_context(
        {
            "dietaryRestrictions": ["high-protein"],
            "dailyProteinTarget": 160,
            "dailyCalorieTarget": 2300,
            "hasChildren": True,
            "kidFriendlyMeals": True,
            "familyOneMeal": False,
            "worksFromHome": True,
            "wfhDays": ["mon", "wed"],
        },
        start_date=date(2026, 9, 7),
        days=7,
    )
    assert "kid-friendly" in ctx.lower()
    assert "milder" in ctx.lower() or "family" in ctx.lower()
    assert "Works from home" in ctx or "works from home" in ctx.lower()
    assert "WFH lunch days" in ctx
    assert "0, 2" in ctx  # Mon + Wed from Sep 7
    assert "160" in ctx
    assert "2300" in ctx


def test_family_one_meal_in_lifestyle_context():
    text = format_lifestyle_context(
        {
            "hasChildren": True,
            "familyOneMeal": True,
        }
    )
    assert "FAMILY ONE-MEAL" in text
    assert "adult_boost" in text.lower() or "adult" in text.lower()
    assert "ONE shared" in text or "one shared" in text.lower()

    ctx = format_preference_context(
        {
            "hasChildren": True,
            "familyOneMeal": True,
            "kidVetoIngredients": ["broccoli"],
            "dislikedIngredients": ["cilantro"],
        }
    )
    assert "FAMILY ONE-MEAL" in ctx
    assert "broccoli" in ctx
    assert "every slot is a family meal" in ctx.lower() or "FAMILY ONE-MEAL" in ctx



def test_lifestyle_includes_gym_and_dinner_headcount():
    text = format_lifestyle_context(
        {
            "hasGymRoutine": True,
            "gymDays": ["mon", "fri"],
            "dinnerHeadcount": 3,
        },
        start_date=date(2026, 9, 7),
        days=7,
    )
    assert "Gym" in text or "gym" in text.lower()
    assert "higher-protein" in text.lower()
    assert "0, 4" in text  # Mon + Fri
    assert "headcount: 3" in text.lower() or "3 people" in text.lower()


def test_format_lifestyle_context_non_wfh_packable():
    text = format_lifestyle_context(
        {
            "worksFromHome": True,
            "wfhDays": ["tue"],
        },
        start_date=date(2026, 9, 7),  # Mon
        days=3,
    )
    assert "WFH lunch days" in text
    assert "1" in text  # Tuesday = day 1
    assert "non-WFH" in text


def test_adult_veto_hard_exclusion_in_preference_context():
    ctx = format_preference_context(
        {
            "dislikedIngredients": ["cilantro", "mushrooms"],
            "allergens": ["peanuts"],
        }
    )
    assert "HARD EXCLUSION" in ctx
    assert "Adult veto" in ctx
    assert "cilantro" in ctx
    assert "mushrooms" in ctx
    assert "NEVER include" in ctx
    # Allergens labeled as safety, distinct from veto
    assert "Allergens (safety" in ctx
    assert "peanuts" in ctx
    # Soft "Disliked ingredients:" wording must not be the only signal
    assert "Disliked ingredients:" not in ctx


def test_kid_veto_only_when_kid_friendly():
    prefs_kids_on = {
        "hasChildren": True,
        "kidFriendlyMeals": True,
        "familyOneMeal": False,
        "dislikedIngredients": ["liver"],
        "kidVetoIngredients": ["broccoli", "peas"],
    }
    assert adult_veto_ingredients(prefs_kids_on) == ["liver"]
    assert kid_veto_ingredients(prefs_kids_on) == ["broccoli", "peas"]

    lines = format_veto_exclusion_lines(prefs_kids_on)
    assert any("Adult veto" in line and "liver" in line for line in lines)
    assert any("Kid veto" in line and "broccoli" in line for line in lines)

    prefs_kids_off = {
        "hasChildren": True,
        "kidFriendlyMeals": False,
        "familyOneMeal": False,
        "kidVetoIngredients": ["broccoli"],
        "dislikedIngredients": ["olives"],
    }
    assert kid_veto_ingredients(prefs_kids_off) == []
    ctx_off = format_preference_context(prefs_kids_off)
    assert "Kid veto" not in ctx_off
    assert "olives" in ctx_off
    assert "Adult veto" in ctx_off


def test_merge_includes_adult_veto_hard_exclusion():
    merged = merge_preferences_into_free_text(
        "high protein week",
        {"dislikedIngredients": ["anchovies"]},
    )
    assert "high protein week" in merged
    assert "HARD EXCLUSION" in merged
    assert "anchovies" in merged
    assert "Adult veto" in merged
