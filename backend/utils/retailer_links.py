"""UK online supermarket search deep links (checkout always on the retailer site)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, quote_plus

# id, display label, search URL template ({q} = URL-encoded query)
UK_ONLINE_GROCERS: Tuple[Tuple[str, str, str], ...] = (
    ("tesco", "Tesco", "https://www.tesco.com/groceries/en-GB/search?query={q}"),
    (
        "sainsburys",
        "Sainsbury's",
        "https://www.sainsburys.co.uk/gol-ui/SearchResults/{q}",
    ),
    ("asda", "Asda", "https://groceries.asda.com/search?q={q}"),
    ("morrisons", "Morrisons", "https://groceries.morrisons.com/search?q={q}"),
    ("waitrose", "Waitrose", "https://www.waitrose.com/ecom/search?searchTerm={q}"),
    ("ocado", "Ocado", "https://www.ocado.com/search?entry={q}"),
    ("aldi", "Aldi", "https://www.aldi.co.uk/results?query={q}"),
    ("lidl", "Lidl", "https://www.lidl.co.uk/q/search?q={q}"),
    ("iceland", "Iceland", "https://www.iceland.co.uk/search?q={q}"),
    (
        "marksandspencer",
        "M&S Food",
        "https://www.marksandspencer.com/l/food/search?q={q}",
    ),
    ("coop", "Co-op", "https://www.coop.co.uk/shop/search?q={q}"),
    ("booths", "Booths", "https://www.booths.co.uk/search?q={q}"),
    (
        "amazon",
        "Amazon",
        "https://www.amazon.co.uk/s?k={q}&i=amazonfresh",
    ),
)

# Open Prices / receipt store strings → retailer id
_STORE_ALIASES: Dict[str, str] = {
    "tesco": "tesco",
    "sainsbury": "sainsburys",
    "sainsburys": "sainsburys",
    "asda": "asda",
    "morrisons": "morrisons",
    "waitrose": "waitrose",
    "ocado": "ocado",
    "aldi": "aldi",
    "lidl": "lidl",
    "iceland": "iceland",
    "marks": "marksandspencer",
    "m&s": "marksandspencer",
    "spencer": "marksandspencer",
    "co-op": "coop",
    "coop": "coop",
    "booths": "booths",
    "amazon": "amazon",
}


def retailer_search_query(ingredient_name: str, matched_product: str | None = None) -> str:
    if matched_product and len(matched_product.strip()) >= 3:
        return matched_product.strip()
    return (ingredient_name or "").strip()


def _encode_query(query: str, *, use_plus: bool = True) -> str:
    text = (query or "").strip()
    if not text:
        return ""
    if use_plus:
        return quote_plus(text)
    return quote(text, safe="")


def retailer_catalog() -> List[Dict[str, str]]:
    return [{"id": rid, "label": label} for rid, label, _ in UK_ONLINE_GROCERS]


def uk_retailer_search_urls(query: str) -> Dict[str, str]:
    """Search URLs for every supported UK online grocer."""
    q_plus = _encode_query(query, use_plus=True)
    q_path = _encode_query(query, use_plus=False)
    if not q_plus:
        return {}

    out: Dict[str, str] = {}
    for rid, _label, template in UK_ONLINE_GROCERS:
        if "{q}" not in template:
            continue
        # Sainsbury's gol-ui uses path segment (often plus-encoded)
        if rid == "sainsburys":
            out[rid] = template.format(q=q_plus)
        elif rid in ("waitrose", "marksandspencer", "lidl"):
            out[rid] = template.format(q=q_plus)
        else:
            out[rid] = template.format(q=q_plus if "search?" in template or "?q=" in template else q_path)
    return out


def match_retailer_id_from_store(store: Optional[str]) -> Optional[str]:
    if not store:
        return None
    norm = re.sub(r"[^a-z0-9&'\s-]+", " ", str(store).lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    for needle, rid in _STORE_ALIASES.items():
        if needle in norm:
            return rid
    return None


def enrich_item_retailer_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    """Attach retailer_links and preferred_retailer_id from name + optional store hint."""
    query = retailer_search_query(item.get("name") or "", item.get("product_hint"))
    links = uk_retailer_search_urls(query)
    if links:
        item["retailer_links"] = links
    pref = match_retailer_id_from_store(item.get("store_hint"))
    if pref:
        item["preferred_retailer_id"] = pref
    return item
