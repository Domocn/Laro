"""PUT /recipes/{id} must not wipe nutrition / dietary_tags / difficulty when a client omits them.

The update handler only overwrites those columns for fields in `model_fields_set`; this pins the
pydantic behaviour that relies on (omitted -> not in set, explicitly sent -> in set).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import RecipeCreate  # noqa: E402

BASE = {"title": "Soup", "ingredients": [], "instructions": ["Boil"]}


def test_omitted_fields_are_not_marked_sent():
    r = RecipeCreate(**BASE)
    for f in ("nutrition", "dietary_tags", "difficulty"):
        assert f not in r.model_fields_set


def test_explicit_fields_are_marked_sent_even_when_empty():
    r = RecipeCreate(**BASE, nutrition=None, dietary_tags=[], difficulty=None)
    for f in ("nutrition", "dietary_tags", "difficulty"):
        assert f in r.model_fields_set


def test_update_handler_uses_fields_set():
    src = open(os.path.join(os.path.dirname(__file__), "..", "routers", "recipes.py"), encoding="utf-8").read()
    body = src[src.index("async def update_recipe("):src.index("await recipe_repository.update_recipe(recipe_id, update_data)")]
    assert "model_fields_set" in body
    assert '"nutrition" in sent' in body
