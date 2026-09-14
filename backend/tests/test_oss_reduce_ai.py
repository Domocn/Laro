"""Tests for free OSS scrape + nutrition helpers (no paid APIs)."""
from __future__ import annotations

import pytest

from services.oss_recipe_scrape import (
    is_social_or_video_url,
    scrape_recipe_oss,
    to_laro_recipe,
)
from services.nutrition_lookup import UK_REFERENCE_INTAKES, uk_percent_ri
from utils.ingredient_parse import parse_ingredient_line


def test_social_urls_skipped_for_oss_scrape():
    assert is_social_or_video_url("https://www.instagram.com/reel/abc/")
    assert is_social_or_video_url("https://tiktok.com/@x/video/1")
    assert not is_social_or_video_url("https://www.bbcgoodfood.com/recipes/easy-pancakes")


def test_to_laro_recipe_splits_ingredients():
    recipe = to_laro_recipe(
        title="Test Pancakes",
        ingredients=["100g plain flour", "2 large eggs"],
        instructions=["Mix", "Cook"],
        servings="4",
        scrape_engine="test",
    )
    assert recipe is not None
    assert recipe["title"] == "Test Pancakes"
    assert len(recipe["ingredients"]) == 2
    assert recipe["ingredients"][0]["name"]
    assert recipe["scrape_engine"] == "test"
    assert recipe["servings"] == 4


def test_ingredient_parser_oss_or_legacy():
    parsed = parse_ingredient_line("2 cups all-purpose flour, sifted")
    assert parsed["name"]
    assert parsed.get("quantity") == 2.0 or parsed.get("amount") in ("2", "2.0")
    assert "cup" in (parsed.get("unit") or "")


def test_uk_reference_intakes_and_percent_ri():
    assert UK_REFERENCE_INTAKES["energy_kcal"] == 2000.0
    assert UK_REFERENCE_INTAKES["salt_g"] == 6.0
    pct = uk_percent_ri(
        {"calories": 200, "fat": 7, "carbs": 26, "protein": 5, "salt": 0.6, "fibre": 3}
    )
    assert pct["energy_kcal_pct"] == 10.0
    assert pct["fat_pct"] == 10.0
    assert pct["salt_pct"] == 10.0


def test_oss_scrape_bbc_good_food_live():
    """Live free scrape — skips if network/site unavailable."""
    import httpx

    url = "https://www.bbcgoodfood.com/recipes/easy-pancakes"
    try:
        html = httpx.get(
            url,
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "LaroTest/1.0"},
        ).text
    except Exception:
        pytest.skip("network unavailable")
    recipe = scrape_recipe_oss(url, html)
    if not recipe:
        pytest.skip("site blocked or schema changed")
    assert recipe["title"]
    assert recipe["ingredients"]
    assert recipe.get("scrape_engine") in ("recipe-scrapers", "extruct")
