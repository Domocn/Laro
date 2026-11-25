"""
Per-100 g nutrition for batch / base recipes (butters, nut butters, plant milks, pestos, sauces,
jams, stocks, spice mixes, breads ...), where "per serving" means nothing.

* ``weight_info(badges, yield_factor)`` -> ``{total_grams, raw_grams, nutrition_per_100g}`` from
  the line badges (``services.line_macros``): every line carries its grams ``g`` (database lines
  always, AI lines since the prompt asks for them). Water counts in the weight. ``None`` while a
  line with calories has no grams yet.
* ``auto_basis(title, category)`` -> "100g" | "serving": conservative keyword match on the title's
  head noun ("Basil Pesto" yes, "Pesto Pasta" no, "Bread with herbed olive oil" no).
* ``effective_basis(recipe)``: the user's override (``adaptations.nutrition_basis``) else auto.
* ``BAKE_YIELD``: baked goods lose water in the oven, so the finished weight is the raw
  ingredient weight x a yield factor. One table, used everywhere.

Nothing here is stored: ``attach_weight_fields`` derives the numbers from the stored badges every
time the recipe is shaped for the API, so they can never drift from the per-serving totals.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

BASES = ("serving", "100g")

# Finished weight / raw ingredient weight for baked goods (moisture lost in the oven).
# Bread / loaves lose ~10-15 % of the dough weight (lean loaves nearer 12 %); cakes, brownies,
# muffins and traybakes ~8-12 %. Mid-range values; the UI says "about".
BAKE_YIELD: Dict[str, float] = {
    "bread": 0.88,
    "cake": 0.90,
}

# --- title parsing ----------------------------------------------------------------------------

# A connector means the title is a dish served with / in something ("Bread with herbed olive oil",
# "Chicken in black bean sauce", "Salmon on garlic butter"), never a base item.
_DISH_CONNECTOR = re.compile(r"\b(with|in|on|over|served|topped|stuffed|filled)\b", re.I)
# Trailing qualifiers that don't change what the item is.
_TRAILING_NOISE = re.compile(
    r"(?:\s+(?:recipe|homemade|easy|quick|simple|basic|best|classic|vegan|vegetarian|"
    r"gluten[- ]free|dairy[- ]free|gf|df|v|vg|no[- ]knead))+$",
    re.I,
)

_PLANT_MILK = (r"(?:oat|almond|soy|soya|cashew|coconut|rice|hemp|pea|hazelnut|macadamia|pistachio|"
               r"walnut|plant|nut|seed|tiger ?nut|quinoa|flax|banana|peanut)\s+milk")

# Head-noun phrases (end of the title) that make a batch / base item.
_BASE_HEADS = [
    r"butter", r"spread", r"ghee", _PLANT_MILK, r"mylk", r"pesto", r"sauce", r"dressing", r"vinaigrette",
    r"mayo", r"mayonnaise", r"aioli", r"jam", r"marmalade", r"curd", r"syrup",
    r"flour\s+(?:blend|mix)", r"stock", r"broth", r"spice\s+(?:mix|blend)", r"seasoning", r"paste",
    r"granola", r"crumble\s+topping", r"icing", r"frosting", r"buttercream", r"chutney", r"pickles?",
    r"relish", r"ketchup", r"compote",
]
# Breads: also batch items (a loaf cut however you like).
_BREAD_HEADS = [
    r"bread", r"loaf", r"loaves", r"shokupan", r"focaccia", r"brioche", r"sourdough", r"baguettes?",
    r"ciabatta", r"rolls", r"buns", r"bloomer", r"challah", r"babka",
]
# "rolls" / "buns" that are dishes, not bread.
_NOT_BREAD = re.compile(
    r"\b(spring|egg|summer|sushi|cabbage|lasagne|lasagna|sausage|pork|bao|steamed|"
    r"meat|lobster|crab|ham)\s+(rolls?|buns?)$",
    re.I,
)
# Baked cake-type items (yield only - not auto per-100 g).
_CAKE_HEADS = [
    r"cake", r"cakes", r"brownies?", r"blondies?", r"muffins?", r"traybake", r"tray\s+bake", r"slice",
    r"flapjacks?", r"cupcakes?", r"loaf\s+cake", r"gingerbread", r"cookies?", r"biscuits?", r"scones?",
]
_NOT_CAKE = re.compile(r"\b(fish|crab|rice|potato|salmon|tuna|corn|bean|lentil|veggie|vegetable|pan)\s+cakes?$|"
                       r"\bno[- ]bake\b|\bpizza\s+slice$", re.I)

_BASE_RE = re.compile(r"(?:^|\s)(?:" + "|".join(_BASE_HEADS) + r")$", re.I)
_BREAD_RE = re.compile(r"(?:^|\s)(?:" + "|".join(_BREAD_HEADS) + r")$", re.I)
_CAKE_RE = re.compile(r"(?:^|\s)(?:" + "|".join(_CAKE_HEADS) + r")$", re.I)


def _title_parts(title: Any) -> list:
    """The title (without brackets) plus each bracketed part, cleaned for head-noun matching:
    "Shokupan (Japanese Rice Bread)" -> ["shokupan", "japanese rice bread"]."""
    text = " ".join(str(title or "").split())
    parts = [re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text)] + re.findall(r"\(([^)]*)\)", text)
    out = []
    for part in parts:
        s = part.lower().replace("&", " and ")
        s = re.sub(r"[^\w\s'-]", " ", s)
        s = re.sub(r"\s+", " ", s).strip(" -'")
        s = _TRAILING_NOISE.sub("", s).strip()
        if s:
            out.append(s)
    return out


def _is_dish(part: str) -> bool:
    return bool(_DISH_CONNECTOR.search(part))


def item_kind(title: Any) -> Optional[str]:
    """"bread" / "base" / "cake" from the title's head noun, else None (a dish)."""
    for part in _title_parts(title):
        if _is_dish(part):
            continue
        if _BREAD_RE.search(part) and not _NOT_BREAD.search(part):
            return "bread"
        if _BASE_RE.search(part):
            return "base"
        if _CAKE_RE.search(part) and not _NOT_CAKE.search(part):
            return "cake"
    return None


def bake_kind(title: Any) -> Optional[str]:
    """Key into ``BAKE_YIELD`` for a baked item, else None."""
    kind = item_kind(title)
    return kind if kind in BAKE_YIELD else None


def bake_yield(title: Any) -> Optional[float]:
    kind = bake_kind(title)
    return BAKE_YIELD[kind] if kind else None


def auto_basis(title: Any, category: Any = None) -> str:
    """"100g" for batch / base items (title head noun, or the Sauce category), else "serving"."""
    kind = item_kind(title)
    if kind in ("base", "bread"):
        return "100g"
    if str(category or "").strip().lower() == "sauce" and not any(_is_dish(p) for p in _title_parts(title)):
        return "100g"
    return "serving"


def clean_basis(value: Any) -> Optional[str]:
    v = str(value or "").strip().lower().replace(" ", "")
    if v in ("100g", "per100g", "100"):
        return "100g"
    if v in ("serving", "perserving"):
        return "serving"
    return None


def effective_basis(recipe: Dict[str, Any], adaptations: Optional[Dict[str, Any]] = None) -> str:
    override = clean_basis((adaptations or {}).get("nutrition_basis"))
    return override or auto_basis(recipe.get("title"), recipe.get("category"))


# --- weights ----------------------------------------------------------------------------------

def _grams(badge: Dict[str, Any]) -> Optional[float]:
    g = badge.get("g")
    if isinstance(g, bool) or g is None:
        return None
    try:
        g = float(g)
    except (TypeError, ValueError):
        return None
    return g if g >= 0 else None


def weight_info(badges: Optional[Iterable[Any]], yield_factor: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """``{total_grams, raw_grams, nutrition_per_100g}`` for one list, or None when any line with
    calories has no grams (zero-calorie lines without grams - "salt to taste" - weigh ~0).

    ``total_grams`` is the finished weight (raw x ``yield_factor`` for baked goods); per-100 g is
    the whole list's macros x 100 / finished weight. ``carbs_total`` (incl. fibre, the US / CA
    label basis) is added only when every line knows its ``c_total`` (a line with no carbs
    counts as 0); otherwise it is left out and clients show the UK ``carbs``.
    """
    if badges is None:
        return None
    raw = 0.0
    sums = {"cal": 0.0, "p": 0.0, "c": 0.0, "f": 0.0}
    carbs_total: Optional[float] = 0.0
    seen = False
    for badge in badges:
        if not isinstance(badge, dict):
            return None
        seen = True
        for k in sums:
            sums[k] += float(badge.get(k) or 0)
        if carbs_total is not None:
            if badge.get("c_total") is not None:
                carbs_total += float(badge.get("c_total") or 0)
            elif not float(badge.get("c") or 0):
                pass  # no carbs at all: 0 on either basis
            else:
                carbs_total = None  # one line without a total: never show a partial sum
        g = _grams(badge)
        if g is None:
            if float(badge.get("cal") or 0) > 0:
                return None
            continue
        raw += g
    if not seen or raw <= 0:
        return None
    factor = yield_factor if yield_factor and 0 < yield_factor <= 1 else 1.0
    total = raw * factor
    per = {
        "calories": int(round(sums["cal"] * 100 / total)),
        "protein": round(sums["p"] * 100 / total, 1),
        "carbs": round(sums["c"] * 100 / total, 1),
        "fat": round(sums["f"] * 100 / total, 1),
    }
    if carbs_total is not None:
        per["carbs_total"] = round(carbs_total * 100 / total, 1)
    out: Dict[str, Any] = {"total_grams": int(round(total)), "nutrition_per_100g": per}
    if factor != 1.0:
        out["raw_grams"] = int(round(raw))
    return out


def attach_weight_fields(recipe: Dict[str, Any], adaptations: Optional[Dict[str, Any]],
                         original_badges: Optional[list]) -> Optional[Dict[str, Any]]:
    """Response-only fields on a copy of ``adaptations`` (created when the recipe has none):

      nutrition_basis_auto              "100g" when the title looks like a batch item (else absent)
      bake_yield                        factor, when the title is a baked item
      total_grams / raw_grams / nutrition_per_100g     Original (when every line weighs)
      versions[i].{total_grams, raw_grams, nutrition_per_100g}
      low_fodmap_macros / versions[i].low_fodmap_macros  the same

    ``nutrition_basis`` (the user's override) is left exactly as stored, so a client sending the
    adaptations back never turns the automatic choice into an override.
    """
    out: Dict[str, Any] = dict(adaptations or {})
    for key in ("nutrition_basis_auto", "bake_yield", "total_grams", "raw_grams", "nutrition_per_100g"):
        out.pop(key, None)
    factor = bake_yield(recipe.get("title"))
    if auto_basis(recipe.get("title"), recipe.get("category")) == "100g":
        out["nutrition_basis_auto"] = "100g"  # absent = "serving" (keeps ordinary recipes unchanged)
    if factor:
        out["bake_yield"] = factor
    info = weight_info(original_badges, factor)
    if info:
        out.update(info)

    def with_weights(variant: Any) -> Any:
        if not isinstance(variant, dict):
            return variant
        v = {k: val for k, val in variant.items() if k not in ("total_grams", "raw_grams", "nutrition_per_100g")}
        w = weight_info(v.get("ingredient_macros") if isinstance(v.get("ingredient_macros"), list) else None, factor)
        if w and isinstance(v.get("nutrition"), dict):
            v.update(w)
        return v

    if isinstance(out.get("low_fodmap_macros"), dict):
        out["low_fodmap_macros"] = with_weights(out["low_fodmap_macros"])
    if isinstance(out.get("versions"), list):
        versions = []
        for version in out["versions"]:
            v = with_weights(version)
            if isinstance(v, dict) and isinstance(v.get("low_fodmap_macros"), dict):
                v["low_fodmap_macros"] = with_weights(v["low_fodmap_macros"])
            versions.append(v)
        out["versions"] = versions
    return out or None
