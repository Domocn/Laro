# Food composition data (`foods.json.gz`)

`foods.json.gz` is built by `backend/scripts/build_food_db.py` from the datasets
below and loaded by `backend/utils/food_dataset.py`. The raw downloads are not
committed; rebuild with the script (instructions in its docstring).

| Source | Version | Rows | Licence |
|---|---|---|---|
| McCance and Widdowson's Composition of Foods Integrated Dataset (CoFID), UK OHID / Public Health England | 2021 | 2,853 | [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) |
| USDA FoodData Central, Foundation Foods | 2026-04-30 | 317 | Public domain ([CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)) |
| USDA FoodData Central, SR Legacy | 2018-04 | 6,188 | Public domain ([CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)) |

Contains public sector information licensed under the Open Government Licence v3.0.
Source: <https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid>.

USDA, Agricultural Research Service. FoodData Central. <https://fdc.nal.usda.gov/>.

## What was changed

All values are per 100 g edible portion.

- **Carbohydrate** is *available* carbohydrate for every row. CoFID reports it that
  way (as monosaccharide equivalents, which is why sugars can read slightly over
  100 g). USDA reports carbohydrate "by difference", which includes fibre, so USDA
  carbs here = by-difference minus total dietary fibre (floored at 0).
- **Fibre**: CoFID AOAC fibre where measured, otherwise NSP (Englyst); USDA total
  dietary fibre (AOAC).
- **Salt** = sodium x 2.5 (both sources).
- **Energy**: CoFID kcal; USDA nutrient 208 (kcal), falling back to the Atwater
  specific / general factors (Foundation Foods), then kJ / 4.184.
- **State** (`raw`, `boiled`, `canned`, `dried`, `frozen`, `fried`, ...) is parsed
  from the description; blank means no state word (as sold).
- Dropped: USDA baby foods, fast/restaurant foods, mixed meals, American
  Indian/Alaska Native foods and branded SR Legacy items (brand names in capitals),
  plus rows with no energy or protein value.
- One CoFID description is clarified (values untouched): 14-820 "Coconut milk"
  (22 kcal) is the liquid from a fresh coconut, so it is labelled as coconut water.

# UK supermarket label medians (`uk_labels.json`)

`uk_labels.json` is built by `backend/scripts/build_uk_labels.py` and loaded by
`backend/utils/uk_labels.py`. For processed / branded foods whose shop-bought recipe differs
from a generic composition table (houmous, plant drinks and spreads, vegan cheese, pastes and
sauces, tofu, tinned beans drained, breadcrumbs, stock, pastry, gluten-free bread and wraps,
cocoa) it stores the per-100 g median of UK product labels, at least 8 products per food. The
file records the build date, the searches used, the number of products and a few examples.

| Source | Built | Foods | Licence |
|---|---|---|---|
| Open Food Facts, products sold in the United Kingdom | 2026-10-21/22 | 36 | Database: [Open Database Licence (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/); contents: [Database Contents Licence (DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/) |

Contains information from Open Food Facts (<https://world.openfoodfacts.org>), which is made
available under the Open Database Licence (ODbL). `uk_labels.json` is a derived database and
is likewise available under the ODbL.

Products are filtered by name and category (no cooked pouches, ready meals, flavoured,
reduced-fat or per-serving-only labels). Carbohydrate on UK / EU labels is available
carbohydrate, the same basis as CoFID.

## Carbohydrate basis in lookups

Every food entry exposes `carbs` (available carbohydrate, fibre excluded - the UK default)
and `carbs_total` (total carbohydrate including fibre - the US basis). The curated table in
`backend/utils/food_db.py` was mostly USDA-sourced, so its carbs are converted once at import
(carbs - fibre); kcal are never changed.

Values are food-composition averages for meal planning, not medical advice.
