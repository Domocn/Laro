"""Postgres returns TIMESTAMP columns as datetime; older rows/paths used ISO text."""
from datetime import datetime, timezone
from typing import Optional


def as_utc(value) -> Optional[datetime]:
    """Return an aware UTC datetime from a datetime, ISO string, or None."""
    if value is None or value == "":
        return None
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
