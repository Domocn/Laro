"""Tests for creator website discovery (link-in-bio style offers)."""

from services.creator_website import (
    caption_mentions_full_recipe,
    handle_domain_candidates,
    is_social_or_linkpage_host,
    _looks_like_recipe_page,
    _norm_handle,
    _search_terms_from_caption,
    _score_recipe_url,
    _website_home,
)


def test_handle_domain_candidates_eliya():
    hosts = handle_domain_candidates("eliya.eats")
    assert "eliyaeats.com" in hosts
    assert "eliya-eats.com" in hosts


def test_norm_handle_strips_at():
    assert _norm_handle("@Eliya.Eats") == "eliya.eats"


def test_is_social_host():
    assert is_social_or_linkpage_host("www.instagram.com")
    assert is_social_or_linkpage_host("linktr.ee")
    assert not is_social_or_linkpage_host("eliyaeats.com")


def test_website_home_rejects_social():
    assert _website_home("https://www.instagram.com/eliya.eats/") is None
    assert _website_home("https://eliyaeats.com/category/recipes/") == "https://eliyaeats.com/"


def test_looks_like_recipe_page():
    assert _looks_like_recipe_page(
        "https://eliyaeats.com/baked-protein-pancake-bowls-great-for-meal-prep-and-no-banana-needed/"
    )
    assert not _looks_like_recipe_page("https://eliyaeats.com/")
    assert not _looks_like_recipe_page("https://eliyaeats.com/category/recipes/")


def test_caption_mentions_full_recipe():
    assert caption_mentions_full_recipe("My protein pancake recipe is linked in my bio")
    assert not caption_mentions_full_recipe("Just a cute lunch photo")


def test_search_terms_and_score():
    terms = _search_terms_from_caption(
        "microwave cinnamon roll protein pancake bowl\nlinked in bio",
        "Cinnamon Roll Protein Pancake Bowl",
    )
    assert terms
    assert "cinnamon" in terms[0].lower() or "Cinnamon" in terms[0]
    url = "https://eliyaeats.com/baked-protein-pancake-bowls-great-for-meal-prep-and-no-banana-needed/"
    assert _score_recipe_url(url, {"protein", "pancake", "bowl", "baked"}) >= 3
