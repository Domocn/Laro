"""Unit tests for structured meal-plan PDF/text import."""
import pytest
from pathlib import Path

from services.meal_plan_import import (
    parse_meal_plan_text,
    extract_text_from_pdf_bytes,
    parsed_plan_to_dict,
)


SAMPLE_PLAN = """
7-Day Simple High-Protein Meal Plan
Daily target: 1,000 kcal | 75 g protein
Meal frequency: 1 dinner + 2 snacks daily
Weekly Schedule
Day 	Snack 1 	Snack 2 	Dinner
Monday 	Greek Yoghurt, Pear &
Banana-Chip Crunch
Banana & Almond
Skyr Pot
Air-Fryer Chicken,
Potatoes & Veg
Tuesday 	Greek Yoghurt, Pear &
Banana-Chip Crunch
Banana & Almond
Skyr Pot
Air-Fryer Chicken,
Potatoes & Veg

Meal Breakdown
DINNER 1 — Air-Fryer Chicken, Potatoes & Veg
Served Monday, Tuesday and Friday
Ingredients — 1 serving
● Chicken breast — 140 g
● White potatoes — 250 g
● Broccoli — 150 g
● Olive oil — 8 g
Method
1. Chop the potatoes into small cubes and coat with olive oil.
2. Air fry at 190°C for 18–22 minutes.
3. Season the chicken and cook thoroughly.
Macros
544 kcal | 42.1 g protein | 66.8 g carbohydrate | 12.8 g fat
This is a particularly high-volume dinner.

DINNER 2 — Air-Fryer Salmon, Potatoes & Veg
Served Wednesday and Saturday
Ingredients — 1 serving
● Salmon fillet — 130 g
● White potatoes — 180 g
● Peas — 100 g
Method
1. Cube and season the potatoes.
2. Air fry potatoes then salmon.
Macros
558 kcal | 38.8 g protein | 55.1 g carbohydrate | 20.1 g fat

DINNER 3 — Air-Fryer Beef & Potato Bowl
Served Thursday and Sunday
Ingredients — 1 serving
● 5% lean beef mince — 150 g
● White potatoes — 210 g
● Broccoli — 150 g
Method
1. Form patties and air fry with potatoes.
Macros
548 kcal | 43.9 g protein | 64.6 g carbohydrate | 14.5 g fat

SNACK 1 — Greek Yoghurt, Pear & Banana-Chip Crunch
Served every day
Ingredients
● 0% Greek yoghurt — 200 g
● Pear — 100 g
● Banana chips — 10 g
Method
1. Chop the pear and add it to the yoghurt.
2. Crush banana chips on top.
Macros
227 kcal | 21.2 g protein | 28.2 g carbohydrate | 4.3 g fat

SNACK 2 — Banana & Almond Skyr Pot
Served every day
Ingredients
● Plain Skyr — 150 g
● Banana — 80 g
● Almonds — 10 g
Method
1. Slice banana into Skyr.
2. Crush almonds on top.
Macros
224 kcal | 19.5 g protein | 26.4 g carbohydrate | 5.5 g fat

Shopping List
● Chicken breast — 420 g
● Salmon fillets — 260 g
● 0% Greek yoghurt — 1,400 g
● White potatoes — 1,530 g
● Olive oil — 38 g

Preparation Tip
Portion protein and potatoes ahead. Snacks need almost no cooking.
"""


def test_parse_high_protein_meal_plan_structure():
    plan = parse_meal_plan_text(SAMPLE_PLAN)
    assert "High-Protein" in plan.title or "Meal Plan" in plan.title
    assert "1000" in plan.daily_targets.replace(",", "") or "1,000" in plan.daily_targets
    assert len(plan.meals) == 5  # 3 dinners + 2 snacks

    titles = {m.title for m in plan.meals}
    assert any("Chicken" in t for t in titles)
    assert any("Salmon" in t for t in titles)
    assert any("Beef" in t for t in titles)
    assert any("Yoghurt" in t or "Yogurt" in t for t in titles)
    assert any("Skyr" in t for t in titles)

    chicken = next(m for m in plan.meals if "Chicken" in m.title)
    assert chicken.nutrition.get("calories") == 544
    assert chicken.nutrition.get("protein") == 42
    assert any(i["name"].lower().startswith("chicken") for i in chicken.ingredients)
    assert len(chicken.instructions) >= 2
    assert set(chicken.served_days) == {0, 1, 4}  # Mon Tue Fri

    # Every day has snacks + dinners from served lines
    for day in plan.schedule:
        types = [s["meal_type"] for s in day]
        assert types.count("Snack") >= 2
        assert "Dinner" in types

    assert len(plan.shopping_list) >= 4
    data = parsed_plan_to_dict(plan)
    assert data["parser"] == "structured"
    assert len(data["schedule"]) == 7


def test_shopping_list_skips_pdf_tip_orphans_and_parses_thousands():
    """PDF tip wraps like 'preparation / significantly / easier.' must not become items."""
    from services.meal_plan_import import _parse_shopping_list, _norm_ws

    block = _norm_ws(
        """
Shopping List
● Chicken breast — 420 g ● 0% Greek yoghurt — 1,400 g ● Sweetcorn — 200 g drained
Frozen broccoli, cauliflower, peas and sweetcorn are perfectly suitable and can make
preparation

significantly

easier.

● Pear — 700 g ● Paprika ● Garlic granules ● Salt ● Black pepper
Seasonings can be adjusted to taste provided calorie-containing sauces or marinades are not
added

without

accounting

for

them.

Preparation Tip
Portion ahead.
"""
    )
    items = _parse_shopping_list(block)
    names = [i["name"].lower() for i in items]
    junk = {
        "preparation",
        "significantly",
        "easier",
        "easier.",
        "added",
        "without",
        "accounting",
        "for",
        "them",
        "them.",
    }
    assert not any(n.strip() in junk for n in names)
    assert not any("seasonings" in n for n in names)
    yoghurt = next(i for i in items if "yoghurt" in i["name"].lower())
    assert yoghurt["amount"] == "1400"
    assert yoghurt["unit"] == "g"
    assert any("chicken" in n for n in names)
    assert any(n == "paprika" for n in names)
    assert len(items) >= 6
    assert len(items) <= 20


def test_parse_rejects_short_text():
    with pytest.raises(ValueError):
        parse_meal_plan_text("too short")


def test_extract_uploaded_pdf_if_present():
    candidates = [
        Path("/home/ubuntu/.cursor/projects/workspace/uploads/mealplan.30831514__1__964e.PDF"),
        Path("/home/ubuntu/.cursor/projects/workspace/uploads/mealplan.30831514_51e4.PDF"),
    ]
    pdf_path = next((p for p in candidates if p.exists()), None)
    if pdf_path is None:
        pytest.skip("uploaded sample PDF not present")
    text = extract_text_from_pdf_bytes(pdf_path.read_bytes())
    plan = parse_meal_plan_text(text)
    assert len(plan.meals) >= 4
    chicken = next(m for m in plan.meals if "Chicken" in m.title)
    assert len(chicken.ingredients) >= 4
    assert len(chicken.instructions) >= 3
    assert chicken.nutrition.get("calories") == 544
    assert any("Chicken" in m.title for m in plan.meals)
    assert any(m.category == "Snack" or m.meal_type.startswith("Snack") for m in plan.meals)
    # Mon should have dinner + snacks
    assert len(plan.schedule[0]) >= 3


def test_inline_bullets_and_steps_from_jammed_pdf_line():
    from services.meal_plan_import import _split_inline_bullets, _split_inline_steps, _norm_ws

    jammed = (
        "DINNER  1  —  Air-Fryer  Chicken\n"
        "Ingredients  —  1  serving\n"
        "●  Chicken  breast  —  140  g  ●  White  potatoes  —  250  g  ●  Broccoli  —  150  g\n"
        "Method\n"
        "1.  Chop  potatoes.  2.  Air  fry.  3.  Cook  chicken.\n"
        "Macros\n"
        "544  kcal  |  42.1  g  protein  |  66.8  g  carbohydrate  |  12.8  g  fat\n"
    )
    text = _norm_ws(jammed)
    plan = parse_meal_plan_text(text)
    assert len(plan.meals) == 1
    assert len(plan.meals[0].ingredients) >= 3
    assert len(plan.meals[0].instructions) >= 3
    assert len(_split_inline_bullets("● A — 1 g ● B — 2 g")) == 2
    assert len(_split_inline_steps("1. One. 2. Two. 3. Three.")) == 3


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "meal_plans"


def test_uploaded_1400_kcal_plan_fixture():
    """User's 1,400 kcal plan: lunch + 2 snacks + 3 dinners; no 'window' junk."""
    pdf = FIXTURES / "high_protein_1400.pdf"
    if not pdf.exists():
        pytest.skip("fixture PDF missing")
    text = extract_text_from_pdf_bytes(pdf.read_bytes())
    plan = parse_meal_plan_text(text)
    titles = [m.title.lower() for m in plan.meals]
    assert not any("window" in t or "kcal" in t for t in titles)
    assert any("overnight" in t or "oat" in t for t in titles)
    assert any("chicken" in t for t in titles)
    assert any("salmon" in t for t in titles)
    assert any("meatball" in t or "beef" in t for t in titles)
    assert len(plan.meals) == 6
    # Each day: lunch + 2 snacks + 1 dinner
    for day in plan.schedule:
        types = [s["meal_type"] for s in day]
        assert types.count("Lunch") == 1
        assert types.count("Dinner") == 1
        assert types.count("Snack") == 2
    chicken = next(m for m in plan.meals if "Chicken" in m.title)
    assert chicken.nutrition.get("calories")
    assert len(chicken.ingredients) >= 4
    # Colon-style amounts parsed (not empty)
    assert any(i.get("amount") for i in chicken.ingredients)


def test_uploaded_1000_kcal_plan_fixture():
    """User's 1,000 kcal plan remains the golden structured format."""
    pdf = FIXTURES / "simple_high_protein_1000.pdf"
    if not pdf.exists():
        pytest.skip("fixture PDF missing")
    text = extract_text_from_pdf_bytes(pdf.read_bytes())
    plan = parse_meal_plan_text(text)
    assert len(plan.meals) == 5
    assert not any("window" in m.title.lower() for m in plan.meals)
    for day in plan.schedule:
        types = [s["meal_type"] for s in day]
        assert types.count("Dinner") == 1
        assert types.count("Snack") == 2
    chicken = next(m for m in plan.meals if "Chicken" in m.title)
    assert chicken.nutrition.get("calories") == 544
    assert set(chicken.served_days) == {0, 1, 4}


def test_plan_source_note_strips_structure_chrome():
    from services.meal_plan_import import plan_source_note, parse_meal_plan_text

    note = plan_source_note(
        "7-Day High-Protein Meal Plan Daily target: 1,400 kcal and 115g protein Structure:",
        "Daily target: 1,400 kcal and 115g protein Structure: Lunch, snacks",
    )
    assert "Structure" not in note
    assert "7-Day High-Protein Meal Plan" in note
    assert "1,400" in note or "1400" in note
    assert note.startswith("From:")


def test_parse_does_not_auto_stamp_from_description():
    from services.meal_plan_import import parse_meal_plan_text

    plan = parse_meal_plan_text(SAMPLE_PLAN)
    assert plan.meals
    for meal in plan.meals:
        assert not (meal.description or "").startswith("From:")
