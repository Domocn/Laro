"""Ask Laro gets the user's fridge, soonest expiry first."""
import os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers.ai import _fridge_context_text  # noqa: E402


def test_sorted_by_expiry_with_labels():
    items = [
        {"name": "Eggs", "quantity": "6", "unit": "pcs", "expiry_date": "2026-10-30"},
        {"name": "Spinach", "quantity": "1", "unit": "bag", "expiry_date": date(2026, 10, 21)},
        {"name": "Cheddar", "expiry_date": None},
        {"name": "Milk", "expiry_date": "2026-10-19"},
    ]
    txt = _fridge_context_text(items, today=date(2026, 10, 20))
    order = [n for n in ("Milk", "Spinach", "Eggs", "Cheddar")]
    positions = [txt.index(n) for n in order]
    assert positions == sorted(positions)
    assert "Spinach (1 bag): expires tomorrow" in txt
    assert "Milk: EXPIRED 1 day(s) ago" in txt
    assert "Cheddar: no expiry date" in txt


def test_empty_fridge_adds_nothing():
    assert _fridge_context_text([]) == ""
