"""
Recipe macros from one source of truth: the per-ingredient-line estimates.

Every list a recipe page can show gets per-serving totals = sum(line macros) / servings, so the
totals card always equals what the per-ingredient badges add up to:

  Original                ``ingredient_macros`` [{p, c, f, cal}] + ``nutrition_*`` columns
  Original + Low FODMAP   ``adaptations.low_fodmap_macros``          {nutrition, ingredient_macros}
  a named version         ``adaptations.versions[i].nutrition`` / ``.ingredient_macros``
  version + Low FODMAP    ``adaptations.versions[i].low_fodmap_macros``

Line macros come from ``services.line_macros`` (AI, cached per normalised line so identical lines
never cost a second call). A Low FODMAP swap replaces the ingredient's name and keeps its amount
("2 cloves garlic" -> "2 cloves garlic-infused oil"), exactly as the page shows it.

``macros_sig`` records a list's inputs (lines, servings, swaps): a save keeps stored macros whose
inputs did not change, and drops (pending) those whose inputs changed but could not be estimated
yet; the background job / next request fills them.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from services import confirmed_lines as _confirmed
from utils.ingredient_groups import legacy_name
from utils.recipe_fields import (
    CORE_NUTRITION_KEYS,
    columns_to_nutrition,
    ensure_list_field,
    normalize_adaptations,
    normalize_ingredient,
)

logger = logging.getLogger(__name__)

Badge = Dict[str, int]
Lookup = Callable[[Any], Optional[Badge]]

_SIG_VERSION = "lines-v3"  # bump to invalidate every stored version macro (v2: food database first; v3: UK-first foods + c_total)
_BADGE_TO_NUTRITION = {"cal": "calories", "p": "protein", "c": "carbs", "f": "fat"}
_VERSION_MACRO_FIELDS = ("nutrition", "ingredient_macros", "low_fodmap_macros", "macros_sig", "ingredients_sig")
TOTALS_TOLERANCE = 0.05


def _ing(item: Any) -> Dict[str, str]:
    return normalize_ingredient(item)


def line_key(item: Any) -> str:
    d = _ing(item)
    return "|".join(" ".join(str(d[k]).lower().split()) for k in ("amount", "unit", "name"))


def _sig(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _ingredients(value: Any) -> List[Dict[str, str]]:
    """All lines, index-aligned with what the page shows (badges are per displayed line)."""
    return [_ing(i) for i in ensure_list_field(value)]


def recipe_servings(recipe: Dict[str, Any]) -> int:
    try:
        return max(1, int(recipe.get("servings") or 1))
    except (TypeError, ValueError):
        return 1


def _swaps(adaptations: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    return ((adaptations or {}).get("low_fodmap") or {}).get("swaps") or []


def swapped_list(ings: Sequence[Dict[str, str]], swaps: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, str]], bool]:
    """The list with Low FODMAP swaps applied (name replaced, amount kept) + whether any applied."""
    from services.recipe_variants import find_swap

    out, hit = [], False
    for ing in ings:
        swap = find_swap(ing["name"], list(swaps)) if swaps else None
        if swap:
            out.append({**ing, "name": swap["to"]})
            hit = True
        else:
            out.append(ing)
    return out, hit


def sum_badges(badges: Sequence[Badge]) -> Dict[str, int]:
    return {name: sum(int(b.get(short) or 0) for b in badges) for short, name in _BADGE_TO_NUTRITION.items()}


def per_serving(badges: Sequence[Badge], servings: int) -> Dict[str, int]:
    """Per-serving {calories, protein, carbs, fat} = sum of the lines / servings."""
    total = sum_badges(badges)
    s = max(1, int(servings or 1))
    return {k: int(round(total[k] / s)) for k in CORE_NUTRITION_KEYS}


def _confirmed_for(recipe_or_adaptations: Any, version: str = "", low_fodmap: bool = False) -> Dict[str, Badge]:
    """{normalised line: badge} the user confirmed for one list (services/confirmed_lines.py)."""
    value = recipe_or_adaptations
    if isinstance(value, dict) and ("adaptations" in value or "ingredients" in value):
        value = value.get("adaptations")  # a recipe, not its adaptations
    return _confirmed.for_list(value, version, low_fodmap)


def _sig_part(part: Any) -> Any:
    """Ingredient lines hash in their pre-sections form ("Group: name", no ``group`` key), so
    recipes whose legacy name prefixes became sections keep their stored signatures."""
    if isinstance(part, list) and part and all(isinstance(i, dict) and "name" in i for i in part):
        return [{**{k: v for k, v in i.items() if k != "group"}, "name": legacy_name(i)} for i in part]
    return part


def _list_sig(parts: List[Any], *confirmed: Dict[str, Badge]) -> str:
    """A list's inputs; confirmations count only when present (no churn for older recipes)."""
    parts = [_sig_part(p) for p in parts]
    if any(confirmed):
        parts = parts + [[sorted((k, stored_badge(v)["cal"], stored_badge(v)["p"], stored_badge(v)["c"],
                                  stored_badge(v)["f"]) for k, v in c.items()) for c in confirmed]]
    return _sig(parts)


def _badges(
    ings: Sequence[Dict[str, str]], lookup: Lookup, confirmed: Optional[Dict[str, Badge]] = None
) -> Optional[List[Badge]]:
    """Line macros for every line, or None when any line has no estimate yet. A line the user
    confirmed uses their figures (never the database / AI)."""
    out = []
    for ing in ings:
        if not ing["name"].strip():  # blank / heading-only line contributes nothing
            out.append({"p": 0, "c": 0, "f": 0, "cal": 0})
            continue
        if confirmed:
            hit = _confirmed.confirmed_for_line(confirmed, ing)
            if hit is not None:
                out.append(stored_badge(hit))
                continue
        badge = lookup(ing)
        if badge is None:
            return None
        out.append(stored_badge(badge))
    return out


_PROVENANCE_OUT = ("src", "food", "g", "g_src", "source")  # what a stored badge keeps (the UI shows it)


def stored_badge(badge: Dict[str, Any]) -> Badge:
    """``{p, c, f, cal}`` ints (+ ``c_total``, US-basis carbs incl. fibre, when known) plus
    provenance (``src`` "db"/"ai"; for "db": ``food``, ``g``, ``source``; grams ``g`` + ``g_src``
    for both) - the shape saved in ``ingredient_macros`` lists."""
    out: Dict[str, Any] = {k: int(badge.get(k) or 0) for k in ("p", "c", "f", "cal")}
    try:
        if badge.get("c_total") is not None and float(badge["c_total"]) >= 0:
            out["c_total"] = int(round(float(badge["c_total"])))
    except (TypeError, ValueError):
        pass  # junk US-basis carbs: drop them, keep the badge
    for key in _PROVENANCE_OUT:
        if badge.get(key) not in (None, ""):
            out[key] = badge[key]
    return out


def _db_answer(item: Any) -> Optional[Badge]:
    from services import line_macros

    if not line_macros.DB_FIRST:
        return None
    return line_macros.resolve_line_from_db(line_macros.ingredient_line(item))


def badges_current(
    ings: Sequence[Dict[str, str]], badges: Optional[Sequence[Any]], confirmed: Optional[Dict[str, Badge]] = None
) -> bool:
    """Stored badges still match the food-database-first rule: every line carries provenance,
    no AI badge sits on a line the database now answers, and database badges equal what the
    database says today. A user-confirmed line must carry exactly its confirmed figures."""
    if badges is None:
        return False
    for ing, badge in zip(ings, badges):
        if not ing["name"].strip():
            continue
        want = _confirmed.confirmed_for_line(confirmed or {}, ing)
        if want is not None or _confirmed.is_confirmed_badge(badge):
            if want is None or not isinstance(badge, dict) or stored_badge(want) != stored_badge(badge):
                return False
            continue
        if not isinstance(badge, dict) or badge.get("src") not in ("db", "ai"):
            return False
        hit = _db_answer(ing)
        if hit is None:
            if badge["src"] == "db":
                return False
            if badge.get("g") is None:
                return False  # AI line saved before grams were estimated (per-100 g needs them)
        elif _comparable(hit) != _comparable(badge):
            return False
    return True


def _comparable(badge: Dict[str, Any]) -> Dict[str, Any]:
    out = stored_badge(badge)
    out.pop("g_src", None)  # implied by src for database lines (older badges lack it)
    return out


def _variant(
    ings: Sequence[Dict[str, str]], servings: int, lookup: Lookup, confirmed: Optional[Dict[str, Badge]] = None
) -> Optional[Dict[str, Any]]:
    badges = _badges(ings, lookup, confirmed)
    if badges is None:
        return None
    return {"nutrition": per_serving(badges, servings), "ingredient_macros": badges}


def all_lines(recipe: Dict[str, Any]) -> List[Dict[str, str]]:
    """Every ingredient line any view of this recipe shows (Original, versions, Low FODMAP)."""
    adaptations = normalize_adaptations(recipe.get("adaptations")) or {}
    swaps = _swaps(adaptations)
    lists = [_ingredients(recipe.get("ingredients"))]
    lists += [_ingredients(v.get("ingredients")) for v in adaptations.get("versions") or []]
    out: List[Dict[str, str]] = []
    for ings in lists:
        out.extend(ings)
        if swaps:
            out.extend(swapped_list(ings, swaps)[0])
    return [i for i in out if i["name"].strip()]


def version_needs_macros(version: Dict[str, Any]) -> bool:
    return not (isinstance(version.get("nutrition"), dict) and version.get("macros_sig"))


def refresh_adaptation_macros(
    recipe: Dict[str, Any],
    previous: Any = None,
    *,
    force: bool = False,
    lookup: Optional[Lookup] = None,
) -> Optional[Dict[str, Any]]:
    """Return ``recipe['adaptations']`` with version / Low FODMAP macros from the line macros.

    ``lookup(ingredient) -> {p,c,f,cal} | None``. A list whose lines are not all known keeps
    its stored macros when its inputs are unchanged (same ``macros_sig``, here or in
    ``previous``), otherwise its macros are dropped (shown as pending).
    """
    lookup = lookup or (lambda _ing: None)
    adaptations = normalize_adaptations(recipe.get("adaptations"))
    if not adaptations:
        return adaptations
    versions = adaptations.get("versions") or []
    swaps = _swaps(adaptations)
    servings = recipe_servings(recipe)
    prev = normalize_adaptations(previous) or {}
    prev_versions = {v["name"].lower(): v for v in prev.get("versions") or []}

    out_versions = []
    for version in versions:
        v = dict(version)
        ings = _ingredients(v.get("ingredients"))
        lf_ings, lf_hit = swapped_list(ings, swaps)
        conf = _confirmed_for(adaptations, v["name"], False)
        conf_lf = _confirmed_for(adaptations, v["name"], True) if lf_hit else {}
        sig = _list_sig([_SIG_VERSION, ings, servings, swaps if lf_hit else []], conf, conf_lf)
        computed = _variant(ings, servings, lookup, conf)
        lf = _variant(lf_ings, servings, lookup, conf_lf) if lf_hit else None
        if computed is not None and (lf is not None or not lf_hit):
            for field in _VERSION_MACRO_FIELDS:
                v.pop(field, None)
            v.update(computed)
            if lf is not None:
                v["low_fodmap_macros"] = lf
            v["ingredients_sig"] = _sig(v.get("ingredients") or [])
            v["macros_sig"] = sig
        elif not force and v.get("macros_sig") == sig and isinstance(v.get("nutrition"), dict):
            pass  # unchanged inputs, keep what is stored
        else:
            old = prev_versions.get(v["name"].lower()) or {}
            for field in _VERSION_MACRO_FIELDS:
                v.pop(field, None)
            if not force and old.get("macros_sig") == sig and isinstance(old.get("nutrition"), dict):
                for field in _VERSION_MACRO_FIELDS:
                    if field in old:
                        v[field] = old[field]
        out_versions.append(v)
    if versions:
        adaptations["versions"] = out_versions

    base = _ingredients(recipe.get("ingredients"))
    lf_base, lf_hit = swapped_list(base, swaps)
    if lf_hit:
        conf_lf = _confirmed_for(adaptations, "", True)
        sig = _list_sig([_SIG_VERSION, "original-low-fodmap", base, servings, swaps], conf_lf)
        lf = _variant(lf_base, servings, lookup, conf_lf)
        current = adaptations.get("low_fodmap_macros") or {}
        old = prev.get("low_fodmap_macros") or {}
        if lf is not None:
            adaptations["low_fodmap_macros"] = {**lf, "macros_sig": sig}
        elif not force and current.get("macros_sig") == sig:
            pass
        elif not force and old.get("macros_sig") == sig:
            adaptations["low_fodmap_macros"] = old
        else:
            adaptations.pop("low_fodmap_macros", None)
    else:
        adaptations.pop("low_fodmap_macros", None)
    return normalize_adaptations(adaptations)


def compute_recipe_macros(
    recipe: Dict[str, Any], lookup: Lookup, previous: Any = None, *, force: bool = False
) -> Dict[str, Any]:
    """DB fields for the whole recipe from line macros.

    Returns ``{"fields": {...}, "complete": bool, "nutrition": per-serving | None}``. ``fields``
    holds ``ingredient_macros`` + ``nutrition_*`` (only when every Original line is known) and
    ``adaptations`` (when the recipe has any).
    """
    fields: Dict[str, Any] = {}
    base = _ingredients(recipe.get("ingredients"))
    badges = _badges(base, lookup, _confirmed_for(recipe)) if base else None
    nutrition = None
    if badges is not None:
        nutrition = per_serving(badges, recipe_servings(recipe))
        fields["ingredient_macros"] = badges
        for key in CORE_NUTRITION_KEYS:
            fields[f"nutrition_{key}"] = nutrition[key]
    complete = badges is not None or not base
    if badges is not None and any(b.get("src") == "ai" and b.get("g") is None for b in badges):
        complete = False  # AI lines without grams: the background job fills them (per-100 g)
    if normalize_adaptations(recipe.get("adaptations")):
        adaptations = refresh_adaptation_macros(recipe, previous, force=force, lookup=lookup)
        fields["adaptations"] = adaptations
        if adaptations_need_macros(adaptations):
            complete = False
    return {"fields": fields, "complete": complete, "nutrition": nutrition}


def _lookup_from(lines: Sequence[Dict[str, str]], estimates: Sequence[Optional[Badge]]) -> Lookup:
    from services.line_macros import ingredient_line, normalize_line

    table = {normalize_line(ingredient_line(i)): e for i, e in zip(lines, estimates) if e is not None}

    def lookup(item: Any) -> Optional[Badge]:
        key = normalize_line(ingredient_line(item))
        if not key:
            return {"p": 0, "c": 0, "f": 0, "cal": 0}
        return table.get(key)

    return lookup


def _seeded_badges(recipe: Dict[str, Any]) -> Dict[str, Badge]:
    """The Original's stored AI badges by normalised line (estimates saved before the shared
    cache existed): reused for their own lines so existing recipes keep their badges and cost no
    new AI calls. Lines the food database answers are never seeded - the database wins."""
    from services.line_macros import ingredient_line, normalize_line

    seeded: Dict[str, Badge] = {}
    for ing, badge in zip(_ingredients(recipe.get("ingredients")), stored_badges(recipe) or []):
        if not (isinstance(badge, dict) and ing["name"].strip()) or badge.get("src") in ("db", "user", "barcode"):
            continue
        if _db_answer(ing) is not None:
            continue
        entry = {**{k: int(badge.get(k) or 0) for k in ("p", "c", "f", "cal")}, "src": "ai"}
        g = badge.get("g")
        if isinstance(g, (int, float)) and not isinstance(g, bool) and g >= 0:
            entry.update({"g": g, "g_src": "ai"})
        seeded.setdefault(normalize_line(ingredient_line(ing)), entry)
    return seeded


def weightless_lines(recipe: Dict[str, Any]) -> List[Tuple[str, str, Badge]]:
    """(key, line text, badge) for the Original's stored AI badges that have no grams yet
    (``line_macros.fill_grams`` input; the backfill batches these across recipes)."""
    from services.line_macros import ingredient_line, normalize_line

    seeded = _seeded_badges(recipe)
    texts = {normalize_line(ingredient_line(i)): ingredient_line(i) for i in _ingredients(recipe.get("ingredients"))}
    return [(k, texts.get(k, k), b) for k, b in seeded.items() if b.get("g") is None]


def lines_to_estimate(recipe: Dict[str, Any]) -> List[Dict[str, str]]:
    """Lines of this recipe that need the cache / AI (not covered by its own stored badges)."""
    from services.line_macros import ingredient_line, normalize_line

    seeded = _seeded_badges(recipe)
    return [i for i in all_lines(recipe) if normalize_line(ingredient_line(i)) not in seeded]


async def recipe_lookup(
    recipe: Dict[str, Any],
    *,
    allow_ai: bool = True,
    client=None,
    fill_weights: bool = False,
    region: Optional[str] = None,
) -> Lookup:
    """Line macros for every list of the recipe (own stored badges, cache, then AI).
    ``fill_weights``: also estimate grams for AI lines that have none (per-100 g).
    ``region`` ("uk" / "us"): food-data region for the lookups; None keeps the default (UK)."""
    from services.line_macros import estimate_line_macros, fill_grams, ingredient_line, normalize_line
    from utils.region import region_kwargs

    seeded = _seeded_badges(recipe)
    if fill_weights:
        texts = {normalize_line(ingredient_line(i)): ingredient_line(i) for i in all_lines(recipe)}
        grams = await fill_grams(
            [(k, texts.get(k, k), b) for k, b in seeded.items() if b.get("g") is None],
            client=client, allow_ai=allow_ai,
        )
        for k, g in grams.items():
            seeded[k] = {**seeded[k], "g": g, "g_src": "ai"}
    lines = lines_to_estimate(recipe)
    extra = region_kwargs(estimate_line_macros, region) if region else {}
    estimates = (await estimate_line_macros(lines, client=client, allow_ai=allow_ai, fill_weights=fill_weights, **extra)
                 if lines else [])
    base = _lookup_from(lines, estimates)

    def lookup(item: Any) -> Optional[Badge]:
        hit = seeded.get(normalize_line(ingredient_line(item)))
        return dict(hit) if hit is not None else base(item)

    return lookup


async def refresh_recipe_macros(
    recipe: Dict[str, Any],
    previous: Any = None,
    *,
    allow_ai: bool = True,
    force: bool = False,
    client=None,
    fill_weights: bool = False,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """``compute_recipe_macros`` with the line macros fetched. Never raises: on error returns
    ``{"fields": {}, "complete": False, "nutrition": None}``. ``fill_weights``: also estimate
    grams for AI lines without them (one weights-only AI call per batch of lines)."""
    try:
        lookup = await recipe_lookup(
            recipe, allow_ai=allow_ai, client=client, fill_weights=fill_weights, region=region
        )
        return compute_recipe_macros(recipe, lookup, previous, force=force)
    except Exception:
        logger.warning("Recipe macro refresh failed for recipe %s", recipe.get("id"), exc_info=True)
        return {"fields": {}, "complete": False, "nutrition": None}


async def refresh_adaptation_macros_async(
    recipe: Dict[str, Any], previous: Any = None, *, force: bool = False, allow_ai: bool = True
) -> Optional[Dict[str, Any]]:
    """Adaptations only (kept for callers that just need versions). Never fails a save."""
    try:
        lookup = await recipe_lookup(recipe, allow_ai=allow_ai)
        return refresh_adaptation_macros(recipe, previous, force=force, lookup=lookup)
    except Exception:
        logger.warning("Version macro refresh failed for recipe %s", recipe.get("id"), exc_info=True)
        return normalize_adaptations(recipe.get("adaptations"))


def adaptations_need_macros(adaptations: Any) -> bool:
    """True when a version or the Original's Low FODMAP option has no stored macros."""
    data = normalize_adaptations(adaptations) or {}
    if any(version_needs_macros(v) for v in data.get("versions") or []):
        return True
    swaps = _swaps(data)
    if swaps:
        for v in data.get("versions") or []:
            if swapped_list(_ingredients(v.get("ingredients")), swaps)[1] and not v.get("low_fodmap_macros"):
                return True
    return False


def original_badges_current(recipe: Dict[str, Any]) -> bool:
    """The Original's stored badges line up with its list and follow the database-first rule."""
    return badges_current(_ingredients(recipe.get("ingredients")), stored_badges(recipe), _confirmed_for(recipe))


def stored_badges(recipe: Dict[str, Any]) -> Optional[List[Badge]]:
    """The Original's stored line macros when they line up with its ingredient list."""
    value = recipe.get("ingredient_macros")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    base = _ingredients(recipe.get("ingredients"))
    if isinstance(value, list) and base and len(value) == len(base):
        return value
    return None


def totals_match(stored: Optional[Dict[str, Any]], expected: Dict[str, int], tolerance: float = TOTALS_TOLERANCE) -> bool:
    """Stored per-serving core macros within ``tolerance`` of the line sum (1 unit slack)."""
    if not stored:
        return False
    for key in CORE_NUTRITION_KEYS:
        have = stored.get(key)
        if have is None:
            return False
        try:
            have = float(have)
        except (TypeError, ValueError):
            return False
        want = float(expected[key])
        if abs(have - want) > max(1.0, abs(want) * tolerance):
            return False
    return True


def macros_consistent(recipe: Dict[str, Any]) -> bool:
    """True when the Original's totals equal its stored line macros / servings and every version
    (and Low FODMAP option) has line-based macros. False -> the backfill recomputes it."""
    base = _ingredients(recipe.get("ingredients"))
    if base:
        badges = stored_badges(recipe)
        if badges is None or not badges_current(base, badges, _confirmed_for(recipe)):
            return False
        if not totals_match(columns_to_nutrition(recipe), per_serving(badges, recipe_servings(recipe))):
            return False
    adaptations = normalize_adaptations(recipe.get("adaptations")) or {}
    servings = recipe_servings(recipe)
    swaps = _swaps(adaptations)
    for v in adaptations.get("versions") or []:
        ings = _ingredients(v.get("ingredients"))
        _, lf_hit = swapped_list(ings, swaps)
        conf = _confirmed_for(adaptations, v["name"], False)
        conf_lf = _confirmed_for(adaptations, v["name"], True) if lf_hit else {}
        if v.get("macros_sig") != _list_sig([_SIG_VERSION, ings, servings, swaps if lf_hit else []], conf, conf_lf):
            return False
        if not isinstance(v.get("nutrition"), dict):
            return False
        badges = v.get("ingredient_macros")
        if isinstance(badges, list) and len(badges) == len(ings) and not badges_current(ings, badges, conf):
            return False
    if swapped_list(base, swaps)[1]:
        lf = adaptations.get("low_fodmap_macros") or {}
        conf_lf = _confirmed_for(adaptations, "", True)
        if lf.get("macros_sig") != _list_sig([_SIG_VERSION, "original-low-fodmap", base, servings, swaps], conf_lf):
            return False
    return True


def choice_macros(
    recipe: Dict[str, Any], version: Any = None, low_fodmap: bool = False
) -> Optional[Dict[str, Any]]:
    """Stored {nutrition, ingredient_macros} for a version / Low FODMAP choice, or None when the
    choice is the plain Original or nothing is stored (callers fall back to the recipe's own)."""
    from services.recipe_variants import find_version

    adaptations = normalize_adaptations((recipe or {}).get("adaptations")) or {}
    chosen = find_version(recipe, version)
    swaps = _swaps(adaptations)
    if chosen:
        if low_fodmap and swaps and chosen.get("low_fodmap_macros"):
            return chosen["low_fodmap_macros"]
        if chosen.get("nutrition"):
            return {"nutrition": chosen["nutrition"], "ingredient_macros": chosen.get("ingredient_macros") or []}
        return None
    if low_fodmap and adaptations.get("low_fodmap_macros"):
        lf = adaptations["low_fodmap_macros"]
        return {"nutrition": lf.get("nutrition"), "ingredient_macros": lf.get("ingredient_macros") or []}
    return None


def plausibility_flags(recipe: Dict[str, Any], lookup: Lookup) -> List[Dict[str, Any]]:
    """[{recipe_id, title, list, line, reason}] for implausible lines / per-serving totals."""
    from services.line_macros import ingredient_line
    from services.macro_plausibility import check_line, check_totals

    adaptations = normalize_adaptations(recipe.get("adaptations")) or {}
    swaps = _swaps(adaptations)
    servings = recipe_servings(recipe)
    lists: List[Tuple[str, List[Dict[str, str]]]] = [("Original", _ingredients(recipe.get("ingredients")))]
    lists += [(v["name"], _ingredients(v.get("ingredients"))) for v in adaptations.get("versions") or []]
    if swaps:
        for label, ings in list(lists):
            lf, hit = swapped_list(ings, swaps)
            if hit:
                lists.append((f"{label} (Low FODMAP)", lf))
    flags: List[Dict[str, Any]] = []
    seen = set()
    for label, ings in lists:
        known = []
        for ing in ings:
            badge = lookup(ing) if ing["name"].strip() else {"p": 0, "c": 0, "f": 0, "cal": 0}
            if badge is None:
                continue
            known.append(badge)
            text = ingredient_line(ing)
            for reason in check_line(text, badge):
                if (text, reason) not in seen:
                    seen.add((text, reason))
                    flags.append({"recipe_id": recipe.get("id"), "title": recipe.get("title"), "list": label,
                                  "line": text, "reason": reason})
        if ings and len(known) == len(ings):
            for reason in check_totals(per_serving(known, servings), recipe):
                flags.append({"recipe_id": recipe.get("id"), "title": recipe.get("title"), "list": label,
                              "line": None, "reason": reason})
    return flags
