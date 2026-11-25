"""pantry.expiry_date is a DATE column: plain 'YYYY-MM-DD' from date pickers must be converted
to a date before insert (asyncpg raised 'str' object has no attribute 'toordinal' -> 500)."""
import os, sys
from datetime import date, datetime

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routers.pantry import _expiry_to_date  # noqa: E402


def test_plain_date_string_becomes_date():
    assert _expiry_to_date("2026-10-21") == date(2026, 10, 21)


def test_iso_datetime_string_and_objects():
    assert _expiry_to_date("2026-10-21T09:30:00Z") == date(2026, 10, 21)
    assert _expiry_to_date(datetime(2026, 10, 21, 9, 30)) == date(2026, 10, 21)
    assert _expiry_to_date(date(2026, 10, 21)) == date(2026, 10, 21)


def test_empty_is_none_and_garbage_is_400():
    assert _expiry_to_date(None) is None and _expiry_to_date("") is None
    with pytest.raises(HTTPException) as e:
        _expiry_to_date("next tuesday")
    assert e.value.status_code == 400
