"""Unit tests for cookbook buy-search helpers and link safety."""
import os

import pytest

from routers.cookbooks import (
    _build_buy_links,
    _dedupe_results,
    _pick_isbn,
    _safe_outbound_url,
)
from models import CookbookBuySearchResult


def test_pick_isbn_prefers_isbn13():
    assert _pick_isbn(["0451524934", "9780451524935"]) == "9780451524935"
    assert _pick_isbn(["979-8-8495-9641-9"]) == "9798849596419"
    assert _pick_isbn([]) is None


def test_safe_outbound_blocks_pirate_hosts():
    assert _safe_outbound_url("https://openlibrary.org/works/OL1W")
    assert _safe_outbound_url("https://libgen.is/book/x") is None
    assert _safe_outbound_url("https://z-library.se/book") is None
    assert _safe_outbound_url("not-a-url") is None


def test_build_buy_links_legal_only_no_filetype_pdf():
    links = _build_buy_links(
        title="Salt Fat Acid Heat",
        author="Samin Nosrat",
        isbn="9781476753836",
        publisher="Simon & Schuster",
        open_library_key="/works/OL18147901W",
        archive_id="saltfatacidheat00nosr",
    )
    kinds = {link.kind for link in links}
    assert "amazon" in kinds
    assert "bookshop" in kinds
    assert "open_library" in kinds
    assert "archive" in kinds
    assert "drm_free_search" in kinds
    assert "publisher" in kinds

    for link in links:
        assert "filetype:pdf" not in link.url.lower()
        assert "libgen" not in link.url.lower()
        assert "zlib" not in link.url.lower()

    drm = next(link for link in links if link.kind == "drm_free_search")
    assert "PDF" in drm.url or "pdf" in drm.url.lower()
    assert "buy" in drm.url.lower()


def test_amazon_affiliate_tag_only_when_configured(monkeypatch):
    monkeypatch.delenv("AMAZON_AFFILIATE_TAG", raising=False)
    links = _build_buy_links(
        title="Joy of Cooking",
        author="Rombauer",
        isbn="9780743246262",
        publisher=None,
        open_library_key=None,
    )
    amazon = next(link for link in links if link.kind == "amazon")
    assert "tag=" not in amazon.url

    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "laro-20")
    links2 = _build_buy_links(
        title="Joy of Cooking",
        author="Rombauer",
        isbn="9780743246262",
        publisher=None,
        open_library_key=None,
    )
    amazon2 = next(link for link in links2 if link.kind == "amazon")
    assert "tag=laro-20" in amazon2.url


def test_dedupe_results_by_isbn_and_title():
    a = CookbookBuySearchResult(title="A", author="X", isbn="9780000000001", source="open_library")
    b = CookbookBuySearchResult(title="A", author="X", isbn="9780000000001", source="google_books")
    c = CookbookBuySearchResult(title="B", author="Y", isbn=None, source="open_library")
    out = _dedupe_results([a, b, c], limit=10)
    assert len(out) == 2
    assert out[0].isbn == "9780000000001"
