"""Optional recipe adaptations (Low FODMAP swaps) round-trip through the recipe models."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import RecipeCreate, RecipeResponse  # noqa: E402
from utils.recipe_fields import RECIPE_COLUMNS, prepare_recipe_for_response, recipe_row_for_insert  # noqa: E402

BASE = {"title": "Lentil Wrap", "ingredients": [{"name": "garlic"}], "instructions": ["Cook"]}
FODMAP = {"low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}], "notes": "Check lentils."}}


def test_adaptations_tracked_only_when_sent():
    assert "adaptations" not in RecipeCreate(**BASE).model_fields_set  # omitted -> keep existing
    sent = RecipeCreate(**BASE, adaptations=FODMAP)
    assert "adaptations" in sent.model_fields_set
    assert sent.adaptations == FODMAP
    assert "adaptations" in RecipeCreate(**BASE, adaptations=None).model_fields_set  # explicit clear


def test_response_round_trip_from_db_row():
    row = {
        "id": "r1", "title": "Lentil Wrap", "description": "", "ingredients": json.dumps([{"name": "garlic"}]),
        "instructions": json.dumps(["Cook"]), "prep_time": 0, "cook_time": 0, "servings": 2, "category": "Dinner",
        "tags": "[]", "image_url": "", "author_id": "u1", "household_id": None,
        "created_at": "2026-10-21T00:00:00", "updated_at": "2026-10-21T00:00:00",
        "adaptations": json.dumps(FODMAP),
    }
    shaped = prepare_recipe_for_response(row, estimate_missing_nutrition=False)
    assert RecipeResponse(**shaped).model_dump()["adaptations"] == FODMAP
    row["adaptations"] = None
    shaped = prepare_recipe_for_response(row, estimate_missing_nutrition=False)
    assert RecipeResponse(**shaped).adaptations is None


def test_adaptations_is_a_recipe_column():
    assert "adaptations" in RECIPE_COLUMNS
    assert recipe_row_for_insert({**BASE, "adaptations": FODMAP})["adaptations"] == FODMAP


def test_fodmap_note_parser_standard_and_explicit_swaps():
    from services.recipe_pdf_import import fodmap_adaptation_from_note

    short = fodmap_adaptation_from_note("Low FODMAP adaptation: garlic + onion adaption")
    assert short == {"low_fodmap": {"swaps": [
        {"from": "garlic", "to": "garlic-infused oil"},
        {"from": "onion", "to": "green tops of spring onions or leek"},
    ], "notes": ""}}

    explicit = fodmap_adaptation_from_note(
        "Low FODMAP adaptation: swap the red onion for chives; use lactose-free yoghurt instead of yoghurt. "
        "One wrap is close to a low FODMAP serving."
    )
    swaps = explicit["low_fodmap"]["swaps"]
    assert {"from": "red onion", "to": "chives"} in swaps
    assert {"from": "yoghurt", "to": "lactose-free yoghurt"} in swaps
    assert not any(s["from"] == "onion" for s in swaps)  # explicit onion swap wins
    assert "One wrap" in explicit["low_fodmap"]["notes"]
    assert fodmap_adaptation_from_note("Low FODMAP adaptation:") is None


def test_backfill_endpoint_updates_only_unadapted_fodmap_recipes(monkeypatch):
    import asyncio
    import routers.recipes as recipes_router

    rows = [
        {"id": "a", "instructions": ["Cook", "Low FODMAP adaptation: garlic adaption"], "adaptations": None},
        {"id": "b", "instructions": ["Cook", "Low FODMAP adaptation: onion adaption"], "adaptations": FODMAP},
        {"id": "c", "instructions": ["Cook"], "adaptations": None},
    ]
    calls = {}

    class FakeRepo:
        async def find_by_author(self, author_id, limit=500):
            calls["author"] = author_id
            return rows

        async def update_recipe(self, recipe_id, data):
            calls.setdefault("updates", []).append((recipe_id, data))
            return 1

    monkeypatch.setattr(recipes_router, "recipe_repository", FakeRepo())
    result = asyncio.run(recipes_router.backfill_fodmap_adaptations(user={"id": "u1"}))
    assert calls["author"] == "u1"
    assert result["scanned"] == 3 and result["updated"] == 1 and result["recipe_ids"] == ["a"]
    rid, data = calls["updates"][0]
    assert rid == "a"
    assert data["adaptations"]["low_fodmap"]["swaps"] == [{"from": "garlic", "to": "garlic-infused oil"}]
    assert "instructions" not in data  # the original step is left in place


def test_handlers_persist_adaptations():
    src = open(os.path.join(os.path.dirname(__file__), "..", "routers", "recipes.py"), encoding="utf-8").read()
    create = src[src.index("async def create_recipe("):src.index("await recipe_repository.create(recipe_doc)")]
    assert 'recipe_doc["adaptations"]' in create
    update = src[src.index("async def update_recipe("):src.index("await recipe_repository.update_recipe(recipe_id, update_data)")]
    assert '"adaptations" in sent' in update


def test_versions_round_trip_with_fodmap():
    versions = [{"name": "Pomegranate", "ingredients": [{"name": "pomegranate", "amount": "1", "unit": ""}],
                 "instructions": ["Scatter"], "notes": "Best fresh"}]
    value = {**FODMAP, "versions": versions}
    sent = RecipeCreate(**BASE, adaptations=value)
    row = {
        "id": "r1", "title": "Lentil Wrap", "description": "", "ingredients": "[]", "instructions": "[]",
        "prep_time": 0, "cook_time": 0, "servings": 2, "category": "Dinner", "tags": "[]", "image_url": "",
        "author_id": "u1", "household_id": None, "created_at": "2026-10-21T00:00:00",
        "updated_at": "2026-10-21T00:00:00", "adaptations": json.dumps(sent.adaptations),
    }
    shaped = prepare_recipe_for_response(row, estimate_missing_nutrition=False)
    assert RecipeResponse(**shaped).adaptations == value
