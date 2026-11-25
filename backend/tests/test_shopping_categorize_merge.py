"""Shopping list quality: most-specific aisle wins; prep wording doesn't split duplicates."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.grocery_aisles import categorize_grocery_item as cat  # noqa: E402
from routers.shopping_lists import _strip_prep_suffix  # noqa: E402


def test_specific_keyword_beats_generic_one():
    assert cat("coconut milk") == "Canned Goods"      # not Dairy via "milk"
    assert cat("tomato purée") == "Canned Goods"      # not Produce via "tomato"
    assert cat("2 garlic bread") == "Bakery"          # not Produce via "garlic"
    assert cat("almond milk") == "Beverages"
    assert cat("peanut butter") == "Condiments & Sauces"


def test_plain_items_unchanged():
    assert cat("milk") == "Dairy"
    assert cat("butter") == "Dairy"
    assert cat("onion") == "Produce"
    assert cat("chicken thighs") == "Meat & Seafood"
    assert cat("penne") == "Pasta & Grains"


def test_prep_suffix_stripped_for_merging():
    assert _strip_prep_suffix("onion, finely chopped") == "onion"
    assert _strip_prep_suffix("garlic cloves, crushed") == "garlic cloves"
    assert _strip_prep_suffix("salt, flaky") == "salt, flaky"
    assert _strip_prep_suffix("onion") == "onion"
