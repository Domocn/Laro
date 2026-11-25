"""Regression tests for PR #301: private-recipe IDOR fixes and cover-import SSRF checks."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import routers.favorites as favorites
import routers.recipe_versions as recipe_versions
import routers.voice_cooking as voice_cooking
import utils.image_store as image_store
import utils.security as security

OWNER = {"id": "owner", "role": "user", "household_id": "h1"}
STRANGER = {"id": "stranger", "role": "user", "household_id": "h2"}
HOUSEMATE = {"id": "mate", "role": "user", "household_id": "h1"}
PRIVATE_RECIPE = {
    "id": "r1", "author_id": "owner", "household_id": "h1",
    "title": "Secret", "ingredients": [], "instructions": ["Step"], "current_version": 2,
}


@pytest.fixture
def repos(monkeypatch):
    recipe_repo = MagicMock()
    recipe_repo.find_by_id = AsyncMock(return_value=dict(PRIVATE_RECIPE))
    recipe_repo.update_recipe = AsyncMock()
    version_repo = MagicMock()
    version_repo.find_by_recipe = AsyncMock(return_value=[])
    version_repo.get_version = AsyncMock(
        return_value={"recipe_id": "r1", "version": 1, "data": {"title": "Old"}, "created_by": "owner"}
    )
    version_repo.get_next_version_number = AsyncMock(return_value=3)
    version_repo.create_version = AsyncMock()
    user_repo = MagicMock()
    user_repo.find_by_id = AsyncMock(return_value={"name": "Owner"})
    user_repo.add_favorite = AsyncMock()

    for mod in (recipe_versions, favorites, voice_cooking):
        monkeypatch.setattr(mod, "recipe_repository", recipe_repo, raising=False)
    monkeypatch.setattr(recipe_versions, "recipe_version_repository", version_repo)
    monkeypatch.setattr(recipe_versions, "user_repository", user_repo)
    monkeypatch.setattr(favorites, "user_repository", user_repo)
    return recipe_repo, version_repo, user_repo


async def _assert_hidden(coro):
    with pytest.raises(HTTPException) as exc:
        await coro
    assert exc.value.status_code == 404


# --- Recipe versions -------------------------------------------------------

@pytest.mark.asyncio
async def test_stranger_cannot_list_versions(repos):
    await _assert_hidden(recipe_versions.list_recipe_versions("r1", user=STRANGER))


@pytest.mark.asyncio
async def test_stranger_cannot_read_version(repos):
    _, version_repo, _ = repos
    await _assert_hidden(recipe_versions.get_recipe_version("r1", 1, user=STRANGER))
    version_repo.get_version.assert_not_called()


@pytest.mark.asyncio
async def test_stranger_cannot_compare_versions(repos):
    data = recipe_versions.VersionCompare(version_a=1, version_b=2)
    await _assert_hidden(recipe_versions.compare_recipe_versions("r1", data, user=STRANGER))


@pytest.mark.asyncio
async def test_stranger_cannot_restore_version(repos):
    recipe_repo, _, _ = repos
    await _assert_hidden(recipe_versions.restore_recipe_version("r1", 1, user=STRANGER))
    recipe_repo.update_recipe.assert_not_called()


@pytest.mark.asyncio
async def test_owner_and_household_can_read_versions(repos):
    for user in (OWNER, HOUSEMATE):
        result = await recipe_versions.get_recipe_version("r1", 1, user=user)
        assert result["version"] == 1
        listing = await recipe_versions.list_recipe_versions("r1", user=user)
        assert listing["recipe_id"] == "r1"


@pytest.mark.asyncio
async def test_missing_recipe_returns_404(repos):
    recipe_repo, _, _ = repos
    recipe_repo.find_by_id.return_value = None
    await _assert_hidden(recipe_versions.get_recipe_version("nope", 1, user=OWNER))


# --- Favorites -------------------------------------------------------------

@pytest.mark.asyncio
async def test_stranger_cannot_favorite_private_recipe(repos):
    _, _, user_repo = repos
    await _assert_hidden(favorites.add_favorite("r1", user=STRANGER))
    user_repo.add_favorite.assert_not_called()


@pytest.mark.asyncio
async def test_owner_can_favorite(repos):
    result = await favorites.add_favorite("r1", user=OWNER)
    assert result["is_favorite"] is True


# --- Voice cooking ---------------------------------------------------------

@pytest.mark.asyncio
async def test_stranger_cannot_prepare_voice_steps(repos):
    await _assert_hidden(voice_cooking.prepare_recipe_for_voice("r1", user=STRANGER))


@pytest.mark.asyncio
async def test_owner_can_prepare_voice_steps(repos):
    result = await voice_cooking.prepare_recipe_for_voice("r1", user=OWNER)
    assert result["recipe_id"] == "r1"


# --- Cover import SSRF -----------------------------------------------------

def _resp(status=200, location=None, content=b"x" * 128):
    r = MagicMock()
    r.is_redirect = location is not None
    r.headers = {"location": location} if location else {}
    r.content = content
    r.raise_for_status = MagicMock()
    return r


def _fake_safety(blocked_hosts):
    def check(url):
        from urllib.parse import urlparse
        host = urlparse(url).hostname
        return (False, "blocked") if host in blocked_hosts else (True, None)
    return check


@pytest.fixture
def no_save(monkeypatch):
    monkeypatch.setattr(image_store, "save_compressed_jpeg", lambda data, prefix="": "/api/uploads/x.jpg")


@pytest.mark.asyncio
async def test_cover_blocks_private_image_url(monkeypatch, no_save):
    monkeypatch.setattr(security, "is_safe_external_url", _fake_safety({"10.0.0.5"}))
    client = MagicMock()
    client.get = AsyncMock()
    assert await image_store.stash_remote_cover(client, "http://10.0.0.5/admin.png") is None
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_cover_blocks_redirect_to_metadata(monkeypatch, no_save):
    monkeypatch.setattr(security, "is_safe_external_url", _fake_safety({"169.254.169.254"}))
    client = MagicMock()
    client.get = AsyncMock(return_value=_resp(302, location="http://169.254.169.254/latest/meta-data"))
    assert await image_store.stash_remote_cover(client, "https://cdn.example.com/a.jpg") is None
    assert client.get.await_count == 1
    assert client.get.await_args.kwargs["follow_redirects"] is False


@pytest.mark.asyncio
async def test_cover_follows_safe_relative_redirect(monkeypatch, no_save):
    monkeypatch.setattr(security, "is_safe_external_url", _fake_safety(set()))
    client = MagicMock()
    client.get = AsyncMock(side_effect=[_resp(301, location="/real.jpg"), _resp()])
    assert await image_store.stash_remote_cover(client, "https://cdn.example.com/a.jpg") == "/api/uploads/x.jpg"
    assert client.get.await_args_list[1].args[0] == "https://cdn.example.com/real.jpg"


@pytest.mark.asyncio
async def test_cover_gives_up_on_redirect_loop(monkeypatch, no_save):
    monkeypatch.setattr(security, "is_safe_external_url", _fake_safety(set()))
    client = MagicMock()
    client.get = AsyncMock(return_value=_resp(302, location="https://cdn.example.com/loop"))
    assert await image_store.stash_remote_cover(client, "https://cdn.example.com/a.jpg") is None
    assert client.get.await_count == 5
