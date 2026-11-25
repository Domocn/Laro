"""Normalize meal-reminder lead time to minutes-before-meal (int)."""
from __future__ import annotations

from typing import Any, Optional

DEFAULT_LEAD_MINUTES = 30
DEFAULT_DINNER_MINUTES = 18 * 60
MIN_LEAD = 5
MAX_LEAD = 180


def coerce_lead_minutes(value: Any, default: Optional[int] = DEFAULT_LEAD_MINUTES) -> Optional[int]:
    """
    Canonical reminder_time is minutes before the meal (web notification_settings).

    Accepts:
      - int / float minutes (15, 30, 60, 120)
      - numeric strings ("30")
      - legacy Android HH:MM dinner clocks, converted to minutes before 18:00
    """
    if value is None or value is False:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        minutes = int(value)
        if MIN_LEAD <= minutes <= MAX_LEAD:
            return minutes
        return default
    text = str(value).strip()
    if not text:
        return default
    if text.isdigit():
        minutes = int(text)
        if MIN_LEAD <= minutes <= MAX_LEAD:
            return minutes
        return default
    if ":" in text:
        try:
            hour_s, minute_s = text.split(":", 1)
            hour = int(hour_s)
            minute = int(minute_s.split(":")[0] if ":" in minute_s else minute_s)
            clock = hour * 60 + minute
            lead = DEFAULT_DINNER_MINUTES - clock
            if MIN_LEAD <= lead <= MAX_LEAD:
                return lead
        except (ValueError, IndexError):
            pass
    return default


def lead_minutes_for_storage(value: Any) -> str:
    """Persist minutes as a decimal string (mobile VARCHAR column)."""
    return str(coerce_lead_minutes(value, DEFAULT_LEAD_MINUTES))
