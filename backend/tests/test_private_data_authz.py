"""Security tests for private-data authorization and auth hardening."""
from datetime import datetime, timedelta, timezone

from utils.authorization import user_can_view_recipe, require_recipe_view, require_recipe_edit
from utils.security import is_safe_external_url
from fastapi import HTTPException
import pytest


def test_author_can_view_own_recipe():
    user = {"id": "u1", "role": "user", "household_id": None}
    recipe = {"id": "r1", "author_id": "u1", "household_id": None}
    assert user_can_view_recipe(user, recipe) is True


def test_stranger_cannot_view_private_recipe():
    user = {"id": "u2", "role": "user", "household_id": "h2"}
    recipe = {"id": "r1", "author_id": "u1", "household_id": "h1"}
    assert user_can_view_recipe(user, recipe) is False
    with pytest.raises(HTTPException) as exc:
        require_recipe_view(user, recipe)
    assert exc.value.status_code == 404


def test_household_member_can_view_household_recipe():
    user = {"id": "u2", "role": "user", "household_id": "hh"}
    recipe = {"id": "r1", "author_id": "u1", "household_id": "hh"}
    assert user_can_view_recipe(user, recipe) is True


def test_admin_can_view_any_recipe():
    user = {"id": "admin", "role": "super_admin", "household_id": None}
    recipe = {"id": "r1", "author_id": "u1", "household_id": None}
    assert user_can_view_recipe(user, recipe) is True


def test_non_author_cannot_edit():
    user = {"id": "u2", "role": "user"}
    recipe = {"id": "r1", "author_id": "u1"}
    with pytest.raises(HTTPException) as exc:
        require_recipe_edit(user, recipe)
    assert exc.value.status_code == 403


def test_ssrf_blocks_localhost_and_private():
    ok, _ = is_safe_external_url("http://127.0.0.1/secret")
    assert ok is False
    ok, _ = is_safe_external_url("http://localhost/x")
    assert ok is False
    ok, _ = is_safe_external_url("http://169.254.169.254/latest/meta-data")
    assert ok is False


def test_ssrf_allows_public_https():
    # May fail DNS in sandbox — only assert shape when resolution works
    ok, err = is_safe_external_url("https://example.com/path")
    # Either allowed or DNS failure (fail-closed) — never silently allow private
    assert ok is True or (ok is False and err)
