"""Unit tests for multi-recipe PDF separation / dedupe."""
from services.recipe_pdf_import import (
    dedupe_recipes,
    normalize_recipe_title,
    parse_llm_recipes_payload,
    split_recipe_text_chunks,
)


SAMPLE_MULTI = """
Recipe 1
Chocolate Cake
Ingredients:
2 cups flour
1 cup sugar
Instructions:
Mix and bake.

Recipe 2
Tomato Soup
Ingredients:
4 tomatoes
1 onion
Instructions:
Simmer until soft.
"""


def test_split_separates_numbered_recipes():
    chunks = split_recipe_text_chunks(SAMPLE_MULTI)
    assert len(chunks) >= 2
    joined = " ".join(chunks).lower()
    assert "chocolate cake" in joined or "flour" in joined
    assert "tomato" in joined or "soup" in joined
    # Non-overlapping: first chunk should not contain second title block fully
    assert chunks[0] != chunks[1]


def test_dedupe_skips_library_and_batch_duplicates():
    recipes = [
        {"title": "Tomato Soup", "ingredients": [], "instructions": ["a"]},
        {"title": "tomato soup", "ingredients": [], "instructions": ["b"]},
        {"title": "New Dish", "ingredients": [], "instructions": ["c"]},
        {"title": "New Dish", "ingredients": [], "instructions": ["d"]},
    ]
    kept, skipped = dedupe_recipes(recipes, {"chili"})
    titles = [r["title"] for r in kept]
    assert titles == ["Tomato Soup", "New Dish"]
    assert any(s["reason"] == "duplicate_in_pdf" for s in skipped)
    kept2, skipped2 = dedupe_recipes(
        [{"title": "Tomato Soup", "ingredients": [], "instructions": ["a"]}],
        {"tomato soup"},
    )
    assert kept2 == []
    assert any(s["reason"] == "already_in_library" for s in skipped2)
    assert all(r.get("needs_review") for r in kept)
    assert all("needs-review" in r.get("tags", []) for r in kept)


def test_parse_llm_payload_array_and_single():
    multi = parse_llm_recipes_payload(
        {"recipes": [{"title": "Alpha Cake", "ingredients": [], "instructions": ["1"]}]}
    )
    assert len(multi) == 1
    single = parse_llm_recipes_payload({"title": "Solo", "ingredients": [], "instructions": ["x"]})
    assert len(single) == 1
    assert normalize_recipe_title("Hello, World!") == "hello world"


FUDGE_PDF = """
Low-and-Slow Coffee Cocoa Protein Fudge
A refined low-and-slow, cold-set version of the brownie/tofu hack — fixes the soggy middle and firms up into proper
fudge
Ingredients
375 g standard chocolate brownie mix
480 g Tofu King Silken Tofu (1 full block)
1 tsp Beanies Easter Cream instant coffee, to taste
2 tbsp cocoa powder, for dusting
Steps
1. Combine the brownie mix and tofu until a batter forms.
2. Bake at 150C.
Notes
Bake time is 40-45 minutes.
"""


def test_wrapped_title_stays_one_recipe():
    chunks = split_recipe_text_chunks(FUDGE_PDF)
    assert len(chunks) == 1
    assert "brownie mix" in chunks[0].lower()
    assert "steps" in chunks[0].lower()


def test_coalesce_title_stub_with_wrap_word_body():
    from services.recipe_pdf_import import coalesce_incomplete_recipes

    recipes = [
        {
            "title": "Low-and-Slow Coffee Cocoa Protein Fudge",
            "ingredients": [],
            "instructions": [],
        },
        {
            "title": "fudge",
            "ingredients": [{"name": "brownie mix", "amount": "375", "unit": "g"}],
            "instructions": ["Bake", "Chill"],
        },
    ]
    kept = coalesce_incomplete_recipes(recipes)
    assert len(kept) == 1
    assert kept[0]["title"] == "Low-and-Slow Coffee Cocoa Protein Fudge"
    assert kept[0]["ingredients"]
    assert kept[0]["instructions"]



def test_merge_section_fragments_folds_generic_and_repeat_titles():
    from services.recipe_pdf_import import merge_section_fragments

    recipes = [
        {"title": "Dairy-Free Milk", "ingredients": [{"name": "oats"}], "instructions": []},
        {"title": "SHAWARMA-STYLE TOFU FRITES WRAP", "ingredients": [{"name": "tofu"}, {"name": "wraps"}], "instructions": ["Press tofu"]},
        {"title": "RECIPE SECTION 11", "ingredients": [], "instructions": ["Bake frites"]},
        {"title": "Shawarma-Style Tofu Wrap (Low FODMAP)", "ingredients": [{"name": "tofu"}, {"name": "garlic oil"}], "instructions": ["Assemble"]},
        {"title": "Chocolate Fudge", "ingredients": [{"name": "cocoa"}], "instructions": ["Set"]},
    ]
    out = merge_section_fragments(recipes)
    assert [r["title"] for r in out] == ["Dairy-Free Milk", "SHAWARMA-STYLE TOFU FRITES WRAP", "Chocolate Fudge"]
    wrap = out[1]
    # The "(Low FODMAP)" split-off becomes the dish's adaptation note, not extra ingredients.
    assert [i["name"] for i in wrap["ingredients"]] == ["tofu", "wraps"]
    assert wrap["instructions"] == ["Press tofu", "Bake frites", "Low FODMAP adaptation: Assemble; tofu; garlic oil"]


def test_merge_section_fragments_folds_steps_only_and_drops_leading_tail():
    from services.recipe_pdf_import import merge_section_fragments

    recipes = [
        {"title": "Wrap Cooking", "ingredients": [], "instructions": ["Flip the wrap"]},
        {"title": "Tofu Katsu and Slaw Wrap", "ingredients": [{"name": "tofu"}], "instructions": ["Slice tofu"]},
        {"title": "Bread the Tofu", "ingredients": [], "instructions": ["Coat in breadcrumbs"]},
        {"title": "Green Goddess Tofu Sandwich", "ingredients": [{"name": "bread"}], "instructions": ["Toast"]},
    ]
    out = merge_section_fragments(recipes)
    assert [r["title"] for r in out] == ["Tofu Katsu and Slaw Wrap", "Green Goddess Tofu Sandwich"]
    assert out[0]["instructions"] == ["Slice tofu", "Coat in breadcrumbs"]


def test_parse_llm_payload_keeps_low_fodmap_swaps():
    from services.recipe_pdf_import import tag_dietary_adaptations

    parsed = parse_llm_recipes_payload({"recipes": [
        {
            "title": "Lentil Wrap",
            "ingredients": [{"name": "garlic"}, {"name": "red lentils"}],
            "instructions": ["Cook", "Low FODMAP adaptation: garlic adaption"],
            "low_fodmap": {
                "swaps": [{"from": "garlic", "to": "garlic-infused oil"}, {"from": "", "to": "x"}],
                "notes": "One wrap is close to a low FODMAP serving.",
            },
        },
        {"title": "Plain Toast", "ingredients": [{"name": "bread"}], "instructions": ["Toast"], "low_fodmap": None},
    ]})
    assert parsed[0]["adaptations"] == {"low_fodmap": {
        "swaps": [{"from": "garlic", "to": "garlic-infused oil"}],
        "notes": "One wrap is close to a low FODMAP serving.",
    }}
    assert parsed[1]["adaptations"] is None
    tagged = tag_dietary_adaptations(parsed)
    assert "low-fodmap-option" in tagged[0]["tags"]
    assert "low-fodmap-option" not in tagged[1]["tags"]
    # The original note stays as the last instruction too.
    assert tagged[0]["instructions"][-1].startswith("Low FODMAP adaptation:")


def test_merge_section_fragments_carries_split_off_low_fodmap_swaps():
    from services.recipe_pdf_import import merge_section_fragments

    swaps = {"low_fodmap": {"swaps": [{"from": "onion", "to": "spring onion greens"}], "notes": ""}}
    out = merge_section_fragments([
        {"title": "Tofu Curry", "ingredients": [{"name": "onion"}], "instructions": ["Fry"]},
        {"title": "Tofu Curry (Low FODMAP)", "ingredients": [], "instructions": ["Use spring onion greens"], "adaptations": swaps},
    ])
    assert len(out) == 1
    assert out[0]["adaptations"] == swaps


def test_prompt_mentions_standard_swaps():
    from services.recipe_pdf_import import MULTI_RECIPE_PDF_PROMPT

    assert '"low_fodmap"' in MULTI_RECIPE_PDF_PROMPT
    assert "garlic-infused oil" in MULTI_RECIPE_PDF_PROMPT
    assert "spring onions or leek" in MULTI_RECIPE_PDF_PROMPT


def test_normalize_adaptations_round_trip():
    import json
    from utils.recipe_fields import normalize_adaptations, prepare_recipe_for_response

    value = {"low_fodmap": {"swaps": [{"from": " garlic ", "to": "garlic-infused oil"}], "notes": " Check lentils "}}
    clean = normalize_adaptations(value)
    assert clean == {"low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}], "notes": "Check lentils"}}
    assert normalize_adaptations(json.dumps(value)) == clean
    assert normalize_adaptations({"low_fodmap": {"swaps": [], "notes": "  "}}) is None
    assert normalize_adaptations("not json") is None
    shaped = prepare_recipe_for_response(
        {"id": "r1", "title": "T", "ingredients": "[]", "instructions": "[]", "adaptations": json.dumps(value)},
        estimate_missing_nutrition=False,
    )
    assert shaped["adaptations"] == clean



PESTO_VERSIONS = [
    {"name": "Salted Tomato and Feta", "ingredients": [{"name": "pasta"}, {"name": "feta", "amount": "100", "unit": "g"}],
     "instructions": ["Boil pasta", "Crumble feta"], "notes": "Use ripe tomatoes"},
    {"name": "Pomegranate", "ingredients": ["pasta", "pomegranate seeds"], "instructions": ["Boil pasta", "Scatter seeds"]},
]


def test_parse_payload_keeps_versions():
    out = parse_llm_recipes_payload({"recipes": [{
        "title": "Pesto Pasta",
        "ingredients": [{"name": "pasta"}, {"name": "chicken"}],
        "instructions": ["Boil pasta", "Fry chicken"],
        "low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}]},
        "versions": PESTO_VERSIONS,
    }]})
    versions = out[0]["adaptations"]["versions"]
    assert [v["name"] for v in versions] == ["Salted Tomato and Feta", "Pomegranate"]
    assert versions[0]["ingredients"][1] == {"name": "feta", "amount": "100", "unit": "g"}
    assert versions[0]["notes"] == "Use ripe tomatoes"
    assert versions[1]["ingredients"][1]["name"] == "pomegranate seeds"
    assert out[0]["adaptations"]["low_fodmap"]["swaps"][0]["from"] == "garlic"


def test_normalize_versions_validates_and_caps():
    from utils.recipe_fields import MAX_RECIPE_VERSIONS, normalize_adaptations

    raw = {"versions": [
        {"name": "  Chocolate   Orange ", "ingredients": [{"name": "flour"}], "instructions": ["Bake"]},
        {"name": "chocolate orange", "ingredients": [{"name": "dupe"}], "instructions": []},  # repeated name
        {"name": "", "ingredients": [{"name": "x"}]},  # unnamed
        {"name": "Empty", "ingredients": [], "instructions": ["  "]},  # nothing in it
        {"name": "Original", "ingredients": [{"name": "x"}]},  # clashes with the base
        "junk",
    ]}
    clean = normalize_adaptations(raw)
    assert clean == {"versions": [
        {"name": "Chocolate Orange", "ingredients": [{"name": "flour", "amount": "", "unit": ""}], "instructions": ["Bake"]},
    ]}
    many = {"versions": [{"name": f"V{i}", "instructions": ["Cook"]} for i in range(25)]}
    assert len(normalize_adaptations(many)["versions"]) == MAX_RECIPE_VERSIONS
    assert normalize_adaptations({"versions": []}) is None


def test_fold_dash_titled_versions_into_one_recipe():
    from services.recipe_pdf_import import fold_recipe_versions

    out = fold_recipe_versions([
        {"title": "Pesto Pasta — Chicken Schnitzel", "description": "", "ingredients": [{"name": "chicken"}], "instructions": ["Fry"]},
        {"title": "Pesto Pasta – Salted Tomato and Feta", "description": "Summery", "ingredients": [{"name": "feta"}], "instructions": ["Crumble"]},
        {"title": "Pesto Pasta - Pomegranate", "ingredients": [{"name": "pomegranate"}], "instructions": ["Scatter"]},
        {"title": "Stir-Fry Noodles", "ingredients": [{"name": "noodles"}], "instructions": ["Fry"]},
    ])
    assert [r["title"] for r in out] == ["Pesto Pasta", "Stir-Fry Noodles"]
    pesto = out[0]
    assert pesto["ingredients"] == [{"name": "chicken"}]
    assert "Chicken Schnitzel" in pesto["description"]
    versions = pesto["adaptations"]["versions"]
    assert [v["name"] for v in versions] == ["Salted Tomato and Feta", "Pomegranate"]
    assert versions[0]["notes"] == "Summery"
    assert versions[1]["instructions"] == ["Scatter"]


def test_fold_uses_plain_title_as_original_and_leaves_singles_alone():
    from services.recipe_pdf_import import fold_recipe_versions

    out = fold_recipe_versions([
        {"title": "Hot Cross Buns", "ingredients": [{"name": "flour"}, {"name": "raisins"}], "instructions": ["Bake"]},
        {"title": "Hot Cross Buns — Chocolate Orange", "ingredients": [{"name": "flour"}, {"name": "chocolate"}], "instructions": ["Bake"]},
        {"title": "Lemon Cake — Glazed", "ingredients": [{"name": "lemon"}], "instructions": ["Bake"]},
        {"title": "Cinnamon Buns", "ingredients": [{"name": "bun dough"}], "instructions": ["Roll"]},
        {"title": "Coffee Scrolls", "ingredients": [{"name": "bun dough"}], "instructions": ["Roll"]},
    ])
    assert [r["title"] for r in out] == ["Hot Cross Buns", "Lemon Cake — Glazed", "Cinnamon Buns", "Coffee Scrolls"]
    assert out[0]["ingredients"][1]["name"] == "raisins"
    assert out[0]["adaptations"]["versions"][0]["name"] == "Chocolate Orange"
    assert not out[1].get("adaptations")


def test_fold_before_section_merge_keeps_versions_apart():
    from services.recipe_pdf_import import fold_recipe_versions, merge_section_fragments

    out = merge_section_fragments(fold_recipe_versions([
        {"title": "Pesto Pasta", "ingredients": [{"name": "pasta"}], "instructions": ["Boil"]},
        {"title": "Pesto Pasta — Pomegranate", "ingredients": [{"name": "pomegranate"}], "instructions": ["Scatter"]},
    ]))
    assert len(out) == 1
    assert out[0]["ingredients"] == [{"name": "pasta"}]
    assert out[0]["adaptations"]["versions"][0]["ingredients"][0]["name"] == "pomegranate"


def test_section_merge_keeps_versions_when_fodmap_note_follows():
    from services.recipe_pdf_import import merge_section_fragments

    versions = {"versions": [{"name": "Pomegranate", "ingredients": [{"name": "pomegranate"}], "instructions": ["Scatter"]}]}
    swaps = {"low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}], "notes": ""}}
    out = merge_section_fragments([
        {"title": "Pesto Pasta", "ingredients": [{"name": "garlic"}], "instructions": ["Boil"], "adaptations": versions},
        {"title": "Pesto Pasta (Low FODMAP)", "ingredients": [], "instructions": ["Use garlic oil"], "adaptations": swaps},
    ])
    assert out[0]["adaptations"]["versions"] == versions["versions"]
    assert out[0]["adaptations"]["low_fodmap"] == swaps["low_fodmap"]


def test_fodmap_backfill_keeps_existing_versions():
    from services.recipe_pdf_import import plan_fodmap_backfill

    versions = [{"name": "Pomegranate", "ingredients": [], "instructions": ["Scatter"]}]
    plan = plan_fodmap_backfill([{
        "id": "r1", "instructions": ["Boil", "Low FODMAP adaptation: garlic adaption"], "adaptations": {"versions": versions},
    }])
    assert plan[0][1]["versions"] == versions
    assert plan[0][1]["low_fodmap"]["swaps"][0]["from"] == "garlic"


def test_prompt_explains_versions_vs_separate_dishes():
    from services.recipe_pdf_import import MULTI_RECIPE_PDF_PROMPT

    assert '"versions"' in MULTI_RECIPE_PDF_PROMPT
    assert "FULL ingredients" in MULTI_RECIPE_PDF_PROMPT
    assert "SEPARATE recipes" in MULTI_RECIPE_PDF_PROMPT
    assert "separate recipes, not versions" in MULTI_RECIPE_PDF_PROMPT


def test_parse_payload_keeps_page_notes():
    out = parse_llm_recipes_payload({"recipes": [{
        "title": "Lentil Wraps",
        "description": "A weeknight favourite.",
        "servings": "Makes 6 wraps",
        "ingredients": [{"name": "Sauce: tahini"}, {"name": "lentils"}],
        "instructions": ["Sauce: Whisk the tahini", "Cook the lentils"],
        "notes": ["Allow 3–6 hours for the lentils to soak.", " Makes 6 wraps. ", "", "Allow 3–6 hours for the lentils to soak."],
    }]})
    recipe = out[0]
    assert recipe["servings"] == 6
    assert recipe["description"] == "A weeknight favourite."
    assert recipe["adaptations"] == {"page_notes": ["Allow 3–6 hours for the lentils to soak.", "Makes 6 wraps."]}
    single = parse_llm_recipes_payload([{"title": "Soup", "ingredients": ["x"], "notes": "Freezes well."}])
    assert single[0]["adaptations"]["page_notes"] == ["Freezes well."]


def test_normalize_page_notes_caps_and_round_trips():
    import json
    from utils.recipe_fields import normalize_adaptations, prepare_recipe_for_response

    many = normalize_adaptations({"page_notes": [f"Tip {i}" for i in range(40)] + [{"bad": 1}]})
    assert len(many["page_notes"]) == 30
    assert normalize_adaptations({"page_notes": ["  "]}) is None
    value = {"low_fodmap": {"swaps": [], "notes": "Small portions"}, "page_notes": ["To serve: with lime"]}
    shaped = prepare_recipe_for_response(
        {"id": "r1", "title": "T", "ingredients": "[]", "instructions": "[]", "adaptations": json.dumps(value)},
        estimate_missing_nutrition=False,
    )
    assert shaped["adaptations"] == value


def test_low_fodmap_note_in_page_notes_still_tags():
    from services.recipe_pdf_import import LOW_FODMAP_TAG, tag_dietary_adaptations

    out = tag_dietary_adaptations([{"title": "Wrap", "instructions": ["Cook"],
                                    "adaptations": {"page_notes": ["Low FODMAP adaptation: garlic adaption"]}}])
    assert LOW_FODMAP_TAG in out[0]["tags"]


def test_section_merge_keeps_page_notes_from_both_fragments():
    from services.recipe_pdf_import import merge_section_fragments

    out = merge_section_fragments([
        {"title": "Lentil Wraps", "ingredients": [{"name": "lentils"}], "instructions": ["Cook"],
         "adaptations": {"page_notes": ["Soak 3–6 hours."]}},
        {"title": "Method", "ingredients": [], "instructions": ["Wrap"], "adaptations": {"page_notes": ["Keeps 3 days."]}},
    ])
    assert out[0]["adaptations"]["page_notes"] == ["Soak 3–6 hours.", "Keeps 3 days."]


def test_versions_found_summary():
    from services.recipe_pdf_import import fold_recipe_versions, versions_found

    recipes = fold_recipe_versions([
        {"title": "Pesto Pasta — Chicken Schnitzel", "ingredients": [{"name": "chicken"}], "instructions": ["Fry"]},
        {"title": "Pesto Pasta — Pomegranate", "ingredients": [{"name": "pomegranate"}], "instructions": ["Scatter"],
         "adaptations": {"page_notes": ["Best fresh."]}},
        {"title": "Toast", "ingredients": [{"name": "bread"}], "instructions": ["Toast"]},
    ])
    assert versions_found(recipes) == [{"recipe": "Pesto Pasta", "versions": ["Pomegranate"]}]
    assert recipes[0]["adaptations"]["versions"][0]["notes"] == "Best fresh."
    assert versions_found([{"title": "X", "adaptations": None}]) == []


def test_prompt_keeps_everything_on_the_page():
    from services.recipe_pdf_import import MULTI_RECIPE_PDF_PROMPT

    assert '"notes"' in MULTI_RECIPE_PDF_PROMPT
    assert "nothing practical may be dropped" in MULTI_RECIPE_PDF_PROMPT
    assert "Do NOT copy the" in MULTI_RECIPE_PDF_PROMPT  # author backstory is left out
    assert "max 20 words" in MULTI_RECIPE_PDF_PROMPT
    assert "Sauce: " in MULTI_RECIPE_PDF_PROMPT
    assert "Makes 6 wraps" in MULTI_RECIPE_PDF_PROMPT


def test_split_keeps_text_before_first_heading():
    from services.recipe_pdf_import import pack_recipe_sections, split_recipe_text_chunks

    text = (
        "50\nHONEY CHILLI CAULIFLOWER\n1 medium cauliflower\n2 tbsp honey\nRoast until crisp and toss in the sauce.\n\n"
        "Spinach and Feta Triangles\nIngredients\n200g spinach\n100g feta\nMethod\nFold and bake.\n\n"
        "Swedish Sandwich Cake\nIngredients\n1 loaf bread\nMethod\nLayer and chill.\n"
    )
    chunks = split_recipe_text_chunks(text, max_chunks=100)
    assert "HONEY CHILLI CAULIFLOWER" in chunks[0]
    assert any("HONEY CHILLI" in s for s in pack_recipe_sections(text))


def test_add_on_versions_get_the_base_recipe():
    from services.recipe_pdf_import import parse_llm_recipes_payload

    out = parse_llm_recipes_payload({"recipes": [{
        "title": "Pesto Pasta",
        "ingredients": [{"name": "pasta"}, {"name": "basil"}, {"name": "olive oil"}],
        "instructions": ["Cook pasta", "Blitz pesto", "Stir through"],
        "versions": [
            {"name": "Pomegranate", "ingredients": [{"name": "pomegranate"}], "instructions": ["Sprinkle arils"]},
            {"name": "Full", "ingredients": [{"name": "pasta"}, {"name": "basil"}, {"name": "feta"}],
             "instructions": ["Cook pasta", "Blitz pesto", "Stir through", "Top with feta"]},
        ],
    }]})
    pom, full = out[0]["adaptations"]["versions"]
    assert [i["name"] for i in pom["ingredients"]] == ["pasta", "basil", "olive oil", "pomegranate"]
    assert pom["instructions"] == ["Cook pasta", "Blitz pesto", "Stir through", "Sprinkle arils"]
    assert [i["name"] for i in full["ingredients"]] == ["pasta", "basil", "feta"]  # already whole: untouched
    assert len(full["instructions"]) == 4
