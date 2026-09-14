"""Unit tests for Cobalt social media fallback."""
from services.cobalt_media import (
    _author_from_url,
    _pick_video_url,
    merge_social_meta,
)


def test_author_from_tiktok_url():
    assert (
        _author_from_url("https://www.tiktok.com/@kalejunkie/video/7496658508012637470")
        == "kalejunkie"
    )


def test_author_from_instagram_url():
    assert _author_from_url("https://www.instagram.com/reel/abc/") == ""
    assert _author_from_url("https://www.instagram.com/@chef/reel/abc/") == "chef"


def test_pick_tunnel_url():
    video, thumb = _pick_video_url(
        {"status": "tunnel", "url": "https://cobalt.example/tunnel/abc", "filename": "x.mp4"}
    )
    assert video.endswith("/tunnel/abc")
    assert thumb is None


def test_pick_picker_prefers_video():
    video, thumb = _pick_video_url(
        {
            "status": "picker",
            "picker": [
                {"type": "photo", "url": "https://x/p.jpg"},
                {"type": "video", "url": "https://x/v.mp4", "thumb": "https://x/t.jpg"},
            ],
        }
    )
    assert video == "https://x/v.mp4"
    assert thumb == "https://x/t.jpg"


def test_merge_fills_video_from_cobalt():
    primary = {
        "source": "socialfetch_tiktok",
        "uploader": "kalejunkie",
        "caption": "recipe text",
        "description": "recipe text",
        "video_url": None,
        "thumbnail": "",
    }
    secondary = {
        "source": "cobalt",
        "uploader": "kalejunkie",
        "caption": "",
        "video_url": "https://cobalt/tunnel/1",
        "thumbnail": "https://t.jpg",
    }
    merged = merge_social_meta(primary, secondary)
    assert merged["video_url"] == "https://cobalt/tunnel/1"
    assert merged["caption"] == "recipe text"
    assert merged["uploader"] == "kalejunkie"
    assert "cobalt" in merged["source"]


def test_merge_cobalt_only():
    cobalt = {"source": "cobalt", "video_url": "https://x", "uploader": "a"}
    assert merge_social_meta(None, cobalt)["video_url"] == "https://x"
