import pytest

from utils.retailer_links import (
    match_retailer_id_from_store,
    retailer_catalog,
    uk_retailer_search_urls,
)


def test_catalog_covers_major_uk_grocers():
    ids = {r["id"] for r in retailer_catalog()}
    for expected in (
        "tesco",
        "sainsburys",
        "asda",
        "morrisons",
        "waitrose",
        "ocado",
        "aldi",
        "lidl",
        "iceland",
        "marksandspencer",
        "coop",
    ):
        assert expected in ids


def test_search_urls_for_query():
    urls = uk_retailer_search_urls("semi skimmed milk")
    assert "tesco" in urls
    assert "semi" in urls["tesco"].lower() or "milk" in urls["tesco"].lower()
    assert urls["asda"].startswith("https://groceries.asda.com/search")
    assert len(urls) >= 10


@pytest.mark.parametrize(
    "store,expected",
    [
        ("Tesco Extra", "tesco"),
        ("Sainsbury's Local", "sainsburys"),
        ("ASDA Superstore", "asda"),
        ("Waitrose & Partners", "waitrose"),
        ("M&S Simply Food", "marksandspencer"),
    ],
)
def test_store_hint_matching(store, expected):
    assert match_retailer_id_from_store(store) == expected
