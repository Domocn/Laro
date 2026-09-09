"""
Calendar busyness for meal-plan difficulty (ICS subscription MVP).

Privacy:
- Fetch ICS over HTTPS server-side; never log VEVENT SUMMARY/DESCRIPTION.
- Returned structures are busy intervals only (start/end), no event titles.
- LLM prompts receive per-day busy/free labels + busy evening hours — never titles.
"""
from __future__ import annotations

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

EVENING_START_HOUR = 16
EVENING_END_HOUR = 21

BUSY_HOURS_MODERATE = 0.5
BUSY_HOURS_BUSY = 2.0

MAX_ICS_BYTES = 2_000_000
ICS_FETCH_TIMEOUT_S = 12.0

_COUNTRY_TZ = {
    "GB": "Europe/London",
    "UK": "Europe/London",
    "IE": "Europe/Dublin",
    "US": "America/New_York",
    "CA": "America/Toronto",
    "AU": "Australia/Sydney",
    "NZ": "Pacific/Auckland",
    "DE": "Europe/Berlin",
    "FR": "Europe/Paris",
    "ES": "Europe/Madrid",
    "IT": "Europe/Rome",
    "NL": "Europe/Amsterdam",
    "PT": "Europe/Lisbon",
    "BR": "America/Sao_Paulo",
    "JP": "Asia/Tokyo",
    "KR": "Asia/Seoul",
    "CN": "Asia/Shanghai",
    "HK": "Asia/Hong_Kong",
    "SG": "Asia/Singapore",
}


@dataclass(frozen=True)
class BusyInterval:
    """Inclusive-start exclusive-end busy window in UTC (aware)."""

    start: datetime
    end: datetime
    all_day: bool = False


def resolve_calendar_timezone(prefs: Optional[dict] = None) -> tzinfo:
    prefs = prefs or {}
    raw = (prefs.get("calendarTimezone") or "").strip()
    if raw:
        try:
            return ZoneInfo(raw)
        except ZoneInfoNotFoundError:
            pass
    country = str(prefs.get("country") or "").strip().upper()
    if country in _COUNTRY_TZ:
        try:
            return ZoneInfo(_COUNTRY_TZ[country])
        except ZoneInfoNotFoundError:
            pass
    return timezone.utc


def normalize_ics_url(raw: Optional[str]) -> Optional[str]:
    text = (raw or "").strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https":
        raise ValueError("Calendar ICS URL must use HTTPS")
    if not parsed.hostname:
        raise ValueError("Calendar ICS URL is missing a host")
    host = parsed.hostname.lower()
    if host in ("localhost", "metadata.google.internal") or host.endswith(".local"):
        raise ValueError("Calendar ICS URL host is not allowed")
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError("Calendar ICS URL must not target private networks")
    except ValueError as e:
        if "private" in str(e).lower() or "not allowed" in str(e).lower():
            raise
        try:
            infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except socket.gaierror as ge:
            raise ValueError(f"Could not resolve calendar host: {host}") from ge
        for info in infos:
            addr = info[4][0]
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                continue
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                raise ValueError("Calendar ICS URL must not target private networks")
    return text


def _unfold_ics(text: str) -> str:
    return re.sub(r"\r?\n[ \t]", "", text)


def _parse_prop_line(line: str) -> Tuple[str, Dict[str, str], str]:
    if ":" not in line:
        return "", {}, ""
    left, value = line.split(":", 1)
    parts = left.split(";")
    name = parts[0].upper()
    params: Dict[str, str] = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v.strip().strip('"')
        else:
            params[p.upper()] = ""
    return name, params, value


def _parse_ics_dt(
    value: str,
    params: Dict[str, str],
    *,
    default_tz: tzinfo,
) -> Tuple[datetime, bool]:
    value = value.strip()
    is_date = params.get("VALUE", "").upper() == "DATE" or (
        len(value) == 8 and value.isdigit()
    )
    tzid = params.get("TZID")

    if is_date:
        d = datetime.strptime(value[:8], "%Y%m%d").date()
        local_midnight = datetime.combine(d, time.min, tzinfo=default_tz)
        return local_midnight.astimezone(timezone.utc), True

    zulu = value.endswith("Z")
    raw = value[:-1] if zulu else value
    if "." in raw:
        raw = raw.split(".", 1)[0]
    if "T" in raw:
        dt = datetime.strptime(raw[:15], "%Y%m%dT%H%M%S")
    else:
        dt = datetime.strptime(raw[:8], "%Y%m%d")

    if zulu:
        return dt.replace(tzinfo=timezone.utc), False
    if tzid:
        try:
            local_tz = ZoneInfo(tzid)
        except ZoneInfoNotFoundError:
            local_tz = default_tz
        return dt.replace(tzinfo=local_tz).astimezone(timezone.utc), False
    return dt.replace(tzinfo=default_tz).astimezone(timezone.utc), False


def parse_ics_busy_intervals(
    ics_text: str,
    *,
    default_tz: Optional[tzinfo] = None,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> List[BusyInterval]:
    if not ics_text or not ics_text.strip():
        return []
    default_tz = default_tz or timezone.utc
    unfolded = _unfold_ics(ics_text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = unfolded.split("\n")

    intervals: List[BusyInterval] = []
    in_event = False
    dtstart: Optional[datetime] = None
    dtend: Optional[datetime] = None
    duration: Optional[timedelta] = None
    start_all_day = False
    end_all_day = False
    transp = "OPAQUE"

    def flush():
        nonlocal dtstart, dtend, duration, start_all_day, end_all_day, transp
        if dtstart is None:
            return
        if (transp or "OPAQUE").upper() == "TRANSPARENT":
            return
        end = dtend
        if end is None and duration is not None:
            end = dtstart + duration
        if end is None:
            if start_all_day:
                end = dtstart + timedelta(days=1)
            else:
                end = dtstart + timedelta(hours=1)
        if end <= dtstart:
            return
        all_day = start_all_day or end_all_day
        if window_start and end <= window_start:
            return
        if window_end and dtstart >= window_end:
            return
        intervals.append(BusyInterval(start=dtstart, end=end, all_day=all_day))

    for line in lines:
        if not line or line.startswith(" "):
            continue
        name, params, value = _parse_prop_line(line)
        if name == "BEGIN" and value.strip().upper() == "VEVENT":
            in_event = True
            dtstart = dtend = None
            duration = None
            start_all_day = end_all_day = False
            transp = "OPAQUE"
            continue
        if name == "END" and value.strip().upper() == "VEVENT":
            if in_event:
                flush()
            in_event = False
            continue
        if not in_event:
            continue
        if name == "DTSTART":
            dtstart, start_all_day = _parse_ics_dt(value, params, default_tz=default_tz)
        elif name == "DTEND":
            dtend, end_all_day = _parse_ics_dt(value, params, default_tz=default_tz)
        elif name == "DURATION":
            duration = _parse_duration(value)
        elif name == "TRANSP":
            transp = value.strip()

    return intervals


def _parse_duration(value: str) -> Optional[timedelta]:
    text = (value or "").strip().upper()
    m = re.fullmatch(
        r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?",
        text,
    )
    if not m:
        return None
    days = int(m.group(1) or 0)
    hours = int(m.group(2) or 0)
    minutes = int(m.group(3) or 0)
    seconds = int(m.group(4) or 0)
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def _overlap_seconds(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> float:
    start = max(a0, b0)
    end = min(a1, b1)
    if end <= start:
        return 0.0
    return (end - start).total_seconds()


def classify_evening_hours(hours: float, *, all_day: bool = False) -> str:
    if all_day:
        return "busy"
    if hours >= BUSY_HOURS_BUSY:
        return "busy"
    if hours >= BUSY_HOURS_MODERATE:
        return "moderate"
    return "free"


def day_busyness_levels(
    intervals: Sequence[BusyInterval],
    *,
    start_date: date,
    days: int,
    local_tz: tzinfo,
    evening_start_hour: int = EVENING_START_HOUR,
    evening_end_hour: int = EVENING_END_HOUR,
) -> List[Dict[str, Any]]:
    plan_days = max(int(days or 0), 0)
    out: List[Dict[str, Any]] = []
    for offset in range(plan_days):
        d = start_date + timedelta(days=offset)
        eve_start_local = datetime.combine(
            d, time(evening_start_hour, 0), tzinfo=local_tz
        )
        eve_end_local = datetime.combine(d, time(evening_end_hour, 0), tzinfo=local_tz)
        eve_start = eve_start_local.astimezone(timezone.utc)
        eve_end = eve_end_local.astimezone(timezone.utc)
        day_start_local = datetime.combine(d, time.min, tzinfo=local_tz)
        day_end_local = datetime.combine(d + timedelta(days=1), time.min, tzinfo=local_tz)
        day_start = day_start_local.astimezone(timezone.utc)
        day_end = day_end_local.astimezone(timezone.utc)

        busy_secs = 0.0
        event_count = 0
        all_day = False
        for iv in intervals:
            if iv.all_day and iv.start < day_end and iv.end > day_start:
                all_day = True
                event_count += 1
                continue
            overlap = _overlap_seconds(iv.start, iv.end, eve_start, eve_end)
            if overlap > 0:
                busy_secs += overlap
                event_count += 1

        hours = round(busy_secs / 3600.0, 2)
        if all_day:
            hours = max(hours, float(evening_end_hour - evening_start_hour))
        level = classify_evening_hours(hours, all_day=all_day)
        out.append(
            {
                "day": offset,
                "date": d.isoformat(),
                "level": level,
                "evening_busy_hours": hours,
                "evening_event_count": event_count,
                "all_day": all_day,
            }
        )
    return out


def format_calendar_busyness_context(
    day_levels: Sequence[Dict[str, Any]],
    *,
    start_date: Optional[date] = None,
) -> str:
    if not day_levels:
        return ""
    lines: List[str] = [
        "Calendar evening busyness (16:00–21:00 local; busy times only — no event titles): "
        "on busy evenings prefer quick dinners, leftovers, or kid-simple meals; "
        "on free evenings normal/complex recipes are OK."
    ]
    start_iso = start_date.isoformat() if start_date else day_levels[0].get("date")
    busy_days = [str(d["day"]) for d in day_levels if d.get("level") == "busy"]
    moderate_days = [str(d["day"]) for d in day_levels if d.get("level") == "moderate"]
    free_days = [str(d["day"]) for d in day_levels if d.get("level") == "free"]
    detail_bits = []
    for d in day_levels:
        if d.get("level") == "free" and not d.get("all_day"):
            continue
        bit = f"day {d['day']}={d['level']}"
        if d.get("all_day"):
            bit += " (all-day)"
        elif d.get("evening_busy_hours"):
            bit += f" (~{d['evening_busy_hours']}h)"
        detail_bits.append(bit)
    lines.append(
        f"For this plan (day 0 = {start_iso}): "
        f"busy evenings: {', '.join(busy_days) if busy_days else 'none'}; "
        f"moderate: {', '.join(moderate_days) if moderate_days else 'none'}; "
        f"free: {', '.join(free_days) if free_days else 'none'}."
    )
    if detail_bits:
        lines.append("Detail: " + "; ".join(detail_bits) + ".")
    return "\n".join(f"- {line}" for line in lines)


async def fetch_ics_text(url: str) -> str:
    import httpx

    safe_url = normalize_ics_url(url)
    assert safe_url is not None
    headers = {
        "User-Agent": "LaroCalendarBusy/1.0",
        "Accept": "text/calendar, text/plain, */*",
    }
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=ICS_FETCH_TIMEOUT_S,
        max_redirects=3,
    ) as client:
        resp = await client.get(safe_url, headers=headers)
        final = str(resp.url)
        normalize_ics_url(final)
        resp.raise_for_status()
        content = resp.content
        if len(content) > MAX_ICS_BYTES:
            raise ValueError("Calendar ICS feed is too large")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text.upper():
        raise ValueError("URL did not return a valid iCalendar feed")
    logger.info(
        "Fetched calendar ICS (%s bytes) from host %s",
        len(content),
        urlparse(final).hostname,
    )
    return text


async def load_busyness_for_prefs(
    prefs: Optional[dict],
    *,
    start_date: Union[date, datetime, str],
    days: int = 7,
) -> Optional[List[Dict[str, Any]]]:
    if not prefs or not prefs.get("useCalendarForMealDifficulty"):
        return None
    url = (prefs.get("calendarIcsUrl") or "").strip()
    if not url:
        return None
    if isinstance(start_date, datetime):
        start = start_date.date()
    elif isinstance(start_date, date):
        start = start_date
    else:
        try:
            start = datetime.strptime(str(start_date).strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    local_tz = resolve_calendar_timezone(prefs)
    window_start = datetime.combine(start, time.min, tzinfo=local_tz).astimezone(
        timezone.utc
    )
    window_end = datetime.combine(
        start + timedelta(days=max(int(days), 1)), time.min, tzinfo=local_tz
    ).astimezone(timezone.utc)

    try:
        ics = await fetch_ics_text(url)
        intervals = parse_ics_busy_intervals(
            ics,
            default_tz=local_tz,
            window_start=window_start - timedelta(days=1),
            window_end=window_end + timedelta(days=1),
        )
        return day_busyness_levels(
            intervals, start_date=start, days=days, local_tz=local_tz
        )
    except Exception as e:
        logger.warning(
            "Calendar busyness unavailable (%s): %s",
            type(e).__name__,
            str(e)[:200],
        )
        return None
