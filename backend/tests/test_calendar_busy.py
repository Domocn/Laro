"""Tests for ICS busy parsing and evening busyness → meal difficulty mapping."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from utils.calendar_busy import (
    classify_evening_hours,
    day_busyness_levels,
    format_calendar_busyness_context,
    normalize_ics_url,
    parse_ics_busy_intervals,
)
from utils.preference_context import format_preference_context


SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:busy-evening@test
DTSTART:20260907T170000Z
DTEND:20260907T190000Z
SUMMARY:Secret Meeting Title Must Not Leak
DESCRIPTION:Do not log this
END:VEVENT
BEGIN:VEVENT
UID:all-day@test
DTSTART;VALUE=DATE:20260908
DTEND;VALUE=DATE:20260909
SUMMARY:All Day Offsite
TRANSP:OPAQUE
END:VEVENT
BEGIN:VEVENT
UID:free-transparent@test
DTSTART:20260909T170000Z
DTEND:20260909T180000Z
SUMMARY:Should Be Ignored
TRANSP:TRANSPARENT
END:VEVENT
BEGIN:VEVENT
UID:morning-only@test
DTSTART:20260910T090000Z
DTEND:20260910T100000Z
SUMMARY:Morning Standup
END:VEVENT
END:VCALENDAR
"""


def test_normalize_ics_url_requires_https():
    with pytest.raises(ValueError, match="HTTPS"):
        normalize_ics_url("http://example.com/cal.ics")
    assert normalize_ics_url("https://calendar.google.com/calendar/ical/x/private/y/basic.ics")


def test_normalize_ics_url_blocks_localhost():
    with pytest.raises(ValueError):
        normalize_ics_url("https://localhost/secret.ics")
    with pytest.raises(ValueError):
        normalize_ics_url("https://127.0.0.1/secret.ics")


def test_parse_ics_strips_titles_and_respects_transp():
    intervals = parse_ics_busy_intervals(SAMPLE_ICS, default_tz=timezone.utc)
    # 3 opaque events (evening, all-day, morning); transparent skipped
    assert len(intervals) == 3
    for iv in intervals:
        assert not hasattr(iv, "summary")
        assert iv.start.tzinfo is not None
        assert iv.end > iv.start
    all_day = [iv for iv in intervals if iv.all_day]
    assert len(all_day) == 1


def test_day_busyness_evening_window_mapping():
    # Plan week starting Mon 2026-09-07 (UTC evenings align with Z times above)
    intervals = parse_ics_busy_intervals(SAMPLE_ICS, default_tz=timezone.utc)
    levels = day_busyness_levels(
        intervals,
        start_date=date(2026, 9, 7),
        days=4,
        local_tz=timezone.utc,
    )
    by_day = {d["day"]: d for d in levels}
    # Day 0: 17:00–19:00 UTC = 2h evening → busy
    assert by_day[0]["level"] == "busy"
    assert by_day[0]["evening_busy_hours"] == 2.0
    # Day 1: all-day → busy
    assert by_day[1]["level"] == "busy"
    assert by_day[1]["all_day"] is True
    # Day 2: transparent evening ignored → free
    assert by_day[2]["level"] == "free"
    # Day 3: morning only → free evening
    assert by_day[3]["level"] == "free"
    assert by_day[3]["evening_busy_hours"] == 0.0


def test_classify_evening_hours_thresholds():
    assert classify_evening_hours(0.0) == "free"
    assert classify_evening_hours(0.4) == "free"
    assert classify_evening_hours(0.5) == "moderate"
    assert classify_evening_hours(1.5) == "moderate"
    assert classify_evening_hours(2.0) == "busy"
    assert classify_evening_hours(0.0, all_day=True) == "busy"


def test_format_calendar_context_has_no_titles():
    levels = [
        {
            "day": 0,
            "date": "2026-09-07",
            "level": "busy",
            "evening_busy_hours": 2.0,
            "evening_event_count": 1,
            "all_day": False,
        },
        {
            "day": 1,
            "date": "2026-09-08",
            "level": "free",
            "evening_busy_hours": 0.0,
            "evening_event_count": 0,
            "all_day": False,
        },
    ]
    text = format_calendar_busyness_context(levels, start_date=date(2026, 9, 7))
    assert "busy" in text.lower()
    assert "Secret" not in text
    assert "Meeting" not in text
    assert "day 0" in text


def test_preference_context_includes_calendar_with_wfh():
    levels = [
        {
            "day": 0,
            "date": "2026-09-07",
            "level": "busy",
            "evening_busy_hours": 3.0,
            "evening_event_count": 2,
            "all_day": False,
        },
        {
            "day": 1,
            "date": "2026-09-08",
            "level": "free",
            "evening_busy_hours": 0.0,
            "evening_event_count": 0,
            "all_day": False,
        },
    ]
    ctx = format_preference_context(
        {
            "worksFromHome": True,
            "wfhDays": ["mon"],
            "useCalendarForMealDifficulty": True,
        },
        start_date=date(2026, 9, 7),
        days=2,
        calendar_busyness=levels,
    )
    assert "WFH" in ctx or "Works from home" in ctx
    assert "Calendar evening busyness" in ctx
    assert "busy" in ctx.lower()
    assert "Secret" not in ctx


def test_folded_ics_line_and_duration():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:dur@test
DTSTART:20260907T180000Z
DURATION:PT90M
SUMMARY:Folded
  Title Continues
END:VEVENT
END:VCALENDAR
"""
    intervals = parse_ics_busy_intervals(ics, default_tz=timezone.utc)
    assert len(intervals) == 1
    assert intervals[0].end - intervals[0].start == __import__("datetime").timedelta(minutes=90)


def test_local_tz_evening_overlap():
    # 18:00–19:00 Europe/London on 2026-09-07 (BST = UTC+1 → 17:00–18:00Z)
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:local@test
DTSTART;TZID=Europe/London:20260907T180000
DTEND;TZID=Europe/London:20260907T190000
SUMMARY:Hidden
END:VEVENT
END:VCALENDAR
"""
    london = ZoneInfo("Europe/London")
    intervals = parse_ics_busy_intervals(ics, default_tz=london)
    levels = day_busyness_levels(
        intervals, start_date=date(2026, 9, 7), days=1, local_tz=london
    )
    assert levels[0]["level"] in ("moderate", "busy")
    assert levels[0]["evening_busy_hours"] == 1.0
