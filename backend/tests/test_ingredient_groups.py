"""Ingredient sections ("For the sauce"): the ``group`` field, splitting legacy "Sauce: tahini"
name prefixes, importer output, macros on clean names, old confirmations / signatures still
matching, shopping names and the backfill script."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Ingredient, RecipeResponse  # noqa: E402
from utils.ingredient_groups import legacy_name, split_ingredient_group, with_group  # noqa: E402
from utils.recipe_fields import normalize_adaptations, normalize_ingredient, prepare_recipe_for_response  # noqa: E402


# --- normaliser --------------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Basil Pesto: almonds or cashews", ("Basil Pesto", "almonds or cashews")),
    ("Sauce: 2 tbsp tahini", ("Sauce", "2 tbsp tahini")),
    ("For the topping: flaked almonds", ("For the topping", "flaked almonds")),
    ("almonds", ("", "almonds")),
    ("Note:no space", ("", "Note:no space")),
    ("Step 2: something", ("", "Step 2: something")),  # digits are never a heading
    ("1: flour", ("", "1: flour")),
    ("A: b", ("", "A: b")),  # heading needs 2+ characters
    ("", ("", "")),
    (None, ("", "")),
])
def test_split_matches_the_web_rule(name, expected):
    assert split_ingredient_group(name) == expected


def test_normalize_ingredient_splits_legacy_prefix():
    assert normalize_ingredient({"name": "Basil Pesto: almonds or cashews", "amount": "75", "unit": "g"}) == {
        "name": "almonds or cashews", "amount": "75", "unit": "g", "group": "Basil Pesto",
    }
    assert normalize_ingredient("Dressing: lemon juice") == {
        "name": "lemon juice", "amount": "", "unit": "", "group": "Dressing",
    }


def test_explicit_group_wins_and_repeated_prefix_is_dropped():
    assert normalize_ingredient({"name": "Sauce: tahini", "group": "sauce"})["name"] == "tahini"
    # A different prefix is part of the name when the line already has a section.
    out = normalize_ingredient({"name": "Note: to taste", "group": "Sauce"})
    assert out["group"] == "Sauce" and out["name"] == "Note: to taste"
    assert normalize_ingredient({"name": "tahini", "section": "Sauce:"})["group"] == "Sauce"


def test_ungrouped_lines_keep_their_old_shape():
    assert normalize_ingredient({"name": "flour", "amount": "1", "unit": "cup", "group": ""}) == {
        "name": "flour", "amount": "1", "unit": "cup",
    }


def test_with_group_and_legacy_name():
    ing = with_group({"name": "Basil Pesto: almonds", "amount": "75", "unit": "g", "group": ""})
    assert ing == {"name": "almonds", "amount": "75", "unit": "g", "group": "Basil Pesto"}
    assert legacy_name(ing) == "Basil Pesto: almonds"
    assert legacy_name({"name": "flour"}) == "flour"


# --- model round trip --------------------------------------------------------------------------

def test_model_round_trip_and_backward_compatibility():
    assert Ingredient(name="flour").group == ""
    assert Ingredient(name="flour", group=None).group == ""
    assert Ingredient(**{"name": "tahini", "amount": "2", "unit": "tbsp", "group": "Sauce"}).model_dump() == {
        "name": "tahini", "amount": "2", "unit": "tbsp", "group": "Sauce",
    }


def _row(**extra):
    row = {
        "id": "r1", "title": "Pesto pasta", "description": "", "instructions": [], "prep_time": 0,
        "cook_time": 0, "servings": 2, "category": "Dinner", "tags": [], "image_url": "",
        "author_id": "u1", "household_id": "u1", "created_at": "2026-01-01", "updated_at": "2026-01-01",
        "ingredients": json.dumps([
            {"name": "pasta", "amount": "200", "unit": "g"},
            {"name": "Basil Pesto: almonds or cashews", "amount": "75", "unit": "g"},
        ]),
    }
    row.update(extra)
    return row


def test_response_returns_clean_names_and_groups():
    shaped = prepare_recipe_for_response(_row(), estimate_missing_nutrition=False)
    out = RecipeResponse(**shaped).model_dump()
    assert out["ingredients"] == [
        {"name": "pasta", "amount": "200", "unit": "g", "group": ""},
        {"name": "almonds or cashews", "amount": "75", "unit": "g", "group": "Basil Pesto"},
    ]


def test_version_ingredients_and_swaps_are_split():
    adaptations = normalize_adaptations({
        "versions": [{"name": "Vegan", "ingredients": [{"name": "Sauce: tahini", "amount": "2", "unit": "tbsp"}]}],
        "low_fodmap": {"swaps": [{"from": "Sauce: garlic", "to": "garlic-infused oil"}]},
    })
    assert adaptations["versions"][0]["ingredients"] == [
        {"name": "tahini", "amount": "2", "unit": "tbsp", "group": "Sauce"},
    ]
    assert adaptations["low_fodmap"]["swaps"] == [{"from": "garlic", "to": "garlic-infused oil"}]


# --- importer ----------------------------------------------------------------------------------

def test_pdf_payload_emits_group_not_prefix():
    from services.recipe_pdf_import import parse_llm_recipes_payload

    recipes = parse_llm_recipes_payload({"recipes": [{
        "title": "Pesto Pasta",
        "ingredients": [
            {"name": "pasta", "amount": "200", "unit": "g"},
            {"name": "Basil Pesto: almonds or cashews", "amount": "75", "unit": "g"},
            {"name": "basil", "amount": "1", "unit": "bunch", "group": "Basil Pesto"},
        ],
        "instructions": ["Cook the pasta."],
    }]})
    ings = recipes[0]["ingredients"]
    assert ings[0] == {"name": "pasta", "amount": "200", "unit": "g"}
    assert ings[1] == {"name": "almonds or cashews", "amount": "75", "unit": "g", "group": "Basil Pesto"}
    assert ings[2]["group"] == "Basil Pesto" and ings[2]["name"] == "basil"


def test_prompts_ask_for_group():
    from routers.prompts import DEFAULT_PROMPTS
    from services.recipe_pdf_import import MULTI_RECIPE_IMAGES_PROMPT, MULTI_RECIPE_PDF_PROMPT

    for prompt in (MULTI_RECIPE_PDF_PROMPT, MULTI_RECIPE_IMAGES_PROMPT, DEFAULT_PROMPTS["recipe_extraction"]):
        assert '"group": "Sauce"' in prompt
    assert '{"name": "Sauce: tahini"' not in MULTI_RECIPE_PDF_PROMPT


def test_merging_fragments_keeps_same_food_in_different_sections():
    from services.recipe_pdf_import import _absorb

    base = {"title": "Buns", "ingredients": [{"name": "salt", "group": "Dough"}], "instructions": []}
    extra = {"title": "Buns", "ingredients": [{"name": "salt", "group": "Filling"}, {"name": "salt", "group": "Dough"}],
             "instructions": []}
    merged = _absorb(base, extra)
    assert [i["group"] for i in merged["ingredients"]] == ["Dough", "Filling"]


# --- macros ------------------------------------------------------------------------------------

def test_food_matching_uses_the_clean_name():
    from services.line_macros import ingredient_line, resolve_line_from_db

    grouped = normalize_ingredient({"name": "Basil Pesto: almonds", "amount": "75", "unit": "g"})
    assert ingredient_line(grouped) == "75 g almonds"
    plain = resolve_line_from_db("75 g almonds", _cache=False)
    assert plain is not None
    assert resolve_line_from_db(ingredient_line(grouped), _cache=False) == plain


def test_line_key_ignores_sections():
    from services.version_macros import line_key

    assert line_key({"name": "Basil Pesto: almonds", "amount": "75", "unit": "g"}) == \
        line_key({"name": "almonds", "amount": "75", "unit": "g", "group": "Pesto"}) == "75|g|almonds"


def test_signature_unchanged_when_prefix_becomes_group():
    from services.version_macros import _list_sig

    legacy = [{"name": "Basil Pesto: almonds", "amount": "75", "unit": "g"}]
    grouped = [{"name": "almonds", "amount": "75", "unit": "g", "group": "Basil Pesto"}]
    assert _list_sig(["v", legacy, 2]) == _list_sig(["v", grouped, 2])


def _confirmed_recipe():
    from services.confirmed_lines import confirm_key

    entry = {"p": 10, "c": 5, "f": 30, "cal": 350, "source": "user", "confirmed_at": "2026-01-01T00:00:00+00:00"}
    return {
        "id": "r1",
        "servings": 1,
        "ingredients": [{"name": "Basil Pesto: almonds", "amount": "75", "unit": "g"}],
        # Checked before sections existed: keyed by the prefixed line.
        "adaptations": {"confirmed_lines": {confirm_key("75 g Basil Pesto: almonds"): entry}},
    }


def test_old_confirmations_still_apply_to_grouped_lines():
    from services import confirmed_lines as cl
    from services import version_macros as vm

    recipe = _confirmed_recipe()
    payload = cl.check_payload(recipe, lambda _ing: None)
    line = payload["lines"][0]
    assert line["confirmed"] and line["name"] == "almonds" and line["macros"]["cal"] == 350
    assert line["key"] == cl.confirm_key("75 g almonds")
    badges = vm._badges(vm._ingredients(recipe["ingredients"]), lambda _ing: None, vm._confirmed_for(recipe))
    assert badges[0]["cal"] == 350


def test_old_confirmations_survive_a_save_and_a_recheck_replaces_them():
    from services import confirmed_lines as cl

    recipe = _confirmed_recipe()
    kept = cl.prune(normalize_adaptations(recipe["adaptations"]), recipe)
    assert list(kept["confirmed_lines"]) == [cl.confirm_key("75 g Basil Pesto: almonds")]
    merged = cl.merge_lines(recipe["adaptations"], recipe, None, False,
                            [{"index": 0, "p": 1, "c": 1, "f": 1, "cal": 20, "source": "user"}])
    assert list(merged["confirmed_lines"]) == [cl.confirm_key("75 g almonds")]


# --- update / shopping -------------------------------------------------------------------------

def test_update_payload_ingredients_are_split():
    from models import RecipeCreate

    recipe = RecipeCreate(title="x", instructions=[], ingredients=[
        {"name": "Sauce: tahini", "amount": "2", "unit": "tbsp"},
        {"name": "lemon", "amount": "1", "unit": "", "group": "Sauce"},
        {"name": "pasta", "amount": "200", "unit": "g"},
    ])
    out = [with_group(i.model_dump()) for i in recipe.ingredients]
    assert out == [
        {"name": "tahini", "amount": "2", "unit": "tbsp", "group": "Sauce"},
        {"name": "lemon", "amount": "1", "unit": "", "group": "Sauce"},
        {"name": "pasta", "amount": "200", "unit": "g"},
    ]


def test_shopping_list_merges_on_the_clean_name():
    from routers import shopping_lists

    assert shopping_lists.shopping_name("Basil Pesto: almonds, chopped") == "almonds"
    items = [
        {"name": shopping_lists.shopping_name(n), "amount": a, "unit": "g", "recipe_id": "r1", "recipe_name": "x"}
        for n, a in (("almonds", "50"), ("Basil Pesto: almonds", "75"))
    ]
    merged = shopping_lists.combine_quantities(items)
    assert len(merged) == 1 and merged[0]["name"] == "almonds"


# --- backfill ----------------------------------------------------------------------------------

def test_backfill_splits_lists_swaps_and_rekeys_confirmations():
    from scripts.backfill_ingredient_groups import backfill_recipe
    from services.confirmed_lines import confirm_key

    row = _confirmed_recipe()
    row["ingredients"] = json.dumps(row["ingredients"] + [{"name": "pasta", "amount": "200", "unit": "g"}])
    row["adaptations"] = json.dumps({
        **row["adaptations"],
        "versions": [{"name": "Vegan", "ingredients": [{"name": "Sauce: tahini", "amount": "2", "unit": "tbsp"}]}],
        "low_fodmap": {"swaps": [{"from": "Sauce: garlic", "to": "garlic oil"}]},
    })
    result = backfill_recipe(row)
    assert result["stats"] == {"lines": 1, "version_lines": 1, "swaps": 1, "confirmed": 1}
    assert result["ingredients"] == [
        {"name": "almonds", "amount": "75", "unit": "g", "group": "Basil Pesto"},
        {"name": "pasta", "amount": "200", "unit": "g"},
    ]
    adapt = result["adaptations"]
    assert adapt["versions"][0]["ingredients"][0]["group"] == "Sauce"
    assert adapt["low_fodmap"]["swaps"][0]["from"] == "garlic"
    assert list(adapt["confirmed_lines"]) == [confirm_key("75 g almonds")]


def test_backfill_leaves_clean_recipes_alone():
    from scripts.backfill_ingredient_groups import backfill_recipe

    assert backfill_recipe({"ingredients": json.dumps([{"name": "flour", "amount": "1", "unit": "cup"}]),
                            "adaptations": None}) is None
