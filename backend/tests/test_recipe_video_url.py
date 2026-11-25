"""Recipe video links are stored server-side (were device-only on Android)."""
import os, sys
import pytest
from fastapi import HTTPException
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import RecipeCreate  # noqa: E402
from routers.recipes import _clean_video_url  # noqa: E402


def test_video_url_optional_and_tracked():
    base = {"title": "T", "ingredients": [], "instructions": ["x"]}
    assert "video_url" not in RecipeCreate(**base).model_fields_set   # omitted -> keep existing
    assert "video_url" in RecipeCreate(**base, video_url="https://youtu.be/x").model_fields_set


def test_clean_video_url():
    assert _clean_video_url("  https://www.youtube.com/watch?v=abc ") == "https://www.youtube.com/watch?v=abc"
    assert _clean_video_url("") is None
    with pytest.raises(HTTPException):
        _clean_video_url("javascript:alert(1)")
