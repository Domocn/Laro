from datetime import datetime, timezone

from utils.share_links import generate_share_code, parse_share_expiry, public_share_path


def test_parse_share_expiry_accepts_datetime():
    dt = datetime(2026, 12, 7, 19, 17, 31, tzinfo=timezone.utc)
    assert parse_share_expiry(dt) == dt


def test_parse_share_expiry_accepts_naive_datetime():
    dt = datetime(2026, 12, 7, 19, 17, 31)
    parsed = parse_share_expiry(dt)
    assert parsed.tzinfo == timezone.utc
    assert parsed.replace(tzinfo=None) == dt


def test_parse_share_expiry_accepts_iso_string():
    parsed = parse_share_expiry("2026-12-07T19:17:31.720787+00:00")
    assert parsed.year == 2026
    assert parsed.tzinfo is not None


def test_parse_share_expiry_accepts_zulu_string():
    parsed = parse_share_expiry("2026-12-07T19:17:31Z")
    assert parsed.tzinfo is not None


def test_generate_share_code_is_short_alnum():
    code = generate_share_code()
    assert len(code) == 6
    assert code.isalnum()


def test_public_share_path():
    assert public_share_path("xgdghK") == "/recipe/xgdghK"
