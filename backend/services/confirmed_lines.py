"""
User-confirmed ("locked") ingredient-line macros: the "Check the numbers" step.

Before / while cooking the user can check the lines whose numbers are uncertain (AI estimates,
vague amounts, no weight, plausibility flags) and fix them: enter what they used, scan the
product's barcode or type the label figures. Confirmed figures are stored per recipe in
``adaptations.confirmed_lines``::

    {"<version>|<0|1>|<normalised line text>": {
        "p", "c", "f", "cal", "c_total"?, "g"?, "source": "user" | "barcode",
        "barcode"?, "product"?, "confirmed_at"}}

The key is the stable line key: the normalised line text as that list shows it (Low FODMAP lists
carry the swapped name), the version name (lower-case, "" = Original) and the Low FODMAP flag.
Editing a line's text changes its key, so its confirmation no longer applies (and is pruned on
save). Line-macro computation (``services.version_macros``) prefers a confirmed value over the
food database / AI, and recompute / backfill never overwrite it.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

CONFIRMED_SOURCES = ("user", "barcode")
MAX_CONFIRMED = 400
_CAPS = {"p": 1000, "c": 2000, "f": 1000, "cal": 10000}  # same caps as services/line_macros.py
_MAX_KEY = 700

# Per-serving override for one cook (meal log / Health Connect / Google Health).
OVERRIDE_LIMITS = {"calories": 5000, "protein": 500, "carbs": 800, "fat": 500, "fiber": 200, "sugar": 500}


def _num(value: Any, hi: float, *, integer: bool = True) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n or n < 0 or n > hi:  # NaN / out of range
        return None
    return int(round(n)) if integer else round(n, 1)


def confirm_key(line_text: Any, version: Any = None, low_fodmap: bool = False) -> str:
    from services.line_macros import ingredient_line, normalize_line

    text = ingredient_line(line_text) if isinstance(line_text, dict) else str(line_text or "")
    name = " ".join(str(version or "").split()).lower()[:80]
    if name == "original":
        name = ""
    return f"{name}|{1 if low_fodmap else 0}|{normalize_line(text)}"[:_MAX_KEY]


def clean_entry(value: Any) -> Optional[Dict[str, Any]]:
    """One confirmed line, validated; None when unusable."""
    if not isinstance(value, dict):
        return None
    out: Dict[str, Any] = {}
    for key, hi in _CAPS.items():
        n = _num(value.get(key), hi)
        if n is None:
            return None
        out[key] = n
    c_total = _num(value.get("c_total"), _CAPS["c"])
    if c_total is not None:
        out["c_total"] = c_total
    g = _num(value.get("g"), 100000, integer=False)
    if g is not None:
        out["g"] = g
    source = str(value.get("source") or "user").strip().lower()
    out["source"] = source if source in CONFIRMED_SOURCES else "user"
    barcode = re.sub(r"\D", "", str(value.get("barcode") or ""))[:20]
    if barcode:
        out["barcode"] = barcode
    product = " ".join(str(value.get("product") or "").split())[:200]
    if product:
        out["product"] = product
    when = str(value.get("confirmed_at") or "").strip()[:40]
    out["confirmed_at"] = when or datetime.now(timezone.utc).isoformat()
    return out


def normalize_confirmed(value: Any) -> Dict[str, Dict[str, Any]]:
    """``adaptations.confirmed_lines`` cleaned (bad entries dropped, capped)."""
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(value, dict):
        return out
    for key, entry in value.items():
        key = str(key or "")[:_MAX_KEY]
        if key.count("|") < 2 or not key.split("|", 2)[2]:
            continue
        cleaned = clean_entry(entry)
        if cleaned is not None:
            out[key] = cleaned
        if len(out) >= MAX_CONFIRMED:
            break
    return out


def badge_from_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """A confirmed entry as a stored line badge (``src`` "user" / "barcode")."""
    badge: Dict[str, Any] = {k: int(entry.get(k) or 0) for k in ("p", "c", "f", "cal")}
    badge["src"] = entry.get("source") if entry.get("source") in CONFIRMED_SOURCES else "user"
    if entry.get("product"):
        badge["food"] = entry["product"]
    if entry.get("g") is not None:
        badge["g"] = entry["g"]
    badge["source"] = badge["src"]
    return badge


def is_confirmed_badge(badge: Any) -> bool:
    return isinstance(badge, dict) and badge.get("src") in CONFIRMED_SOURCES


def confirmed_of(adaptations: Any) -> Dict[str, Dict[str, Any]]:
    from utils.recipe_fields import normalize_adaptations

    data = adaptations if isinstance(adaptations, dict) and "confirmed_lines" in adaptations else (
        normalize_adaptations(adaptations) or {})
    return normalize_confirmed(data.get("confirmed_lines"))


def for_list(adaptations: Any, version: Any = None, low_fodmap: bool = False) -> Dict[str, Dict[str, Any]]:
    """{normalised line text: badge} confirmed for one list (version + Low FODMAP flag)."""
    prefix = confirm_key("", version, low_fodmap)  # "<version>|<lf>|"
    out: Dict[str, Dict[str, Any]] = {}
    for key, entry in confirmed_of(adaptations).items():
        if key.startswith(prefix):
            out[key[len(prefix):]] = badge_from_entry(entry)
    return out


def line_variants(ing: Any) -> List[str]:
    """Normalised texts a confirmation of this line may be stored under: the line as shown, then
    for a grouped line its pre-sections form ("75 g basil pesto: almonds") so checks made before
    ingredient sections existed still apply."""
    from services.line_macros import ingredient_line, normalize_line
    from utils.ingredient_groups import legacy_name

    out = [normalize_line(ingredient_line(ing))]
    if isinstance(ing, dict) and ing.get("group"):
        old = normalize_line(ingredient_line({**ing, "name": legacy_name(ing)}))
        if old not in out:
            out.append(old)
    return out


def confirmed_for_line(table: Dict[str, Any], ing: Any) -> Optional[Dict[str, Any]]:
    """The ``for_list`` entry for one line (current key first, then its pre-sections key)."""
    for text in line_variants(ing):
        hit = table.get(text)
        if hit is not None:
            return hit
    return None


# --- lists ------------------------------------------------------------------------------------

def recipe_lists(recipe: Dict[str, Any]) -> List[Tuple[str, bool, List[Dict[str, str]]]]:
    """[(version name ("" = Original), low_fodmap, ingredients)] for every list the page shows."""
    from services.version_macros import _ingredients, _swaps, swapped_list
    from utils.recipe_fields import normalize_adaptations

    adaptations = normalize_adaptations(recipe.get("adaptations")) or {}
    swaps = _swaps(adaptations)
    out: List[Tuple[str, bool, List[Dict[str, str]]]] = []
    bases = [("", _ingredients(recipe.get("ingredients")))]
    bases += [(v["name"], _ingredients(v.get("ingredients"))) for v in adaptations.get("versions") or []]
    for name, ings in bases:
        out.append((name, False, ings))
        if swaps:
            lf, hit = swapped_list(ings, swaps)
            if hit:
                out.append((name, True, lf))
    return out


def choice_list(recipe: Dict[str, Any], version: Any = None, low_fodmap: bool = False) -> Tuple[str, bool, List[Dict[str, str]]]:
    """The list a version / Low FODMAP choice shows: (version name, effective LF flag, lines).
    Unknown versions fall back to the Original; LF only counts when a swap applies."""
    from services.recipe_variants import find_version

    chosen = find_version(recipe, version)
    name = chosen["name"] if chosen else ""
    lists = {(n.lower(), lf): ings for n, lf, ings in recipe_lists(recipe)}
    if low_fodmap and (name.lower(), True) in lists:
        return name, True, lists[(name.lower(), True)]
    return name, False, lists.get((name.lower(), False), [])


def valid_keys(recipe: Dict[str, Any]) -> set:
    keys = set()
    for name, lf, ings in recipe_lists(recipe):
        for ing in ings:
            if ing["name"].strip():
                keys.update(confirm_key(text, name, lf) for text in line_variants(ing))
    return keys


def prune(adaptations: Optional[Dict[str, Any]], recipe: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Adaptations without confirmations whose line no longer exists (edited / removed)."""
    if not adaptations or "confirmed_lines" not in adaptations:
        return adaptations
    current = normalize_confirmed(adaptations.get("confirmed_lines"))
    keep_keys = valid_keys({**recipe, "adaptations": adaptations})
    kept = {k: v for k, v in current.items() if k in keep_keys}
    out = dict(adaptations)
    if kept:
        out["confirmed_lines"] = kept
    else:
        out.pop("confirmed_lines", None)
    return out or None


_MISSING = object()


def reconcile_on_update(existing_adaptations: Any, sent_adaptations: Any, merged_recipe: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Adaptations for a recipe save + whether they differ from what is stored.

    A client that sends ``adaptations`` without ``confirmed_lines`` (every editor before this
    feature) keeps the stored confirmations; one that sends the key replaces them. Either way
    confirmations for lines that no longer exist are dropped (editing a line invalidates it).
    """
    from utils.recipe_fields import normalize_adaptations

    before = normalize_adaptations(existing_adaptations)
    if sent_adaptations is _MISSING:
        base = before
    else:
        base = normalize_adaptations(sent_adaptations)
        raw_sent = sent_adaptations if isinstance(sent_adaptations, dict) else {}
        if "confirmed_lines" not in raw_sent:
            stored = (before or {}).get("confirmed_lines")
            if stored:
                base = {**(base or {}), "confirmed_lines": stored}
    after = normalize_adaptations(prune(base, {**merged_recipe, "adaptations": base}))
    return after, after != before


# --- uncertainty -------------------------------------------------------------------------------

SOURCE_LABELS = {
    "user": "You checked",
    "barcode": "Barcode",
    "cofid": "CoFID",
    "usda": "USDA",
    "fdc": "USDA",
    "off": "UK label",
    "openfoodfacts": "UK label",
    "uk_label": "UK label",
    "label": "UK label",
    "curated": "Laro list",
    "food_db": "Laro list",
}


def source_label(badge: Optional[Dict[str, Any]]) -> str:
    if not badge:
        return "No estimate yet"
    src = badge.get("src")
    if src in CONFIRMED_SOURCES:
        return SOURCE_LABELS[src]
    if src != "db":
        return "AI estimate"
    source = str(badge.get("source") or "").lower()
    for key, label in SOURCE_LABELS.items():
        if key in source:
            return label
    return "Food database"


def line_reasons(text: str, badge: Optional[Dict[str, Any]]) -> List[str]:
    """Why a line's numbers deserve a look (empty = trusted). Confirmed lines are trusted."""
    from services.line_macros import _VAGUE_RE
    from services.macro_plausibility import check_line, is_vague

    if badge is None:
        return ["No estimate yet"]
    if is_confirmed_badge(badge):
        return []
    reasons: List[str] = []
    if badge.get("src") != "db":
        reasons.append("AI estimate")
    if is_vague(text) or _VAGUE_RE.search(text or ""):
        reasons.append("Vague amount")
    if badge.get("g") in (None, "") and (badge.get("cal") or 0) > 0:
        reasons.append("No weight given")
    for reason in check_line(text, badge):
        reasons.append(f"Looks off: {reason}")
    return list(dict.fromkeys(reasons))


def check_payload(recipe: Dict[str, Any], lookup, version: Any = None, low_fodmap: bool = False) -> Dict[str, Any]:
    """Everything the "Check the numbers" screen shows for one version / Low FODMAP choice."""
    from services.line_macros import ingredient_line
    from services.version_macros import per_serving, recipe_servings, stored_badge

    name, lf, ings = choice_list(recipe, version, low_fodmap)
    confirmed = confirmed_of(recipe.get("adaptations"))
    servings = recipe_servings(recipe)
    lines = []
    known = []
    for index, ing in enumerate(ings):
        if not ing["name"].strip():
            continue
        text = ingredient_line(ing)
        key = confirm_key(text, name, lf)
        entry = next((confirmed[k] for k in (confirm_key(t, name, lf) for t in line_variants(ing)) if k in confirmed), None)
        badge = badge_from_entry(entry) if entry else lookup(ing)
        badge = stored_badge(badge) if badge is not None else None
        if badge is not None:
            known.append(badge)
        reasons = line_reasons(text, badge)
        row: Dict[str, Any] = {
            "index": index,
            "key": key,
            "line": text,
            "amount": ing.get("amount") or "",
            "unit": ing.get("unit") or "",
            "name": ing["name"],
            "macros": badge,
            "source_label": source_label(badge),
            "uncertain": bool(reasons),
            "reasons": reasons,
            "confirmed": bool(entry),
        }
        if entry:
            for k in ("confirmed_at", "barcode", "product", "c_total"):
                if entry.get(k) is not None:
                    row[k] = entry[k]
        lines.append(row)
    complete = len(known) == len(lines)
    return {
        "recipe_id": recipe.get("id"),
        "version": name,
        "low_fodmap": lf,
        "servings": servings,
        "lines": lines,
        "uncertain_count": sum(1 for r in lines if r["uncertain"]),
        "complete": complete,
        "nutrition": per_serving(known, servings) if complete else None,
    }


# --- what the user entered -> line macros -------------------------------------------------------

def badge_from_label(
    per: Dict[str, Any], *, basis: str = "100g", used_g: Optional[float] = None, packs: Optional[float] = None,
    pack_g: Optional[float] = None,
) -> Dict[str, Any]:
    """Line macros from label figures. ``basis`` "100g": figures per 100 g x ``used_g`` / 100.
    "pack": figures per pack x ``packs`` (or ``used_g`` / ``pack_g``). Raises ValueError."""
    figures = {}
    for short, names in (("cal", ("kcal", "calories", "energy_kcal", "cal")), ("p", ("protein", "p")),
                         ("c", ("carbs", "carbohydrate", "c")), ("f", ("fat", "f"))):
        value = next((per.get(n) for n in names if per.get(n) not in (None, "")), None)
        n = _num(value, 10000, integer=False)
        if n is None:
            raise ValueError(f"Missing or invalid {names[0]}")
        figures[short] = float(n)
    if basis == "pack":
        if packs is None and used_g is not None and pack_g:
            packs = float(used_g) / float(pack_g)
        if packs is None or not (0 < float(packs) <= 50):
            raise ValueError("How many packs did you use?")
        scale = float(packs)
        grams = float(pack_g) * scale if pack_g else None
    else:
        if used_g is None or not (0 < float(used_g) <= 10000):
            raise ValueError("How many grams (or ml) did you use?")
        scale = float(used_g) / 100.0
        grams = float(used_g)
    if basis == "100g" and figures["cal"] > 950:
        raise ValueError("That is more than 950 kcal per 100 g: check the label")
    out = {k: int(round(v * scale)) for k, v in figures.items()}
    for k, hi in _CAPS.items():
        if out[k] > hi:
            raise ValueError("That works out too high for one line: check the amount")
    if grams is not None:
        out["g"] = round(grams, 1)
    return out


def food_name(name: str) -> str:
    """The food in an ingredient name without its vague amount words
    ("drizzle of olive oil" -> "olive oil", "a handful of spinach" -> "spinach")."""
    from services.line_macros import _VAGUE_RE, _strip_name

    s = " ".join(_VAGUE_RE.sub(" ", name or "").split())
    s = re.sub(r"^(?:(?:a|an|some|of)\s+)+", "", s, flags=re.I)
    s = _strip_name(s.split(",")[0])  # ", washed" / ", chopped": prep notes
    return s or " ".join(str(name or "").split())


def used_line(amount: Any, unit: Any, name: str) -> str:
    """'<amount> <unit> <food>' for an amount the user typed."""
    parts = [" ".join(str(x or "").split())[:40] for x in (amount, unit)]
    return " ".join(p for p in (*parts, food_name(name)) if p)


def validate_override(value: Any) -> Optional[Dict[str, int]]:
    """Per-serving nutrition for one cook; None when absent. Raises ValueError when invalid."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("nutrition_override must be an object")
    out: Dict[str, int] = {}
    for key, hi in OVERRIDE_LIMITS.items():
        raw = value.get(key)
        if raw is None:
            if key in ("calories", "protein", "carbs", "fat"):
                raise ValueError(f"nutrition_override.{key} is required")
            continue
        n = _num(raw, hi)
        if n is None:
            raise ValueError(f"nutrition_override.{key} must be between 0 and {hi}")
        out[key] = n
    if not any(out[k] for k in ("calories", "protein", "carbs", "fat")):
        raise ValueError("nutrition_override is all zero")
    # Energy from the macros can't wildly exceed the calories (labels round; fibre / alcohol vary).
    energy = 4 * out["protein"] + 4 * out["carbs"] + 9 * out["fat"]
    if energy > out["calories"] * 1.6 + 60:
        raise ValueError("nutrition_override macros don't add up to its calories")
    return out


def merge_lines(
    adaptations: Any, recipe: Dict[str, Any], version: Any, low_fodmap: bool,
    lines: Sequence[Dict[str, Any]], clear: Sequence[str] = (),
) -> Dict[str, Any]:
    """Adaptations with confirmations added / cleared for lines of one list (by line text or
    index). Raises ValueError for a line that is not in that list."""
    from services.line_macros import ingredient_line, normalize_line
    from utils.recipe_fields import normalize_adaptations

    data = dict(normalize_adaptations(adaptations) or {})
    current = normalize_confirmed(data.get("confirmed_lines"))
    name, lf, ings = choice_list(recipe, version, low_fodmap)
    texts = [ingredient_line(i) for i in ings]
    by_norm = {normalize_line(t): t for t in texts if t.strip()}
    # A grouped line's pre-sections key, so a re-check / clear replaces the old confirmation.
    old_keys = {normalize_line(t): line_variants(i)[1:] for t, i in zip(texts, ings) if t.strip()}

    def resolve(item: Dict[str, Any]) -> str:
        idx = item.get("index")
        if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(texts) and texts[idx].strip():
            return texts[idx]
        text = normalize_line(item.get("line"))
        if text in by_norm:
            return by_norm[text]
        raise ValueError(f"Line not in this recipe: {str(item.get('line') or idx)[:80]}")

    for item in lines:
        if not isinstance(item, dict):
            raise ValueError("Each line must be an object")
        text = resolve(item)
        entry = clean_entry({**item, "confirmed_at": datetime.now(timezone.utc).isoformat()})
        if entry is None:
            raise ValueError(f"Invalid numbers for: {text[:80]}")
        for old in old_keys.get(normalize_line(text), []):
            current.pop(confirm_key(old, name, lf), None)
        current[confirm_key(text, name, lf)] = entry
    for raw in clear:
        text = normalize_line(raw)
        for old in old_keys.get(text, []):
            current.pop(confirm_key(old, name, lf), None)
        current.pop(confirm_key(by_norm.get(text, text), name, lf), None)
    if len(current) > MAX_CONFIRMED:
        raise ValueError("Too many checked lines on this recipe")
    if current:
        data["confirmed_lines"] = current
    else:
        data.pop("confirmed_lines", None)
    return data
