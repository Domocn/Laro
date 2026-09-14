"""Inspiration features: aliases, UK traffic lights, household recipe edit."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.ingredient_aliases import (
    apply_alias_to_ingredient,
    normalize_ingredient_key,
)
from services.nutrition_lookup import uk_percent_ri, uk_traffic_lights_per_100g
from utils.authorization import require_recipe_edit


def test_normalize_ingredient_key_strips_noise():
    assert normalize_ingredient_key("  Spring Onions (chopped)! ") == "spring onions"


def test_apply_alias_to_dict_and_string():
    alias_map = {"scallion": "spring onion", "scallions": "spring onion"}
    updated, changed = apply_alias_to_ingredient(
        {"name": "Scallion", "amount": "1"}, alias_map
    )
    assert changed
    assert updated["name"] == "spring onion"

    updated, changed = apply_alias_to_ingredient("2 cups scallions", alias_map)
    assert changed
    assert updated == "2 cups spring onion"


def test_uk_traffic_lights_bands():
    lights = uk_traffic_lights_per_100g(
        {"fat": 2.0, "saturates": 1.0, "sugars": 10.0, "salt": 2.0}
    )
    assert lights["fat"]["color"] == "green"
    assert lights["saturates"]["color"] == "green"
    assert lights["sugars"]["color"] == "amber"
    assert lights["salt"]["color"] == "red"


def test_uk_percent_ri_serving():
    pct = uk_percent_ri(
        {"calories": 500, "fat": 35, "carbs": 65, "protein": 25, "salt": 1.5}
    )
    assert pct["energy_kcal_pct"] == 25.0
    assert pct["fat_pct"] == 50.0
    assert pct["salt_pct"] == 25.0


def test_household_member_can_edit_shared_recipe():
    author = {"id": "u1", "role": "user", "household_id": "hh1"}
    collaborator = {"id": "u2", "role": "user", "household_id": "hh1"}
    stranger = {"id": "u3", "role": "user", "household_id": "hh2"}
    recipe = {"id": "r1", "author_id": "u1", "household_id": "hh1"}

    require_recipe_edit(author, recipe)
    require_recipe_edit(collaborator, recipe)
    with pytest.raises(HTTPException) as exc:
        require_recipe_edit(stranger, recipe)
    assert exc.value.status_code == 403


def test_solo_recipe_author_only():
    author = {"id": "u1", "role": "user", "household_id": None}
    other = {"id": "u2", "role": "user", "household_id": None}
    recipe = {"id": "r1", "author_id": "u1", "household_id": None}
    require_recipe_edit(author, recipe)
    with pytest.raises(HTTPException):
        require_recipe_edit(other, recipe)
