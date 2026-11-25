"""Imported categories map to one Laro category (filters missed raw JSON-LD strings)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.recipe_fields import normalize_category as c  # noqa: E402
from routers.ai import _tidy_recipes  # noqa: E402


def test_multi_value_takes_first_known():
    assert c("Breakfast, Brunch, Main course") == "Breakfast"
    assert c("Main course, Dinner") == "Dinner"
    assert c("Starter") == "Appetizer"
    assert c(["Desserts", "Baking"]) == "Dessert"


def test_known_and_unknown():
    assert c("Lunch") == "Lunch" and c("Meal Pack") == "Meal Pack"
    assert c("Vegan stuff") == "Other" and c("") == "Other"


def test_preview_uses_mapped_category():
    assert _tidy_recipes([{"title": "x", "category": "Breakfast, Brunch", "ingredients": []}])[0]["category"] == "Breakfast"


def test_preview_image_object_becomes_url():
    r = _tidy_recipes([{"title": "x", "image_url": {"@type": "ImageObject", "url": "https://x/y.jpg"}}])[0]
    assert r["image_url"] == "https://x/y.jpg"
    assert _tidy_recipes([{"title": "x", "image_url": ["https://a.jpg"]}])[0]["image_url"] == "https://a.jpg"
