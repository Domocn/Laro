"""UK supermarket search deep links (user completes checkout on retailer site)."""
from __future__ import annotations

from urllib.parse import quote_plus


def uk_retailer_search_urls(query: str) -> dict[str, str]:
    q = quote_plus((query or "").strip())
    if not q:
        return {}
    return {
        "tesco": f"https://www.tesco.com/groceries/en-GB/search?query={q}",
        "sainsburys": f"https://www.sainsburys.co.uk/gol-ui/SearchResults/{q}",
        "ocado": f"https://www.ocado.com/search?entry={q}",
    }


def retailer_search_query(ingredient_name: str, matched_product: str | None = None) -> str:
    if matched_product and len(matched_product.strip()) >= 3:
        return matched_product.strip()
    return (ingredient_name or "").strip()
