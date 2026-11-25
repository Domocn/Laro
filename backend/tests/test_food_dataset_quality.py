"""Match-quality suite for ingredient -> food lookups (curated table + CoFID/USDA dataset).

Reference kcal are per 100 g raw / as sold from UK CoFID 2021 (the UK default), the UK
supermarket label medians in data/foods/uk_labels.json for processed foods, or USDA
FoodData Central where neither covers the food. A lookup passes when it lands on a
sensible food, in the right state, within +/-15 % of the reference.
"""
import time

import pytest

from utils import food_dataset
from utils.food_db import find_food, find_food_in_dataset, parse_ingredient_amount

RAW_STATES = {"raw", "as_sold", "dried", "frozen"}
COOKED_STATES = {"cooked", "boiled", "steamed", "canned", "baked", "grilled", "roasted"}

# (recipe line, word that must appear in the name or description, reference kcal/100 g)
COOKBOOK_LINES = [
    ("500 g gluten-free pasta", "pasta", 360),
    ("400 g firm tofu, pressed", "tofu", 125),  # UK label median
    ("3 spring onions, thinly sliced", "onion", 32),
    ("2 garlic cloves, crushed", "garlic", 98),  # CoFID
    ("2 tbsp extra-virgin olive oil", "oil", 884),
    ("400 ml coconut milk", "coconut milk", 190),
    ("100 g dairy-free feta, crumbled", "feta", 285),
    ("3 tbsp nutritional yeast", "nutritional yeast", 380),
    ("2 tbsp tamari", "tamari", 83),  # UK label median
    ("1 tbsp white miso paste", "miso", 198),
    ("50 g desiccated coconut", "coconut", 630),
    ("100 g almond meal", "almond", 590),
    ("2 tbsp cornflour", "corn", 381),
    ("150 g caster sugar", "sugar", 394),
    ("100 g icing sugar", "sugar", 393),
    ("3 tbsp maple syrup", "maple", 260),
    ("1/4 red cabbage, shredded", "cabbage", 23),
    ("1 lebanese cucumber, diced", "cucumber", 15),
    ("200 g long grain rice", "rice", 355),
    ("300 g sushi rice", "rice", 360),
    ("100 g rice vermicelli noodle nests", "vermicelli", 364),
    ("1 cup frozen peas", "pea", 80),
    ("100 g kimchi", "kimchi", 29),  # UK label median (USDA 15)
    ("1 tbsp sesame oil", "sesame", 884),
    ("2 tbsp peanut butter", "peanut butter", 600),
    ("100 g dark chocolate, chopped", "chocolate", 560),
    ("200 g plain flour", "flour", 364),
    ("150 g buckwheat flour", "buckwheat", 335),
    ("2 potatoes, peeled", "potato", 77),
    ("1 sweet potato", "sweet potato", 86),
    ("2 zucchini, grated", "zucchini", 17),
    ("1 carrot, grated", "carrot", 38),
    ("150 g red lentils", "lentil", 352),
    ("200 g dried kidney beans", "kidney", 266),  # CoFID red kidney, dried
    ("200 g dried black beans", "black bean", 341),
    ("100 g baby spinach", "spinach", 18),  # CoFID 13-521 baby spinach
    ("1 bunch kale, stems removed", "kale", 33),  # CoFID curly kale
    ("250 g mushrooms, sliced", "mushroom", 22),
    ("1 red bell pepper", "pepper", 24),  # CoFID 21, USDA 26-31
    ("2 tomatoes, diced", "tomato", 14),  # CoFID
    ("250 g cherry tomatoes, halved", "tomato", 20),
    ("2 tbsp lemon juice", "lemon", 22),
    ("1 lime", "lime", 9),  # CoFID "Limes, flesh only" (organic acids not counted; USDA 30)
    ("1 avocado", "avocado", 189),  # CoFID
    ("2 ripe bananas", "banana", 89),
    ("150 g frozen raspberries", "raspberr", 52),
    ("125 g blueberries", "blueberr", 40),  # CoFID
    ("250 g strawberries, hulled", "strawberr", 32),
    ("100 g rolled oats", "oat", 380),
    ("100 g cashews", "cashew", 553),
    ("50 g almonds", "almond", 579),
    ("50 g walnuts, chopped", "walnut", 654),
    ("2 tbsp pumpkin seeds", "pumpkin", 559),
    ("2 tbsp chia seeds", "chia", 486),
    ("1 tbsp honey", "honey", 304),
    ("2 tbsp soy sauce", "soy", 60),
    ("1 tsp dijon mustard", "mustard", 151),
    ("3 tbsp mayonnaise", "mayonnaise", 680),
    ("30 g cocoa powder", "cocoa", 365),  # UK label median (CoFID 312)
    ("1 tsp baking powder", "baking powder", 184),  # UK label median
    ("1 tsp vanilla extract", "vanilla", 288),
    ("1 tsp ground cinnamon", "cinnamon", 247),
    ("2 eggplants", "aubergine", 15),
    ("500 g beef mince", "beef", 225),
    ("100 g halloumi", "halloumi", 313),
    ("1 red onion", "onion", 40),
]

COOKED_LINES = [
    ("1 x 400g tin chickpeas, drained", "chickpea", 139),
    ("200 g cooked rice", "rice", 130),
    ("200 g cooked chicken breast", "chicken", 165),
    ("1 tin chopped tomatoes", "tomato", 20),
    ("400 g can black beans, drained", "black bean", 102),  # UK label median
    ("300 g boiled potatoes", "potato", 74),
    ("2 cups cooked brown rice", "rice", 112),
    ("150 g cooked red lentils", "lentil", 110),
    ("1 tin tuna in brine, drained", "tuna", 109),
]

# Lines the dataset must refuse rather than guess (wrong food is worse than no food).
NONSENSE = ["xyzzy flurb", "dragon fruit", "zorblax paste", "vegetable stock cube thing"]


def _lookup(line):
    name = parse_ingredient_amount(line)["name"]
    return find_food(name)


def _label(name, entry):
    return f"{name} {entry.get('description', '')}".lower()


def _within(kcal, ref, tol=0.15):
    return abs(float(kcal) - ref) <= ref * tol


@pytest.mark.parametrize("line,keyword,ref", COOKBOOK_LINES, ids=[c[0] for c in COOKBOOK_LINES])
def test_cookbook_line_resolves_raw(line, keyword, ref):
    hit = _lookup(line)
    assert hit is not None, line
    name, entry = hit
    assert keyword in _label(name, entry), (line, name, entry.get("description"))
    assert entry["state"] in RAW_STATES, (line, entry["state"])
    assert _within(entry["calories"], ref), (line, name, entry["calories"], ref)
    assert entry.get("source")
    assert entry.get("source_id")


@pytest.mark.parametrize("line,keyword,ref", COOKED_LINES, ids=[c[0] for c in COOKED_LINES])
def test_cooked_markers_pick_cooked_values(line, keyword, ref):
    hit = _lookup(line)
    assert hit is not None, line
    name, entry = hit
    assert keyword in _label(name, entry), (line, name, entry.get("description"))
    assert entry["state"] in COOKED_STATES, (line, entry["state"])
    assert _within(entry["calories"], ref, 0.2), (line, name, entry["calories"], ref)


def test_cookbook_pass_rate_is_complete():
    assert len(COOKBOOK_LINES) >= 60
    ok = 0
    for line, keyword, ref in COOKBOOK_LINES:
        hit = _lookup(line)
        if hit and keyword in _label(*hit) and _within(hit[1]["calories"], ref):
            ok += 1
    assert ok == len(COOKBOOK_LINES)


# --- dataset on its own (what a curated miss falls through to) -----------------------

# Lines where CoFID and USDA agree closely enough for a fixed reference.
DATASET_LINES = [
    ("firm tofu", "tofu", 144), ("spring onions", "onion", 32), ("garlic clove", "garlic", 98),
    ("desiccated coconut", "coconut", 630), ("cornflour", "corn", 381), ("caster sugar", "sugar", 394),
    ("icing sugar", "sugar", 393), ("maple syrup", "maple", 260), ("red cabbage", "cabbage", 23),
    ("lebanese cucumber", "cucumber", 14), ("long grain rice", "rice", 355), ("sushi rice", "rice", 355),
    ("frozen peas", "pea", 78), ("sesame oil", "sesame", 890), ("peanut butter", "peanut", 600),
    ("dark chocolate", "chocolate", 546), ("plain flour", "flour", 360), ("buckwheat flour", "buckwheat", 335),
    ("potato", "potato", 80), ("sweet potato", "sweet potato", 86), ("zucchini", "courgette", 16),
    ("carrot", "carrot", 38), ("red lentils", "lentil", 340), ("kidney beans", "kidney", 333),
    ("black beans", "black", 341), ("spinach", "spinach", 24), ("bell pepper", "pepper", 25),
    ("tomato", "tomato", 16), ("cherry tomatoes", "tomato", 20), ("lime", "lime", 30),
    ("avocado", "avocado", 160), ("banana", "banana", 89), ("blueberries", "blueberr", 57),
    ("strawberries", "strawberr", 31), ("oats", "oat", 380), ("cashews", "cashew", 563),
    ("almonds", "almond", 570), ("walnuts", "walnut", 670), ("pumpkin seeds", "pumpkin", 562),
    ("chia seeds", "chia", 486), ("honey", "honey", 295), ("mayonnaise", "mayonnaise", 686),
    ("vanilla extract", "vanilla", 288), ("cinnamon", "cinnamon", 247), ("eggplant", "aubergine", 15),
    ("chicken breast", "chicken", 115), ("beef mince", "beef", 225), ("greek yoghurt", "yogurt", 133),
    ("cheddar cheese", "cheddar", 410), ("halloumi", "halloumi", 313), ("quinoa", "quinoa", 340),
    ("couscous", "couscous", 364), ("brown sugar", "sugar", 380), ("cod", "cod", 78),
    ("roasted peanuts", "peanut", 590), ("dried apricots", "apricot", 200), ("baked beans", "beans", 94),
    ("smoked salmon", "salmon", 184), ("bacon", "bacon", 215), ("chickpeas", "chickpea", 375),
]


@pytest.mark.parametrize("line,keyword,ref", DATASET_LINES, ids=[c[0] for c in DATASET_LINES])
def test_dataset_match(line, keyword, ref):
    hit = find_food_in_dataset(line)
    assert hit is not None, line
    _label_name, entry, match = hit
    assert keyword in match.description.lower(), (line, match.description)
    assert entry["state"] in RAW_STATES | {"roasted", "baked"}, (line, match.description, entry["state"])
    assert _within(entry["calories"], ref), (line, match.description, entry["calories"], ref)
    assert entry["source"] in ("cofid", "usda_foundation", "usda_sr")


@pytest.mark.parametrize("line", NONSENSE)
def test_dataset_refuses_weak_matches(line):
    assert find_food_in_dataset(line) is None


def test_dataset_refuses_rather_than_dropping_identity_words():
    # The dataset has yeast, feta and milk - but these are different products.
    assert find_food_in_dataset("nutritional yeast") is None
    assert find_food_in_dataset("dairy-free feta") is None
    assert find_food_in_dataset("oat milk") is None or "oat" in find_food_in_dataset("oat milk")[2].description.lower()


def test_dataset_whole_word_and_plain_descriptions():
    # "chicken breast" must not land on a breaded / fried product.
    desc = find_food_in_dataset("chicken breast")[2].description.lower()
    assert "breaded" not in desc and "fried" not in desc and "breadcrumb" not in desc
    # Head noun matters: "tomato" is tomatoes, not tomato soup.
    assert find_food_in_dataset("tomato")[2].description.lower().startswith("tomato")
    # "potato" is not sweet potato, nor potato skin.
    desc = find_food_in_dataset("potato")[2].description.lower()
    assert desc.startswith("potato") and "skin," not in desc


def test_dataset_prefers_cofid_on_ties():
    assert find_food_in_dataset("courgette")[2].source == "cofid"
    assert find_food_in_dataset("spinach")[2].source == "cofid"


def test_dataset_cooked_marker():
    _n, entry, match = find_food_in_dataset("200g cooked rice")
    assert match.state in ("cooked", "boiled") and _within(entry["calories"], 130, 0.2)
    _n, entry, match = find_food_in_dataset("1 tin chopped tomatoes")
    assert match.state == "canned"


def test_dataset_hits_report_source_metadata():
    name, entry = find_food("pork belly")
    assert entry["source"] in ("cofid", "usda_foundation", "usda_sr")
    assert entry["source_id"]
    assert entry["description"]
    for key in ("calories", "protein", "carbs", "fat", "fiber", "sugars", "saturates", "salt"):
        assert isinstance(entry[key], (int, float))


def test_curated_entries_report_source():
    name, entry = find_food("chicken breast")
    assert entry["source"] == "curated" and entry["state"] == "raw"
    name, entry = find_food("200g cooked rice")
    assert entry["source"] == "curated" and entry["state"] == "cooked"


def test_partial_curated_hit_yields_to_complete_dataset_match():
    # Curated only knows "cabbage"; the dataset has red cabbage specifically.
    name, entry = find_food("red cabbage")
    assert "red" in entry.get("description", "").lower()


def test_dataset_values_are_available_carbohydrate():
    # USDA carbs are converted to available carbohydrate (by difference minus fibre).
    _n, entry, match = find_food_in_dataset("black beans")
    assert match.source.startswith("usda")
    assert entry["carbs"] < 50  # by-difference would be ~62 g


def test_performance_load_and_lookup():
    food_dataset._DATA = None
    food_dataset._LOAD_FAILED = False
    t = time.perf_counter()
    assert food_dataset.load() is not None
    assert time.perf_counter() - t < 2.0
    names = [parse_ingredient_amount(line)["name"] for line, _k, _r in COOKBOOK_LINES]
    t = time.perf_counter()
    for name in names:
        find_food(name)
        food_dataset.search(name)
    per = (time.perf_counter() - t) / len(names)
    assert per < 0.005, per
