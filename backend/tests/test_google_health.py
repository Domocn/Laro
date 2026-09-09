"""Unit tests for Google Health helpers (no live API)."""
import base64
import hashlib
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet


def test_fernet_roundtrip_from_jwt_secret():
    from services import google_health as gh

    with patch.object(gh.settings, "jwt_secret", "test-secret-for-unit"):
        cipher = gh.encrypt_token("access-token-xyz")
        assert cipher != "access-token-xyz"
        assert gh.decrypt_token(cipher) == "access-token-xyz"


def test_nutrition_payload_anonymous_food():
    from services import google_health as gh

    body = gh._nutrition_payload(
        title="Grilled Chicken",
        nutrition={
            "calories": 165,
            "protein": 31,
            "carbs": 0,
            "fat": 3.6,
            "sodium": 74,
        },
        servings=1.0,
        when=datetime(2026, 6, 16, 18, 0, 0, tzinfo=timezone.utc),
    )
    nl = body["nutritionLog"]
    assert nl["foodDisplayName"] == "Grilled Chicken"
    assert nl["mealType"] == "DINNER"
    assert nl["energy"]["kcal"] == 165
    assert nl["totalFat"]["grams"] == 3.6
    nutrients = {n["nutrient"]: n["quantity"]["grams"] for n in nl["nutrients"]}
    assert nutrients["PROTEIN"] == 31
    assert nutrients["SODIUM"] == pytest.approx(0.074)


def test_nutrition_payload_scales_servings():
    from services import google_health as gh

    body = gh._nutrition_payload(
        title="Pasta",
        nutrition={"calories": 100, "protein": 10, "carbs": 20, "fat": 5},
        servings=2.0,
        when=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    nl = body["nutritionLog"]
    assert nl["energy"]["kcal"] == 200
    assert nl["serving"]["amount"] == 2.0
    assert nl["totalCarbohydrate"]["grams"] == 40


def test_extract_data_point_name_from_lro():
    from services import google_health as gh

    name = gh._extract_data_point_name(
        {
            "done": True,
            "response": {
                "name": "users/me/dataTypes/nutrition-log/dataPoints/abc123",
            },
        }
    )
    assert name.endswith("/dataPoints/abc123")


def test_is_configured_requires_both():
    from services import google_health as gh

    with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": "", "GOOGLE_HEALTH_CLIENT_ID": "", "GOOGLE_HEALTH_CLIENT_SECRET": ""}, clear=False):
        # Clear health-specific then client
        os.environ.pop("GOOGLE_HEALTH_CLIENT_ID", None)
        os.environ.pop("GOOGLE_HEALTH_CLIENT_SECRET", None)
        os.environ["GOOGLE_CLIENT_ID"] = ""
        os.environ["GOOGLE_CLIENT_SECRET"] = ""
        assert gh.is_configured() is False
        os.environ["GOOGLE_CLIENT_ID"] = "cid"
        os.environ["GOOGLE_CLIENT_SECRET"] = "csecret"
        assert gh.is_configured() is True


def test_allowed_redirect_includes_deep_link():
    from services import google_health as gh

    allowed = gh.allowed_redirect_uris()
    assert "laro://oauth/callback/google-health" in allowed
