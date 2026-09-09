"""Tests for Open Prices correction (outlier drops + aggregation)."""
from services.uk_price_corrector import (
    sanitize_price_entry,
    aggregate_price_entries,
    apply_reference_clamps,
)


def test_sanitize_drops_typo_staple_pack():
    entry = {
        "name": "Semi skimmed milk",
        "name_norm": "semi skimmed milk",
        "price": 99.0,
        "quantity": 1000,
        "quantity_unit": "ml",
        "per_kg": 99.0,
        "product_code": "123",
    }
    assert sanitize_price_entry(entry) is None


def test_sanitize_strips_per_kg_from_tiny_sachet():
    entry = {
        "name": "Ham Stock Cubes",
        "name_norm": "ham stock cubes",
        "price": 1.5,
        "quantity": 10,
        "quantity_unit": "g",
        "per_kg": 150.0,
        "product_code": "456",
    }
    cleaned = sanitize_price_entry(entry)
    assert cleaned is not None
    # stock cubes are spice-like → may keep high per_kg; use a non-spice tiny pack
    entry2 = {
        "name": "Chicken Breast Fillets",
        "name_norm": "chicken breast fillets",
        "price": 3.5,
        "quantity": 40,
        "quantity_unit": "g",
        "per_kg": 87.5,
        "product_code": "789",
    }
    cleaned2 = sanitize_price_entry(entry2)
    assert cleaned2 is not None
    assert cleaned2["per_kg"] is None
    assert cleaned2["price"] == 3.5


def test_aggregate_medians_and_drops_outlier():
    rows = [
        {
            "id": "a",
            "name": "Chicken Breast",
            "name_norm": "chicken breast",
            "price": 6.0,
            "quantity": 500,
            "quantity_unit": "g",
            "per_kg": 12.0,
            "product_code": "999",
            "observed_date": "2026-01-01",
        },
        {
            "id": "b",
            "name": "Chicken Breast",
            "name_norm": "chicken breast",
            "price": 5.5,
            "quantity": 500,
            "quantity_unit": "g",
            "per_kg": 11.0,
            "product_code": "999",
            "observed_date": "2026-02-01",
        },
        {
            "id": "c",
            "name": "Chicken Breast",
            "name_norm": "chicken breast",
            "price": 20.0,  # outlier vs ~£5.75 median (still passes sanitize)
            "quantity": 500,
            "quantity_unit": "g",
            "per_kg": 40.0,
            "product_code": "999",
            "observed_date": "2026-03-01",
        },
    ]
    out, stats = aggregate_price_entries(rows)
    assert stats["outliers_dropped"] >= 1
    assert len(out) == 1
    assert 5.0 <= out[0]["price"] <= 7.0
    assert out[0]["per_kg"] is not None
    assert 10.0 <= out[0]["per_kg"] <= 13.0


def test_reference_clamp_replaces_wild_per_kg():
    entries = [
        {
            "name": "Chicken Breast Mini Fillets",
            "price": 4.0,
            "per_kg": 55.0,  # wild
            "quantity": 400,
            "quantity_unit": "g",
        }
    ]
    refs = {
        "en:chicken-breasts": {
            "median_per_kg": 7.5,
            "n": 40,
            "band": (3.0, 16.0, 20.0),
        }
    }
    out, clamped = apply_reference_clamps(entries, refs)
    assert clamped == 1
    assert out[0]["per_kg"] == 7.5
    assert out[0]["per_kg_source"] == "open_prices_consensus"
