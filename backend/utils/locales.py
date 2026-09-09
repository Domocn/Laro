"""Locale / country catalogues — keep in sync with frontend/src/lib/locales.js."""

LANGUAGES = {
    "en-US": {"name": "English (US)", "flag": "🇺🇸", "voice": "en-US"},
    "en-GB": {"name": "English (UK)", "flag": "🇬🇧", "voice": "en-GB"},
    "es": {"name": "Español", "flag": "🇪🇸", "voice": "es-ES"},
    "fr": {"name": "Français", "flag": "🇫🇷", "voice": "fr-FR"},
    "de": {"name": "Deutsch", "flag": "🇩🇪", "voice": "de-DE"},
    "it": {"name": "Italiano", "flag": "🇮🇹", "voice": "it-IT"},
    "pt-BR": {"name": "Português (Brasil)", "flag": "🇧🇷", "voice": "pt-BR"},
    "pt-PT": {"name": "Português (Portugal)", "flag": "🇵🇹", "voice": "pt-PT"},
    "zh": {"name": "中文（简体）", "flag": "🇨🇳", "voice": "zh-CN"},
    "yue": {"name": "粵語 (Cantonese)", "flag": "🇭🇰", "voice": "zh-HK"},
    "ja": {"name": "日本語", "flag": "🇯🇵", "voice": "ja-JP"},
    "ko": {"name": "한국어", "flag": "🇰🇷", "voice": "ko-KR"},
}

COUNTRIES = {
    "US": {"name": "United States", "flag": "🇺🇸", "language": "en-US", "measurementUnit": "imperial", "currency": "USD"},
    "GB": {"name": "United Kingdom", "flag": "🇬🇧", "language": "en-GB", "measurementUnit": "metric", "currency": "GBP"},
    "IE": {"name": "Ireland", "flag": "🇮🇪", "language": "en-GB", "measurementUnit": "metric", "currency": "EUR"},
    "CA": {"name": "Canada", "flag": "🇨🇦", "language": "en-US", "measurementUnit": "metric", "currency": "CAD"},
    "AU": {"name": "Australia", "flag": "🇦🇺", "language": "en-GB", "measurementUnit": "metric", "currency": "AUD"},
    "NZ": {"name": "New Zealand", "flag": "🇳🇿", "language": "en-GB", "measurementUnit": "metric", "currency": "NZD"},
    "ES": {"name": "Spain", "flag": "🇪🇸", "language": "es", "measurementUnit": "metric", "currency": "EUR"},
    "MX": {"name": "Mexico", "flag": "🇲🇽", "language": "es", "measurementUnit": "metric", "currency": "MXN"},
    "FR": {"name": "France", "flag": "🇫🇷", "language": "fr", "measurementUnit": "metric", "currency": "EUR"},
    "BE": {"name": "Belgium", "flag": "🇧🇪", "language": "fr", "measurementUnit": "metric", "currency": "EUR"},
    "DE": {"name": "Germany", "flag": "🇩🇪", "language": "de", "measurementUnit": "metric", "currency": "EUR"},
    "AT": {"name": "Austria", "flag": "🇦🇹", "language": "de", "measurementUnit": "metric", "currency": "EUR"},
    "CH": {"name": "Switzerland", "flag": "🇨🇭", "language": "de", "measurementUnit": "metric", "currency": "CHF"},
    "IT": {"name": "Italy", "flag": "🇮🇹", "language": "it", "measurementUnit": "metric", "currency": "EUR"},
    "BR": {"name": "Brazil", "flag": "🇧🇷", "language": "pt-BR", "measurementUnit": "metric", "currency": "BRL"},
    "PT": {"name": "Portugal", "flag": "🇵🇹", "language": "pt-PT", "measurementUnit": "metric", "currency": "EUR"},
    "CN": {"name": "China", "flag": "🇨🇳", "language": "zh", "measurementUnit": "metric", "currency": "CNY"},
    "HK": {"name": "Hong Kong", "flag": "🇭🇰", "language": "yue", "measurementUnit": "metric", "currency": "HKD"},
    "MO": {"name": "Macao", "flag": "🇲🇴", "language": "yue", "measurementUnit": "metric", "currency": "MOP"},
    "TW": {"name": "Taiwan", "flag": "🇹🇼", "language": "zh", "measurementUnit": "metric", "currency": "TWD"},
    "JP": {"name": "Japan", "flag": "🇯🇵", "language": "ja", "measurementUnit": "metric", "currency": "JPY"},
    "KR": {"name": "South Korea", "flag": "🇰🇷", "language": "ko", "measurementUnit": "metric", "currency": "KRW"},
}

DEFAULT_LANGUAGE = "en-GB"
DEFAULT_COUNTRY = "GB"


def normalize_language(code: str | None) -> str:
    if not code:
        return DEFAULT_LANGUAGE
    if code == "en":
        return "en-US"
    # Legacy bare Portuguese → Brazil (previous default)
    if code == "pt":
        return "pt-BR"
    lower = str(code).lower().replace("_", "-")
    # Browser / BCP-47 aliases for Cantonese
    if lower in ("zh-hk", "zh-mo", "zh-yue", "yue-hk", "yue-hant") or lower.startswith("yue"):
        return "yue"
    if code in LANGUAGES:
        return code
    by_lower = {k.lower(): k for k in LANGUAGES}
    if lower in by_lower:
        return by_lower[lower]
    parts = str(code).replace("_", "-").split("-")
    base = parts[0].lower()
    if base == "en":
        region = parts[1].upper() if len(parts) > 1 else ""
        if region in ("GB", "UK"):
            return "en-GB"
        return "en-US"
    if base == "pt":
        region = parts[1].upper() if len(parts) > 1 else ""
        if region == "PT":
            return "pt-PT"
        return "pt-BR"
    if base in LANGUAGES:
        return base
    return DEFAULT_LANGUAGE


def normalize_country(code: str | None) -> str:
    if not code:
        return DEFAULT_COUNTRY
    upper = str(code).upper()
    if upper == "UK":
        return "GB"
    return upper if upper in COUNTRIES else DEFAULT_COUNTRY


def defaults_for_country(country_code: str | None) -> dict:
    country = normalize_country(country_code)
    info = COUNTRIES[country]
    return {
        "country": country,
        "language": info["language"],
        "measurementUnit": info["measurementUnit"],
        "currency": info["currency"],
    }
