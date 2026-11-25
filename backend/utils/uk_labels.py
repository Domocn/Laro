"""UK supermarket label medians for processed / branded foods (``data/foods/uk_labels.json``).

For foods whose shop-bought recipe differs from a generic composition table - houmous,
plant drinks and spreads, vegan cheese, pastes and sauces, tofu, tinned beans (drained),
breadcrumbs, stock cubes - the per-100 g median of real UK labels (Open Food Facts, built
by ``scripts/build_uk_labels.py``) is a better answer than CoFID / USDA. ``find_food``
consults this table first for the UK region.

Matching is by whole recipe wording only (each food lists its aliases): "fresh breadcrumbs"
and "breadcrumbs" are different foods, "smoked tofu" matches nothing here and falls through.
Entries flagged ``cooked_only`` (tinned beans, drained) answer only lines that say tinned /
drained / cooked, so plain "kidney beans" stays the dried figure.
"""
from __future__ import annotations

import json
import os
import re
import threading
from typing import Any, Dict, Optional, Tuple

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "foods", "uk_labels.json")

_NUMERIC = ("calories", "protein", "carbs", "fat", "fiber", "sugars", "saturates", "salt")

# Words in a recipe line that never change which product it is.
_NOISE = frozenset(
    "a an the of and to for with plus about approx approximately large small medium heaped level "
    "chopped diced finely roughly crumbled grated shredded sliced cubed torn pressed patted dry "
    "drained rinsed drained and rinsed softened melted chilled cold room temperature "
    "tin tins tinned can cans canned jar jarred carton tub pack packet block shop bought "
    "store ready made good quality organic optional serve serving to taste cooked of".split()
)

_LOCK = threading.Lock()
_DATA: Optional[Dict[str, Any]] = None
_EXACT: Dict[Tuple[str, ...], str] = {}


def _singular(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _words(text: str) -> Tuple[str, ...]:
    text = (text or "").lower().replace("-", " ").replace("*", "")
    return tuple(_singular(w) for w in re.findall(r"[a-z0-9%]+", text))


def load() -> Dict[str, Any]:
    """The label table (``{"foods": {...}, "built": ..., ...}``); empty when missing."""
    global _DATA
    if _DATA is not None:
        return _DATA
    with _LOCK:
        if _DATA is None:
            try:
                with open(DATA_PATH, encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                import logging

                logging.getLogger(__name__).exception("UK label table failed to load from %s", DATA_PATH)
                data = {"foods": {}}
            exact: Dict[Tuple[str, ...], str] = {}
            for key, food in (data.get("foods") or {}).items():
                for alias in [key.replace(" (cooked)", "")] + list(food.get("aliases") or []):
                    exact.setdefault(_words(alias), key)
            _EXACT.clear()
            _EXACT.update(exact)
            _DATA = data
    return _DATA


def entry_for(key: str) -> Optional[Dict[str, Any]]:
    """A food-table shaped entry for a label key (``carbs`` available, ``carbs_total`` incl. fibre)."""
    food = (load().get("foods") or {}).get(key)
    if not food:
        return None
    out: Dict[str, Any] = {k: float(food.get(k) or 0) for k in _NUMERIC}
    out["carbs_total"] = round(out["carbs"] + out["fiber"], 1)
    base = key.replace(" (cooked)", "")
    drained = " (tinned, drained)" if food.get("cooked_only") else ""
    out.update({
        "tags": [],
        "category": food.get("category") or "other",
        "source": "uk_labels",
        "source_id": key,
        "description": f"{base[:1].upper()}{base[1:]}{drained}, UK supermarket average",
        "state": food.get("state") or "as_sold",
        "match_score": 1.0,
        "products": int(food.get("products") or 0),
    })
    return out


def _candidates(text: str):
    """The recipe wording as written, then with prep / pack words dropped."""
    s = re.sub(r"\([^)]*\)", " ", (text or "").lower())
    s = re.split(r"\s+or\s+|\s*/\s*|,", s)[0]
    words = _words(s)
    yield words
    yield tuple(w for w in words if w not in _NOISE)


def find(name: str, *, cooked: bool = False) -> Optional[Tuple[str, Dict[str, Any]]]:
    """``(key, entry)`` when the line names a food in the UK label table, else None."""
    load()
    foods = (_DATA or {}).get("foods") or {}
    for words in _candidates(name):
        key = _EXACT.get(words) if words else None
        if key is None:
            continue
        if foods.get(key, {}).get("cooked_only") and not cooked:
            return None  # plain "chickpeas" is the dried pulse, not the tin
        entry = entry_for(key)
        if entry is not None:
            return key, entry
    return None
