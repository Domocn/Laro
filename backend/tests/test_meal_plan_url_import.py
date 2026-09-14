"""Tests for meal-plan URL helpers (no network)."""
import pytest

from services.meal_plan_url_import import (
    looks_like_structured_meal_plan,
    normalize_meal_plan_url,
    _html_to_text,
)
from services.meal_plan_import import parse_meal_plan_text


def test_normalize_adds_https():
    assert normalize_meal_plan_url("example.com/plan").startswith("https://")


def test_normalize_rejects_blank():
    with pytest.raises(ValueError):
        normalize_meal_plan_url("  ")


def test_looks_like_structured_meal_plan_positive():
    text = """
DINNER 1 — Huel Hot & Savoury Thai Green Curry
Served Monday and Thursday
Ingredients
● 1 pouch Huel Hot & Savoury
Method
1. Add water and stir
Macros
400 kcal | 25 g protein | 40 g carbohydrate | 12 g fat
"""
    assert looks_like_structured_meal_plan(text) is True
    plan = parse_meal_plan_text(text)
    assert any("Huel" in m.title for m in plan.meals)


def test_looks_like_structured_meal_plan_product_page_negative():
    text = """
Shop Huel ready-to-drink
Chocolate 400 kcal
Vanilla 380 kcal
Add to bag
"""
    assert looks_like_structured_meal_plan(text) is False


def test_html_to_text_strips_scripts():
    html = "<html><script>evil()</script><body><h1>Meal Plan</h1><p>Dinner</p></body></html>"
    text = _html_to_text(html)
    assert "evil" not in text
    assert "Meal Plan" in text
    assert "Dinner" in text
