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
