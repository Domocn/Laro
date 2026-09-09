"""Tests for Instagram public GraphQL / reel media helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.instagram_media import (
    _dig_items,
    _item_to_meta,
    _pick_best_video_url,
    caption_looks_like_recipe,
    fetch_via_reel_media_api,
    instagram_shortcode,
)


def test_caption_looks_like_recipe():
    assert caption_looks_like_recipe(
        "Ingredients:\n2 cups flour\n1 tsp salt\nBake 20 minutes"
    )
    assert not caption_looks_like_recipe("Link in bio #fyp #viral")
    assert not caption_looks_like_recipe("What did you have for breakfast? Blame maths.")


def test_instagram_shortcode_reel_and_post():
    assert instagram_shortcode("https://www.instagram.com/reel/DOvzTywjPGN/") == "DOvzTywjPGN"
    assert instagram_shortcode("https://www.instagram.com/reels/abc_12/") == "abc_12"
    assert instagram_shortcode("https://www.instagram.com/p/C0djb2Yow4C/?hl=en") == "C0djb2Yow4C"
    assert instagram_shortcode("https://www.allrecipes.com/x") is None


def test_pick_best_video_url_prefers_largest():
    versions = [
        {"width": 480, "height": 854, "url": "http://a/small.mp4"},
        {"width": 720, "height": 1280, "url": "http://a/big.mp4"},
        {"width": 360, "height": 640, "url": "http://a/tiny.mp4"},
    ]
    assert _pick_best_video_url(versions) == "http://a/big.mp4"


def test_dig_items_web_info_shape():
    payload = {
        "data": {
            "xdt_api__v1__media__shortcode__web_info": {
                "items": [
                    {
                        "caption": {"text": "1 cup flour\nBake 20 min"},
                        "user": {"username": "baker"},
                        "video_versions": [
                            {"width": 720, "height": 1280, "url": "https://cdn.example/v.mp4"}
                        ],
                    }
                ]
            }
        }
    }
    item = _dig_items(payload)
    assert item is not None
    meta = _item_to_meta(item, "https://www.instagram.com/reel/x/")
    assert meta["uploader"] == "baker"
    assert "flour" in meta["caption"]
    assert meta["video_url"].endswith(".mp4")


@pytest.mark.asyncio
async def test_reel_media_api_parses_download_link(monkeypatch):
    monkeypatch.setenv("REEL_MEDIA_API_URL", "https://downloader.example/")

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "title": "Oats",
                "description": "Banana oats recipe",
                "download_link": "https://cdn.example/oats.mp4",
                "username": "chef",
            }

    client = AsyncMock()
    client.get = AsyncMock(return_value=FakeResp())
    meta = await fetch_via_reel_media_api(
        "https://www.instagram.com/reel/abc/", client
    )
    assert meta is not None
    assert meta["video_url"] == "https://cdn.example/oats.mp4"
    assert meta["uploader"] == "chef"
    assert meta["source"] == "reel_media_api"


@pytest.mark.asyncio
async def test_oembed_fallback_returns_caption(monkeypatch):
    from services import instagram_media as im

    monkeypatch.delenv("REEL_MEDIA_API_URL", raising=False)
    im._graphql_cooldown_until = 0.0
    im._resolve_cache.clear()

    class OembedResp:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = "{}"

        def json(self):
            return {
                "title": "1 cup oats\n2 bananas\nMix and chill overnight",
                "author_name": "chef_oats",
            }

    async def fake_gql(url, client):
        return None

    async def fake_api(url, client):
        return None

    client = AsyncMock()
    client.get = AsyncMock(return_value=OembedResp())

    with patch.object(im, "fetch_via_reel_media_api", fake_api), patch.object(
        im, "fetch_instagram_graphql_meta", fake_gql
    ), patch.object(im, "httpx") as hx:
        # resolve creates its own AsyncClient — patch the class
        class CM:
            async def __aenter__(self):
                return client

            async def __aexit__(self, *a):
                return False

        hx.AsyncClient = MagicMock(return_value=CM())
        meta = await im.resolve_instagram_media("https://www.instagram.com/reel/abc123/")

    assert meta is not None
    assert meta["source"] == "instagram_oembed"
    assert meta["uploader"] == "chef_oats"
    assert "oats" in meta["caption"].lower()
    assert meta["video_url"] is None


@pytest.mark.asyncio
async def test_graphql_cooldown_skips():
    from services import instagram_media as im

    im._mark_graphql_cooldown("test")
    assert im._graphql_on_cooldown()
    client = AsyncMock()
    assert (
        await im.fetch_instagram_graphql_meta(
            "https://www.instagram.com/reel/abc/", client
        )
        is None
    )
