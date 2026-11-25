"""Recipe macros from one source: totals = sum(line macros) / servings for the Original, every
version and the Low FODMAP option; line macros are AI estimates cached per normalised line."""
import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.recipe_fields import normalize_adaptations  # noqa: E402

PASTA = {"amount": "500", "unit": "g", "name": "dried pasta"}
GARLIC = {"amount": "2", "unit": "cloves", "name": "garlic"}
OIL = {"amount": "125", "unit": "ml", "name": "olive oil"}
TOFU = {"amount": "450", "unit": "g", "name": "tofu"}

# What the (mocked) AI answers per line.
TABLE = {
    "500 g dried pasta": {"p": 60, "c": 350, "f": 7, "cal": 1750},
    "2 cloves garlic": {"p": 0, "c": 2, "f": 0, "cal": 9},
    "2 cloves garlic-infused oil": {"p": 0, "c": 0, "f": 9, "cal": 80},
    "125 ml olive oil": {"p": 0, "c": 0, "f": 115, "cal": 1035},
    "450 g tofu": {"p": 36, "c": 9, "f": 21, "cal": 360},
    "225 g tofu": {"p": 18, "c": 4, "f": 10, "cal": 180},
    "100 g onion": {"p": 1, "c": 9, "f": 0, "cal": 40},
    "100 g leek greens": {"p": 1, "c": 6, "f": 0, "cal": 30},
}


class FakeAI:
    def __init__(self, table=TABLE):
        self.table = table
        self.calls = []  # list of line lists sent

    async def __call__(self, client, system, prompt, user_id=None, **kw):
        lines = []
        for row in prompt.split("\n"):
            head, _, rest = row.partition(". ")
            if head.isdigit() and rest:
                lines.append(rest)
        self.calls.append(lines)
        # Every answer carries the line's weight too ("g"), as the prompt now asks.
        return json.dumps({"items": [{**self.table.get(l.lower(), {"p": 1, "c": 1, "f": 1, "cal": 10}), "g": 100}
                                     for l in lines]})


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.reads = 0

    async def get_many(self, keys):
        self.reads += 1
        return {k: self.rows[k] for k in keys if k in self.rows}

    async def put_many(self, values, model=""):
        self.rows.update(values)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    import dependencies
    from services import line_macros

    ai = FakeAI()
    store = MemoryStore()
    monkeypatch.setattr(dependencies, "call_llm", ai)
    monkeypatch.setattr(line_macros, "store", store)
    # These tests cover the AI / cache mechanics: the food-database-first path is switched off
    # here and covered in test_line_macros_db.py.
    monkeypatch.setattr(line_macros, "DB_FIRST", False)
    line_macros._MEMORY.clear()
    line_macros._DB_SAVED.clear()
    yield ai, store
    line_macros._MEMORY.clear()
    line_macros._DB_SAVED.clear()


@pytest.fixture
def ai(_isolated):
    return _isolated[0]


@pytest.fixture
def store(_isolated):
    return _isolated[1]


def _recipe(**over):
    base = {
        "id": "r1",
        "title": "Pesto Pasta",
        "servings": 4,
        "nutrition_calories": 566,
        "nutrition_protein": 20,
        "nutrition_carbs": 70,
        "nutrition_fat": 22,
        "ingredients": [PASTA, GARLIC, OIL],
        "adaptations": {
            "low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}]},
            "versions": [
                {"name": "Lemon Pepper Tofu", "ingredients": [PASTA, GARLIC, OIL, TOFU], "instructions": ["Cook"]},
            ],
        },
    }
    base.update(over)
    return base


def _run(coro):
    return asyncio.run(coro)


def _ai(badge):
    """A line macro as returned / stored for an AI estimate (provenance src="ai", AI grams)."""
    return {**badge, "src": "ai", "g": 100.0, "g_src": "ai"}


def _ai_no_grams(badge):
    """An AI estimate without a weight (cache rows / replies from before grams were asked for)."""
    return {**badge, "src": "ai"}


def _sum(*keys):
    return sum(TABLE[k]["cal"] for k in keys)


# --- line macro helper ---------------------------------------------------------------------

def test_estimate_line_macros_uses_ai_then_cache(ai, store):
    from services.line_macros import estimate_line_macros

    out = _run(estimate_line_macros([PASTA, OIL, "500 g  Dried Pasta."]))
    assert out[0] == _ai(TABLE["500 g dried pasta"]) and out[1] == _ai(TABLE["125 ml olive oil"])
    assert out[2] == out[0]  # same normalised line
    assert len(ai.calls) == 1 and len(ai.calls[0]) == 2  # duplicates sent once
    assert set(store.rows) == {"500 g dried pasta", "125 ml olive oil"}
    again = _run(estimate_line_macros([OIL, PASTA]))
    assert again == [_ai(TABLE["125 ml olive oil"]), _ai(TABLE["500 g dried pasta"])]
    assert len(ai.calls) == 1  # memory cache hit


def test_db_cache_hit_skips_ai(ai, store):
    from services import line_macros

    store.rows["450 g tofu"] = {"p": 1, "c": 2, "f": 3, "cal": 99}
    out = _run(line_macros.estimate_line_macros([TOFU]))
    assert out == [_ai_no_grams({"p": 1, "c": 2, "f": 3, "cal": 99})] and ai.calls == []  # old rows: src "ai"


def test_cache_only_mode_never_calls_ai(ai):
    from services.line_macros import estimate_line_macros

    assert _run(estimate_line_macros([PASTA], allow_ai=False)) == [None]
    assert ai.calls == []


def test_batches_are_at_most_40_lines(ai):
    from services.line_macros import estimate_line_macros

    lines = [f"{i} g sugar" for i in range(1, 96)]
    out = _run(estimate_line_macros(lines))
    assert all(o is not None for o in out)
    assert sorted(len(c) for c in ai.calls) == [15, 40, 40]


def test_misaligned_reply_is_rejected_then_retried_in_halves(monkeypatch):
    import dependencies
    from services.line_macros import estimate_line_macros

    calls = []

    async def flaky(client, system, prompt, user_id=None, **kw):
        n = sum(1 for row in prompt.split("\n") if row.partition(". ")[0].isdigit())
        calls.append(n)
        items = [{"p": 1, "c": 1, "f": 1, "cal": 10}] * (n if len(calls) > 1 else n - 1)
        return json.dumps({"items": items})

    monkeypatch.setattr(dependencies, "call_llm", flaky)
    out = _run(estimate_line_macros(["1 egg", "2 eggs", "3 eggs", "4 eggs"]))
    assert calls == [4, 2, 2] and all(o == _ai_no_grams({"p": 1, "c": 1, "f": 1, "cal": 10}) for o in out)


def test_ai_failure_returns_none(monkeypatch):
    import dependencies
    from services.line_macros import estimate_line_macros

    async def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(dependencies, "call_llm", boom)
    assert _run(estimate_line_macros([PASTA])) == [None]


def test_clamps_bad_values(monkeypatch):
    import dependencies
    from services.line_macros import estimate_line_macros

    async def wild(*a, **k):
        return json.dumps({"items": [{"p": -4, "c": "12.6", "f": 1500, "cal": 99999}]})

    monkeypatch.setattr(dependencies, "call_llm", wild)
    assert _run(estimate_line_macros([PASTA])) == [_ai_no_grams({"p": 0, "c": 13, "f": 0, "cal": 0})]


def test_prompt_has_vague_amount_guidance():
    from services.line_macros import build_user_prompt

    prompt = build_user_prompt(["drizzle light-flavoured vegetable oil"]).lower()
    for phrase in ("drizzle = about 1 tbsp", "splash = about 1 tbsp", "pinch = ~0", "handful = about 30 g",
                   "to taste", "as needed", "never assume 100 g"):
        assert phrase in prompt
    assert "exactly 1 items" in prompt


def test_uses_the_big_model_on_cloud(monkeypatch):
    import dependencies
    from config import settings
    from services import line_macros

    seen = {}

    async def spy(client, system, prompt, user_id=None, **kw):
        seen.update(kw)
        return json.dumps({"items": [{"p": 1, "c": 1, "f": 1, "cal": 10}]})

    monkeypatch.setattr(dependencies, "call_llm", spy)
    monkeypatch.setattr(settings, "is_cloud", True)
    _run(line_macros.estimate_line_macros(["1 apple"]))
    assert seen["ollama_model_override"] == line_macros.LINE_MACROS_MODEL == "gpt-oss:120b"
    assert seen["format_json"] is True
    monkeypatch.setattr(settings, "is_cloud", False)
    line_macros._MEMORY.clear()
    _run(line_macros.estimate_line_macros(["1 pear"]))
    assert seen["ollama_model_override"] is None  # self-host: the configured model


# --- totals -----------------------------------------------------------------------------------

def test_totals_are_the_line_sum_over_servings():
    from services.version_macros import refresh_recipe_macros

    result = _run(refresh_recipe_macros(_recipe()))
    f = result["fields"]
    assert result["complete"] is True
    # Pesto Pasta: 1750 + 9 + 1035 = 2794 kcal / 4 servings = 698.5 -> 698 (not the AI-guessed 566)
    assert f["nutrition_calories"] == round(_sum("500 g dried pasta", "2 cloves garlic", "125 ml olive oil") / 4)
    assert f["nutrition_fat"] == round((7 + 0 + 115) / 4)
    assert f["ingredient_macros"] == [_ai(TABLE["500 g dried pasta"]), _ai(TABLE["2 cloves garlic"]), _ai(TABLE["125 ml olive oil"])]


def test_versions_and_low_fodmap_follow_the_same_rule():
    from services.version_macros import choice_macros, refresh_recipe_macros

    recipe = _recipe()
    recipe.update(_run(refresh_recipe_macros(recipe))["fields"])
    ad = recipe["adaptations"]
    v = ad["versions"][0]
    assert v["nutrition"]["calories"] == round(_sum("500 g dried pasta", "2 cloves garlic", "125 ml olive oil", "450 g tofu") / 4)
    assert sum(b["cal"] for b in v["ingredient_macros"]) == _sum("500 g dried pasta", "2 cloves garlic", "125 ml olive oil", "450 g tofu")
    lf = v["low_fodmap_macros"]
    assert lf["ingredient_macros"][1] == _ai(TABLE["2 cloves garlic-infused oil"])
    assert lf["nutrition"]["calories"] == round(
        _sum("500 g dried pasta", "2 cloves garlic-infused oil", "125 ml olive oil", "450 g tofu") / 4)
    orig_lf = ad["low_fodmap_macros"]
    assert orig_lf["nutrition"]["calories"] == round(
        _sum("500 g dried pasta", "2 cloves garlic-infused oil", "125 ml olive oil") / 4)
    assert "nutrition_estimated" not in v["nutrition"]  # no "est." anchoring flag any more
    assert choice_macros(recipe, "lemon pepper tofu", True) == lf
    assert choice_macros(recipe, None, True)["nutrition"] == orig_lf["nutrition"]
    assert choice_macros(recipe, None, False) is None


def test_badges_always_add_up_to_the_totals():
    from services.version_macros import refresh_recipe_macros

    recipe = _recipe(servings=3)
    fields = _run(refresh_recipe_macros(recipe))["fields"]
    lists = [(fields["ingredient_macros"], {k: fields[f"nutrition_{k}"] for k in ("calories", "protein", "carbs", "fat")})]
    for v in fields["adaptations"]["versions"]:
        lists.append((v["ingredient_macros"], v["nutrition"]))
        lists.append((v["low_fodmap_macros"]["ingredient_macros"], v["low_fodmap_macros"]["nutrition"]))
    lf = fields["adaptations"]["low_fodmap_macros"]
    lists.append((lf["ingredient_macros"], lf["nutrition"]))
    for badges, totals in lists:
        for short, name in (("cal", "calories"), ("p", "protein"), ("c", "carbs"), ("f", "fat")):
            assert totals[name] == round(sum(b[short] for b in badges) / 3)


def test_identical_lines_across_lists_cost_one_ai_call(ai):
    from services.version_macros import refresh_recipe_macros

    _run(refresh_recipe_macros(_recipe()))
    sent = [line for call in ai.calls for line in call]
    assert len(sent) == len(set(sent)) == 5  # pasta, garlic, oil, tofu, garlic-infused oil
    ai.calls.clear()
    _run(refresh_recipe_macros(_recipe(id="r2", title="Another")))
    assert ai.calls == []


def test_cache_only_save_keeps_unchanged_and_drops_stale_versions():
    from services.version_macros import refresh_recipe_macros

    recipe = _recipe()
    stored = _run(refresh_recipe_macros(recipe))["fields"]["adaptations"]
    from services import line_macros

    line_macros._MEMORY.clear()
    line_macros.store.rows.clear()  # nothing cached any more
    # Same inputs (edit form sends versions without macros) -> carried over from `previous`.
    sent = {"low_fodmap": stored["low_fodmap"], "versions": [
        {"name": "Lemon Pepper Tofu", "ingredients": [PASTA, GARLIC, OIL, TOFU], "instructions": ["Cook"]},
    ]}
    out = _run(refresh_recipe_macros({**recipe, "adaptations": sent}, stored, allow_ai=False))
    assert out["fields"]["adaptations"]["versions"][0]["nutrition"] == stored["versions"][0]["nutrition"]
    assert out["fields"]["adaptations"]["low_fodmap_macros"] == stored["low_fodmap_macros"]
    assert "ingredient_macros" not in out["fields"] and out["complete"] is False
    # Edited list, nothing cached -> pending (no stale numbers), filled later.
    edited = {**sent, "versions": [{**sent["versions"][0], "ingredients": [PASTA, dict(TOFU, amount="225")]}]}
    out = _run(refresh_recipe_macros({**recipe, "adaptations": edited}, stored, allow_ai=False))
    assert "nutrition" not in out["fields"]["adaptations"]["versions"][0]


def test_existing_original_badges_are_reused_without_ai(ai):
    from services.version_macros import macros_consistent, refresh_recipe_macros

    # Pesto Pasta as imported: sensible AI badges (3274 kcal) but a separate 566 kcal/serving guess.
    badges = [{"p": 60, "c": 350, "f": 7, "cal": 1750}, {"p": 0, "c": 2, "f": 0, "cal": 9},
              {"p": 0, "c": 0, "f": 115, "cal": 1515}]
    recipe = _recipe(ingredient_macros=json.dumps(badges), adaptations=None)
    assert not macros_consistent(recipe)
    result = _run(refresh_recipe_macros(recipe))
    assert ai.calls == []
    assert result["fields"]["ingredient_macros"] == [{**b, "src": "ai"} for b in badges]  # kept, marked as AI
    assert result["fields"]["nutrition_calories"] == round(3274 / 4)  # 818, what the badges add up to
    # Saved before grams were estimated: not consistent until the weights are filled in, which
    # costs one weights-only AI call and never changes the macros.
    assert not macros_consistent({**recipe, **result["fields"]})
    filled = _run(refresh_recipe_macros(recipe, fill_weights=True))
    assert len(ai.calls) == 1 and len(ai.calls[0]) == 3
    assert filled["fields"]["ingredient_macros"] == [_ai(b) for b in badges]
    assert filled["fields"]["nutrition_calories"] == round(3274 / 4)
    assert macros_consistent({**recipe, **filled["fields"]})


def test_servings_change_recomputes():
    from services.version_macros import refresh_recipe_macros

    four = _run(refresh_recipe_macros(_recipe()))["fields"]
    two = _run(refresh_recipe_macros(_recipe(servings=2), four["adaptations"]))["fields"]
    assert abs(two["nutrition_calories"] - 2 * four["nutrition_calories"]) <= 1
    assert two["adaptations"]["versions"][0]["macros_sig"] != four["adaptations"]["versions"][0]["macros_sig"]


def test_old_food_db_version_macros_are_replaced():
    from services.version_macros import macros_consistent, refresh_recipe_macros

    recipe = _recipe()
    recipe["adaptations"]["versions"][0].update({
        "nutrition": {"calories": 900, "protein": 1, "carbs": 1, "fat": 1, "nutrition_estimated": True},
        "macros_sig": "0123456789abcdef",
    })
    assert not macros_consistent(recipe)
    fields = _run(refresh_recipe_macros(recipe))["fields"]
    assert fields["adaptations"]["versions"][0]["nutrition"]["calories"] != 900
    assert macros_consistent({**recipe, **fields})


def test_blank_lines_stay_index_aligned():
    from services.version_macros import refresh_recipe_macros

    recipe = _recipe(ingredients=[PASTA, {"amount": "", "unit": "", "name": ""}, OIL], adaptations=None)
    f = _run(refresh_recipe_macros(recipe))["fields"]
    assert len(f["ingredient_macros"]) == 3 and f["ingredient_macros"][1] == {"p": 0, "c": 0, "f": 0, "cal": 0}


def test_totals_match_tolerance():
    from services.version_macros import totals_match

    want = {"calories": 700, "protein": 15, "carbs": 88, "fat": 31}
    assert totals_match({"calories": 730, "protein": 15, "carbs": 90, "fat": 31}, want)
    assert not totals_match({"calories": 566, "protein": 15, "carbs": 88, "fat": 31}, want)
    assert not totals_match({"calories": None, "protein": 15, "carbs": 88, "fat": 31}, want)


# --- plausibility -----------------------------------------------------------------------------

def test_plausibility_flags():
    from services.macro_plausibility import check_line, check_totals

    assert check_line("100 g butter", {"cal": 1200})  # 12 kcal/g
    assert not check_line("100 g butter", {"cal": 717})
    assert check_line("drizzle light-flavoured vegetable oil", {"cal": 884})
    assert not check_line("drizzle light-flavoured vegetable oil", {"cal": 120})
    assert check_line("400 g firm tofu", {"cal": 0})
    assert check_line("2 tbsp sugar", {"cal": 0})
    assert not check_line("salt to taste", {"cal": 0})
    assert not check_line("500 ml water", {"cal": 0})
    assert not check_line("pinch of sugar", {"cal": 0})  # vague: 0 is fine
    assert check_totals({"calories": 2400})
    assert check_totals({"calories": 10})
    assert not check_totals({"calories": 650})


def test_plausibility_flags_for_a_recipe(monkeypatch):
    from services.version_macros import plausibility_flags

    table = {"500 g dried pasta": {"p": 60, "c": 350, "f": 7, "cal": 1750},
             "drizzle olive oil": {"p": 0, "c": 0, "f": 100, "cal": 884},
             "400 g tofu": {"p": 0, "c": 0, "f": 0, "cal": 0}}
    from services.line_macros import ingredient_line, normalize_line

    recipe = {"id": "r9", "title": "Bad", "servings": 2,
              "ingredients": [PASTA, {"amount": "", "unit": "", "name": "drizzle olive oil"},
                              {"amount": "400", "unit": "g", "name": "tofu"}]}
    flags = plausibility_flags(recipe, lambda ing: table.get(normalize_line(ingredient_line(ing))))
    reasons = {(f["line"], f["reason"].split(" ")[0]) for f in flags}
    assert ("drizzle olive oil", "vague") in reasons
    assert any(f["line"] == "400 g tofu" and "0 kcal" in f["reason"] for f in flags)
    assert all(f["recipe_id"] == "r9" and f["list"] == "Original" for f in flags)


# --- normalisation (unchanged contract) ---------------------------------------------------------

def test_normalize_keeps_numbers_only_and_caps_badges():
    value = {
        "low_fodmap": {"swaps": [{"from": "garlic", "to": "oil"}]},
        "low_fodmap_macros": {"nutrition": {"calories": "500", "protein": 20.6, "evil": "<x>"},
                              "ingredient_macros": [{"p": 1, "c": 2, "f": 3, "cal": 40}], "macros_sig": "abc123"},
        "versions": [{
            "name": "Tofu", "ingredients": [{"name": "tofu", "amount": "1", "unit": ""}], "instructions": ["x"],
            "nutrition": {"calories": "nope", "protein": -5, "carbs": 10, "fat": 1e9, "nutrition_estimated": True},
            "ingredient_macros": [{"p": "7", "c": None, "f": 2, "cal": 99999}, {"p": 1, "c": 1, "f": 1, "cal": 1}],
            "macros_sig": "bad sig with spaces", "ingredients_sig": "0123abcd",
            "low_fodmap_macros": {"nutrition": {}, "ingredient_macros": []},
        }],
    }
    out = normalize_adaptations(value)
    assert out["low_fodmap_macros"] == {"nutrition": {"calories": 500, "protein": 21},
                                        "ingredient_macros": [{"p": 1, "c": 2, "f": 3, "cal": 40}], "macros_sig": "abc123"}
    v = out["versions"][0]
    assert v["nutrition"] == {"carbs": 10, "fat": 100000, "nutrition_estimated": True}
    assert v["ingredient_macros"] == [{"p": 7, "c": 0, "f": 2, "cal": 10000}]
    assert "macros_sig" not in v and v["ingredients_sig"] == "0123abcd"
    assert "low_fodmap_macros" not in v


def test_plain_versions_still_round_trip_unchanged():
    versions = [{"name": "Pomegranate", "ingredients": [{"name": "pomegranate", "amount": "1", "unit": ""}],
                 "instructions": ["Scatter"], "notes": "Best fresh"}]
    assert normalize_adaptations({"versions": versions}) == {"versions": versions}


# --- endpoints ---------------------------------------------------------------------------------

class FakeRepo:
    def __init__(self, rows):
        self.rows = {r["id"]: dict(r) for r in rows}
        self.updates = []

    async def find_by_author(self, author_id, limit=500):
        self.author = author_id
        return [dict(r) for r in self.rows.values()]

    async def find_by_id(self, recipe_id):
        r = self.rows.get(recipe_id)
        return dict(r) if r else None

    async def update_recipe(self, recipe_id, data):
        self.updates.append((recipe_id, data))
        self.rows[recipe_id].update(data)
        return 1


def test_backfill_fixes_mismatched_totals_and_is_idempotent(monkeypatch, ai):
    import routers.recipes as recipes_router
    from services.version_macros import macros_consistent

    good = _recipe(id="good")
    good.update(_run(recipes_router.refresh_recipe_macros(good))["fields"])
    ai.calls.clear()
    bad_totals = dict(good, id="bad", nutrition_calories=566)  # badges say 698
    no_badges = _recipe(id="none", ingredient_macros=None,
                        ingredients=[PASTA, {"amount": "", "unit": "", "name": "drizzle olive oil"}], adaptations=None)
    repo = FakeRepo([good, bad_totals, no_badges, {"id": "empty", "ingredients": [], "adaptations": None}])
    monkeypatch.setattr(recipes_router, "recipe_repository", repo)
    out = _run(recipes_router.backfill_macros(user={"id": "u1"}))
    assert repo.author == "u1"
    assert out["scanned"] == 4 and out["updated"] == 2 and out["remaining"] == 0 and out["incomplete"] == 0
    assert set(out["recipe_ids"]) == {"bad", "none"}
    assert repo.rows["bad"]["nutrition_calories"] == good["nutrition_calories"]
    assert all(macros_consistent(r) for r in repo.rows.values())
    assert all("updated_at" in data for _, data in repo.updates)
    assert isinstance(out["flagged"], list)
    # Second run: nothing to do, no AI.
    ai.calls.clear()
    again = _run(recipes_router.backfill_macros(user={"id": "u1"}))
    assert again["updated"] == 0 and again["remaining"] == 0 and ai.calls == []
    # Old name still works.
    alias = _run(recipes_router.backfill_version_macros(user={"id": "u1"}))
    assert alias["updated"] == 0


def test_backfill_reports_flags(monkeypatch):
    import routers.recipes as recipes_router
    from services import line_macros

    line_macros.store.rows["drizzle olive oil"] = {"p": 0, "c": 0, "f": 100, "cal": 884}
    row = _recipe(id="oily", ingredients=[{"amount": "", "unit": "", "name": "drizzle olive oil"}], adaptations=None)
    monkeypatch.setattr(recipes_router, "recipe_repository", FakeRepo([row]))
    out = _run(recipes_router.backfill_macros(user={"id": "u1"}))
    assert any(f["recipe_id"] == "oily" and f["line"] == "drizzle olive oil" for f in out["flagged"])


def test_backfill_time_box_leaves_remaining(monkeypatch):
    import routers.recipes as recipes_router

    monkeypatch.setattr(recipes_router, "BACKFILL_SECONDS", 0)
    monkeypatch.setattr(recipes_router, "recipe_repository", FakeRepo([_recipe(id="a"), _recipe(id="b")]))
    out = _run(recipes_router.backfill_macros(user={"id": "u1"}))
    assert out["updated"] == 0 and out["remaining"] == 2


def test_ingredient_macros_endpoint_writes_totals(monkeypatch):
    import routers.recipes as recipes_router
    from fastapi import HTTPException

    row = _recipe()
    repo = FakeRepo([row])
    monkeypatch.setattr(recipes_router, "recipe_repository", repo)
    monkeypatch.setattr(recipes_router, "require_recipe_view", lambda user, recipe: None)
    monkeypatch.setattr(recipes_router, "is_premium_user", lambda user: user.get("pro", False))

    class Req:
        class app:
            class state:
                http_client = None

    with pytest.raises(HTTPException) as e:
        _run(recipes_router.get_ingredient_macros("r1", Req(), user={"id": "u1"}))
    assert e.value.status_code == 403
    out = _run(recipes_router.get_ingredient_macros("r1", Req(), user={"id": "u1", "pro": True}))
    assert len(out["ingredient_macros"]) == 3
    assert out["nutrition"]["calories"] == round(sum(b["cal"] for b in out["ingredient_macros"]) / 4)
    stored = repo.rows["r1"]
    assert stored["nutrition_calories"] == out["nutrition"]["calories"]
    assert stored["adaptations"]["versions"][0]["nutrition"]["calories"] > out["nutrition"]["calories"]
    # Cached badges + drifted totals -> totals corrected without AI.
    repo.rows["r1"]["nutrition_calories"] = 566
    again = _run(recipes_router.get_ingredient_macros("r1", Req(), user={"id": "u1", "pro": True}))
    assert again["ingredient_macros"] == out["ingredient_macros"]
    assert repo.rows["r1"]["nutrition_calories"] == out["nutrition"]["calories"]


def test_macros_preview_computes_and_gates_badges(monkeypatch):
    import routers.recipes as recipes_router

    repo = FakeRepo([_recipe()])
    monkeypatch.setattr(recipes_router, "recipe_repository", repo)
    monkeypatch.setattr(recipes_router, "require_recipe_view", lambda user, recipe: None)
    monkeypatch.setattr(recipes_router, "is_premium_user", lambda user: user.get("pro", False))
    body = recipes_router.MacrosPreviewRequest(version="Lemon Pepper Tofu", low_fodmap=False)
    free = _run(recipes_router.macros_preview("r1", body, user={"id": "u1"}))
    expected = round(_sum("500 g dried pasta", "2 cloves garlic", "125 ml olive oil", "450 g tofu") / 4)
    assert free["nutrition"]["calories"] == expected and free["ingredient_macros"] == []
    assert repo.rows["r1"]["adaptations"]["versions"][0]["macros_sig"]  # persisted
    pro = _run(recipes_router.macros_preview("r1", body, user={"id": "u1", "pro": True}))
    assert len(pro["ingredient_macros"]) == 4


def test_save_and_import_paths_compute_macros():
    here = os.path.dirname(__file__)
    src = open(os.path.join(here, "..", "routers", "recipes.py"), encoding="utf-8").read()
    update = src[src.index("async def update_recipe("):src.index("await recipe_repository.update_recipe(recipe_id, update_data)")]
    assert "refresh_recipe_macros" in update and 'update_data["ingredient_macros"] = None' in update
    create = src[src.index("async def create_recipe("):src.index("await recipe_repository.create(recipe_doc)")]
    assert "refresh_recipe_macros" in create
    ai_src = open(os.path.join(here, "..", "routers", "ai.py"), encoding="utf-8").read()
    pdf = ai_src[ai_src.index("async def _import_recipes_from_pdf_text("):ai_src.index("class DriveImportRequest")]
    assert "refresh_recipe_macros" in pdf and "schedule_recipe_macros" in pdf


def test_background_fill_saves_and_skips_unchanged(monkeypatch):
    import dependencies
    from services import recipe_macros_jobs

    repo = FakeRepo([_recipe()])
    monkeypatch.setattr(dependencies, "recipe_repository", repo)
    assert _run(recipe_macros_jobs.fill_recipe_macros("r1")) is True
    assert repo.rows["r1"]["nutrition_calories"] == round(
        _sum("500 g dried pasta", "2 cloves garlic", "125 ml olive oil") / 4)
    assert _run(recipe_macros_jobs.fill_recipe_macros("r1")) is False  # nothing changed
    assert _run(recipe_macros_jobs.fill_recipe_macros("missing")) is False


def test_pdf_fold_keeps_each_versions_printed_macros():
    from services.recipe_pdf_import import fold_recipe_versions

    recipes = [
        {"title": "Pesto Pasta", "ingredients": [PASTA], "instructions": ["Boil"],
         "nutrition": {"calories": 566, "protein": 20, "carbs": 70, "fat": 22}},
        {"title": "Pesto Pasta — Lemon Pepper Tofu", "ingredients": [PASTA, TOFU], "instructions": ["Boil", "Fry"],
         "nutrition": {"calories": 700, "protein": 40, "carbs": 72, "fat": 30}},
    ]
    folded = fold_recipe_versions(recipes)
    assert len(folded) == 1
    assert folded[0]["adaptations"]["versions"][0]["nutrition"]["calories"] == 700
