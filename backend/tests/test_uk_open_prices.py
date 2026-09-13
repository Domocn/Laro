"""Unit tests for UK Open Prices offline catalog helpers."""
from services.uk_open_prices import (
    normalize_price_name,
    _entry_from_price_item,
    _score_match,
    _estimate_usage_cost,
    MIN_MATCH_SCORE,
)


def test_normalize_strips_prefixes():
    assert normalize_price_name("Fresh Chicken Breast") == "chicken breast"
    # Multiple prefixes + minced
    assert normalize_price_name("Organic British Minced Beef") == "beef"


def test_entry_from_price_item_gbp_only():
    item = {
        "currency": "GBP",
        "price": 2.5,
        "date": "2026-03-01",
        "price_per": "KILOGRAM",
        "product": {
            "product_name": "Skyr Natural",
            "code": "123",
            "product_quantity": 450,
            "product_quantity_unit": "g",
        },
        "location": {"osm_brand": "Tesco"},
    }
    entry = _entry_from_price_item(item)
    assert entry is not None
    assert entry["currency"] == "GBP"
    assert entry["store"] == "Tesco"
    assert entry["per_kg"] == 2.5
    assert entry["name_norm"] == "skyr natural"


def test_entry_rejects_non_gbp():
    assert _entry_from_price_item(
        {"currency": "EUR", "price": 1.0, "product": {"product_name": "Milk"}}
    ) is None


def test_score_rejects_false_friends():
    """Short/ambiguous queries must not latch onto unrelated catalog rows."""
    cases = [
        ("graham flour", {"name": "Plain White Flour", "name_norm": "plain white flour"}),
        ("boiling water", {"name": "collagen water", "name_norm": "collagen water"}),
        ("banana", {"name": "Banana Chips", "name_norm": "banana chips"}),
        ("milk", {"name": "Oat Milk", "name_norm": "oat milk"}),
        ("milk", {"name": "Milk crispy wafer", "name_norm": "milk crispy wafer"}),
        ("salt", {"name": "Peri peri salt", "name_norm": "peri peri salt"}),
        ("salt", {"name": "Salt & pepper chicken", "name_norm": "salt pepper chicken"}),
        ("black pepper", {"name": "Lemon & Black Pepper Peri-naise", "name_norm": "lemon black pepper peri-naise"}),
        ("black pepper", {"name": "Black Pepper & Sea Salt Crackers", "name_norm": "black pepper sea salt crackers"}),
        ("black pepper", {"name": "Sea Salt & Black Pepper Basa Fillets", "name_norm": "sea salt black pepper basa fillets"}),
        ("ham", {"name": "Ham Stock Cubes", "name_norm": "ham stock cubes"}),
        ("pea", {"name": "Chick peas", "name_norm": "chick peas"}),
        (
            "Paprika, garlic granules, salt and black pepper",
            {"name": "Sea Salt & Black Pepper Basa Fillets", "name_norm": "sea salt black pepper basa fillets"},
        ),
    ]
    for query, entry in cases:
        assert _score_match(query, entry) < MIN_MATCH_SCORE, (query, entry["name"], _score_match(query, entry))


def test_score_accepts_good_matches():
    cases = [
        ("chicken breast", {"name": "Chicken Breast Mini Fillets", "name_norm": "chicken breast mini fillets"}),
        ("peanut butter", {"name": "Peanut Butter", "name_norm": "peanut butter"}),
        ("butter", {"name": "Butter", "name_norm": "butter"}),
        ("garlic", {"name": "Garlic", "name_norm": "garlic"}),
        ("olive oil", {"name": "Organic extra virgin olive oil", "name_norm": "organic extra virgin olive oil"}),
        ("broccoli", {"name": "Broccoli", "name_norm": "broccoli"}),
        ("banana", {"name": "Bananas", "name_norm": "bananas"}),
        ("onion", {"name": "Brown Onions", "name_norm": "brown onions"}),
    ]
    for query, entry in cases:
        assert _score_match(query, entry) >= MIN_MATCH_SCORE, (query, entry["name"], _score_match(query, entry))


def test_estimate_uses_per_kg_not_broken_median_pack():
    entry = {"price": 3.50, "per_kg": 7.0, "quantity": 500, "quantity_unit": "g"}
    cost, method = _estimate_usage_cost(entry, 200, "g")
    assert method == "per_kg"
    assert cost == 1.40


def test_estimate_count_share_for_eggs():
    entry = {"price": 2.50, "quantity": 6, "quantity_unit": None, "per_kg": None}
    cost, method = _estimate_usage_cost(entry, 6, None)
    assert method == "count_share"
    assert cost == 2.50  # whole pack
