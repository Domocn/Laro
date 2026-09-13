"""
Build short preference snippets for AI recipe / meal-plan prompts.

Used by chat, fridge search (recipe ideas), auto meal plan, and cooking assistant
so dietaryRestrictions, nutrition goals, preferredRecipeSites, lifestyle (kids/WFH),
calendar evening busyness (busy times only), and the curated food DB actually affect
suggestions.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable, List, Optional, Sequence, Union
from urllib.parse import urlparse

# Canonical weekday codes (Mon-first). Python date.weekday() uses the same order.
WEEKDAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_ALIASES = {
    "mon": "mon",
    "monday": "mon",
    "0": "mon",
    "tue": "tue",
    "tues": "tue",
    "tuesday": "tue",
    "1": "tue",
    "wed": "wed",
    "weds": "wed",
    "wednesday": "wed",
    "2": "wed",
    "thu": "thu",
    "thur": "thu",
    "thurs": "thu",
    "thursday": "thu",
    "3": "thu",
    "fri": "fri",
    "friday": "fri",
    "4": "fri",
    "sat": "sat",
    "saturday": "sat",
    "5": "sat",
    "sun": "sun",
    "sunday": "sun",
    "6": "sun",
    "7": "sun",  # some UIs use 1–7 with Sunday=7
}


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return []


def normalize_recipe_site(raw: str) -> Optional[str]:
    """
    Normalize a user-entered site to a bare hostname (no scheme/path).

    Accepts "bbcgoodfood.com", "https://www.nytimes.com/section/food", etc.
    """
    text = (raw or "").strip().lower()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    try:
        host = urlparse(text).hostname or ""
    except Exception:
        return None
    host = host.strip().lower()
    if host.startswith("www."):
        host = host[4:]
    # Reject empty / nonsense
    if not host or "." not in host or " " in host:
        return None
    return host


def normalize_preferred_recipe_sites(sites: Iterable[Any], *, max_sites: int = 12) -> List[str]:
    seen = set()
    out: List[str] = []
    for raw in sites or []:
        host = normalize_recipe_site(str(raw) if raw is not None else "")
        if not host or host in seen:
            continue
        seen.add(host)
        out.append(host)
        if len(out) >= max_sites:
            break
    return out


def normalize_wfh_days(raw: Any) -> List[str]:
    """
    Normalize WFH weekdays to canonical mon–sun codes (stable order, deduped).

    Accepts names ("Monday", "mon"), ints (0–6 Mon-first), or strings of those.
    """
    if raw is None:
        return []
    items: List[Any]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        # JSON array string or comma-separated
        if text.startswith("["):
            try:
                import json

                parsed = json.loads(text)
                items = list(parsed) if isinstance(parsed, (list, tuple)) else [text]
            except Exception:
                items = [p.strip() for p in text.strip("[]").split(",")]
        else:
            items = [p.strip() for p in text.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        items = list(raw)
    else:
        items = [raw]

    seen = set()
    out: List[str] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            key = str(item)
        else:
            key = str(item).strip().lower()
        code = WEEKDAY_ALIASES.get(key)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    # Stable calendar order
    return [d for d in WEEKDAY_CODES if d in seen]


def wants_family_one_meal(prefs: Optional[dict]) -> bool:
    """
    One shared dish for the whole household (kid-suitable base + adult upgrades).

    Defaults True when hasChildren; explicit False turns it off.
    """
    if not prefs:
        return False
    explicit = prefs.get("familyOneMeal")
    if explicit is True:
        return True
    if explicit is False:
        return False
    return bool(prefs.get("hasChildren"))


def wants_kid_friendly(prefs: Optional[dict]) -> bool:
    if not prefs:
        return False
    # Family one-meal mode always needs a kid-suitable shared base
    if wants_family_one_meal(prefs):
        return True
    explicit = prefs.get("kidFriendlyMeals")
    if explicit is True:
        return True
    if explicit is False:
        return False
    return bool(prefs.get("hasChildren"))


def adult_veto_ingredients(prefs: Optional[dict]) -> List[str]:
    """Personal dislikes (preference) — always applied to meal ideas / plans."""
    if not prefs:
        return []
    return _as_str_list(prefs.get("dislikedIngredients"))


def kid_veto_ingredients(prefs: Optional[dict]) -> List[str]:
    """Kid veto list — only when kid-friendly / family meals are active."""
    if not prefs or not wants_kid_friendly(prefs):
        return []
    return _as_str_list(prefs.get("kidVetoIngredients"))


def format_veto_exclusion_lines(prefs: Optional[dict]) -> List[str]:
    """
    Hard-exclusion lines for AI prompts.

    Adult veto = personal preference (not allergens/safety).
    Kid veto = only when kid-friendly / family meals apply.
    """
    if not prefs:
        return []
    lines: List[str] = []
    adult = adult_veto_ingredients(prefs)
    if adult:
        lines.append(
            "HARD EXCLUSION — Adult veto list (personal preference, NOT allergens): "
            "NEVER include these ingredients in any meal, recipe idea, garnish, sauce, "
            f"side, or hidden component: {', '.join(adult)}. "
            "Choose alternatives; do not soft-suggest or optionally include them."
        )
    kid = kid_veto_ingredients(prefs)
    if kid:
        family_note = (
            " In FAMILY ONE-MEAL mode every slot is a family meal — never include these."
            if wants_family_one_meal(prefs)
            else " Adults-only meals may ignore this list."
        )
        lines.append(
            "HARD EXCLUSION — Kid veto list (kid-friendly / family meal slots only): "
            "NEVER include these ingredients when planning kid-friendly or family meals: "
            f"{', '.join(kid)}."
            f"{family_note}"
        )
    return lines


def _parse_start_date(start: Union[date, datetime, str, None]) -> Optional[date]:
    if start is None:
        return None
    if isinstance(start, datetime):
        return start.date()
    if isinstance(start, date):
        return start
    text = str(start).strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def wfh_day_indices_for_plan(
    prefs: Optional[dict],
    *,
    start_date: Union[date, datetime, str, None],
    days: int = 7,
) -> List[int]:
    """
    Map WFH weekdays onto 0-based plan day indices relative to start_date.

    Day 0 = start_date (first day of the generated meal plan), regardless of
    weekStartsOn. Only applies when worksFromHome is true and wfhDays is set.
    """
    if not prefs or not prefs.get("worksFromHome"):
        return []
    wfh = normalize_wfh_days(prefs.get("wfhDays") or [])
    if not wfh:
        return []
    start = _parse_start_date(start_date)
    if start is None:
        return []
    plan_days = max(int(days or 0), 0)
    wfh_set = set(wfh)
    indices: List[int] = []
    for offset in range(plan_days):
        d = start + timedelta(days=offset)
        code = WEEKDAY_CODES[d.weekday()]
        if code in wfh_set:
            indices.append(offset)
    return indices


def format_lifestyle_context(
    prefs: Optional[dict],
    *,
    start_date: Union[date, datetime, str, None] = None,
    days: Optional[int] = None,
    calendar_busyness: Optional[Sequence[dict]] = None,
) -> str:
    """
    Kid-friendly + WFH lunch pacing + optional calendar evening busyness.
    When start_date/days are provided, include day-index mapping for the plan.
    calendar_busyness is precomputed busy/free levels (no event titles).
    """
    if not prefs:
        return ""

    lines: List[str] = []

    if wants_family_one_meal(prefs):
        lines.append(
            "FAMILY ONE-MEAL MODE: Cook ONE shared dish for the whole household "
            "(kids and adults together) — not separate kids/adults menus. "
            "Prefer mild, recognizable, not heavily spiced recipes that scale to "
            "family portions. Honour kid veto and adult veto lists on every meal. "
            "For dinners (and shared lunches), include a short adult_boost tip "
            "(e.g. extra chili, cheese, protein side, or spice at the table) so "
            "adults can upgrade their plate without changing the base dish. "
            "When generating new recipes, tag them family-friendly."
        )
    elif wants_kid_friendly(prefs):
        lines.append(
            "Kid-friendly meals: prefer simpler recipes, milder flavours, and "
            "family-portion-friendly dishes (easy to share / scale for children)."
        )
    elif prefs.get("hasChildren") is False:
        # Explicit no-kids — no line needed
        pass

    if prefs.get("worksFromHome"):
        wfh = normalize_wfh_days(prefs.get("wfhDays") or [])
        if wfh:
            pretty = ", ".join(d.capitalize() for d in wfh)
            lines.append(
                f"Works from home on: {pretty}. On those days, lunches may be warmer "
                "or take longer to cook; on other days prefer quicker packable lunches "
                "or leftovers-friendly meals."
            )
            if start_date is not None and days is not None:
                indices = wfh_day_indices_for_plan(prefs, start_date=start_date, days=days)
                if indices:
                    non_wfh = [i for i in range(int(days)) if i not in set(indices)]
                    start_iso = _parse_start_date(start_date)
                    lines.append(
                        f"For this plan (day 0 = {start_iso}), "
                        f"WFH lunch days (0-based): {', '.join(map(str, indices))}"
                        + (
                            f"; non-WFH lunch days: {', '.join(map(str, non_wfh))}"
                            if non_wfh
                            else ""
                        )
                        + "."
                    )
                else:
                    lines.append(
                        "No WFH days fall in this plan window — treat lunches as "
                        "quick/packable or leftovers-friendly."
                    )
        else:
            lines.append(
                "Works from home (days not specified): when at home, lunches may be "
                "warmer/longer-cook; when out, prefer quick packable or leftovers-friendly lunches."
            )

    if prefs.get("hasGymRoutine"):
        gym = normalize_wfh_days(prefs.get("gymDays") or [])
        if gym:
            pretty = ", ".join(d.capitalize() for d in gym)
            lines.append(
                f"Gym / activity days: {pretty}. On those evenings, prefer higher-protein "
                "dinners (lean meat, fish, eggs, dairy, legumes) to support recovery."
            )
            if start_date is not None and days is not None:
                # Reuse WFH index mapper with gymDays shaped as wfhDays
                gym_prefs = {
                    "worksFromHome": True,
                    "wfhDays": gym,
                }
                indices = wfh_day_indices_for_plan(
                    gym_prefs, start_date=start_date, days=days
                )
                if indices:
                    start_iso = _parse_start_date(start_date)
                    lines.append(
                        f"For this plan (day 0 = {start_iso}), "
                        f"higher-protein dinner days (0-based): {', '.join(map(str, indices))}."
                    )
        else:
            lines.append(
                "Gym / activity routine (days not specified): when training, prefer "
                "higher-protein dinners."
            )

    if prefs.get("dinnerHeadcount") is not None:
        try:
            hc = int(prefs.get("dinnerHeadcount"))
            if 1 <= hc <= 20:
                lines.append(
                    f"Usual dinner headcount: {hc} people — scale portions accordingly."
                )
        except (TypeError, ValueError):
            pass

    if calendar_busyness:
        from utils.calendar_busy import format_calendar_busyness_context

        cal_block = format_calendar_busyness_context(
            calendar_busyness,
            start_date=_parse_start_date(start_date),
        )
        if cal_block:
            lines.extend(
                line[2:] if line.startswith("- ") else line
                for line in cal_block.splitlines()
            )

    if not lines:
        return ""
    return "\n".join(f"- {line}" for line in lines)


def format_preference_context(
    prefs: Optional[dict],
    *,
    include_sites: bool = True,
    include_allergens: bool = True,
    include_dislikes: bool = True,
    include_cuisines: bool = True,
    include_nutrition_goals: bool = True,
    include_lifestyle: bool = True,
    start_date: Union[date, datetime, str, None] = None,
    days: Optional[int] = None,
    calendar_busyness: Optional[Sequence[dict]] = None,
) -> str:
    """
    Return a multi-line block suitable for appending to an AI system/user prompt.
    Empty string when nothing useful is set.
    """
    if not prefs:
        return ""

    lines: List[str] = []

    dietary = _as_str_list(prefs.get("dietaryRestrictions") or prefs.get("dietary"))
    if dietary:
        # Emphasize high-protein when selected (goal diet, not an exclusion)
        labels = []
        for d in dietary:
            if d.lower().replace("_", "-") in ("high-protein", "high protein"):
                labels.append("high-protein (prioritise protein-forward meals)")
            else:
                labels.append(d)
        lines.append(f"Dietary preferences: {', '.join(labels)}")

    if include_nutrition_goals:
        from utils.food_db import resolve_nutrition_goals

        goals = resolve_nutrition_goals(prefs)
        if goals.get("daily_protein_g") is not None or goals.get("daily_calories") is not None:
            goal_bits = []
            if goals.get("daily_protein_g") is not None:
                goal_bits.append(f"~{goals['daily_protein_g']}g protein/day")
            if goals.get("daily_calories") is not None:
                goal_bits.append(f"~{goals['daily_calories']} kcal/day")
            if goals.get("protein_per_meal_g") is not None:
                goal_bits.append(f"~{goals['protein_per_meal_g']}g protein/meal")
            # Optional carb/fat targets when user set them explicitly
            raw_carb = prefs.get("dailyCarbTarget")
            raw_fat = prefs.get("dailyFatTarget")
            try:
                if raw_carb is not None and float(raw_carb) > 0:
                    goal_bits.append(f"~{int(float(raw_carb))}g carbs/day")
            except (TypeError, ValueError):
                pass
            try:
                if raw_fat is not None and float(raw_fat) > 0:
                    goal_bits.append(f"~{int(float(raw_fat))}g fat/day")
            except (TypeError, ValueError):
                pass
            lines.append(f"Nutrition goals: {', '.join(goal_bits)}")

    if include_allergens:
        allergens = _as_str_list(prefs.get("allergens"))
        if allergens:
            lines.append(
                "Allergens (safety — never include; distinct from preference vetoes): "
                f"{', '.join(allergens)}"
            )

    if include_dislikes:
        lines.extend(format_veto_exclusion_lines(prefs))

    if include_cuisines:
        cuisines = _as_str_list(prefs.get("favoriteCuisines"))
        if cuisines:
            lines.append(f"Favorite cuisines: {', '.join(cuisines)}")

    if include_sites:
        sites = normalize_preferred_recipe_sites(
            prefs.get("preferredRecipeSites") or []
        )
        if sites:
            lines.append(
                "Preferred recipe websites (bias ideas toward these styles/sources when suggesting "
                f"new recipes; do not invent paywalled full text): {', '.join(sites)}"
            )

    lifestyle = ""
    if include_lifestyle:
        lifestyle = format_lifestyle_context(
            prefs,
            start_date=start_date,
            days=days,
            calendar_busyness=calendar_busyness,
        )

    if not lines and not lifestyle:
        return ""

    block = "User cooking preferences:\n" + "\n".join(f"- {line}" for line in lines)
    if lifestyle:
        if lines:
            block = block + "\n" + lifestyle
        else:
            block = "User cooking preferences:\n" + lifestyle
    return block


def merge_preferences_into_free_text(
    free_text: Optional[str],
    prefs: Optional[dict],
    *,
    start_date: Union[date, datetime, str, None] = None,
    days: Optional[int] = None,
    calendar_busyness: Optional[Sequence[dict]] = None,
) -> str:
    """
    Combine a one-off free-text preference (e.g. meal-plan dialog) with saved prefs.
    """
    parts: List[str] = []
    text = (free_text or "").strip()
    if text:
        parts.append(text)

    ctx = format_preference_context(
        prefs,
        start_date=start_date,
        days=days,
        calendar_busyness=calendar_busyness,
    )
    if ctx:
        parts.append(ctx)

    return "\n".join(parts) if parts else "balanced variety"


async def load_user_preference_context(user_id: str, **kwargs) -> str:
    """Load prefs from DB and format for prompts."""
    from dependencies import user_preferences_repository

    prefs = await user_preferences_repository.find_by_user(user_id)
    return format_preference_context(prefs, **kwargs)


async def load_user_prefs_and_food_context(
    user_id: str,
    *,
    pantry_items: Optional[Sequence[str]] = None,
    query: Optional[str] = None,
    include_food_db: bool = True,
    **pref_kwargs,
) -> str:
    """
    Preference snippet plus curated food-DB building blocks for recipe ideas.
    """
    from dependencies import user_preferences_repository
    from utils.food_db import build_ai_food_context

    prefs = await user_preferences_repository.find_by_user(user_id)
    parts: List[str] = []
    pref_ctx = format_preference_context(prefs, **pref_kwargs)
    if pref_ctx:
        parts.append(pref_ctx)
    if include_food_db:
        food_ctx = build_ai_food_context(
            prefs,
            pantry_items=pantry_items,
            query=query,
            seed=f"{user_id}:{query or ''}",
        )
        if food_ctx:
            parts.append(food_ctx)
    return "\n\n".join(parts)
