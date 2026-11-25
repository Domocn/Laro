"""
Link tracking - where visitors and new sign-ups come from.

Stores no personal data: just a source label (instagram, whatsapp, code:CIRCLEUP, google, ...),
an optional campaign, the landing page, the referring site's host and a device type.
"""
import re
from datetime import datetime, timezone
from typing import Optional

_SOURCE_RE = re.compile(r"[^a-z0-9:._#-]+")

# In-app browsers announce themselves in the user agent
_UA_SOURCES = [
    ("instagram", "instagram"),
    ("fban", "facebook"),
    ("fbav", "facebook"),
    ("fb_iab", "facebook"),
    ("musical_ly", "tiktok"),
    ("bytedancewebview", "tiktok"),
    ("snapchat", "snapchat"),
    ("linkedinapp", "linkedin"),
    ("twitter", "x"),
    ("pinterest", "pinterest"),
    ("whatsapp", "whatsapp"),
    ("gsa/", "google-app"),
]


_BOT_RE = re.compile(
    r"bot\b|bot/|crawler|spider|slurp|googleother|google-inspectiontool|lighthouse|headless"
    r"|facebookexternalhit|bingpreview|embedly|preview",
    re.I,
)


def is_bot(user_agent: str) -> bool:
    """Search crawlers and link-preview fetchers: not people, so not visits or user-facing bugs."""
    return bool(_BOT_RE.search(user_agent or ""))


_SOURCE_ALIASES = {"ig": "instagram", "fb": "facebook", "wa": "whatsapp", "tt": "tiktok"}


def clean_source(value: Optional[str], limit: int = 100) -> Optional[str]:
    """Lower-case, safe characters only. Promo/friend codes keep their case after 'code:'."""
    if not value:
        return None
    value = str(value).strip()[:limit]
    if value.lower().startswith("code:"):
        code = re.sub(r"[^A-Za-z0-9#_-]+", "", value[5:])
        return f"code:{code.upper()}" if code else None
    value = _SOURCE_RE.sub("-", value.lower()).strip("-")
    return _SOURCE_ALIASES.get(value, value) or None


def source_from_user_agent(user_agent: str) -> Optional[str]:
    ua = (user_agent or "").lower()
    for needle, source in _UA_SOURCES:
        if needle in ua:
            return source
    return None


def device_from_user_agent(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "iphone" in ua or "ipad" in ua:
        return "iphone"
    if "android" in ua:
        return "android"
    if "okhttp" in ua:
        return "android-app"
    return "desktop"


def signup_source_for(client_source: Optional[str], user_agent: str) -> Optional[str]:
    """Source saved on the new user: what the web app remembered, else the app/browser itself."""
    source = clean_source(client_source)
    if source:
        return source
    if "okhttp" in (user_agent or "").lower():
        return "android-app"
    return source_from_user_agent(user_agent)


async def record_visit(conn, *, source: str, campaign: Optional[str], landing: Optional[str],
                       referrer_host: Optional[str], user_agent: str) -> None:
    await conn.execute(
        """INSERT INTO link_visits (created_at, source, campaign, landing, referrer_host, device)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        datetime.now(timezone.utc).replace(tzinfo=None),
        source,
        clean_source(campaign),
        (landing or "")[:200] or None,
        (referrer_host or "").lower()[:200] or None,
        device_from_user_agent(user_agent),
    )


async def link_report(conn, since: datetime) -> dict:
    """Visits and sign-ups per source since a date, biggest first."""
    visits = await conn.fetch(
        """SELECT source, count(*) AS visits,
                  count(*) FILTER (WHERE device = 'iphone') AS iphone,
                  count(*) FILTER (WHERE device = 'android') AS android,
                  count(*) FILTER (WHERE device = 'desktop') AS desktop,
                  max(created_at) AS last_visit
           FROM link_visits WHERE created_at >= $1
           GROUP BY source ORDER BY visits DESC LIMIT 100""",
        since,
    )
    signups = await conn.fetch(
        """SELECT COALESCE(signup_source,
                           CASE WHEN signup_promo_code IS NOT NULL THEN 'code:' || signup_promo_code END,
                           'unknown') AS source,
                  count(*) AS signups
           FROM users WHERE created_at >= $1
           GROUP BY 1 ORDER BY signups DESC LIMIT 100""",
        since,
    )
    campaigns = await conn.fetch(
        """SELECT source, campaign, count(*) AS visits FROM link_visits
           WHERE created_at >= $1 AND campaign IS NOT NULL
           GROUP BY source, campaign ORDER BY visits DESC LIMIT 50""",
        since,
    )
    referrers = await conn.fetch(
        """SELECT referrer_host, count(*) AS visits FROM link_visits
           WHERE created_at >= $1 AND referrer_host IS NOT NULL
           GROUP BY referrer_host ORDER BY visits DESC LIMIT 30""",
        since,
    )

    by_source: dict = {}
    for r in visits:
        by_source[r["source"]] = {
            "source": r["source"], "visits": r["visits"], "signups": 0,
            "iphone": r["iphone"], "android": r["android"], "desktop": r["desktop"],
            "last_visit": r["last_visit"].isoformat() + "Z" if r["last_visit"] else None,
        }
    for r in signups:
        row = by_source.setdefault(r["source"], {
            "source": r["source"], "visits": 0, "signups": 0,
            "iphone": 0, "android": 0, "desktop": 0, "last_visit": None,
        })
        row["signups"] = r["signups"]
    sources = sorted(by_source.values(), key=lambda s: (s["signups"], s["visits"]), reverse=True)
    return {
        "sources": sources,
        "total_visits": sum(s["visits"] for s in sources),
        "total_signups": sum(s["signups"] for s in sources),
        "campaigns": [dict(r) for r in campaigns],
        "referrers": [dict(r) for r in referrers],
    }
