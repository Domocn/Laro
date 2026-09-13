"""Tests for Honeydew-style source attribution (IG handles + website authors)."""

from bs4 import BeautifulSoup

from routers.ai import (
    extract_html_page_author,
    extract_schema_author,
    normalize_source_author,
    parse_recipe_object,
    with_source_meta,
)


def test_normalize_instagram_handle():
    assert normalize_source_author("@jacobchamings_pt") == "jacobchamings_pt"
    assert normalize_source_author("https://www.instagram.com/chef_oats/") == "chef_oats"
    assert normalize_source_author("  Chef.Oats  ") == "Chef.Oats"


def test_normalize_website_author_and_host():
    assert normalize_source_author("Smitten Kitchen") == "Smitten Kitchen"
    assert normalize_source_author("bonappetit.com") == "bonappetit.com"
    assert normalize_source_author({"name": "Deb Perelman"}) == "Deb Perelman"
    assert normalize_source_author(["Alice Waters"]) == "Alice Waters"
    assert normalize_source_author("This is a very long caption that should not be treated as an author name at all") is None


def test_extract_schema_author_from_person():
    data = {
        "@type": "Recipe",
        "name": "Pasta",
        "author": {"@type": "Person", "name": "Ina Garten"},
        "recipeIngredient": ["1 lb pasta"],
        "recipeInstructions": ["Boil water"],
    }
    assert extract_schema_author(data) == "Ina Garten"
    parsed = parse_recipe_object(data)
    assert parsed["source_author"] == "Ina Garten"


def test_extract_html_page_author_prefers_meta_then_host():
    html = """
    <html><head>
      <meta name="author" content="Serious Eats" />
      <meta property="og:site_name" content="Serious Eats" />
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert extract_html_page_author(soup, "https://www.seriouseats.com/pasta") == "Serious Eats"

    bare = BeautifulSoup("<html><head></head></html>", "html.parser")
    assert extract_html_page_author(bare, "https://www.budgetbytes.com/chili") == "budgetbytes.com"


def test_extract_html_page_author_wprm_byline():
    html = """
    <html><body>
      <div class="wprm-recipe-author">Beth Moncel</div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert extract_html_page_author(soup, "https://www.budgetbytes.com/x") == "Beth Moncel"


def test_with_source_meta_attaches_author():
    payload = with_source_meta(
        {"status": "success", "recipe": {"title": "Soup"}},
        "https://example.com/soup",
        author="Example Kitchen",
    )
    assert payload["source_author"] == "Example Kitchen"
    assert payload["recipe"]["source_author"] == "Example Kitchen"
    assert payload["source_url"] == "https://example.com/soup"
