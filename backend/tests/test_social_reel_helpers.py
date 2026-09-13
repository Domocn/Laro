"""Unit tests for social reel / login-wall helpers used by import-url."""

from routers.ai import (
    _is_social_reel_url,
    _looks_like_login_wall,
)


def test_is_social_reel_url_instagram_reel():
    assert _is_social_reel_url("https://www.instagram.com/reel/DcwDHf1OJtr/")
    assert _is_social_reel_url("https://www.instagram.com/reels/abc/")
    assert _is_social_reel_url("https://www.tiktok.com/@x/video/123")


def test_is_social_reel_url_rejects_non_social():
    assert not _is_social_reel_url("https://www.allrecipes.com/recipe/123/pasta/")


def test_looks_like_login_wall():
    wall = (
        "Log into Instagram\n"
        "Sign up to see photos and videos from your friends.\n"
        "Don't have an account? Sign up.\n"
    )
    assert _looks_like_login_wall(wall)
    recipe = "Ingredients\n2 tablespoons olive oil\nPreheat oven to 180C\n1 cup of flour"
    assert not _looks_like_login_wall(recipe)
