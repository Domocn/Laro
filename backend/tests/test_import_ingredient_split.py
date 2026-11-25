"""Website imports split '100g plain flour' into amount/unit/name (was all in name)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routers.ai import _split_ingredient_amounts  # noqa: E402


def _ing(name):
    return {"name": name, "amount": "", "unit": ""}


def test_splits_quantities_and_keeps_words():
    r = _split_ingredient_amounts({"ingredients": [
        _ing("100g plain flour"), _ing("300ml milk"), _ing("salt and pepper"), _ing("lemon wedges to serve"),
        {"name": "olive oil", "amount": "1", "unit": "tbsp"},
    ]})
    ings = r["ingredients"]
    assert (ings[0]["amount"], ings[0]["unit"]) == ("100", "g") and "flour" in ings[0]["name"]
    assert (ings[1]["amount"], ings[1]["unit"]) == ("300", "ml") and ings[1]["name"] == "milk"
    assert ings[2]["name"] == "salt and pepper" and ings[2]["amount"] == ""     # no quantity -> untouched
    assert ings[3]["name"] == "lemon wedges to serve"
    assert ings[4] == {"name": "olive oil", "amount": "1", "unit": "tbsp"}       # already split -> untouched
