"""
Per-ingredient-line macros: the single source every recipe total is built from.

``estimate_line_macros(lines)`` returns ``[{p, c, f, cal, src, ...}]`` (grams protein / carbs /
fat, kcal) for each line at the quantity written ("500 g dried pasta", "drizzle of olive oil"),
or ``None`` for a line that could not be estimated (AI unavailable / failed).

* **Database first.** A line with a concrete amount ("500 g", "2 tbsp", "125 ml", "2 eggs",
  "1 garlic clove") whose food has a confident offline ``find_food`` match (curated table, then
  UK CoFID / USDA) is computed as per-100 g values x grams / 100. Provenance rides along:
  ``src="db"``, ``food`` (matched food), ``g`` (grams used), ``source`` / ``source_id``.
  Water / salt (all-zero foods) are 0 whatever the amount.
* **Both carb figures.** ``c`` is available carbohydrate (UK basis, fibre excluded - the
  default everywhere); database lines also carry ``c_total`` (total carbohydrate incl. fibre,
  US basis) so totals can be shown either way without recomputing. AI lines have no
  ``c_total`` (callers fall back to ``c``).
* **Region.** ``region="uk"`` (default) looks foods up UK-first (UK labels, CoFID); ``"us"``
  uses USDA first (``utils.food_db.find_food``). Only UK database answers are written to the
  shared cache table.
* **AI fallback** for the rest (vague amounts, unknown foods, no sane volume -> grams
  conversion): the nutrition prompt in JSON mode, at most ``BATCH_SIZE`` lines per call,
  ``src="ai"``.
* Every answer is cached by the normalised line text, in memory and in the
  ``ingredient_line_macros`` table (with its provenance), so identical lines across recipes /
  versions / Low FODMAP lists never cost a second AI call. Database results are recomputed live
  (cheap, offline) and always win over a cached AI row for the same line.
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

Badge = Dict[str, Any]  # {"p", "c", "f", "cal"[, "c_total"]} ints + provenance ("src", "food", "g", "source", "source_id")
MACRO_KEYS = ("p", "c", "f", "cal")
PROVENANCE_KEYS = ("src", "food", "g", "g_src", "source", "source_id")

BATCH_SIZE = 40
PARALLEL_CALLS = 4
# Cloud: the larger model is far better at quantities than the default chat model.
LINE_MACROS_MODEL = os.environ.get("OLLAMA_MACROS_MODEL") or os.environ.get("OLLAMA_IMPORT_MODEL", "gpt-oss:120b")
# Whole-line amounts: 335 g coconut oil is 335 g fat / ~2,890 kcal, 1 kg flour ~3,640 kcal.
_CAPS = {"p": 1000, "c": 2000, "f": 1000, "cal": 10000}
_MAX_KEY = 500

SYSTEM_PROMPT = "You are a precise nutrition estimator. Reply ONLY with compact JSON, no prose."

VAGUE_AMOUNT_GUIDANCE = (
    "Vague amounts: a drizzle = about 1 tbsp; a splash = about 1 tbsp; a dash = about 1 tsp; "
    "a knob = about 1 tbsp; a sprinkle = about 1 tsp; a handful = about 30 g; a pinch = ~0; "
    '"to taste" / "as needed" / "for serving" / "optional" with no quantity = a small amount, '
    "usually ~0 for salt, pepper, spices, herbs, water and stock, otherwise about 1 tsp. "
    "Never assume 100 g for a line with a vague or missing amount. "
    "A count with no size (\"1 onion\", \"2 eggs\") = one typical medium item each. "
    "Dried pasta, rice and grains are weighed dry unless the line says cooked."
)


def build_user_prompt(lines: Sequence[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {n}" for i, n in enumerate(lines))
    return (
        f"Estimate the macros contributed by EACH ingredient line below, at the exact quantity given:\n{numbered}\n\n"
        f"{VAGUE_AMOUNT_GUIDANCE}\n\n"
        f'Return JSON: {{"items": [{{"p": <protein grams int>, "c": <carbs grams int>, '
        f'"f": <fat grams int>, "cal": <kcal int>, "g": <weight of the ingredient as used, grams int>}}, ...]}} '
        f"with EXACTLY {len(lines)} items in the SAME order. "
        f"Use 0 where an ingredient contributes ~none (water, salt, spices), but still give water / "
        f"stock / milk their weight in g (1 ml = 1 g). Integers only."
    )


def build_grams_prompt(lines: Sequence[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {n}" for i, n in enumerate(lines))
    return (
        f"Estimate the WEIGHT in grams of EACH ingredient line below, as used in the recipe:\n{numbered}\n\n"
        f"{VAGUE_AMOUNT_GUIDANCE} Liquids: 1 ml = about 1 g (oil 0.92 g). Drained tins: the drained weight.\n\n"
        f'Return JSON: {{"items": [{{"g": <grams int>}}, ...]}} with EXACTLY {len(lines)} items in the SAME '
        f"order. Integers only."
    )


def normalize_line(text: Any) -> str:
    """Cache key: lower-case, single spaces, no trailing punctuation."""
    s = " ".join(str(text or "").lower().split())
    return s.strip(" ,.;:-")[:_MAX_KEY]


def ingredient_line(item: Any) -> str:
    """'amount unit name' for an ingredient dict / string, as the AI sees it."""
    if isinstance(item, dict):
        parts = [str(item.get(k) or "").strip() for k in ("amount", "unit", "name")]
        return " ".join(p for p in parts if p)
    return " ".join(str(item or "").split())


def clamp(value: Any, hi: int) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return n if 0 <= n <= hi else 0


def clean_grams(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        g = float(value)
    except (TypeError, ValueError):
        return None
    return round(g, 1) if 0 <= g <= 100000 else None


def clean_badge(item: Any) -> Badge:
    """Macros as clamped ints; ``src`` defaults to "ai" (cache rows written before provenance
    existed were AI estimates) and database provenance is kept when present. Grams ``g`` ride
    along for both, with ``g_src`` ("db" measured from the amount, "ai" estimated)."""
    item = item if isinstance(item, dict) else {}
    out: Badge = {k: clamp(item.get(k), hi) for k, hi in _CAPS.items()}
    g = clean_grams(item.get("g"))
    if item.get("c_total") is not None:  # US-basis carbs (incl. fibre); absent on old / AI rows
        out["c_total"] = clamp(item.get("c_total"), _CAPS["c"])
    if item.get("src") == "db":
        out["src"] = "db"
        for key in ("food", "source", "source_id"):
            if item.get(key):
                out[key] = str(item[key])[:200]
        if g is not None:
            out["g"] = g
            out["g_src"] = "db"
    else:
        out["src"] = "ai"
        if g is not None:
            out["g"] = g
            out["g_src"] = "ai"
    return out


def macros_of(badge: Any) -> Dict[str, int]:
    """Just ``{p, c, f, cal}`` (drops provenance)."""
    badge = badge if isinstance(badge, dict) else {}
    return {k: int(badge.get(k) or 0) for k in MACRO_KEYS}


# --- database first ----------------------------------------------------------------------------
#
# amount -> grams:
#   mass (g / kg / oz / lb)                    qty x UNIT_CONVERSIONS
#   volume (ml / l / cup / tbsp / tsp)         ml x density(food) - oils 0.92, water-like liquids
#                                              1.0, flours / sugars / oats / rice ... per-cup
#                                              weights; no density -> AI
#   egg / clove / fillet / breast / thigh      PIECE_WEIGHTS_G for the food (clove only for garlic)
#   bare count ("2 eggs", "1 lemon")           PIECE_WEIGHTS_G when the whole food name is a
#                                              known countable item ("cherry tomatoes" is not
#                                              "tomato") -> else AI
#   "1 can (400 g) chickpeas"                  the weight in brackets
#   vague ("drizzle", "pinch", "to taste")     AI (unless the food is all-zero: water / salt)

DB_FIRST = True  # tests of the AI / cache mechanics switch this off
DATASET_MIN_SCORE = 0.9  # stricter than find_food's own floor: the line's numbers depend on it
MAX_DB_GRAMS = 5000.0

_UNICODE_FRACTIONS = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3", "⅛": "1/8", "⅕": "1/5"}

_VAGUE_RE = re.compile(
    r"\b(drizzles?|pinch(?:es)?|handfuls?|splash(?:es)?|dash(?:es)?|knobs?|sprinkl\w*|glugs?|squeeze[sd]?|"
    r"to taste|as needed|as required|if needed|if you like|a few|few|some|little|generous(?:ly)?|"
    r"heap(?:ed|ing)|scant|juice|juiced|zest|zested|dollops?|smidgen|bunch(?:es)?|sprigs?)\b",
    re.I,
)
# Range / multiplier straight after the number ("1-2 tbsp", "2 x 400 g tins", "3 or 4").
_RANGE_RE = re.compile(r"^\s*(?:-|–|—|to\b|or\b|x\b|×)\s*\d")
_PAREN_MASS_RE = re.compile(r"\(\s*(\d+(?:\.\d+)?)\s*(g|grams?|kg|ml|oz)\s*\)", re.I)

_MASS_UNITS = {"g": 1.0, "gram": 1.0, "grams": 1.0, "kg": 1000.0, "kilogram": 1000.0,
               "oz": 28.35, "ounce": 28.35, "ounces": 28.35, "lb": 453.6, "pound": 453.6, "pounds": 453.6}
_VOLUME_UNITS = {"ml": 1.0, "l": 1000.0, "liter": 1000.0, "liters": 1000.0, "cup": 240.0, "cups": 240.0,
                 "tbsp": 15.0, "tablespoon": 15.0, "tablespoons": 15.0,
                 "tsp": 5.0, "teaspoon": 5.0, "teaspoons": 5.0}
_EXTRA_UNITS = {"litre": "l", "litres": "l", "millilitre": "ml", "millilitres": "ml", "milliliter": "ml",
                "milliliters": "ml", "grammes": "g", "kgs": "kg", "lbs": "lb", "tbs": "tbsp", "tbsps": "tbsp",
                "tsps": "tsp", "tblsp": "tbsp"}
# Count units whose weight comes from the food's piece weight.
_PIECE_UNITS = {"egg", "eggs", "clove", "cloves", "fillet", "fillets", "breast", "breasts",
                "thigh", "thighs", "stalk", "stalks", "ear", "ears"}
# Packaging / vague portions: only usable with a weight in brackets.
_CONTAINER_WORDS = frozenset(
    "can cans tin tins jar jars pack packs packet packets package packages bag bags box boxes carton cartons "
    "bottle bottles block blocks bunch bunches head heads sachet sachets pot pots punnet punnets loaf loaves "
    "bar bars slice slices piece pieces sprig sprigs sheet sheets stick sticks wedge wedges cube cubes "
    "item items serving servings portion portions scoop scoops handful handfuls cup cups".split()
)
# Words that don't change what a counted item weighs ("1 red onion" is an onion).
_PIECE_NOISE = frozenset(
    "a an of fresh ripe red green yellow orange-fleshed organic free range whole raw peeled unpeeled large "
    "medium small clove cloves fillet fillets skinless boneless unwaxed british uk chopped diced sliced minced "
    "crushed grated halved quartered trimmed".split()
)
# Zero-calorie foods: these extra words don't hide a different food ("cold water", "sea salt").
_ZERO_NOISE = frozenset(
    "a an the of to for as and or cold warm hot boiling boiled lukewarm tepid iced ice filtered tap "
    "sparkling still fine coarse sea kosher flaky table rock pink himalayan taste needed required "
    "pinch dash some more extra plus serving reserved cooking pasta seasoning about approx".split()
)

# (pattern, grams per ml); None = no sane conversion (AI). First match wins: specific first.
_DENSITIES: List[Tuple[re.Pattern, Optional[float]]] = [(re.compile(rx, re.I), d) for rx, d in (
    (r"\bin oil\b|\bsugar snap|\bnoodles?\b|\bpasta\b|spaghetti|macaroni|penne|\bfusilli|"
     r"milk powder|powdered milk|milk chocolate|stock (?:cube|pot|powder)|bouillon (?:cube|powder)|"
     r"protein powder|ice cream|\bleaves\b|chopped (?:fresh )?(?:parsley|coriander|cilantro|basil|mint|dill|chives)", None),
    (r"\boils?\b", 0.92),
    (r"maple syrup", 1.32),
    (r"\bhoney\b|golden syrup|treacle|molasses|\bagave|rice syrup|date syrup|\bsyrup\b", 1.4),
    (r"cream of tartar", 0.6),
    (r"cream cheese", 1.0),
    (r"\bwater\b|\bmilk\b|buttermilk|\bkefir\b|\bstock\b|\bbroth\b|\bjuice\b|vinegar|soy sauce|\btamari\b|"
     r"fish sauce|worcestershire|\bwine\b|\bbeer\b|\bcider\b|\bsake\b|\bmirin\b|\bcoffee\b|\btea\b|\bcream\b|"
     r"cr[eè]me fra[iî]che|yogh?urt|\bpassata\b|coconut water|liquid smoke|hot sauce|sriracha|vanilla extract|"
     r"\bextract\b|\bespresso\b|\brum\b|\bbrandy\b|\bsherry\b|\bvodka\b|\bwhisk(?:e)?y\b", 1.0),
    (r"tomato (?:paste|pur[eé]e)", 1.1),
    (r"mayonnaise|\bmayo\b", 0.93),
    (r"ketchup|hoisin|bbq sauce|barbecue sauce|sweet chilli sauce|sweet chili sauce|gochujang", 1.12),
    (r"\bmiso\b", 1.15),
    (r"\bmustard\b|\bpesto\b|curry paste|\bharissa\b|\bsauce\b", 1.03),
    (r"\bjam\b|marmalade|\bpreserves?\b", 1.35),
    (r"\bbutter beans?\b|\bbeans?\b|chickpeas?|garbanzo", 0.7),
    (r"peanut butter|almond butter|cashew butter|nut butter|\btahini\b", 1.08),
    (r"\bbutter\b|\bghee\b|margarine|\blard\b", 0.95),
    (r"almond flour|ground almonds|almond meal|almonds ground", 0.4),
    (r"coconut flour", 0.47),
    (r"oat flour", 0.38),
    (r"corn ?flour|corn ?starch|arrowroot|tapioca (?:flour|starch)|potato starch", 0.53),
    (r"\bflour\b", 0.53),
    (r"brown sugar|muscovado|demerara", 0.92),
    (r"icing sugar|powdered sugar|confectioners", 0.5),
    (r"coconut sugar", 0.75),
    (r"\bsugar\b", 0.84),
    (r"cocoa|cacao powder", 0.36),
    (r"\boats\b|porridge oats|rolled oats|oatmeal", 0.38),
    (r"cooked rice|rice,? cooked|leftover rice", 0.66),
    (r"\brice\b", 0.77),
    (r"quinoa", 0.71),
    (r"couscous", 0.73),
    (r"bulgur|bulghur|freekeh|pearl barley|\bbarley\b", 0.75),
    (r"lentils?|split peas", 0.8),
    (r"\bpeas\b|sweetcorn|\bcorn\b", 0.6),
    (r"parmesan|pecorino|grana padano|grated cheese|shredded cheese|cheese,? (?:grated|shredded)|"
     r"(?:grated|shredded) .*cheese|(?:grated|shredded) (?:cheddar|mozzarella)|(?:cheddar|mozzarella),? (?:grated|shredded)", 0.42),
    (r"nutritional yeast", 0.25),
    (r"chia|flax|linseed|sesame seeds?|hemp seeds?|poppy seeds?|pumpkin seeds?|sunflower seeds?|pepitas", 0.62),
    (r"desiccated coconut|shredded coconut|coconut flakes", 0.35),
    (r"chocolate chips|chocolate chunks|choc chips", 0.7),
    (r"raisins|sultanas|currants|dried cranberries", 0.6),
    (r"panko", 0.25),
    (r"breadcrumbs", 0.45),
    (r"chopped (?:nuts|walnuts|pecans|hazelnuts|almonds)|walnuts|pecans|\bnuts\b", 0.5),
    (r"almonds|cashews|peanuts|hazelnuts|pistachios|macadamias", 0.6),
    (r"baking powder|baking soda|bicarbonate|bicarb", 0.9),
    (r"\byeast\b", 0.62),
    (r"\bsalt\b", 1.2),
    (r"dried (?:oregano|thyme|basil|rosemary|parsley|mint|dill|tarragon|sage|herbs|chives|marjoram)|"
     r"mixed herbs|italian seasoning|herbes de provence|bay leaf", 0.25),
    (r"\bground\b|\bpowder\b|paprika|turmeric|cinnamon|cumin|coriander seeds?|garam masala|curry powder|"
     r"chill?i flakes|chili flakes|red pepper flakes|nutmeg|allspice|five spice|mixed spice|cayenne|"
     r"black pepper|white pepper|peppercorns|seasoning|za'?atar|sumac|cardamom|cloves? ground", 0.5),
)]


def _density(text: str) -> Optional[float]:
    for rx, value in _DENSITIES:
        if rx.search(text):
            return value
    return None


def _clean_text(text: str) -> str:
    s = " ".join(str(text or "").lower().split())
    for frac, ascii_frac in _UNICODE_FRACTIONS.items():
        s = re.sub(rf"(\d){frac}", rf"\1 {ascii_frac}", s)
        s = s.replace(frac, ascii_frac)
    for word, unit in _EXTRA_UNITS.items():
        s = re.sub(rf"(?<=\d)\s*{word}\b", f" {unit}", s)
        s = re.sub(rf"^(\S+\s+){word}\b", rf"\1{unit}", s)
    s = re.sub(r"^(\d+(?:\.\d+)?)(g|kg|ml|l|oz|lb)\b", r"\1 \2", s)  # "500g" -> "500 g"
    return s


def _tokens(text: str) -> List[str]:
    from utils import food_dataset

    return food_dataset.tokens(text)


def _piece_grams(name: str) -> Optional[float]:
    """Grams per item when the whole name is a known countable item ("1 red onion": yes,
    "2 cherry tomatoes": no - 'tomato' would weigh them as large tomatoes)."""
    from utils.food_db import PIECE_WEIGHTS_G

    words = {w for w in _tokens(name.split(",")[0]) if w not in _PIECE_NOISE}
    if not words:
        return None
    for key, grams in PIECE_WEIGHTS_G.items():
        if {w for w in _tokens(key) if w not in _PIECE_NOISE} == words:
            return grams
    return None


def _is_zero(entry: Dict[str, Any]) -> bool:
    return all(float(entry.get(k) or 0) == 0 for k in ("calories", "protein", "carbs", "fat"))


def _food_label(canonical: str, entry: Dict[str, Any]) -> str:
    label = " ".join(str(entry.get("description") or canonical or "").split())
    return (label[:1].upper() + label[1:])[:200]


def _strip_name(name: str) -> str:
    """Food words only: brackets and a trailing ', prep note' removed, leading 'of' dropped."""
    s = re.sub(r"\([^)]*\)", " ", name or "")
    s = re.sub(r"^\s*(?:of|x)\s+", "", " ".join(s.split()))
    return s.strip(" ,.;:-")


def _line_grams(qty: Optional[float], unit: str, name: str, paren_g: Optional[float]) -> Tuple[Optional[float], Optional[str]]:
    """(grams, reason-if-none)."""
    if qty is None or qty <= 0:
        return None, "no amount"
    if unit in _MASS_UNITS:
        return qty * _MASS_UNITS[unit], None
    if unit in _VOLUME_UNITS:
        density = _density(name)
        if density is None:
            return None, "no density"
        return qty * _VOLUME_UNITS[unit] * density, None
    first = (name.split() or [""])[0]
    if unit in _PIECE_UNITS:
        if unit.startswith("clove") and "garlic" not in name:
            return None, "clove of what"
        piece = _piece_grams(name if not unit.startswith("egg") else f"egg {name}")
        if piece is None:
            from utils.food_db import COUNT_UNIT_DEFAULT_G

            piece = COUNT_UNIT_DEFAULT_G.get(unit.rstrip("s")) if unit.rstrip("s") in ("fillet", "breast", "thigh") else None
        return (qty * piece, None) if piece else (None, "unknown piece")
    if unit or first in _CONTAINER_WORDS:
        if paren_g:
            # "1 can (400 g) chickpeas, drained": the label weight includes the liquid.
            drained = 0.6 if re.search(r"\b(drained|rinsed)\b", name) else 1.0
            return qty * paren_g * drained, None
        return None, "container"
    piece = _piece_grams(name)
    if piece is None:
        return None, "unknown piece"
    return qty * piece, None


@functools.lru_cache(maxsize=20000)
def _resolve_cached(text: str, region: str = "uk") -> Optional[Tuple[Tuple[str, Any], ...]]:
    out = resolve_line_from_db(text, region=region, _cache=False)
    return tuple(out.items()) if out else None


def resolve_line_from_db(text: str, *, region: str = "uk", _cache: bool = True) -> Optional[Badge]:
    """``{p, c, c_total, f, cal, src="db", food, g, source, source_id}`` for a line the food
    database can answer on its own (concrete amount + confident offline match), else ``None``
    (-> AI). ``c`` is available carbohydrate (UK basis), ``c_total`` includes fibre (US basis)."""
    from utils.food_db import find_food, normalize_region, parse_ingredient_amount

    region = normalize_region(region)
    if _cache:
        hit = _resolve_cached(" ".join(str(text or "").split()), region)
        return dict(hit) if hit else None

    s = _clean_text(text)
    if not s:
        return None
    paren = _PAREN_MASS_RE.search(s)
    paren_g = None
    if paren:
        n = float(paren.group(1))
        paren_g = n * (1000.0 if paren.group(2) == "kg" else 28.35 if paren.group(2) == "oz" else 1.0)
    parsed = parse_ingredient_amount(re.sub(r"\([^)]*\)", " ", s))
    qty = parsed.get("quantity")
    unit = (parsed.get("unit") or "").strip()
    name = _strip_name(parsed.get("name") or "")
    if not name:
        return None
    match = find_food(name, remote=False, region=region)
    if match is None:
        return None
    canonical, entry = match
    if entry.get("source") != "curated" and float(entry.get("match_score") or 0) < DATASET_MIN_SCORE:
        return None
    provenance = {"src": "db", "food": _food_label(canonical, entry),
                  "source": str(entry.get("source") or ""), "source_id": str(entry.get("source_id") or "")[:100]}

    if _is_zero(entry):
        # "salt to taste", "500 ml cold water": 0 whatever the amount - but not "salt and pepper".
        canon = set(_tokens(canonical))
        extra = [w for w in _tokens(re.sub(r"\([^)]*\)", " ", name)) if w not in canon and w not in _ZERO_NOISE]
        if extra:
            return None
        grams, _ = _line_grams(qty, unit, name, paren_g) if qty else (None, None)
        out = {"p": 0, "c": 0, "c_total": 0, "f": 0, "cal": 0, **provenance}
        if grams is not None:
            out["g"] = round(grams, 1)
            out["g_src"] = "db"
        return out

    if _VAGUE_RE.search(s) or qty is None:
        return None
    rest = s[len(re.match(r"^\s*(\d+/\d+|\d+\s+\d+/\d+|\d+\.?\d*)", s).group(0)):] if re.match(r"^\s*\d", s) else ""
    if _RANGE_RE.match(rest):
        return None
    density_text = f"{name} {canonical}"
    grams, _reason = _line_grams(float(qty), unit, density_text if unit in _VOLUME_UNITS else name, paren_g)
    if grams is None or grams <= 0 or grams > MAX_DB_GRAMS:
        return None
    scale = grams / 100.0
    values = {
        "p": int(round(float(entry.get("protein") or 0) * scale)),
        "c": int(round(float(entry.get("carbs") or 0) * scale)),
        "f": int(round(float(entry.get("fat") or 0) * scale)),
        "cal": int(round(float(entry.get("calories") or 0) * scale)),
    }
    if any(values[k] > hi or values[k] < 0 for k, hi in _CAPS.items()):
        return None  # beyond what a badge can show: leave it to the AI path (same caps)
    carbs_total = entry.get("carbs_total")
    if carbs_total is None:
        carbs_total = float(entry.get("carbs") or 0) + float(entry.get("fiber") or 0)
    values["c_total"] = min(int(round(float(carbs_total) * scale)), _CAPS["c"])
    return {**values, **provenance, "g": round(grams, 1), "g_src": "db"}


# --- cache -----------------------------------------------------------------------------------

_SELECT_COLS = "line_key, protein, carbs, carbs_total, fat, calories, method, food, grams, source, source_id"


class _DbStore:
    """``ingredient_line_macros`` table. Failures never break estimation (memory still works)."""

    async def get_many(self, keys: Sequence[str]) -> Dict[str, Badge]:
        if not keys:
            return {}
        from database.connection import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_SELECT_COLS} FROM ingredient_line_macros WHERE line_key = ANY($1::text[])",
                list(keys),
            )
        out: Dict[str, Badge] = {}
        for r in rows:
            badge: Badge = {"p": r["protein"], "c": r["carbs"], "f": r["fat"], "cal": r["calories"],
                            "src": "db" if r["method"] == "db" else "ai"}
            if r.get("carbs_total") is not None:
                badge["c_total"] = r["carbs_total"]
            if r["method"] == "db":
                badge.update({"food": r["food"], "g": r["grams"], "source": r["source"], "source_id": r["source_id"]})
            elif r["grams"] is not None:
                badge["g"] = r["grams"]  # AI-estimated grams
            out[r["line_key"]] = badge
        return out

    async def put_grams(self, values: Dict[str, Badge], model: str = "") -> None:
        """Add AI-estimated grams to cached AI rows that have none (macros untouched); a line with
        no row yet is inserted with the macros it was shown with."""
        if not values:
            return
        from database.connection import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO ingredient_line_macros "
                "(line_key, protein, carbs, fat, calories, model, method, grams) "
                "VALUES ($1, $2, $3, $4, $5, $6, 'ai', $7) "
                "ON CONFLICT (line_key) DO UPDATE SET grams = EXCLUDED.grams "
                "WHERE ingredient_line_macros.method <> 'db' AND ingredient_line_macros.grams IS NULL",
                [(k, int(v.get("p") or 0), int(v.get("c") or 0), int(v.get("f") or 0), int(v.get("cal") or 0),
                  (model or "")[:100], float(v["g"])) for k, v in values.items() if v.get("g") is not None],
            )

    async def put_many(self, values: Dict[str, Badge], model: str = "") -> None:
        """AI rows never overwrite an existing row unless it is a stale database row; database
        rows replace whatever is there (the food database beats an AI guess)."""
        if not values:
            return
        from database.connection import get_pool

        def row(k: str, v: Badge) -> tuple:
            db = v.get("src") == "db"
            g = v.get("g")
            c_total = v.get("c_total")
            return (k, v["p"], v["c"], v["f"], v["cal"], ("food_db" if db else (model or ""))[:100],
                    "db" if db else "ai", (v.get("food") or None) if db else None,
                    float(g) if g is not None else None,
                    (v.get("source") or None) if db else None, (v.get("source_id") or None) if db else None,
                    int(c_total) if c_total is not None else None)

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO ingredient_line_macros "
                "(line_key, protein, carbs, fat, calories, model, method, food, grams, source, source_id, carbs_total) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) "
                "ON CONFLICT (line_key) DO UPDATE SET protein = EXCLUDED.protein, carbs = EXCLUDED.carbs, "
                "carbs_total = EXCLUDED.carbs_total, "
                "fat = EXCLUDED.fat, calories = EXCLUDED.calories, model = EXCLUDED.model, "
                "method = EXCLUDED.method, food = EXCLUDED.food, grams = EXCLUDED.grams, "
                "source = EXCLUDED.source, source_id = EXCLUDED.source_id, created_at = CURRENT_TIMESTAMP "
                "WHERE EXCLUDED.method = 'db' OR ingredient_line_macros.method = 'db'",
                [row(k, v) for k, v in values.items()],
            )


_MEMORY: Dict[str, Badge] = {}
_MEMORY_MAX = 20000
_DB_SAVED: Dict[str, Badge] = {}  # database results already written to the cache table
store: Any = _DbStore()


def _remember(values: Dict[str, Badge]) -> None:
    if len(_MEMORY) + len(values) > _MEMORY_MAX:
        _MEMORY.clear()
    _MEMORY.update(values)


async def cached_line_macros(keys: Iterable[str]) -> Dict[str, Badge]:
    """Cached estimates for normalised keys (memory first, then the DB)."""
    keys = [k for k in dict.fromkeys(keys) if k]
    found = {k: dict(_MEMORY[k]) for k in keys if k in _MEMORY}
    missing = [k for k in keys if k not in found]
    if missing:
        try:
            from_db = await store.get_many(missing)
        except Exception as e:  # DB down / table missing: estimate anyway
            logger.warning("Line macro cache read failed: %s", e)
            from_db = {}
        from_db = {k: clean_badge(v) for k, v in from_db.items()}
        _remember(from_db)
        found.update(from_db)
    return found


async def _save(values: Dict[str, Badge], model: str) -> None:
    _remember(values)
    try:
        await store.put_many(values, model)
    except Exception as e:
        logger.warning("Line macro cache write failed: %s", e)


async def _save_db_results(values: Dict[str, Badge]) -> None:
    """Record database answers (with provenance) in the cache table once per process, replacing
    any AI row for the same line."""
    fresh = {k: v for k, v in values.items() if _DB_SAVED.get(k) != v}
    if not fresh:
        return
    if len(_DB_SAVED) + len(fresh) > _MEMORY_MAX:
        _DB_SAVED.clear()
    try:
        await store.put_many(fresh, "food_db")
        _DB_SAVED.update(fresh)
    except Exception as e:
        logger.warning("Line macro cache write (food db) failed: %s", e)


# --- AI --------------------------------------------------------------------------------------

def _model_override() -> Optional[str]:
    from config import settings

    return LINE_MACROS_MODEL if settings.is_cloud else None


async def _ask_ai(client, lines: Sequence[str]) -> List[Optional[Badge]]:
    """One AI call for up to BATCH_SIZE lines; None per line when the reply is unusable."""
    from dependencies import call_llm

    raw = await call_llm(
        client,
        SYSTEM_PROMPT,
        build_user_prompt(lines),
        None,
        format_json=True,
        max_tokens=4000,
        ollama_model_override=_model_override(),
    )
    match = re.search(r"\{.*\}", raw or "", re.S)
    data = json.loads(match.group(0) if match else raw)
    if isinstance(data, dict):
        items = data.get("items") or data.get("macros")
        if items is None and "cal" in data:
            items = [data]
    else:
        items = data
    if not isinstance(items, list) or len(items) != len(lines):
        # Misaligned answers would put pasta's calories on the salt: refuse the batch.
        raise ValueError(f"AI returned {len(items) if isinstance(items, list) else 0} items for {len(lines)} lines")
    return [clean_badge({**{k: it.get(k) for k in MACRO_KEYS}, "g": it.get("g")}) if isinstance(it, dict) else None
            for it in items]


async def _ask_ai_grams(client, lines: Sequence[str]) -> List[Optional[float]]:
    """One AI call: grams per line (as used) for lines whose macros are already known."""
    from dependencies import call_llm

    raw = await call_llm(
        client,
        SYSTEM_PROMPT,
        build_grams_prompt(lines),
        None,
        format_json=True,
        max_tokens=2000,
        ollama_model_override=_model_override(),
    )
    match = re.search(r"\{.*\}", raw or "", re.S)
    data = json.loads(match.group(0) if match else raw)
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list) or len(items) != len(lines):
        raise ValueError(f"AI returned {len(items) if isinstance(items, list) else 0} weights for {len(lines)} lines")
    return [clean_grams(it.get("g")) if isinstance(it, dict) else clean_grams(it) for it in items]


async def fill_grams(items: Sequence[Tuple[str, str, Badge]], *, client=None, allow_ai: bool = True) -> Dict[str, float]:
    """Grams for lines whose macros are known but whose weight is not (AI badges saved before
    the prompt asked for grams). ``items``: (normalised key, line text, badge). Cached grams
    first; the rest from the AI (weights only, so the macros never change), batched and cached."""
    todo = {k: (t, b) for k, t, b in items if k and b.get("g") is None}
    if not todo:
        return {}
    out: Dict[str, float] = {}
    cached = await cached_line_macros(list(todo))
    for k, badge in cached.items():
        if badge.get("src") != "db" and badge.get("g") is not None:
            out[k] = badge["g"]
    rest = [(k, todo[k]) for k in todo if k not in out]
    if not rest or not allow_ai:
        return out
    import httpx

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=120)
    try:
        sem = asyncio.Semaphore(PARALLEL_CALLS)

        async def run(batch) -> None:
            async with sem:
                try:
                    grams = await _ask_ai_grams(client, [text for _, (text, _) in batch])
                except Exception as e:
                    logger.warning("Line grams estimate failed for %s line(s): %s", len(batch), e)
                    return
            got: Dict[str, Badge] = {}
            for (key, (_, badge)), g in zip(batch, grams):
                if g is None:
                    continue
                out[key] = g
                got[key] = {**macros_of(badge), "src": "ai", "g": g, "g_src": "ai"}
            if got:
                for key, badge in got.items():
                    # Same rule as put_grams: weight added to the cached AI row, else this row.
                    old = _MEMORY.get(key)
                    if old is None:
                        _remember({key: badge})
                    elif old.get("src") != "db" and old.get("g") is None:
                        _MEMORY[key] = {**old, "g": badge["g"], "g_src": "ai"}
                put = getattr(store, "put_grams", None)
                if put is not None:
                    try:
                        await put(got, _model_override() or "")
                    except Exception as e:
                        logger.warning("Line grams cache write failed: %s", e)

        await asyncio.gather(*(run(rest[s:s + BATCH_SIZE]) for s in range(0, len(rest), BATCH_SIZE)))
    finally:
        if own_client:
            await client.aclose()
    return out


async def estimate_line_macros(
    lines: Sequence[Any],
    *,
    client=None,
    allow_ai: bool = True,
    fill_weights: bool = False,
    region: str = "uk",
) -> List[Optional[Badge]]:
    """``[{p, c, f, cal, src, ...}]`` per line (index-aligned), ``None`` where no estimate is
    available. Database answers first, then the cache (AI rows), then the AI.

    ``lines``: ingredient dicts or 'amount unit name' strings. ``allow_ai=False`` answers
    from the database / cache only (used on save so the request never waits on the AI).
    ``fill_weights``: also estimate grams for cached AI lines that have none (per-100 g).
    ``region``: "uk" (default) or "us" food lookups; only UK database answers are cached.
    """
    from utils.food_db import DEFAULT_REGION, normalize_region

    region = normalize_region(region)
    texts = [ingredient_line(x) for x in lines]
    keys = [normalize_line(t) for t in texts]
    known: Dict[str, Badge] = {}
    if DB_FIRST:
        for key, text in zip(keys, texts):
            if key and key not in known:
                hit = resolve_line_from_db(text, region=region)
                if hit is not None:
                    known[key] = hit
        if known and region == DEFAULT_REGION:  # the cache table is keyed by line text only
            await _save_db_results(dict(known))
    rest = [k for k in keys if k and k not in known]
    if rest:
        cached = await cached_line_macros(rest)
        # A cached database row the food database no longer answers is stale: ask again.
        known.update({k: v for k, v in cached.items() if v.get("src") != "db"})
    todo: Dict[str, str] = {}
    for key, text in zip(keys, texts):
        if key and key not in known and key not in todo:
            todo[key] = text
    if todo and allow_ai:
        fresh = await _estimate_missing(list(todo.items()), client)
        known.update(fresh)
    if fill_weights:
        texts_by_key = dict(zip(keys, texts))
        grams = await fill_grams(
            [(k, texts_by_key[k], b) for k, b in known.items() if b.get("src") != "db" and b.get("g") is None],
            client=client, allow_ai=allow_ai,
        )
        for k, g in grams.items():
            known[k] = {**known[k], "g": g, "g_src": "ai"}
    return [dict(known[k]) if k in known else ({"p": 0, "c": 0, "f": 0, "cal": 0} if not k else None) for k in keys]


async def _estimate_missing(todo: List[tuple], client) -> Dict[str, Badge]:
    import httpx

    out: Dict[str, Badge] = {}
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=120)
    try:
        async def run(batch: List[tuple], retry_split: bool) -> None:
            try:
                answers = await _ask_ai(client, [text for _, text in batch])
            except Exception as e:
                if retry_split and len(batch) > 1:  # e.g. a miscounted reply: try each half once
                    mid = len(batch) // 2
                    await run(batch[:mid], False)
                    await run(batch[mid:], False)
                    return
                logger.warning("Line macro estimate failed for %s line(s): %s", len(batch), e)
                return
            got = {key: badge for (key, _), badge in zip(batch, answers) if badge is not None}
            if got:
                await _save(got, _model_override() or "")
                out.update(got)

        sem = asyncio.Semaphore(PARALLEL_CALLS)

        async def limited(batch: List[tuple]) -> None:
            async with sem:
                await run(batch, True)

        await asyncio.gather(*(limited(todo[s:s + BATCH_SIZE]) for s in range(0, len(todo), BATCH_SIZE)))
    finally:
        if own_client:
            await client.aclose()
    return out
