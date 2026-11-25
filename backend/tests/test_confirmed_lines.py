"""User-confirmed line macros ("Check the numbers"): precedence over the food database / AI,
invalidation when a line is edited, never overwritten by recompute / backfill, the endpoints
and the per-cook nutrition override."""
import asyncio
import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import confirmed_lines as cl  # noqa: E402
from services import version_macros as vm  # noqa: E402
from utils.recipe_fields import normalize_adaptations  # noqa: E402

PASTA = {"amount": "500", "unit": "g", "name": "dried pasta"}
BASIL = {"amount": "1", "unit": "bunch", "name": "basil"}
OIL = {"amount": "", "unit": "", "name": "drizzle of olive oil"}
GARLIC = {"amount": "2", "unit": "cloves", "name": "garlic"}

TABLE = {
    "500 g dried pasta": {"p": 60, "c": 350, "f": 7, "cal": 1750, "src": "ai", "g": 500.0, "g_src": "ai"},
    "1 bunch basil": {"p": 1, "c": 1, "f": 0, "cal": 9, "src": "ai", "g": 30.0, "g_src": "ai"},
    "drizzle of olive oil": {"p": 0, "c": 0, "f": 14, "cal": 120, "src": "ai", "g": 15.0, "g_src": "ai"},
    "2 cloves garlic": {"p": 0, "c": 2, "f": 0, "cal": 9, "src": "ai", "g": 6.0, "g_src": "ai"},
    "2 cloves garlic-infused oil": {"p": 0, "c": 0, "f": 9, "cal": 80, "src": "ai", "g": 9.0, "g_src": "ai"},
}


def lookup(item):
    from services.line_macros import ingredient_line, normalize_line

    hit = TABLE.get(normalize_line(ingredient_line(item)))
    return dict(hit) if hit else None


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """No real AI / cache DB: the mocked AI fails, the cache is in memory, and the food
    database is off for the computation tests (lookups come from TABLE)."""
    import dependencies
    from services import line_macros

    class Store:
        async def get_many(self, keys):
            return {}

        async def put_many(self, values, model=""):
            return None

    async def no_ai(*a, **k):
        raise RuntimeError("AI disabled in tests")

    monkeypatch.setattr(dependencies, "call_llm", no_ai)
    monkeypatch.setattr(line_macros, "store", Store())
    monkeypatch.setattr(line_macros, "DB_FIRST", False)
    line_macros._MEMORY.clear()
    yield
    line_macros._MEMORY.clear()


def _recipe(**over):
    base = {
        "id": "r1",
        "title": "Pesto Pasta",
        "servings": 4,
        "author_id": "u1",
        "ingredients": [PASTA, BASIL, OIL, GARLIC],
        "instructions": ["Cook"],
        "adaptations": {
            "low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}]},
            "versions": [{"name": "Extra Basil", "ingredients": [PASTA, BASIL, OIL], "instructions": ["Cook"]}],
        },
    }
    base.update(over)
    return base


def _confirm(recipe, line, version="", lf=False, **vals):
    entry = {"p": 0, "c": 0, "f": 5, "cal": 45, "source": "user", "g": 5.0, **vals}
    adaptations = dict(normalize_adaptations(recipe["adaptations"]) or {})
    confirmed = dict(adaptations.get("confirmed_lines") or {})
    confirmed[cl.confirm_key(line, version, lf)] = entry
    adaptations["confirmed_lines"] = confirmed
    return {**recipe, "adaptations": adaptations}


# --- precedence --------------------------------------------------------------------------------

def test_confirmed_line_wins_over_ai_for_original():
    recipe = _confirm(_recipe(), "drizzle of olive oil")
    out = vm.compute_recipe_macros(recipe, lookup)
    badges = out["fields"]["ingredient_macros"]
    assert badges[2] == {"p": 0, "c": 0, "f": 5, "cal": 45, "src": "user", "g": 5.0, "source": "user"}
    # (1750 + 9 + 45 + 9) / 4
    assert out["nutrition"]["calories"] == round((1750 + 9 + 45 + 9) / 4)
    assert out["fields"]["adaptations"]["confirmed_lines"]


def test_confirmation_is_scoped_to_its_version_and_low_fodmap_flag():
    recipe = _confirm(_recipe(), "drizzle of olive oil", version="Extra Basil")
    out = vm.compute_recipe_macros(recipe, lookup)
    assert out["fields"]["ingredient_macros"][2]["cal"] == 120  # Original keeps the AI line
    version = out["fields"]["adaptations"]["versions"][0]
    assert version["ingredient_macros"][2]["cal"] == 45
    assert version["ingredient_macros"][2]["src"] == "user"

    lf = _confirm(_recipe(), "2 cloves garlic-infused oil", lf=True, f=10, cal=90)
    out = vm.compute_recipe_macros(lf, lookup)
    lf_badges = out["fields"]["adaptations"]["low_fodmap_macros"]["ingredient_macros"]
    assert lf_badges[3]["cal"] == 90
    assert out["fields"]["ingredient_macros"][3]["cal"] == 9  # plain Original untouched


def test_confirmed_line_needs_no_estimate():
    """A confirmed line counts even when the database / AI have nothing for it."""
    recipe = _confirm(_recipe(adaptations={}), "drizzle of olive oil")
    no_oil = lambda item: None if "olive" in item["name"] else lookup(item)  # noqa: E731
    out = vm.compute_recipe_macros(recipe, no_oil)
    assert out["complete"] is True
    assert out["fields"]["ingredient_macros"][2]["src"] == "user"


# --- never overwritten by recompute / backfill -------------------------------------------------

def test_backfill_leaves_confirmed_recipe_alone_and_recompute_keeps_figures():
    recipe = _confirm(_recipe(), "drizzle of olive oil")
    fields = vm.compute_recipe_macros(recipe, lookup)["fields"]
    saved = {**recipe, **fields}
    for k, v in fields.items():
        if k.startswith("nutrition_"):
            saved[k] = v
    assert vm.macros_consistent(saved) is True  # backfill skips it
    again = vm.compute_recipe_macros(saved, lookup, saved.get("adaptations"), force=True)
    assert again["fields"]["ingredient_macros"][2]["cal"] == 45


def test_stale_user_badge_without_confirmation_is_recomputed():
    recipe = _confirm(_recipe(adaptations={}), "drizzle of olive oil")
    fields = vm.compute_recipe_macros(recipe, lookup)["fields"]
    saved = {**recipe, **fields, "adaptations": None}  # confirmation removed, badge still "user"
    assert vm.original_badges_current(saved) is False
    assert vm._seeded_badges(saved).get("drizzle of olive oil") is None  # never re-seeded as AI


def test_existing_sigs_unchanged_without_confirmations():
    recipe = _recipe()
    out = vm.compute_recipe_macros(recipe, lookup)
    version = out["fields"]["adaptations"]["versions"][0]
    ings = vm._ingredients(version["ingredients"])
    assert version["macros_sig"] == vm._sig([vm._SIG_VERSION, ings, 4, []])


# --- invalidation ------------------------------------------------------------------------------

def test_editing_the_line_text_invalidates_its_confirmation():
    existing = _confirm(_recipe(), "drizzle of olive oil")
    edited = {**existing, "ingredients": [PASTA, BASIL, {"amount": "1", "unit": "tbsp", "name": "olive oil"}, GARLIC]}
    after, changed = cl.reconcile_on_update(existing["adaptations"], cl._MISSING, edited)
    assert changed is True
    assert "confirmed_lines" not in (after or {})


def test_client_without_confirmed_lines_keeps_them():
    existing = _confirm(_recipe(), "drizzle of olive oil")
    sent = {"low_fodmap": existing["adaptations"]["low_fodmap"], "versions": existing["adaptations"]["versions"]}
    after, _ = cl.reconcile_on_update(existing["adaptations"], sent, existing)
    assert list(after["confirmed_lines"]) == [cl.confirm_key("drizzle of olive oil")]
    # Sending the key (even empty) replaces them.
    after, changed = cl.reconcile_on_update(existing["adaptations"], {**sent, "confirmed_lines": {}}, existing)
    assert "confirmed_lines" not in after and changed


def test_normalize_keeps_only_valid_entries():
    data = normalize_adaptations({"confirmed_lines": {
        "|0|1 tbsp oil": {"p": 0, "c": 0, "f": 14, "cal": 120, "source": "barcode", "barcode": "50-1234"},
        "bad-key": {"p": 1, "c": 1, "f": 1, "cal": 1},
        "|0|x": {"p": -1, "c": 0, "f": 0, "cal": 0},
        "|0|y": {"p": 1, "c": 1, "f": 1, "cal": 99999},
    }})
    assert list(data["confirmed_lines"]) == ["|0|1 tbsp oil"]
    assert data["confirmed_lines"]["|0|1 tbsp oil"]["barcode"] == "501234"


# --- uncertainty -------------------------------------------------------------------------------

def test_check_payload_flags_ai_and_vague_lines_and_trusts_db_lines():
    def mixed(item):
        if item["name"] == "dried pasta":
            return {"p": 65, "c": 370, "f": 8, "cal": 1790, "src": "db", "food": "Pasta, dried", "g": 500.0,
                    "source": "cofid"}
        return lookup(item)

    payload = cl.check_payload(_recipe(), mixed)
    rows = {r["name"]: r for r in payload["lines"]}
    assert rows["dried pasta"]["uncertain"] is False
    assert rows["dried pasta"]["source_label"] == "CoFID"
    assert rows["drizzle of olive oil"]["uncertain"] is True
    assert "Vague amount" in rows["drizzle of olive oil"]["reasons"]
    assert rows["basil"]["source_label"] == "AI estimate"
    assert payload["complete"] is True
    assert payload["nutrition"]["calories"] == round((1790 + 9 + 120 + 9) / 4)

    confirmed = _confirm(_recipe(), "drizzle of olive oil")
    rows = {r["name"]: r for r in cl.check_payload(confirmed, mixed)["lines"]}
    assert rows["drizzle of olive oil"]["uncertain"] is False
    assert rows["drizzle of olive oil"]["confirmed"] is True
    assert rows["drizzle of olive oil"]["source_label"] == "You checked"


def test_badge_from_label():
    assert cl.badge_from_label({"kcal": 884, "protein": 0, "carbs": 0, "fat": 100}, used_g=13.5) == \
        {"cal": 119, "p": 0, "c": 0, "f": 14, "g": 13.5}
    out = cl.badge_from_label({"kcal": 200, "protein": 10, "carbs": 20, "fat": 5}, basis="pack", packs=0.5, pack_g=80)
    assert out == {"cal": 100, "p": 5, "c": 10, "f": 2, "g": 40.0}
    with pytest.raises(ValueError):
        cl.badge_from_label({"kcal": 2000, "protein": 0, "carbs": 0, "fat": 0}, used_g=10)
    with pytest.raises(ValueError):
        cl.badge_from_label({"kcal": 100, "protein": 1, "carbs": 1, "fat": 1})


# --- nutrition override (cook session / mark cooked) -------------------------------------------

def test_override_validation():
    from pydantic import ValidationError

    from models import CookSessionComplete, MarkCookedRequest

    ok = MarkCookedRequest(nutrition_override={"calories": 520.4, "protein": 20, "carbs": 70, "fat": 18})
    assert ok.nutrition_override == {"calories": 520, "protein": 20, "carbs": 70, "fat": 18}
    assert CookSessionComplete().nutrition_override is None
    for bad in (
        {"calories": 500, "protein": 20, "carbs": 70},  # fat missing
        {"calories": -1, "protein": 20, "carbs": 70, "fat": 10},
        {"calories": 9000, "protein": 20, "carbs": 70, "fat": 10},
        {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},
        {"calories": 100, "protein": 100, "carbs": 100, "fat": 50},  # macros = 1250 kcal
        {"calories": "lots", "protein": 1, "carbs": 1, "fat": 1},
        "520",
    ):
        with pytest.raises(ValidationError):
            CookSessionComplete(nutrition_override=bad)


class _Repo:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.created = []
        self.updates = []

    async def find_by_id(self, rid):
        row = self.rows.get(rid)
        return dict(row) if row else None

    async def find_by_id_and_user(self, sid, uid):
        return self.rows.get(sid)

    async def create(self, row):
        self.created.append(row)
        return row

    async def update_session(self, sid, data):
        self.updates.append((sid, data))
        return 1

    async def update_recipe(self, rid, data):
        self.updates.append((rid, data))
        self.rows[rid] = {**self.rows.get(rid, {}), **data}
        return 1

    async def upsert_feedback(self, **kw):
        return None


@pytest.fixture
def cook_app(monkeypatch):
    from dependencies import get_current_user
    from routers import cooking

    recipes = _Repo({"r1": _recipe()})
    sessions = _Repo({"s1": {"id": "s1", "user_id": "u1", "recipe_id": "r1"}})
    synced = []

    async def fake_sync(user_id, recipe_id, cook_session_id=None, nutrition_override=None):
        synced.append(nutrition_override)
        return None

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(cooking, "recipe_repository", recipes)
    monkeypatch.setattr(cooking, "cook_session_repository", sessions)
    monkeypatch.setattr(cooking, "recipe_feedback_repository", _Repo())
    monkeypatch.setattr(cooking, "_maybe_sync_google_health", fake_sync)
    monkeypatch.setattr(cooking.ws_manager, "broadcast_to_household_or_user", noop)
    app = FastAPI()
    app.include_router(cooking.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "name": "Dom", "household_id": None}
    return TestClient(app), sessions, synced


def test_cook_session_complete_uses_override(cook_app):
    client, sessions, synced = cook_app
    body = {"feedback": "yes", "nutrition_override": {"calories": 480, "protein": 18, "carbs": 66, "fat": 15}}
    r = client.post("/api/cooking/session/s1/complete", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["nutrition_override"]["calories"] == 480
    assert synced == [{"calories": 480, "protein": 18, "carbs": 66, "fat": 15}]
    stored = next(d for sid, d in sessions.updates if sid == "s1")
    assert json.loads(stored["nutrition_override"])["fat"] == 15

    r = client.post("/api/cooking/recipes/r1/mark-cooked", json={"nutrition_override": {"calories": -5}})
    assert r.status_code == 422


def test_mark_cooked_without_override_unchanged(cook_app):
    client, sessions, synced = cook_app
    r = client.post("/api/cooking/recipes/r1/mark-cooked", json={})
    assert r.status_code == 200
    assert r.json()["nutrition_override"] is None
    assert "nutrition_override" not in sessions.created[-1]
    assert synced == [None]


# --- endpoints ---------------------------------------------------------------------------------

@pytest.fixture
def lines_app(monkeypatch):
    from dependencies import get_current_user
    from routers import confirmed_lines as router_mod
    from services import recipe_macros_jobs

    repo = _Repo({"r1": _recipe()})
    monkeypatch.setattr(router_mod, "recipe_repository", repo)

    async def fake_lookup(recipe, allow_ai=True, client=None, **_kwargs):  # fill_weights / region
        return lookup

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(vm, "recipe_lookup", fake_lookup)
    monkeypatch.setattr(recipe_macros_jobs, "schedule_recipe_macros", lambda *a, **k: None)
    from database.websocket_manager import ws_manager

    monkeypatch.setattr(ws_manager, "broadcast_to_household_or_user", noop)
    user = {"id": "u1", "name": "Dom", "household_id": None, "role": "user"}
    app = FastAPI()
    app.include_router(router_mod.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), repo, user


def test_get_check_numbers(lines_app):
    client, _, _ = lines_app
    r = client.get("/api/recipes/r1/check-numbers", params={"low_fodmap": "true"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["low_fodmap"] is True and data["can_edit"] is True
    assert [row["line"] for row in data["lines"]][-1] == "2 cloves garlic-infused oil"
    assert data["uncertain_count"] == 4  # all AI in this fixture


def test_put_confirmed_lines_saves_and_recomputes(lines_app):
    client, repo, _ = lines_app
    body = {"lines": [{"index": 2, "p": 0, "c": 0, "f": 5, "cal": 45, "g": 5}]}
    r = client.put("/api/recipes/r1/confirmed-lines", json=body)
    assert r.status_code == 200, r.text
    saved = repo.rows["r1"]
    assert saved["adaptations"]["confirmed_lines"][cl.confirm_key("drizzle of olive oil")]["cal"] == 45
    assert saved["ingredient_macros"][2]["src"] == "user"
    assert saved["nutrition_calories"] == round((1750 + 9 + 45 + 9) / 4)
    row = next(x for x in r.json()["lines"] if x["index"] == 2)
    assert row["confirmed"] is True and row["uncertain"] is False

    r = client.put("/api/recipes/r1/confirmed-lines", json={"clear": ["drizzle of olive oil"]})
    assert r.status_code == 200
    assert "confirmed_lines" not in (repo.rows["r1"]["adaptations"] or {})
    assert repo.rows["r1"]["ingredient_macros"][2]["cal"] == 120


def test_put_confirmed_lines_rejects_unknown_line_and_non_editors(lines_app):
    client, repo, user = lines_app
    r = client.put("/api/recipes/r1/confirmed-lines", json={"lines": [{"line": "1 kg lard", "p": 0, "c": 0, "f": 1, "cal": 9}]})
    assert r.status_code == 422
    user["id"] = "u2"  # not the author, not in the household: looks like a missing recipe
    r = client.put("/api/recipes/r1/confirmed-lines", json={"lines": [{"index": 0, "p": 1, "c": 1, "f": 1, "cal": 10}]})
    assert r.status_code == 404
    assert "confirmed_lines" not in (repo.rows["r1"]["adaptations"] or {})


def test_estimate_from_barcode_and_label(lines_app, monkeypatch):
    from services import nutrition_lookup

    client, _, _ = lines_app
    monkeypatch.setattr(nutrition_lookup, "lookup_barcode_nutrition", lambda code, prefer_uk=True: {
        "label": "Napolina Extra Virgin Olive Oil", "calories": 824, "protein": 0, "carbs": 0, "fat": 91.6})
    r = client.post("/api/recipes/r1/check-numbers/estimate",
                    json={"index": 2, "mode": "barcode", "barcode": "8001250120083", "used_g": 10})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["source"] == "barcode" and data["product"].startswith("Napolina")
    assert data["macros"] == {"cal": 82, "p": 0, "c": 0, "f": 9, "g": 10.0}

    r = client.post("/api/recipes/r1/check-numbers/estimate",
                    json={"index": 2, "mode": "label", "label": {"kcal": 884, "protein": 0, "carbs": 0, "fat": 100},
                          "used_g": 13.5})
    assert r.json()["macros"]["cal"] == 119

    monkeypatch.setattr(nutrition_lookup, "lookup_barcode_nutrition", lambda code, prefer_uk=True: None)
    r = client.post("/api/recipes/r1/check-numbers/estimate",
                    json={"index": 2, "mode": "barcode", "barcode": "123", "used_g": 10})
    assert r.status_code == 404


def test_estimate_from_amount_uses_food_database(lines_app):
    client, _, _ = lines_app
    r = client.post("/api/recipes/r1/check-numbers/estimate",
                    json={"index": 2, "mode": "amount", "amount": "1", "unit": "tbsp"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["used"] == "1 tbsp olive oil"  # vague words dropped from the food name
    assert data["basis_src"] == "db" and data["source"] == "user"
    assert 100 <= data["macros"]["cal"] <= 140 and data["macros"]["g"] > 0

    r = client.post("/api/recipes/r1/check-numbers/estimate",
                    json={"index": 2, "mode": "amount", "amount": "1", "unit": "glug of mystery"})
    assert r.status_code == 422  # no database answer, AI unavailable: plain-language error


def test_food_name():
    assert cl.food_name("drizzle of olive oil") == "olive oil"
    assert cl.food_name("a handful of spinach, washed") == "spinach"
    assert cl.food_name("basil") == "basil"


def test_barcode_endpoint_returns_per_100g_label(monkeypatch):
    from dependencies import get_current_user
    from routers import nutrition
    from services import nutrition_lookup

    monkeypatch.setattr(nutrition_lookup, "lookup_barcode_nutrition", lambda code, prefer_uk=True: {
        "label": "Tesco Basil 30g", "calories": 23, "protein": 3.2, "carbs": 2.7, "fat": 0.6, "source": "openfoodfacts"})
    app = FastAPI()
    app.include_router(nutrition.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
    r = TestClient(app).get("/api/nutrition/barcode/5000-1234")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["product_name"] == "Tesco Basil 30g" and data["barcode"] == "50001234"
    assert data["per_100g"]["calories"] == 23 and data["per_100g"]["protein"] == 3.2
