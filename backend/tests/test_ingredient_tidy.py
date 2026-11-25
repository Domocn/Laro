"""Imported ingredient rows get safe cosmetic fixes."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.recipe_fields import normalize_ingredient as n  # noqa: E402


def test_prep_word_unit_moves_to_name():
    assert n({"amount": "2", "unit": "sliced", "name": "lemons"}) == {"amount": "2", "unit": "", "name": "lemons, sliced"}


def test_wprm_paren_artefacts():
    assert n({"amount": "2", "unit": "clove", "name": "garlic, (, minced)"})["name"] == "garlic, minced"
    assert n({"amount": "1", "unit": "", "name": "onion (, finely chopped)"})["name"] == "onion (finely chopped)"


def test_prefers_metric_alternative():
    r = n({"amount": "1", "unit": "lb", "name": "/ 500g   beef mince (ground beef)"})
    assert (r["amount"], r["unit"]) == ("500", "g") and r["name"].startswith("beef mince")


def test_normal_rows_untouched():
    row = {"amount": "200", "unit": "g", "name": "feta"}
    assert n(dict(row)) == row


def test_amount_repeated_in_name_is_removed():
    assert n({"amount": "1", "unit": "", "name": "1 large onion"})["name"] == "large onion"
    assert n({"amount": "1", "unit": "tbsp", "name": "1 tbsp oil"})["name"] == "oil"
    assert n({"amount": "2", "unit": "", "name": "2 garlic cloves"})["name"] == "garlic cloves"
    assert n({"amount": "1", "unit": "", "name": "10 eggs"})["name"] == "10 eggs"


def test_fraction_left_in_name_joins_amount():
    r = n({"amount": "1", "unit": "", "name": "\u00bd lb chicken breasts, boneless skinless"})
    assert (r["amount"], r["unit"], r["name"]) == ("1 \u00bd", "lb", "chicken breasts, boneless skinless")
    r = n({"amount": "2", "unit": "", "name": "1/2 cups milk"})
    assert (r["amount"], r["unit"], r["name"]) == ("2 1/2", "cups", "milk")
