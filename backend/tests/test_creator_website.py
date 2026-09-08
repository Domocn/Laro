"""Tests for creator website discovery (link-in-bio style offers)."""

from services.creator_website import (
    caption_mentions_dm_gate,
    caption_mentions_full_recipe,
    handle_domain_candidates,
    host_plausibly_matches_handle,
    is_social_or_linkpage_host,
    _handle_host_score,
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


def test_caption_mentions_dm_gate():
    assert caption_mentions_dm_gate(
        'CARAMEL SLICE WEET-BIX! COMMENT “SLICE” AND I’LL SEND IT OVER'
    )
    assert caption_mentions_dm_gate("DM me for the full recipe")
    assert caption_mentions_dm_gate("Comment RECIPE and I'll send it to your inbox")
    assert not caption_mentions_dm_gate("Full recipe linked in my bio")
    assert not caption_mentions_dm_gate("2 weetabix, 60ml milk, 150g yogurt")


def test_handle_host_score_rejects_wrong_blog():
    assert _handle_host_score("running.and.mumming", "paleorunningmomma.com") < 6
    assert host_plausibly_matches_handle("cindafit.com.au", "cindafit_nutrition")
    assert host_plausibly_matches_handle("joytothefood.com", "_joytothefood_")
    assert host_plausibly_matches_handle("eliyaeats.com", "eliya.eats")


def test_search_terms_and_score():
    terms = _search_terms_from_caption(
        "microwave cinnamon roll protein pancake bowl\nlinked in bio",
        "Cinnamon Roll Protein Pancake Bowl",
    )
    assert terms
    assert "cinnamon" in terms[0].lower() or "Cinnamon" in terms[0]
    url = "https://eliyaeats.com/baked-protein-pancake-bowls-great-for-meal-prep-and-no-banana-needed/"
    assert _score_recipe_url(url, {"protein", "pancake", "bowl", "baked"}) >= 3


def test_search_terms_joytothefood_review_caption():
    title = (
        "“These are the best pancake recipe without protein powder ever! "
        "They turned out just like the picture, fluffy and great "
    )
    caption = (
        "“These are the best pancake recipe without protein powder ever!\"\n\n"
        "⭐Comment RECIPE or PANCAKE and I’ll send ya how to make them!\n\n"
        "recipe + full details also linked in bio ✨"
    )
    terms = _search_terms_from_caption(caption, title)
    blob = " ".join(terms).lower()
    assert "pancake" in blob
    assert "without" in blob and "protein" in blob
    # Should not be dominated by review fluff slug
    assert not any(t.startswith("these best pancake") for t in terms)
