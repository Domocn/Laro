"""Region-aware food lookups: UK (default) vs US, and both carb figures on every entry.

UK: UK supermarket labels -> CoFID -> curated; ``carbs`` is available carbohydrate.
US: USDA FoodData Central first; ``carbs_total`` is total carbohydrate incl. fibre.
"""
import pytest

from services.line_macros import resolve_line_from_db
from utils import food_db
from utils.food_db import FOOD_DATABASE, NUTRITION_PER_100G, find_food, normalize_region

FOODS = ["chia seeds", "almonds", "white bread", "firm tofu"]


@pytest.mark.parametrize("food", FOODS)
@pytest.mark.parametrize("region", ["uk", "us"])
def test_every_entry_carries_both_carb_figures(food, region):
    name, entry = find_food(food, region=region)
    assert "carbs" in entry and "carbs_total" in entry, (food, region)
    assert entry["carbs_total"] >= entry["carbs"]
    fibre = float(entry.get("fiber") or 0)
    assert abs(entry["carbs_total"] - (entry["carbs"] + fibre)) <= 0.2, (food, region, entry)


def test_default_region_is_uk():
    assert find_food("almonds") == find_food("almonds", region="uk")
    assert normalize_region(None) == "uk" and normalize_region("GB") == "uk"
    assert normalize_region("US") == "us" and normalize_region("en-US") == "us"


@pytest.mark.parametrize("food", FOODS)
def test_uk_never_uses_usda_and_us_prefers_it(food):
    _n, uk = find_food(food, region="uk")
    _n, us = find_food(food, region="us")
    assert not str(uk["source"]).startswith("usda"), (food, uk["source"])
    assert str(us["source"]).startswith("usda"), (food, us["source"])


def test_chia_seeds_uk_vs_us_carbs():
    _n, uk = find_food("chia seeds", region="uk")
    assert uk["carbs"] < 12              # UK label ~7.8 g available carbohydrate
    assert uk["carbs_total"] > 35        # same food, US total incl. ~34 g fibre
    _n, us = find_food("chia seeds", region="us")
    assert us["carbs_total"] > 35


def test_almonds_uk_vs_us():
    _n, uk = find_food("almonds", region="uk")
    _n, us = find_food("almonds", region="us")
    assert uk["source"] == "cofid" and uk["carbs"] < 10
    assert us["carbs_total"] > 15


def test_white_bread_uk_vs_us():
    _n, uk = find_food("white bread", region="uk")
    _n, us = find_food("white bread", region="us")
    assert uk["source"] == "cofid" and 220 <= uk["calories"] <= 260
    assert "pita" not in us["description"].lower() and 240 <= us["calories"] <= 290


def test_firm_tofu_uk_label_vs_usda():
    _n, uk = find_food("firm tofu", region="uk")
    _n, us = find_food("firm tofu", region="us")
    assert uk["source"] == "uk_labels" and 110 <= uk["calories"] <= 140
    assert us["source"] == "usda_sr" and us["calories"] == 144


def test_us_region_skips_uk_labels():
    _n, us = find_food("houmous", region="us")
    assert us["source"] != "uk_labels"


def test_curated_table_has_both_bases():
    # US-sourced curated carbs were total carbohydrate; they are now available carbs + a total.
    chia = FOOD_DATABASE["chia seeds"]
    assert chia["carbs_total"] == 42 and chia["carbs"] == 8.0
    weet = FOOD_DATABASE["weetabix"]  # already a UK label: carbs kept, total = carbs + fibre
    assert weet["carbs"] == 69 and weet["carbs_total"] == 79
    assert all("carbs_total" in v for v in NUTRITION_PER_100G.values())


def test_curated_overrides_have_reasons():
    for overrides in (food_db._CURATED_OVERRIDES, food_db._US_CURATED_OVERRIDES):
        for name, reason in overrides.items():
            assert name in FOOD_DATABASE, name
            assert reason.strip()


@pytest.mark.parametrize("region", ["uk", "us"])
def test_line_macros_carry_c_total(region):
    hit = resolve_line_from_db("30 g chia seeds", region=region)
    assert hit is not None and hit["src"] == "db"
    assert hit["c_total"] >= hit["c"]
    if region == "uk":
        assert hit["c"] <= 3 and hit["c_total"] >= 11   # 30 g: ~2 g available, ~13 g total


def test_zero_lines_have_zero_c_total():
    assert resolve_line_from_db("1 tsp salt")["c_total"] == 0


def test_stored_badges_keep_c_total_and_stay_tolerant():
    from services.version_macros import stored_badge
    from utils.recipe_fields import normalize_ingredient_macros

    out = normalize_ingredient_macros([
        {"p": 5, "c": 2, "c_total": 13, "f": 9, "cal": 146, "src": "db", "food": "Chia seeds", "g": 30},
        {"p": 1, "c": 2, "f": 3, "cal": 40, "src": "ai"},              # AI / old rows: no c_total
        {"p": 1, "c": 2, "f": 3, "cal": 40, "c_total": "lots"},        # junk is dropped, not fatal
        {"p": 1, "c": 2, "f": 3, "cal": 40, "c_total": -4},
    ])
    assert out[0]["c_total"] == 13 and "c_total" not in out[1]
    assert "c_total" not in out[2] and "c_total" not in out[3]
    assert stored_badge({"p": 5, "c": 2, "c_total": 13, "f": 9, "cal": 146})["c_total"] == 13
    assert "c_total" not in stored_badge({"p": 5, "c": 2, "f": 9, "cal": 146})
    assert "c_total" not in stored_badge({"p": 5, "c": 2, "f": 9, "cal": 146, "c_total": "lots"})
