"""set_rating writes TIMESTAMP columns via raw asyncpg: it must pass datetimes, not ISO strings
(ISO strings 500'd every rating/notes save)."""
import os


def test_set_rating_uses_datetime_for_db():
    src = open(os.path.join(os.path.dirname(__file__), "..", "routers", "recipes.py"), encoding="utf-8").read()
    body = src[src.index("async def set_rating("):src.index('@router.delete("/{recipe_id}/rating")')]
    assert "db_now = datetime.now(timezone.utc).replace(tzinfo=None)" in body
    assert 'personal_notes or "", now, user' not in body
    assert 'personal_notes or "", now, now' not in body
