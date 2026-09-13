"""Unit tests for SocialFetch.dev social media resolve helpers."""
from services.socialfetch_media import (
    _author_from_data,
    _caption_from_data,
    _video_from_data,
    canonicalize_social_url,
    detect_social_platform,
)


def test_detect_social_platform():
    assert detect_social_platform("https://www.tiktok.com/@chef/video/123") == "tiktok"
    assert detect_social_platform("https://vm.tiktok.com/ZMabc/") == "tiktok"
    assert detect_social_platform("https://www.youtube.com/watch?v=abc") == "youtube"
    assert detect_social_platform("https://youtu.be/abc") == "youtube"
    assert detect_social_platform("https://www.facebook.com/watch?v=1") == "facebook"
    assert detect_social_platform("https://fb.watch/xyz/") == "facebook"
    assert detect_social_platform("https://www.instagram.com/reel/abc/") == "instagram"
    assert detect_social_platform("https://www.instagram.com/share/reel/abc") == "instagram"
    assert detect_social_platform("https://www.budgetbytes.com/x") is None


def test_canonicalize_instagram_share_and_tracking():
    assert (
        canonicalize_social_url("https://www.instagram.com/share/reel/DIdOKNpx66J?igsh=abc")
        == "https://www.instagram.com/reel/DIdOKNpx66J/"
    )
    assert (
        canonicalize_social_url("https://www.instagram.com/share/p/AbCdEfGhIjK/?utm_source=ig")
        == "https://www.instagram.com/p/AbCdEfGhIjK/"
    )
    assert (
        canonicalize_social_url("https://www.instagram.com/reels/AbCdEfGhIjK/")
        == "https://www.instagram.com/reel/AbCdEfGhIjK/"
    )
    assert (
        canonicalize_social_url("https://www.instagram.com/reel/AbCdEfGhIjK/?stkn=MXQ1d2dtMGdoamE5cA==")
        == "https://www.instagram.com/reel/AbCdEfGhIjK/"
    )


def test_caption_and_author_tiktok():
    data = {
        "lookupStatus": "found",
        "video": {"caption": "Pickle sandwich recipe\n1. Bake"},
        "author": {"handle": "kalejunkie"},
        "media": {
            "downloadWithoutWatermarkUrl": "https://cdn.example/v.mp4",
            "thumbnailUrl": "https://cdn.example/t.jpg",
        },
    }
    assert "Pickle sandwich" in _caption_from_data(data, "tiktok")
    assert _author_from_data(data, "tiktok") == "kalejunkie"
    assert _video_from_data(data, "tiktok").endswith("/v.mp4")


def test_facebook_caption_description_and_hd_video():
    data = {
        "lookupStatus": "found",
        "post": {"description": "Dad of 3 recipe vibes"},
        "author": {"name": "Rob Gill", "profileUrl": "https://www.facebook.com/rob.gill.75"},
        "media": {
            "videoHdUrl": "https://video-xx.fbcdn.net/hd.mp4",
            "videoUrl": "https://video-xx.fbcdn.net/sd.mp4",
            "thumbnailUrl": "https://scontent.xx/t.jpg",
        },
    }
    assert _caption_from_data(data, "facebook") == "Dad of 3 recipe vibes"
    assert _author_from_data(data, "facebook") == "Rob Gill"
    assert _video_from_data(data, "facebook").endswith("hd.mp4")


def test_instagram_owner_and_video():
    data = {
        "lookupStatus": "found",
        "post": {"caption": "Sabrina 3 recipe? nah just shoes"},
        "owner": {"handle": "nike", "fullName": "Nike"},
        "media": {"mediaType": "video", "videoUrl": "https://cdninstagram.com/v.mp4"},
    }
    assert "Sabrina" in _caption_from_data(data, "instagram")
    assert _author_from_data(data, "instagram") == "nike"
    assert _video_from_data(data, "instagram").endswith("v.mp4")
