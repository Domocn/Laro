"""Mealime catalog matching and slug rules for the closing-app importer."""
from services.mealime_migrate import (
    extract_mealime_url,
    mealime_slug,
    mealime_url_for,
    normalize_name,
    recipe_payload_for_save,
    resolve_name,
    split_lines,
    _index_catalog,
)


def test_mealime_slug_drops_stopwords():
    assert mealime_slug(
        "Zucchini Noodles with Shrimp & Sun-Dried Tomato Alfredo Sauce"
    ) == "zucchini-noodles-shrimp-sun-dried-tomato-alfredo-sauce"
    assert mealime_slug(
        "Apple Quinoa Salad with Celery, Almonds & Dried Cranberries"
    ) == "apple-quinoa-salad-celery-almonds-dried-cranberries"


def test_split_lines_and_url_extract():
    text = """
    Zucchini Noodles with Shrimp
    https://www.mealime.com/recipes/shrimp-zucchini-coconut-curry-basmati-rice/4036 extra
    • Overnight oats
    """
    lines = split_lines(text)
    assert len(lines) == 3
    assert extract_mealime_url(lines[1]).endswith("/4036")


def test_split_paste_messy_saved_list():
    from services.mealime_migrate import leftover_paste, split_paste

    text = """
    Saved
    1. Zucchini Noodles with Shrimp
    Cook now
    25 min
    • Overnight oats https://www.mealime.com/recipes/overnight-oats/99
    https://www.samsungfood.com/recipes/abc
    """
    entries = split_paste(text)
    assert "Zucchini Noodles with Shrimp" in entries
    assert any("overnight-oats/99" in e for e in entries)
    assert any("samsungfood.com" in e for e in entries)
    assert "Saved" not in entries
    assert leftover_paste(entries, 1).count("\n") == len(entries) - 2


def test_assign_week_skips_occupied():
    from datetime import date
    from services.mealime_migrate import assign_week_dinners, source_type_for_url

    slots = assign_week_dinners(
        ["a", "b", "c"],
        occupied_dates={"2026-10-05"},
        start=date(2026, 10, 5),
        days=4,
    )
    assert slots == [
        ("2026-10-06", "a"),
        ("2026-10-07", "b"),
        ("2026-10-08", "c"),
    ]
    assert source_type_for_url("https://www.mealime.com/recipes/x/1") == "mealime"
    assert source_type_for_url("https://www.samsungfood.com/r/1") == "samsung_food"



def test_resolve_name_from_catalog():
    catalog = _index_catalog([
        {
            "id": 25517,
            "recipeId": 2882,
            "name": "Zucchini Noodles with Shrimp & Sun-Dried Tomato Alfredo Sauce",
            "img": "",
        },
        {
            "id": 4036,
            "recipeId": 1,
            "name": "Shrimp & Zucchini Coconut Curry with Basmati Rice",
            "img": "",
        },
    ])
    hit = resolve_name("zucchini noodles with shrimp sun-dried tomato alfredo sauce", catalog)
    assert hit is not None
    assert hit["id"] == 25517
    assert hit["url"].endswith("/25517")
    assert mealime_url_for(hit).endswith(
        "zucchini-noodles-shrimp-sun-dried-tomato-alfredo-sauce/25517"
    )
    miss = resolve_name("totally fictional moon cheese stew", catalog)
    assert miss is None


def test_recipe_payload_strips_unknown_keys():
    payload = recipe_payload_for_save(
        {
            "title": "Shrimp &amp; Rice",
            "description": "Easy",
            "ingredients": [{"name": "rice"}],
            "instructions": ["Cook"],
            "cuisine": "should-drop",
            "author": "should-drop",
            "category": "",
        },
        "https://www.mealime.com/recipes/x/1",
    )
    assert payload["title"] == "Shrimp & Rice"
    assert payload["source_type"] == "mealime"
    assert "closing-app" in payload["tags"]
    assert "cuisine" not in payload
    assert payload["category"] == "Other"


def test_normalize_name_ignores_stopwords():
    assert normalize_name("Salad with Celery & Almonds") == "salad celery almonds"
