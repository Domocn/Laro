"""Import savers only send real recipe columns (is_favorite etc. made every save fail)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routers.recipe_import import _row  # noqa: E402
from utils.recipe_fields import RECIPE_COLUMNS  # noqa: E402


def test_row_drops_unknown_keys_and_tidies():
    r = _row({
        "id": "x", "title": "Chilli", "is_favorite": False, "times_cooked": 0, "current_version": 1,
        "imported_from": "Web", "category": "Main course, Dinner",
        "image_url": {"@type": "ImageObject", "url": "https://a/b.jpg"},
        "nutrition": {"calories": 410.4, "protein": 30},
        "ingredients": [{"name": "500g beef mince", "amount": "", "unit": ""}],
    })
    assert set(r) <= RECIPE_COLUMNS
    assert r["category"] == "Dinner" and r["image_url"] == "https://a/b.jpg"
    assert r["nutrition_calories"] == 410 and r["nutrition_protein"] == 30
    assert (r["ingredients"][0]["amount"], r["ingredients"][0]["unit"]) == ("500", "g")
