"""Country setting: GB default everywhere; nutrition style + food-data region derive from it."""
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import region as region_mod  # noqa: E402
from utils.region import (  # noqa: E402
    accepts_region,
    food_region_for_country,
    locale_fields,
    nutrition_style_for_country,
    region_kwargs,
    total_carbs_per_serving,
    user_country,
    user_region,
    with_total_carbs,
)


# --- country -> nutrition style / food data ----------------------------------

@pytest.mark.parametrize("country,style,region", [
    ("GB", "uk", "uk"), ("gb", "uk", "uk"), ("UK", "uk", "uk"), ("IE", "uk", "uk"),
    ("FR", "uk", "uk"), ("DE", "uk", "uk"), ("NG", "uk", "uk"), ("JP", "uk", "uk"),
    ("AU", "au", "uk"), ("NZ", "au", "uk"),
    ("CA", "ca", "us"),
    ("US", "us", "us"), ("us", "us", "us"),
])
def test_style_and_food_region_from_country(country, style, region):
    assert nutrition_style_for_country(country) == style
    assert food_region_for_country(country) == region
    assert locale_fields(country) == {"nutritionStyle": style, "foodRegion": region}


@pytest.mark.parametrize("raw", [None, "", "ZZ", "mars", 7])
def test_unknown_country_is_uk(raw):
    assert nutrition_style_for_country(raw) == "uk"
    assert food_region_for_country(raw) == "uk"


def test_every_iso_country_is_accepted():
    from utils.locales import ALL_COUNTRY_CODES, normalize_country

    assert len(ALL_COUNTRY_CODES) == 249
    assert all(normalize_country(c) == c for c in ALL_COUNTRY_CODES)
    assert normalize_country("zz") == "GB"


def test_accepts_region_feature_check():
    def old_find_food(name, remote=False):
        return None

    def new_find_food(name, remote=False, *, region="uk"):
        return region

    def kw_only(name, **kwargs):
        return kwargs

    assert not accepts_region(old_find_food)
    assert accepts_region(new_find_food)
    assert accepts_region(kw_only)
    assert region_kwargs(old_find_food, "us") == {}
    assert region_kwargs(new_find_food, "US") == {"region": "us"}
    assert new_find_food("x", **region_kwargs(new_find_food, "us")) == "us"
    assert old_find_food("x", **region_kwargs(old_find_food, "us")) is None  # never breaks old code


def test_total_carbs_needs_every_line():
    badges = [{"c": 10, "c_total": 14}, {"c": 4, "c_total": 6}]
    assert total_carbs_per_serving(badges, 2) == 10
    assert total_carbs_per_serving(badges + [{"c": 3}], 2) is None  # partial sum never shown
    assert total_carbs_per_serving([], 2) is None
    assert total_carbs_per_serving(None, 2) is None
    assert total_carbs_per_serving(badges, 0) == 20  # servings floor at 1


def test_with_total_carbs_copies_and_falls_back():
    n = {"calories": 300, "carbs": 30}
    out = with_total_carbs(n, [{"c": 30, "c_total": 36}], 1)
    assert out == {"calories": 300, "carbs": 30, "carbs_total": 36}
    assert "carbs_total" not in n  # input untouched
    assert with_total_carbs(n, [{"c": 30}], 1) is n  # no c_total -> UK figures only
    assert with_total_carbs(None, [{"c_total": 1}], 1) is None


@pytest.mark.asyncio
async def test_user_country_and_region_read_preferences(monkeypatch):
    repo = MagicMock()
    repo.find_by_user = AsyncMock(return_value={"country": "US"})
    import dependencies

    monkeypatch.setattr(dependencies, "user_preferences_repository", repo)
    assert await user_country({"id": "u1"}) == "US"
    assert await user_region({"id": "u1"}) == "us"
    repo.find_by_user.return_value = {"country": "CA"}
    assert await user_region({"id": "u1"}) == "us"  # Canada: USDA-first data
    repo.find_by_user.return_value = {"country": "AU"}
    assert await user_region({"id": "u1"}) == "uk"
    repo.find_by_user.return_value = None  # never saved prefs: GB
    assert await user_country({"id": "u1"}) == "GB"
    repo.find_by_user.side_effect = RuntimeError("db down")
    assert await user_region({"id": "u1"}) == "uk"  # never breaks a food lookup
    assert await user_region(None) == "uk"


def test_food_lookups_region_aware_matches_line_macros():
    from services.line_macros import estimate_line_macros

    assert region_mod.food_lookups_region_aware() == accepts_region(estimate_line_macros)


def test_prepare_recipe_adds_total_carbs_from_badges():
    from utils.recipe_fields import prepare_recipe_for_response

    row = {
        "id": "r1", "title": "T", "servings": 2,
        "ingredients": [{"name": "oats", "amount": "100", "unit": "g"}, {"name": "milk", "amount": "200", "unit": "ml"}],
        "instructions": ["Mix"],
        "nutrition_calories": 300, "nutrition_protein": 12, "nutrition_carbs": 40, "nutrition_fat": 8,
        "ingredient_macros": [{"p": 13, "c": 60, "c_total": 70, "f": 7, "cal": 380}, {"p": 7, "c": 10, "c_total": 10, "f": 7, "cal": 130}],
    }
    out = prepare_recipe_for_response(dict(row), estimate_missing_nutrition=False)
    assert out["nutrition"]["carbs"] == 40
    assert out["nutrition"]["carbs_total"] == 40  # (70 + 10) / 2
    row["ingredient_macros"] = [{"p": 13, "c": 60, "f": 7, "cal": 380}, {"p": 7, "c": 10, "f": 7, "cal": 130}]
    out = prepare_recipe_for_response(dict(row), estimate_missing_nutrition=False)
    assert "carbs_total" not in out["nutrition"]  # older rows: UK carbs only


# --- preferences round trip --------------------------------------------------

class _PrefsStore:
    def __init__(self, row=None):
        self.row = row

    async def find_by_user(self, user_id):
        return dict(self.row) if self.row is not None else None

    async def upsert_preferences(self, user_id, data):
        self.row = {**(self.row or {"user_id": user_id}), **data}
        return self.row


@pytest.fixture
def prefs(monkeypatch):
    import routers.preferences as preferences

    store = _PrefsStore()
    monkeypatch.setattr(preferences, "user_preferences_repository", store)
    return preferences, store


@pytest.mark.asyncio
async def test_preferences_default_is_gb_uk(prefs):
    preferences, store = prefs
    user = {"id": "u1"}
    out = await preferences.get_preferences(user=user)  # no row yet
    assert (out["country"], out["nutritionStyle"], out["foodRegion"]) == ("GB", "uk", "uk")
    store.row = {"user_id": "u1", "country": None}  # existing user, NULL column
    out = await preferences.get_preferences(user=user)
    assert (out["nutritionStyle"], out["foodRegion"]) == ("uk", "uk")


@pytest.mark.asyncio
async def test_preferences_country_round_trip(prefs):
    preferences, store = prefs
    user = {"id": "u1"}
    await preferences.update_preferences(preferences.UserPreferences(country="us"), user=user)
    assert store.row["country"] == "US"
    out = await preferences.get_preferences(user=user)
    assert (out["nutritionStyle"], out["foodRegion"]) == ("us", "us")
    assert "nutritionStyle" not in store.row  # derived, never stored
    # A partial save of something else leaves the country alone
    await preferences.update_preferences(preferences.UserPreferences(compactView=True), user=user)
    assert store.row["country"] == "US"
    await preferences.update_preferences(preferences.UserPreferences(country="NZ"), user=user)
    out = await preferences.get_preferences(user=user)
    assert (out["country"], out["nutritionStyle"], out["foodRegion"]) == ("NZ", "au", "uk")
    await preferences.update_preferences(preferences.UserPreferences(country="NG"), user=user)
    assert store.row["country"] == "NG"  # any ISO country, not just the catalogue


# --- registration ------------------------------------------------------------

@pytest.fixture
def register_env(monkeypatch):
    import routers.auth as auth

    store = _PrefsStore()
    settings_repo = MagicMock()
    settings_repo.get_settings = AsyncMock(return_value={})
    user_repo = MagicMock()
    user_repo.find_by_email = AsyncMock(return_value=None)
    user_repo.count = AsyncMock(return_value=5)
    user_repo.create = AsyncMock()
    sessions = MagicMock()
    sessions.create = AsyncMock()

    monkeypatch.setattr(auth, "check_ip_access", AsyncMock(return_value=(True, "")))
    monkeypatch.setattr(auth, "system_settings_repository", settings_repo)
    monkeypatch.setattr(auth, "user_repository", user_repo)
    monkeypatch.setattr(auth, "session_repository", sessions)
    monkeypatch.setattr(auth, "user_preferences_repository", store)
    monkeypatch.setattr(auth, "validate_password", AsyncMock(return_value=(True, "")))
    monkeypatch.setattr(auth, "hash_password", lambda p: "hashed")
    monkeypatch.setattr(auth, "create_token", lambda uid: "tok")
    monkeypatch.setattr(auth, "log_user_activity", AsyncMock())
    monkeypatch.setattr(auth, "is_email_configured", lambda: False)
    request = SimpleNamespace(client=None, headers={})
    return auth, store, request


async def _register(auth, request, **extra):
    body = auth.UserCreateExtended(email="sam@example.com", password="Sup3r-secret!", name="Sam", **extra)
    return await auth.register(body, request, BackgroundTasks())


@pytest.mark.asyncio
async def test_register_without_country_is_gb(register_env):
    auth, store, request = register_env
    out = await _register(auth, request)
    assert out["token"] == "tok"
    assert store.row["country"] == "GB"
    assert store.row["measurementUnit"] == "metric"


@pytest.mark.asyncio
async def test_register_us_gets_us_units(register_env):
    auth, store, request = register_env
    await _register(auth, request, country="US")
    assert store.row["country"] == "US"
    assert store.row["measurementUnit"] == "imperial"


@pytest.mark.asyncio
async def test_register_any_iso_country(register_env):
    auth, store, request = register_env
    await _register(auth, request, country="KE")
    assert store.row["country"] == "KE"
    assert store.row["measurementUnit"] == "metric"
    assert store.row["language"] == "en-GB"


@pytest.mark.asyncio
async def test_register_unknown_country_falls_back_to_gb(register_env):
    auth, store, request = register_env
    await _register(auth, request, country="atlantis")
    assert store.row["country"] == "GB"


# --- recipe macros endpoints ---------------------------------------------------

RECIPE = {
    "id": "r1", "author_id": "u1", "household_id": None, "title": "Oats", "servings": 1,
    "ingredients": [{"name": "oats", "amount": "100", "unit": "g"}], "instructions": ["Mix"],
}
US_BADGES = [{"p": 13, "c": 60, "c_total": 70, "f": 7, "cal": 380, "src": "db"}]


@pytest.fixture
def recipes_env(monkeypatch):
    import routers.recipes as recipes

    repo = MagicMock()
    repo.find_by_id = AsyncMock(return_value=dict(RECIPE))
    repo.update_recipe = AsyncMock()
    seen = {}

    async def fake_refresh(recipe, previous=None, *, allow_ai=True, force=False, client=None, region=None, **kw):
        seen["region"] = region
        return {"fields": {"ingredient_macros": US_BADGES, "nutrition_calories": 380},
                "complete": True, "nutrition": {"calories": 380, "protein": 13, "carbs": 60, "fat": 7}}

    monkeypatch.setattr(recipes, "recipe_repository", repo)
    monkeypatch.setattr(recipes, "refresh_recipe_macros", fake_refresh)
    monkeypatch.setattr(recipes, "require_recipe_view", lambda user, recipe: None)
    monkeypatch.setattr(recipes, "is_premium_user", lambda user: True)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http_client=None)))
    return recipes, repo, seen, request


@pytest.mark.asyncio
async def test_us_user_gets_us_lookups_without_touching_shared_recipe(recipes_env, monkeypatch):
    recipes, repo, seen, request = recipes_env
    monkeypatch.setattr(recipes, "user_region", AsyncMock(return_value="us"))
    monkeypatch.setattr(recipes, "food_lookups_region_aware", lambda: True)
    out = await recipes.get_ingredient_macros("r1", request, user={"id": "u1"})
    assert seen["region"] == "us"
    assert out["region"] == "us"
    assert out["nutrition"]["carbs_total"] == 70
    assert out["ingredient_macros"] == US_BADGES
    repo.update_recipe.assert_not_called()  # stored macros stay on the UK default

    preview = await recipes.macros_preview("r1", recipes.MacrosPreviewRequest(), user={"id": "u1"})
    assert preview["nutrition"]["carbs_total"] == 70
    repo.update_recipe.assert_not_called()


@pytest.mark.asyncio
async def test_us_user_on_old_food_layer_uses_normal_path(recipes_env, monkeypatch):
    recipes, repo, seen, request = recipes_env
    monkeypatch.setattr(recipes, "user_region", AsyncMock(return_value="us"))
    monkeypatch.setattr(recipes, "food_lookups_region_aware", lambda: False)
    out = await recipes.get_ingredient_macros("r1", request, user={"id": "u1"})
    assert seen["region"] is None  # no region passed: the UK default lookups
    assert "region" not in out
    assert out["nutrition"]["carbs_total"] == 70  # c_total still surfaces when the badges have it


# --- per 100 g + zero-carb lines ---------------------------------------------------

def test_per_100g_carries_total_carbs_when_every_line_knows_it():
    from services.nutrition_basis import weight_info

    badges = [
        {"p": 5, "c": 50, "c_total": 60, "f": 2, "cal": 240, "g": 100},
        {"p": 0, "c": 0, "f": 100, "cal": 900, "g": 100},  # oil: no carbs, no c_total -> 0
    ]
    per = weight_info(badges)["nutrition_per_100g"]
    assert per["carbs"] == 25.0
    assert per["carbs_total"] == 30.0


def test_per_100g_leaves_total_out_when_a_line_with_carbs_lacks_it():
    from services.nutrition_basis import weight_info

    badges = [
        {"p": 5, "c": 50, "c_total": 60, "f": 2, "cal": 240, "g": 100},
        {"p": 1, "c": 20, "f": 0, "cal": 80, "g": 100},  # older AI line
    ]
    per = weight_info(badges)["nutrition_per_100g"]
    assert per["carbs"] == 35.0
    assert "carbs_total" not in per  # clients fall back to UK carbs, labelled "Carbs"


def test_zero_carb_lines_count_as_zero_total():
    assert total_carbs_per_serving([{"c": 10, "c_total": 12}, {"c": 0}], 1) == 12
    assert total_carbs_per_serving([{"c": 10, "c_total": 12}, {"c": 3}], 1) is None
