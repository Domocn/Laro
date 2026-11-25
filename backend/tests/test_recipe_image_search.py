"""Tests for matching relevant cover images to imported recipes."""
import pytest

from services.recipe_image_search import (
    curated_unsplash_for_title,
    extract_search_terms,
    _is_usable_image_url,
    _score_label,
)


def test_extract_search_terms_weetabix_cheesecake():
    terms = extract_search_terms("Original Protein Overnight Weetabix (Cheesecake-Style)")
    joined = " ".join(terms).lower()
    assert "weetabix" in joined
    assert "cheesecake" in joined
    # Stopwords stripped
    assert "original" not in terms[0].lower().split() or "weetabix" in terms[0].lower()


def test_extract_search_terms_mango_lassi():
    terms = extract_search_terms("Mango Lassi Custard (High Protein Optional)")
    joined = " ".join(terms).lower()
    assert "mango" in joined
    assert "lassi" in joined or "custard" in joined


def test_curated_weetabix_and_cheesecake():
    url = curated_unsplash_for_title("Original Protein Overnight Weetabix (Cheesecake-Style)")
    assert url and "images.unsplash.com" in url
    # Weetabix keyword should win over generic breakfast hash
    assert "photo-1664802460246" in url


def test_curated_cereal_not_eggs():
    url = curated_unsplash_for_title("Cinnamon Cheerios with milk")
    assert url and "photo-1572319216151" in url


def test_extract_search_terms_skips_n_ingredient_and_healthy():
    pizza = " ".join(extract_search_terms("2 Ingredient Pizza")).lower()
    assert "pizza" in pizza
    assert "ingredient" not in pizza

    bread = " ".join(extract_search_terms("4 Ingredient Healthy Banana Bread")).lower()
    assert "banana" in bread
    assert "bread" in bread
    assert "ingredient" not in bread
    assert "healthy" not in bread.split()


def test_curated_dish_photos_not_generic_stock():
    meat = curated_unsplash_for_title("Beef meat balls", category="Dinner")
    assert meat and "photo-1529042410759" in meat
    assert "photo-1467003909585" not in meat  # salmon

    pizza = curated_unsplash_for_title("2 Ingredient Pizza")
    assert pizza and "photo-1565299624946" in pizza

    bread = curated_unsplash_for_title("4 Ingredient Healthy Banana Bread")
    assert bread and "photo-1632931057819" in bread
    assert "photo-1517673400267" not in bread  # oats
    assert "photo-1490474418585" not in bread  # fruit bowl

    bars = curated_unsplash_for_title("Pear and nut bar")
    assert bars and "photo-1705868432559" in bars


def test_word_boundary_oat_does_not_match_goat():
    url = curated_unsplash_for_title("Goat cheese tart")
    assert url is None or "photo-1517673400267" not in url


def test_reject_logo_urls():
    assert not _is_usable_image_url(
        "https://upload.wikimedia.org/wikipedia/en/a/ab/Weetabix_logo.png",
        label="Weetabix logo",
    )
    assert _is_usable_image_url(
        "https://upload.wikimedia.org/wikipedia/commons/c/c1/Banana_foster_cheesecake.jpg",
        mime="image/jpeg",
        label="File:Banana foster cheesecake.jpg",
    )


def test_score_prefers_matching_food_label():
    assert _score_label("New York cheesecake", ["cheesecake"]) > _score_label(
        "Random car photo", ["cheesecake"]
    )
    assert _score_label("Brand logo icon", ["weetabix"]) < 0


@pytest.mark.asyncio
async def test_find_matching_cheesecake_live():
    """Live network: skip if offline."""
    httpx = pytest.importorskip("httpx")
    from services.recipe_image_search import find_matching_recipe_image

    try:
        url = await find_matching_recipe_image("New York Cheesecake")
    except Exception:
        pytest.skip("network unavailable")
    if not url:
        pytest.skip("no image returned")
    assert url.startswith("https://")
