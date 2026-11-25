"""Permanent check: Laro's per-100 g values vs. what UK supermarket labels say.

Reference values are per-100 g medians of UK products on Open Food Facts (ODbL), fetched
2026-10-22 with the same filters as ``scripts/build_uk_labels.py`` (no cooked pouches, ready
meals or flavoured variants; rice / pasta / lentils / noodles are DRY products). They are
committed here so CI never touches the network. A lookup passes when kcal is within +/-15 %
and protein / fat within max(3 g, 20 %) of the label median.

Several processed foods are answered by ``data/foods/uk_labels.json`` itself (built from the
same source), so for those this guards against regressions in matching rather than being an
independent check; plain foods come from CoFID or the curated table and are checked for real.
Oils: UK labels state per 100 ml (~824-828 kcal), Laro per 100 g (~884-899) - inside 15 %.
"""
import pytest

from utils.food_db import find_food

# (Laro query, UK label kcal, protein g, fat g, number of UK products in the median)
UK_LABEL_REFERENCE = [
    ('pasta', 356.0, 12.0, 1.5, 29),  # OFF search: dried pasta penne
    ('gluten-free pasta', 357.0, 7.1, 1.5, 15),  # OFF search: gluten free pasta
    ('long grain rice', 348.0, 7.1, 0.9, 14),  # OFF search: long grain rice
    ('basmati rice', 352.0, 8.3, 0.8, 42),  # OFF search: basmati rice
    ('plain flour', 346.0, 10.0, 1.3, 31),  # OFF search: plain flour
    ('gluten-free flour blend', 358.0, 5.0, 1.3, 5),  # OFF search: gluten free plain flour
    ('porridge oats', 368.0, 12.0, 7.0, 99),  # OFF search: porridge oats
    ('caster sugar', 400.0, 0.0, 0.0, 7),  # OFF search: caster sugar
    ('icing sugar', 398.5, 0.0, 0.0, 8),  # OFF search: icing sugar
    ('firm tofu', 127.0, 12.0, 6.8, 69),  # OFF search: firm tofu
    ('red lentils', 334.0, 25.0, 1.3, 28),  # OFF search: red split lentils
    ('chickpeas, drained', 122.0, 6.7, 2.4, 44),  # OFF search: chickpeas in water
    ('kidney beans, drained', 105.0, 7.2, 0.6, 50),  # OFF search: red kidney beans in water
    ('coconut milk', 175.0, 1.3, 17.7, 59),  # OFF search: coconut milk
    ('semi-skimmed milk', 49.0, 3.5, 1.7, 147),  # OFF search: semi skimmed milk
    ('oat milk', 49.0, 0.8, 1.6, 100),  # OFF search: oat drink
    ('soy milk', 33.1, 3.3, 1.9, 38),  # OFF search: soya drink unsweetened
    ('unsweetened almond milk', 17.0, 0.6, 1.1, 33),  # OFF search: almond drink unsweetened
    ('dairy-free butter', 713.0, 0.5, 79.0, 13),  # OFF search: plant butter block
    ('butter', 744.0, 0.6, 82.0, 63),  # OFF search: salted butter
    ('cheddar', 416.0, 25.4, 34.9, 118),  # OFF search: mature cheddar
    ('dairy-free cheese', 302.5, 0.8, 22.9, 38),  # OFF search: vegan cheese block
    ('feta', 276.0, 16.0, 23.0, 77),  # OFF search: feta
    ('greek yogurt', 120.0, 4.5, 8.6, 70),  # OFF search: greek style yogurt
    ('coconut yoghurt', 121.0, 0.9, 6.9, 9),  # OFF search: coconut yogurt
    ('olive oil', 824.0, 0.0, 91.6, 143),  # OFF search: extra virgin olive oil
    ('vegetable oil', 828.0, 0.0, 92.0, 58),  # OFF search: vegetable oil
    ('coconut oil', 899.0, 0.0, 99.9, 61),  # OFF search: coconut oil
    ('sesame oil', 828.0, 0.0, 92.0, 31),  # OFF search: sesame oil
    ('peanut butter', 620.0, 26.3, 50.0, 169),  # OFF search: smooth peanut butter
    ('almonds', 595.0, 21.1, 50.0, 20),  # OFF search: whole almonds
    ('cashews', 583.0, 18.0, 48.0, 68),  # OFF search: cashew nuts
    ('walnuts', 696.0, 14.8, 68.5, 57),  # OFF search: walnut pieces
    ('chia seeds', 442.0, 20.0, 30.4, 50),  # OFF search: chia seeds
    ('desiccated coconut', 633.0, 5.6, 62.0, 11),  # OFF search: desiccated coconut
    ('dark chocolate', 565.0, 8.8, 42.6, 5),  # OFF search: dark chocolate 70
    ('milk chocolate', 539.0, 6.3, 31.5, 11),  # OFF search: milk chocolate
    ('cocoa powder', 376.5, 20.0, 21.0, 28),  # OFF search: cocoa powder
    ('maple syrup', 268.5, 0.3, 0.4, 28),  # OFF search: maple syrup
    ('honey', 327.0, 0.5, 0.5, 31),  # OFF search: clear honey
    ('soy sauce', 70.4, 3.8, 0.1, 56),  # OFF search: soy sauce
    ('tamari', 84.0, 11.8, 0.0, 13),  # OFF search: tamari
    ('miso paste', 183.0, 10.3, 6.2, 29),  # OFF search: miso paste
    ('tahini', 648.0, 24.0, 58.4, 42),  # OFF search: tahini
    ('nutritional yeast', 349.0, 47.0, 4.8, 20),  # OFF search: nutritional yeast flakes
    ('mayonnaise', 694.0, 1.1, 75.1, 68),  # OFF search: mayonnaise
    ('ketchup', 102.0, 1.2, 0.2, 112),  # OFF search: tomato ketchup
    ('dijon mustard', 152.0, 7.2, 11.0, 14),  # OFF search: dijon mustard
    ('hummus', 271.0, 6.6, 21.1, 114),  # OFF search: houmous
    ('bread', 239.0, 8.6, 1.9, 49),  # OFF search: white bread
    ('breadcrumbs', 365.0, 11.7, 1.9, 35),  # OFF search: breadcrumbs
    ('rice noodles', 358.0, 6.4, 1.0, 11),  # OFF search: rice noodles
    ('kimchi', 29.0, 1.5, 0.4, 56),  # OFF search: kimchi
    ('weetabix', 362.0, 12.0, 2.0, 11),  # OFF search: weetabix original
    ('cornflour', 357.0, 0.5, 0.5, 19),  # OFF search: cornflour
    ('baking powder', 172.5, 2.4, 0.6, 10),  # OFF search: baking powder
    ('stock powder', 221.0, 6.2, 2.6, 8),  # OFF search: vegetable bouillon powder
    ('frozen peas', 82.0, 5.5, 0.7, 61),  # OFF search: frozen garden peas
    ('tinned sweetcorn', 78.0, 2.8, 1.7, 61),  # OFF search: sweetcorn in water
]


def _close(have, want, rel=0.2, floor=3.0):
    return abs(float(have) - want) <= max(floor, rel * want)


def test_reference_covers_the_staples():
    assert len(UK_LABEL_REFERENCE) >= 55
    assert all(n >= 5 for *_rest, n in UK_LABEL_REFERENCE)


@pytest.mark.parametrize("query,kcal,protein,fat,n", UK_LABEL_REFERENCE, ids=[r[0] for r in UK_LABEL_REFERENCE])
def test_laro_matches_uk_labels(query, kcal, protein, fat, n):
    hit = find_food(query)  # default region: UK
    assert hit is not None, query
    name, entry = hit
    assert abs(float(entry["calories"]) - kcal) <= 0.15 * kcal, (query, name, entry["calories"], kcal)
    assert _close(entry["protein"], protein), (query, name, entry["protein"], protein)
    assert _close(entry["fat"], fat), (query, name, entry["fat"], fat)


@pytest.mark.parametrize("query", ["pasta", "long grain rice", "basmati rice", "red lentils", "rice noodles"])
def test_dry_staples_are_dry(query):
    # Cooked pouches (~130-160 kcal) must never stand in for what recipes weigh: dry goods.
    assert find_food(query)[1]["calories"] > 300


def test_off_items_from_the_audit_are_fixed():
    assert 230 <= find_food("houmous")[1]["calories"] <= 310        # was 166 (USDA homemade)
    assert 100 <= find_food("firm tofu")[1]["calories"] <= 140      # was 144 (USDA)
    assert 20 <= find_food("kimchi")[1]["calories"] <= 45           # was 15
    assert 90 <= find_food("kidney beans, drained")[1]["calories"] <= 120  # was 127
    assert 210 <= find_food("fresh breadcrumbs")[1]["calories"] <= 290      # was 380 (dried)
    assert 330 <= find_food("dried breadcrumbs")[1]["calories"] <= 400
    # UK carbohydrate basis (available carbs, fibre excluded) for the curated nuts / seeds.
    assert find_food("chia seeds")[1]["carbs"] < 12        # US total 42
    assert find_food("almonds")[1]["carbs"] < 12            # US total 22
    assert find_food("tahini")[1]["carbs"] < 10             # US total 21
    assert find_food("peanut butter")[1]["carbs"] < 16      # US total 20
