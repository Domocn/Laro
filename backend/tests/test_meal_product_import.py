"""Tests for prepared meal-pack / shake product import helpers."""
import json

from services.meal_product_import import (
    extract_products_from_html,
    meal_type_for_kind,
    normalize_product,
    parse_llm_products,
    _guess_kind,
    _html_to_text,
)


HUEL_PRODUCT_HTML = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Huel Ready-to-drink Chocolate",
  "description": "Complete nutrition in a bottle. Ready to drink shake.",
  "nutrition": {
    "@type": "NutritionInformation",
    "calories": "400 kcal",
    "proteinContent": "20 g",
    "carbohydrateContent": "37 g",
    "fatContent": "13 g"
  }
}
</script>
</head><body><h1>Huel Ready-to-drink Chocolate</h1></body></html>
"""


def test_extract_huel_rtd_from_json_ld():
    products = extract_products_from_html(HUEL_PRODUCT_HTML)
    assert len(products) == 1
    p = products[0]
    assert "Huel" in p["title"]
    assert p["kind"] in ("rtd", "shake")
    assert p["nutrition"]["calories"] == 400
    assert p["nutrition"]["protein"] == 20
    assert p["nutrition"]["carbs"] == 37
    assert p["nutrition"]["fat"] == 13


def test_guess_kind_pouch():
    assert _guess_kind("Huel Hot & Savoury Thai Green Curry", "pouch meal") == "pouch"
    assert meal_type_for_kind("pouch") == "Dinner"
    assert meal_type_for_kind("shake") == "Breakfast"


def test_parse_llm_products_json():
    raw = json.dumps(
        {
            "source_name": "Huel",
            "products": [
                {
                    "title": "Huel Black Edition Vanilla",
                    "kind": "shake",
                    "nutrition": {"calories": 400, "protein": 40, "carbs": 24, "fat": 17},
                    "instructions": ["Add 500ml water", "Shake"],
                }
            ],
        }
    )
    products = parse_llm_products(raw)
    assert len(products) == 1
    assert products[0]["title"].startswith("Huel Black")
    assert products[0]["nutrition"]["protein"] == 40
    assert "meal-pack" in products[0]["tags"]


def test_normalize_product_requires_title():
    assert normalize_product({"title": ""}) is None


def test_product_to_recipe_is_meal_pack_category():
    from services.meal_product_import import product_to_recipe, normalize_product

    prod = normalize_product(
        {
            "title": "Huel Ready-to-drink Chocolate",
            "kind": "rtd",
            "nutrition": {"calories": 400, "protein": 20, "carbs": 37, "fat": 13},
        }
    )
    recipe = product_to_recipe(prod)
    assert recipe["category"] == "Meal Pack"
    assert recipe["is_meal_pack"] is True
    assert recipe["nutrition"]["calories"] == 400
    assert recipe["servings"] == 1
    assert any(i.get("name") for i in recipe["ingredients"])
    assert recipe["instructions"]
