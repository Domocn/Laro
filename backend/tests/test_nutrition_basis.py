"""Per-100 g nutrition for batch / base recipes: weights, bake-loss yield, auto basis detection,
the user's override and the response fields."""
import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.nutrition_basis import (  # noqa: E402
    BAKE_YIELD,
    attach_weight_fields,
    auto_basis,
    bake_kind,
    bake_yield,
    effective_basis,
    weight_info,
)


# --- auto basis -------------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Dairy-Free Butter",
    "Peanut Butter",
    "Basil Pesto",
    "Rosemary and Garlic Butter",
    "Shokupan (Japanese Rice Bread)",
    "Homemade Oat Milk",
    "Almond milk",
    "Lemon Curd",
    "Strawberry Jam",
    "Vegetable Stock",
    "Bone Broth",
    "Gluten-Free Flour Blend",
    "Cajun Spice Mix",
    "Taco Seasoning",
    "Thai Green Curry Paste",
    "Maple Pecan Granola",
    "Crumble Topping",
    "Cream Cheese Frosting",
    "Mango Chutney",
    "Caesar Dressing",
    "Vegan Mayo",
    "Simple Syrup",
    "Chocolate Hazelnut Spread",
    "Marinara Sauce",
    "Rosemary Focaccia",
    "Brioche",
    "Classic Sourdough",
    "Seeded Loaf",
    "Soft Dinner Rolls",
    "Burger Buns",
    "Banana Bread",
    "Basil Pesto (vegan)",
])
def test_batch_items_default_to_per_100g(title):
    assert auto_basis(title) == "100g"


@pytest.mark.parametrize("title", [
    "Pesto Pasta",
    "Butter Chicken and Tofu Meatball Curry",
    "Garlic Butter Tofu",
    "Bread with herbed olive oil",
    "Breadcrumbs",
    "Homemade breadcrumbs",
    "Bread and Butter Pudding",
    "Chicken in Black Bean Sauce",
    "Spaghetti with Tomato Sauce",
    "Salmon with Lemon Butter",
    "Spring Rolls",
    "Sausage Rolls",
    "Butter Beans on Toast",
    "Peanut Butter Cookies",
    "Chocolate Fudge Cake",
    "Golden Milk Latte",
    "Mushroom Stroganoff",
    "",
])
def test_dishes_stay_per_serving(title):
    assert auto_basis(title) == "serving"


def test_sauce_category_counts_unless_the_title_is_a_dish():
    assert auto_basis("Nan's Gravy", "Sauce") == "100g"
    assert auto_basis("Tofu with Gravy", "Sauce") == "serving"
    assert auto_basis("Nan's Gravy", "Dinner") == "serving"


def test_override_wins_over_auto():
    pesto = {"title": "Basil Pesto"}
    assert effective_basis(pesto, None) == "100g"
    assert effective_basis(pesto, {"nutrition_basis": "serving"}) == "serving"
    assert effective_basis({"title": "Pesto Pasta"}, {"nutrition_basis": "100g"}) == "100g"
    assert effective_basis({"title": "Pesto Pasta"}, {"nutrition_basis": "junk"}) == "serving"


# --- bake-loss yield ----------------------------------------------------------------------------

def test_bake_yield_table():
    assert BAKE_YIELD == {"bread": 0.88, "cake": 0.90}
    assert bake_kind("Shokupan (Japanese Rice Bread)") == "bread"
    assert bake_yield("Rosemary Focaccia") == 0.88
    assert bake_yield("Chocolate Fudge Cake") == 0.90
    assert bake_yield("Double Chocolate Brownies") == 0.90
    assert bake_yield("Blueberry Muffins") == 0.90
    assert bake_yield("Millionaire's Slice") == 0.90
    for not_baked in ("Basil Pesto", "Fish Cakes", "No-Bake Cheesecake", "Bread with herbed olive oil",
                      "Breadcrumbs", "Pesto Pasta"):
        assert bake_yield(not_baked) is None, not_baked


# --- weights / per-100 g maths ------------------------------------------------------------------

def _b(cal, p, c, f, g=None, src="db"):
    out = {"cal": cal, "p": p, "c": c, "f": f, "src": src}
    if g is not None:
        out["g"] = g
        out["g_src"] = src
    return out


def test_per_100g_is_totals_over_total_weight():
    # Dairy-free butter: 200 g coconut oil + 100 g olive oil + 100 ml oat milk (water counts) + salt.
    badges = [_b(1724, 0, 0, 200, 200), _b(884, 0, 0, 100, 100), _b(46, 1, 7, 2, 100),
              _b(0, 0, 0, 0)]  # "pinch of salt": no grams, no calories -> weighs ~0
    info = weight_info(badges)
    assert info["total_grams"] == 400
    assert "raw_grams" not in info
    per = info["nutrition_per_100g"]
    assert per["calories"] == round((1724 + 884 + 46) * 100 / 400)  # 664
    assert per["fat"] == round(302 * 100 / 400, 1)  # 75.5
    assert per["protein"] == 0.2 and per["carbs"] == 1.8


def test_ai_grams_count_and_missing_grams_mean_unknown():
    with_ai = [_b(400, 10, 80, 2, 100), _b(120, 0, 0, 14, 15, src="ai")]
    assert weight_info(with_ai)["total_grams"] == 115
    missing = [_b(400, 10, 80, 2, 100), _b(120, 0, 0, 14, src="ai")]  # calories but no weight yet
    assert weight_info(missing) is None
    assert weight_info(None) is None
    assert weight_info([]) is None


def test_bake_loss_shrinks_the_weight_not_the_macros():
    # Shokupan, servings=1: ~2,500 kcal of dough weighing 1,000 g raw -> 880 g loaf.
    badges = [_b(2275, 63, 470, 8, 625), _b(250, 9, 30, 10, 375)]
    info = weight_info(badges, bake_yield("Shokupan (Japanese Rice Bread)"))
    assert info["raw_grams"] == 1000 and info["total_grams"] == 880
    assert info["nutrition_per_100g"]["calories"] == round(2525 * 100 / 880)  # 287


# --- response fields ----------------------------------------------------------------------------

def test_attach_weight_fields_for_original_versions_and_low_fodmap():
    recipe = {"title": "Basil Pesto", "category": "Sauce"}
    v_badges = [_b(500, 10, 5, 50, 100), _b(0, 0, 0, 0, 50)]
    adaptations = {
        "nutrition_basis": "serving",  # the user's override, kept as stored
        "low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}], "notes": ""},
        "low_fodmap_macros": {"nutrition": {"calories": 1}, "ingredient_macros": [_b(900, 0, 0, 100, 100)]},
        "versions": [{"name": "Walnut", "ingredients": [{"name": "walnuts", "amount": "100", "unit": "g"}],
                      "nutrition": {"calories": 250}, "ingredient_macros": v_badges,
                      "low_fodmap_macros": {"nutrition": {"calories": 2}, "ingredient_macros": [_b(1, 0, 0, 0)]}}],
    }
    out = attach_weight_fields(recipe, adaptations, [_b(600, 6, 6, 60, 200)])
    assert out["nutrition_basis"] == "serving" and out["nutrition_basis_auto"] == "100g"
    assert out["total_grams"] == 200 and out["nutrition_per_100g"]["calories"] == 300
    assert out["low_fodmap_macros"]["total_grams"] == 100
    v = out["versions"][0]
    assert v["total_grams"] == 150 and v["nutrition_per_100g"]["calories"] == 333
    assert "total_grams" not in v["low_fodmap_macros"]  # a line without grams: unknown
    assert "bake_yield" not in out
    assert adaptations["versions"][0].get("total_grams") is None  # input not mutated


def test_ordinary_recipe_without_weights_gets_nothing_extra():
    assert attach_weight_fields({"title": "Pesto Pasta"}, None, None) is None
    out = attach_weight_fields({"title": "Pesto Pasta"}, None, [_b(400, 10, 80, 2, 100)])
    assert out == {"total_grams": 100, "nutrition_per_100g": {"calories": 400, "protein": 10.0,
                                                              "carbs": 80.0, "fat": 2.0}}


def test_bread_response_has_yield_and_finished_weight():
    out = attach_weight_fields({"title": "Shokupan (Japanese Rice Bread)", "servings": 1}, None,
                               [_b(2275, 63, 470, 8, 625), _b(250, 9, 30, 10, 375)])
    assert out["nutrition_basis_auto"] == "100g" and out["bake_yield"] == 0.88
    assert out["raw_grams"] == 1000 and out["total_grams"] == 880


def test_computed_fields_are_never_stored():
    from utils.recipe_fields import normalize_adaptations

    sent = attach_weight_fields({"title": "Basil Pesto"}, {"nutrition_basis": "100g", "page_notes": ["x"]},
                                [_b(600, 6, 6, 60, 200)])
    stored = normalize_adaptations(sent)
    assert stored == {"page_notes": ["x"], "nutrition_basis": "100g"}
    assert normalize_adaptations({"nutrition_basis": "per kilo"}) is None
    assert normalize_adaptations({"nutrition_basis_auto": "100g", "total_grams": 5}) is None


def test_prepare_recipe_for_response_derives_per_100g_from_stored_badges():
    from utils.recipe_fields import prepare_recipe_for_response

    row = {"id": "r1", "title": "Peanut Butter", "description": "", "servings": 10, "category": "Sauce",
           "ingredients": json.dumps([{"name": "roasted peanuts", "amount": "500", "unit": "g"},
                                      {"name": "salt", "amount": "1", "unit": "pinch"}]),
           "ingredient_macros": json.dumps([_b(2935, 129, 80, 247, 500), _b(0, 0, 0, 0)]),
           "instructions": "[]", "nutrition_calories": 294, "nutrition_protein": 13,
           "nutrition_carbs": 8, "nutrition_fat": 25, "adaptations": None}
    out = prepare_recipe_for_response(row)
    ad = out["adaptations"]
    assert ad["nutrition_basis_auto"] == "100g"
    assert ad["total_grams"] == 500 and ad["nutrition_per_100g"]["calories"] == 587
    assert out["nutrition"]["calories"] == 294  # per serving unchanged (meal plan / shopping)


# --- override persistence through the normal update endpoint ----------------------------------

def test_override_persists_through_put_and_keeps_other_adaptations(monkeypatch):
    import routers.recipes as recipes_router
    from models import RecipeCreate

    existing = {
        "id": "r1", "title": "Basil Pesto", "description": "", "author_id": "u1", "household_id": None,
        "ingredients": [{"name": "basil", "amount": "50", "unit": "g"}], "instructions": ["Blend"],
        "servings": 8, "category": "Sauce", "tags": [], "image_url": "", "prep_time": 5, "cook_time": 0,
        "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00",
        "adaptations": {"page_notes": ["Keeps 5 days"],
                        "low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}], "notes": ""}},
    }

    class Repo:
        def __init__(self):
            self.rows = {"r1": dict(existing)}

        async def find_by_id(self, rid):
            return dict(self.rows[rid]) if rid in self.rows else None

        async def update_recipe(self, rid, data):
            self.rows[rid].update(data)
            return 1

    async def noop(*a, **k):
        return None

    repo = Repo()
    monkeypatch.setattr(recipes_router, "recipe_repository", repo)
    monkeypatch.setattr(recipes_router, "require_recipe_edit", lambda user, recipe: None)
    monkeypatch.setattr(recipes_router, "log_action", noop)
    monkeypatch.setattr(recipes_router.ws_manager, "broadcast_to_household_or_user", noop)
    monkeypatch.setattr(recipes_router, "schedule_recipe_macros", lambda *a, **k: None)

    # The page sends the recipe back as it got it (response adaptations incl. derived fields).
    shown = recipes_router.prepare_recipe_for_response(existing)
    body = RecipeCreate(**{**{k: shown[k] for k in ("title", "description", "ingredients", "instructions",
                                                     "servings", "category", "tags", "image_url")},
                           "adaptations": {**(shown["adaptations"] or {}), "nutrition_basis": "serving"}})
    out = asyncio.run(recipes_router.update_recipe("r1", body, request=None, user={"id": "u1"}))
    stored = repo.rows["r1"]["adaptations"]
    assert stored["nutrition_basis"] == "serving"
    assert stored["page_notes"] == ["Keeps 5 days"] and stored["low_fodmap"]["swaps"]
    assert "nutrition_basis_auto" not in stored and "total_grams" not in stored
    assert out.adaptations["nutrition_basis"] == "serving"
    assert out.adaptations["nutrition_basis_auto"] == "100g"


def test_ai_lines_without_grams_leave_the_recipe_incomplete_for_the_background_job():
    from services.version_macros import compute_recipe_macros

    recipe = {"id": "r1", "title": "Basil Pesto", "servings": 4,
              "ingredients": [{"name": "drizzle of olive oil", "amount": "", "unit": ""}]}
    no_grams = compute_recipe_macros(recipe, lambda ing: {"p": 0, "c": 0, "f": 14, "cal": 120, "src": "ai"})
    assert no_grams["complete"] is False and no_grams["fields"]["nutrition_calories"] == 30
    weighed = compute_recipe_macros(recipe, lambda ing: {"p": 0, "c": 0, "f": 14, "cal": 120, "src": "ai",
                                                         "g": 14, "g_src": "ai"})
    assert weighed["complete"] is True
    assert weighed["fields"]["ingredient_macros"][0]["g"] == 14
