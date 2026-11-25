"""Line macros: food database first (concrete amount + confident offline match), AI fallback for
vague / unknown lines, provenance stored and passed through, database answers beat cached AI."""
import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeAI:
    def __init__(self):
        self.calls = []

    async def __call__(self, client, system, prompt, user_id=None, **kw):
        lines = []
        for row in prompt.split("\n"):
            head, _, rest = row.partition(". ")
            if head.isdigit() and rest:
                lines.append(rest)
        self.calls.append(lines)
        return json.dumps({"items": [{"p": 1, "c": 1, "f": 1, "cal": 11, "g": 15} for _ in lines]})


class UpsertStore:
    """Same rules as the SQL: an AI row never replaces a row unless that row came from the
    database; a database row replaces anything."""

    def __init__(self):
        self.rows = {}

    async def get_many(self, keys):
        return {k: dict(self.rows[k]) for k in keys if k in self.rows}

    async def put_many(self, values, model=""):
        for k, v in values.items():
            old = self.rows.get(k)
            if old is None or v.get("src") == "db" or old.get("src") == "db":
                self.rows[k] = dict(v)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    import dependencies
    from services import line_macros

    ai = FakeAI()
    store = UpsertStore()
    monkeypatch.setattr(dependencies, "call_llm", ai)
    monkeypatch.setattr(line_macros, "store", store)
    monkeypatch.setattr(line_macros, "DB_FIRST", True)
    line_macros._MEMORY.clear()
    line_macros._DB_SAVED.clear()
    yield ai, store
    line_macros._MEMORY.clear()
    line_macros._DB_SAVED.clear()


TOFU_FOOD = "Firm tofu, UK supermarket average"  # utils/uk_labels.py (label median)


def _run(coro):
    return asyncio.run(coro)


# --- amount -> grams -> macros ------------------------------------------------------------------

@pytest.mark.parametrize("line, kcal, tol, grams", [
    ("500 g gluten-free pasta", 1785, 10, 500),
    ("450 g firm tofu", 562, 15, 450),            # UK label median 125 kcal / 100 g
    ("2 tbsp olive oil", 240, 15, 27.6),          # 30 ml x 0.92 g/ml
    ("1 garlic clove", 4, 1, 3),
    ("2 cloves garlic, minced", 6, 1, 6),         # CoFID raw garlic 98 kcal / 100 g
    ("125 ml extra-virgin olive oil", 1015, 15, 115),
    ("75 g almonds", 416, 5, 75),                 # CoFID whole almonds 554 kcal / 100 g
    ("2 eggs", 143, 20, 100),
    ("2 large eggs", 143, 20, 100),
    ("1 lemon", 17, 3, 58),
    ("300 ml milk", 138, 10, 300),                 # water-like liquid: 1 g/ml
    ("1 cup plain flour", 460, 20, 127.2),         # ~125 g per cup
    ("1 can (400g) chickpeas, drained", 290, 20, 240),  # UK label median, tinned + drained
    ("500g basmati rice", 1755, 30, 500),
    ("335 g unscented coconut oil (deodorised), melted", 2888, 10, 335),  # AI said 0 in production
    ("1 kg plain flour", 3640, 20, 1000),
])
def test_concrete_lines_resolve_from_the_database(line, kcal, tol, grams):
    from services.line_macros import resolve_line_from_db

    hit = resolve_line_from_db(line)
    assert hit is not None, line
    assert abs(hit["cal"] - kcal) <= tol, (line, hit)
    assert abs(hit["g"] - grams) <= 0.5, (line, hit)
    assert hit["src"] == "db" and hit["food"] and hit["source"]
    assert all(isinstance(hit[k], int) for k in ("p", "c", "f", "cal"))


def test_provenance_names_the_dataset_food():
    from services.line_macros import resolve_line_from_db

    pasta = resolve_line_from_db("500 g gluten-free pasta")
    assert pasta["source"] == "usda_sr" and pasta["source_id"] and pasta["food"].startswith("Pasta, gluten-free")
    tofu = resolve_line_from_db("450 g firm tofu")
    assert tofu["source"] == "uk_labels" and tofu["food"] == TOFU_FOOD


@pytest.mark.parametrize("line", [
    "drizzle of olive oil",
    "handful of spinach",
    "pinch of chilli flakes",
    "salt and pepper",           # pepper is not zero
    "1-2 tbsp olive oil",         # range
    "2 x 400g tins chopped tomatoes",
    "1 tin chopped tomatoes",     # container without a weight
    "2 cherry tomatoes",          # not a 'tomato'-sized piece
    "juice of 1 lemon",
    "1 lemon, juiced",
    "1 tbsp chopped parsley",     # no sane volume -> grams
    "1 stock cube",
    "olive oil",                  # no amount
    "2 tbsp unicorn dust",        # unknown food
    "2 kg butter",                # beyond what a badge can show
])
def test_vague_unknown_or_unconvertible_lines_go_to_the_ai(line):
    from services.line_macros import resolve_line_from_db

    assert resolve_line_from_db(line) is None, line


@pytest.mark.parametrize("line", ["salt to taste", "1 tsp salt", "500 ml cold water", "sea salt"])
def test_water_and_salt_are_zero_from_the_database(line):
    from services.line_macros import resolve_line_from_db

    hit = resolve_line_from_db(line)
    assert hit is not None and hit["src"] == "db"
    assert (hit["p"], hit["c"], hit["f"], hit["cal"]) == (0, 0, 0, 0)


def test_mixed_list_sends_only_vague_lines_to_the_ai(env):
    ai, store = env
    from services.line_macros import estimate_line_macros

    lines = [{"amount": "450", "unit": "g", "name": "firm tofu"},
             {"amount": "", "unit": "", "name": "drizzle of olive oil"},
             "2 tbsp olive oil", "salt to taste", "handful of spinach"]
    out = _run(estimate_line_macros(lines))
    assert [o["src"] for o in out] == ["db", "ai", "db", "db", "ai"]
    assert ai.calls == [["drizzle of olive oil", "handful of spinach"]]
    assert out[0]["food"] == TOFU_FOOD and out[0]["g"] == 450.0
    # Provenance is stored in the cache table.
    row = store.rows["450 g firm tofu"]
    assert row["src"] == "db" and row["food"] == TOFU_FOOD and row["g"] == 450.0
    assert row["source"] == "uk_labels" and row["source_id"] == "firm tofu"
    assert store.rows["drizzle of olive oil"]["src"] == "ai"


def test_database_beats_a_cached_ai_row(env):
    ai, store = env
    from services.line_macros import estimate_line_macros

    store.rows["450 g firm tofu"] = {"p": 1, "c": 1, "f": 1, "cal": 999}  # old AI row (no provenance)
    out = _run(estimate_line_macros(["450 g firm tofu"]))
    assert out[0]["src"] == "db" and abs(out[0]["cal"] - 562) <= 15
    assert ai.calls == []
    assert store.rows["450 g firm tofu"]["src"] == "db"  # superseded in the table too
    # Cache-only mode (used on save) gets the database answer as well.
    from services import line_macros

    line_macros._MEMORY.clear()
    assert _run(estimate_line_macros(["450 g firm tofu"], allow_ai=False))[0]["src"] == "db"


def test_a_stale_database_row_is_not_trusted(env):
    ai, store = env
    from services.line_macros import estimate_line_macros

    # A row the food database wrote earlier, for a line it no longer answers.
    store.rows["drizzle of olive oil"] = {"p": 0, "c": 0, "f": 9, "cal": 80, "src": "db", "food": "Olive oil", "g": 9}
    out = _run(estimate_line_macros(["drizzle of olive oil"]))
    assert out[0]["src"] == "ai" and ai.calls == [["drizzle of olive oil"]]
    assert store.rows["drizzle of olive oil"]["src"] == "ai"  # AI may replace a database row


def test_database_results_are_written_once_per_process(env, monkeypatch):
    _ai, store = env
    from services import line_macros

    writes = []
    real = store.put_many

    async def spy(values, model=""):
        writes.append(dict(values))
        await real(values, model)

    monkeypatch.setattr(store, "put_many", spy)
    _run(line_macros.estimate_line_macros(["75 g almonds"]))
    _run(line_macros.estimate_line_macros(["75 g almonds"]))
    assert len(writes) == 1


def test_sql_upsert_lets_database_rows_win(monkeypatch):
    """The real store: database rows overwrite, AI rows only replace stale database rows."""
    from services import line_macros

    seen = {}

    class Conn:
        async def executemany(self, sql, rows):
            seen["sql"], seen["rows"] = sql, rows

        async def fetch(self, sql, keys):
            return [{"line_key": "75 g almonds", "protein": 16, "carbs": 16, "fat": 37, "calories": 434,
                     "method": "db", "food": "Almonds", "grams": 75.0, "source": "curated", "source_id": "almonds",
                     "carbs_total": 25},
                    {"line_key": "a drizzle", "protein": 0, "carbs": 0, "fat": 9, "calories": 80,
                     "method": None, "food": None, "grams": None, "source": None, "source_id": None}]

    class Pool:
        def acquire(self):
            conn = Conn()

            class Ctx:
                async def __aenter__(self):
                    return conn

                async def __aexit__(self, *a):
                    return False

            return Ctx()

    async def get_pool():
        return Pool()

    import database.connection as connection

    monkeypatch.setattr(connection, "get_pool", get_pool)
    st = line_macros._DbStore()
    _run(st.put_many({"75 g almonds": {"p": 16, "c": 16, "c_total": 25, "f": 37, "cal": 434, "src": "db", "food": "Almonds",
                                       "g": 75.0, "source": "curated", "source_id": "almonds"},
                      "a drizzle": {"p": 0, "c": 0, "f": 9, "cal": 80, "src": "ai"}}, "gpt-oss:120b"))
    assert "ON CONFLICT (line_key) DO UPDATE" in seen["sql"]
    assert "WHERE EXCLUDED.method = 'db' OR ingredient_line_macros.method = 'db'" in seen["sql"]
    rows = {r[0]: r for r in seen["rows"]}
    assert rows["75 g almonds"][5:] == ("food_db", "db", "Almonds", 75.0, "curated", "almonds", 25)
    assert rows["a drizzle"][5:] == ("gpt-oss:120b", "ai", None, None, None, None, None)
    assert "carbs_total = EXCLUDED.carbs_total" in seen["sql"]
    got = _run(st.get_many(["75 g almonds", "a drizzle"]))
    assert got["75 g almonds"]["src"] == "db" and got["75 g almonds"]["g"] == 75.0
    assert got["75 g almonds"]["c_total"] == 25  # US-basis carbs ride along; old rows have none
    assert got["a drizzle"] == {"p": 0, "c": 0, "f": 9, "cal": 80, "src": "ai"}


# --- recipes: provenance passes through, old badges are recomputed once -------------------------

TOFU = {"amount": "450", "unit": "g", "name": "firm tofu"}
OIL = {"amount": "2", "unit": "tbsp", "name": "olive oil"}
DRIZZLE = {"amount": "", "unit": "", "name": "drizzle of olive oil"}


def _recipe(**over):
    base = {"id": "r1", "title": "Tofu", "servings": 2, "ingredients": [TOFU, OIL, DRIZZLE],
            "nutrition_calories": 1, "nutrition_protein": 1, "nutrition_carbs": 1, "nutrition_fat": 1,
            "adaptations": {"versions": [{"name": "Extra tofu", "ingredients": [TOFU, TOFU, DRIZZLE],
                                          "instructions": ["Fry"]}]}}
    base.update(over)
    return base


def test_ingredient_macros_carry_provenance_and_add_up():
    from services.version_macros import macros_consistent, refresh_recipe_macros

    recipe = _recipe()
    fields = _run(refresh_recipe_macros(recipe))["fields"]
    badges = fields["ingredient_macros"]
    assert [b["src"] for b in badges] == ["db", "db", "ai"]
    assert badges[0]["food"] == TOFU_FOOD and badges[0]["g"] == 450.0 and badges[0]["source"] == "uk_labels"
    assert "source_id" not in badges[0]  # kept in the cache table, not on every recipe
    assert fields["nutrition_calories"] == round(sum(b["cal"] for b in badges) / 2)
    version = fields["adaptations"]["versions"][0]
    assert [b["src"] for b in version["ingredient_macros"]] == ["db", "db", "ai"]
    assert macros_consistent({**recipe, **fields})


def test_normalize_adaptations_keeps_provenance_and_drops_junk():
    from utils.recipe_fields import normalize_adaptations, normalize_ingredient_macros

    out = normalize_ingredient_macros([
        {"p": 36, "c": 9, "f": 21, "cal": 648, "src": "db", "food": "  Firm   tofu ", "g": 450, "source": "curated",
         "source_id": "firm tofu", "evil": "<script>"},
        {"p": 1, "c": 1, "f": 1, "cal": 10, "src": "ai", "food": "ignored for ai"},
        {"p": 1, "c": 1, "f": 1, "cal": 10, "src": "<b>", "g": "lots"},
        {"p": 1, "c": 1, "f": 1, "cal": 10, "src": "db", "g": -5, "source": "Bad Source!"},
    ])
    assert out == [
        {"p": 36, "c": 9, "f": 21, "cal": 648, "src": "db", "g": 450.0, "g_src": "db", "food": "Firm tofu",
         "source": "curated"},
        {"p": 1, "c": 1, "f": 1, "cal": 10, "src": "ai"},
        {"p": 1, "c": 1, "f": 1, "cal": 10},
        {"p": 1, "c": 1, "f": 1, "cal": 10, "src": "db"},
    ]
    ad = normalize_adaptations({"versions": [{"name": "V", "ingredients": [TOFU], "instructions": ["x"],
                                              "nutrition": {"calories": 324},
                                              "ingredient_macros": [out[0]]}]})
    assert ad["versions"][0]["ingredient_macros"] == [out[0]]


def test_old_ai_badges_on_database_lines_are_recomputed_once(monkeypatch, env):
    ai, _store = env
    import routers.recipes as recipes_router
    from services.version_macros import macros_consistent

    old = [{"p": 1, "c": 1, "f": 1, "cal": 999}, {"p": 0, "c": 0, "f": 28, "cal": 250},
           {"p": 0, "c": 0, "f": 14, "cal": 120}]  # saved before provenance existed
    row = _recipe(ingredient_macros=json.dumps(old), adaptations=None,
                  nutrition_calories=round(sum(b["cal"] for b in old) / 2), nutrition_protein=1,
                  nutrition_carbs=1, nutrition_fat=round(43 / 2))
    assert not macros_consistent(row)

    class Repo:
        def __init__(self, rows):
            self.rows = {r["id"]: dict(r) for r in rows}

        async def find_by_author(self, author_id, limit=500):
            return [dict(r) for r in self.rows.values()]

        async def update_recipe(self, recipe_id, data):
            self.rows[recipe_id].update(data)
            return 1

    repo = Repo([row])
    monkeypatch.setattr(recipes_router, "recipe_repository", repo)
    out = _run(recipes_router.backfill_macros(user={"id": "u1"}))
    assert out["updated"] == 1 and out["remaining"] == 0
    badges = repo.rows["r1"]["ingredient_macros"]
    # Firm tofu now comes from UK supermarket labels (125 kcal/100 g x 450 g).
    assert badges[0]["src"] == "db" and abs(badges[0]["cal"] - 562) <= 15  # the 999 AI guess is gone
    # Vague line: macros kept; only its weight is asked for (one weights-only AI call).
    assert badges[2] == {"p": 0, "c": 0, "f": 14, "cal": 120, "src": "ai", "g": 15.0, "g_src": "ai"}
    assert ai.calls == [["drizzle of olive oil"]]
    assert macros_consistent(repo.rows["r1"])
    again = _run(recipes_router.backfill_macros(user={"id": "u1"}))
    assert again["updated"] == 0 and again["remaining"] == 0


def test_ingredient_macros_endpoint_recomputes_badges_without_provenance(monkeypatch):
    import routers.recipes as recipes_router

    old = [{"p": 1, "c": 1, "f": 1, "cal": 999}, {"p": 0, "c": 0, "f": 28, "cal": 250},
           {"p": 0, "c": 0, "f": 14, "cal": 120}]
    rows = {"r1": _recipe(ingredient_macros=json.dumps(old), adaptations=None)}

    class Repo:
        async def find_by_id(self, recipe_id):
            return dict(rows[recipe_id])

        async def update_recipe(self, recipe_id, data):
            rows[recipe_id].update(data)
            return 1

    class Req:
        class app:
            class state:
                http_client = None

    monkeypatch.setattr(recipes_router, "recipe_repository", Repo())
    monkeypatch.setattr(recipes_router, "require_recipe_view", lambda user, recipe: None)
    monkeypatch.setattr(recipes_router, "is_premium_user", lambda user: True)
    out = _run(recipes_router.get_ingredient_macros("r1", Req(), user={"id": "u1"}))
    assert [b["src"] for b in out["ingredient_macros"]] == ["db", "db", "ai"]
    assert rows["r1"]["ingredient_macros"][0]["src"] == "db"


# --- plausibility report (production backfill false alarms) -----------------------------------

@pytest.mark.parametrize("line", [
    "1 tsp rice vinegar", "1 tsp salt", "1 tbsp tamari", "1/2 tsp liquid smoke", "1 tsp dried dill",
    "½ tsp vegetarian chicken stock powder", "2 tsp chicken stock powder", "200 ml vegan chicken broth",
    "Carrot Smoked Salmon: 1 tsp salt", "Carrot Smoked Salmon: salt",
])
def test_zero_kcal_small_amounts_and_flavourings_are_not_flagged(line):
    from services.macro_plausibility import check_line

    assert check_line(line, {"cal": 0}) == [], line


@pytest.mark.parametrize("line", [
    "335 g unscented coconut oil (deodorised), melted", "400 g firm tofu", "2 tbsp sugar", "100 g vegan butter",
])
def test_zero_kcal_for_real_amounts_is_still_flagged(line):
    from services.macro_plausibility import check_line

    assert any("0 kcal for a real quantity" in r for r in check_line(line, {"cal": 0})), line


def test_whole_loaf_servings_get_a_slice_count_hint():
    from services.macro_plausibility import check_totals

    loaf = {"servings": 1, "title": "Shokupan (Japanese Rice Bread)"}
    assert check_totals({"calories": 2488}, loaf) == [
        "2488 kcal per serving: servings looks like a whole loaf - set a slice count"]
    assert check_totals({"calories": 2488}, {"servings": 1, "title": "Lemon drizzle cake"})[0].endswith(
        "whole cake - set a slice count")
    assert check_totals({"calories": 2488}, {"servings": 4, "title": "Banana bread"}) == [
        "2488 kcal per serving is over 2000"]
    assert check_totals({"calories": 2488}) == ["2488 kcal per serving is over 2000"]
    assert check_totals({"calories": 600}, loaf) == []


def test_plausibility_flags_pass_the_recipe_for_the_yield_hint():
    from services.version_macros import plausibility_flags

    recipe = {"id": "s1", "title": "Shokupan (Japanese Rice Bread)", "servings": 1,
              "ingredients": [{"amount": "500", "unit": "g", "name": "bread flour"}]}
    flags = plausibility_flags(recipe, lambda ing: {"p": 50, "c": 380, "f": 7, "cal": 2488})
    assert any("whole loaf" in (f["reason"] or "") for f in flags)
    assert recipe["servings"] == 1  # never auto-changed
