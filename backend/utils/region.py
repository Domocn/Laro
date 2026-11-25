"""Nutrition style + food-data region, both derived from the user's country.

The user picks a country (ISO 3166-1 alpha-2, stored as ``user_preferences.country``; default
and existing users "GB"). Two things follow from it:

``nutrition_style`` - how nutrition is shown:

* ``uk`` (default: UK, EU and every country not listed below) - carbs exclude fibre, kcal first
  (kJ secondary), metric, degrees C.
* ``au`` (AU, NZ) - as ``uk`` but energy in kJ first (then kcal).
* ``ca`` (CA) - total carbohydrate incl. fibre, "Calories", metric, degrees C.
* ``us`` (US) - total carbs incl. fibre, "Calories", US customary units, degrees F.

``food_region`` - which food data lookups prefer: ``us`` (USDA first) for US and CA, ``uk``
otherwise. Passed to the food layer only when it supports a ``region`` keyword.
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

DEFAULT_COUNTRY = "GB"
DEFAULT_STYLE = "uk"
DEFAULT_REGION = "uk"  # food-data region
STYLES = ("uk", "au", "ca", "us")

_STYLE_BY_COUNTRY = {"US": "us", "CA": "ca", "AU": "au", "NZ": "au"}
_US_DATA_COUNTRIES = frozenset({"US", "CA"})
# Styles whose carbs figure is total carbohydrate incl. fibre (North American labels).
TOTAL_CARB_STYLES = frozenset({"us", "ca"})


def normalize_country_code(value: Any) -> str:
    from utils.locales import normalize_country

    return normalize_country(str(value) if value is not None else None)


def nutrition_style_for_country(country: Any) -> str:
    return _STYLE_BY_COUNTRY.get(normalize_country_code(country), DEFAULT_STYLE)


def food_region_for_country(country: Any) -> str:
    return "us" if normalize_country_code(country) in _US_DATA_COUNTRIES else DEFAULT_REGION


def locale_fields(country: Any) -> Dict[str, str]:
    """Derived, read-only fields returned with the preferences."""
    return {
        "nutritionStyle": nutrition_style_for_country(country),
        "foodRegion": food_region_for_country(country),
    }


def normalize_region(value: Any) -> str:
    """Food-data region "uk" / "us" (unknown -> "uk")."""
    return "us" if str(value or "").strip().lower() in ("us", "usa") else DEFAULT_REGION


async def user_country(user: Optional[Dict[str, Any]]) -> str:
    """The signed-in user's country (GB unless they chose another). Never raises."""
    if not user or not user.get("id"):
        return DEFAULT_COUNTRY
    try:
        from dependencies import user_preferences_repository

        prefs = await user_preferences_repository.find_by_user(user["id"])
    except Exception:
        logger.debug("Could not read country for user %s", user.get("id"), exc_info=True)
        return DEFAULT_COUNTRY
    return normalize_country_code((prefs or {}).get("country"))


async def user_region(user: Optional[Dict[str, Any]]) -> str:
    """Food-data region for the signed-in user: "us" for US / CA, else "uk"."""
    return food_region_for_country(await user_country(user))


def accepts_region(func: Callable[..., Any]) -> bool:
    """True when ``func`` takes a ``region`` keyword (the region-aware food layer). Lets this
    code run whether or not that layer has landed."""
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False
    if "region" in params:
        return params["region"].kind in (
            inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD
        )
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def region_kwargs(func: Callable[..., Any], region: Any) -> Dict[str, str]:
    """``{"region": region}`` when ``func`` supports it, else ``{}``."""
    return {"region": normalize_region(region)} if accepts_region(func) else {}


def food_lookups_region_aware() -> bool:
    """True once ``services.line_macros.estimate_line_macros`` takes ``region``."""
    try:
        from services.line_macros import estimate_line_macros
    except Exception:
        return False
    return accepts_region(estimate_line_macros)


def total_carbs_per_serving(badges: Optional[Iterable[Any]], servings: Any) -> Optional[int]:
    """Per-serving total carbohydrate (incl. fibre) from line badges' ``c_total``.

    None unless every badge with carbs carries ``c_total`` (older rows / AI estimates may not),
    so a partial sum is never shown as a total. Lines with no carbs count as 0."""
    if badges is None:
        return None
    items = list(badges)
    if not items:
        return None
    total = 0.0
    for badge in items:
        if not isinstance(badge, dict):
            return None
        try:
            if badge.get("c_total") is not None:
                total += float(badge["c_total"])
            elif float(badge.get("c") or 0):
                return None  # carbs without a total (older / AI rows): no partial sums
            # else: no carbs on this line, 0 on either basis
        except (TypeError, ValueError):
            return None
    try:
        s = max(1, int(servings or 1))
    except (TypeError, ValueError):
        s = 1
    return int(round(total / s))


def with_total_carbs(nutrition: Optional[Dict[str, Any]], badges: Optional[Iterable[Any]], servings: Any) -> Optional[Dict[str, Any]]:
    """``nutrition`` plus ``carbs_total`` when the badges can give it (copy; input untouched)."""
    if not nutrition:
        return nutrition
    value = total_carbs_per_serving(badges, servings)
    if value is None:
        return nutrition
    return {**nutrition, "carbs_total": value}
