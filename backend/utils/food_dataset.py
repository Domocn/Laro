"""Full food-composition dataset (UK CoFID 2021 + USDA FoodData Central) for lookups.

The data lives in ``backend/data/foods/foods.json.gz`` (built by
``scripts/build_food_db.py``; see ``data/foods/NOTICE.md`` for sources and licences).
It is loaded once, lazily, into memory with a token index - no network, no database.

``search(text)`` returns the best ``Match`` for an ingredient phrase, or ``None``
when nothing is a confident match. It is deliberately conservative: a wrong food is
worse than no food, because callers fall back to other lookups.

Values are per 100 g edible portion. ``carbs`` is available carbohydrate (fibre
excluded) for every source; entries also carry ``carbs_total`` (available + fibre, the US
"total carbohydrate" basis).
"""
from __future__ import annotations

import gzip
import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "foods", "foods.json.gz")

# Minimum score for a match to be returned at all.
MIN_SCORE = 0.7

_NUMERIC = ("calories", "protein", "carbs", "fat", "fiber", "sugars", "saturates", "salt")

# ---------------------------------------------------------------------------
# Tokenising
# ---------------------------------------------------------------------------


def _singular(w: str) -> str:
    if len(w) > 4 and w.endswith("ves") and w not in ("chives", "olives"):
        return w[:-3] + "f"  # leaves -> leaf, halves -> half
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]  # potatoes, tomatoes
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"  # berries
    if len(w) > 4 and re.search(r"(ch|sh|x)es$", w):
        return w[:-2]  # peaches, radishes, boxes
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def tokens(text: str) -> List[str]:
    return [_singular(w) for w in re.findall(r"[a-z]+", _fold(text))]


# ---------------------------------------------------------------------------
# Query side vocabulary
# ---------------------------------------------------------------------------

# Words in a recipe line that carry no food identity.
_QUERY_NOISE = frozenset(tokens(
    "a an the of and to for with plus about approx approximately "
    "fresh freshly large small medium big little mini heaped level "
    "chopped diced finely roughly coarsely thinly thickly sliced minced crushed grated "
    "shredded peeled deseeded seeded trimmed halved quartered cubed julienned torn "
    "rinsed washed drained soaked melted softened beaten whisked sifted packed "
    "cooked uncooked raw tin tinned can canned jar jarred frozen defrosted thawed "
    "organic ripe good quality optional serve serving garnish boneless skinless "
    "handful pinch dash splash drizzle knob bunch sprig sprigs stick sticks "
    "piece pieces chunk chunks slice slices wedge wedges strip strips cube cubes "
    "floret florets fillet fillets nest nests sheet sheets bag pack packet punnet pod pods rings balls fingers "
    "g kg mg ml l litre liter tbsp tsp tablespoon teaspoon cup cups oz lb "
    "room temperature cold hot warm boiling"
))

# Physical-state words in the query: kept out of the identity tokens but steer state.
_QUERY_STATE_WORDS = {
    "dried": "dried", "dry": "dried", "smoked": "smoked", "roasted": "roasted",
    "toasted": "toasted", "fried": "fried", "baked": "baked", "grilled": "grilled",
    "steamed": "steamed", "boiled": "boiled", "salted": "salted",
}

# Query token -> acceptable dataset tokens (UK/US naming).
_SYNONYMS: Dict[str, FrozenSet[str]] = {}
for _group in (
    "courgette zucchini", "aubergine eggplant", "coriander cilantro", "cornflour cornstarch",
    "chickpea garbanzo", "prawn shrimp", "mince ground", "rocket arugula", "beetroot beet",
    "swede rutabaga", "yoghurt yogurt", "chilli chili chile", "icing powdered",
    "wholemeal whole", "mangetout mange", "sultana raisin", "rapeseed canola", "dried dry",
):
    _ws = [_singular(w) for w in _group.split()]
    for _w in _ws:
        _SYNONYMS[_w] = frozenset(_ws)
_SYNONYMS["bell"] = frozenset({"bell", "sweet", "capsicum"})
_SYNONYMS["capsicum"] = frozenset({"capsicum", "sweet", "bell"})
_SYNONYMS["plain"] = frozenset({"plain", "purpose"})  # plain flour = all-purpose
_SYNONYMS["caster"] = _SYNONYMS["granulated"] = frozenset({"caster", "granulated", "white"})
# Pasta shapes share dried-pasta values ("Pasta, dry").
for _w in tokens("spaghetti penne fusilli linguine tagliatelle macaroni rigatoni farfalle orzo fettuccine conchiglie"):
    _SYNONYMS[_w] = frozenset({_w, "pasta"})

# Modifiers that change the food entirely: never dropped to force a match
# ("nutritional yeast" is not baker's yeast, "dairy-free feta" is not feta).
_UNDROPPABLE = frozenset(tokens("nutritional dairy vegan plant free gluten coconut almond oat soy soya rice"))

# Words that only say what *kind* of thing it is. Never enough on their own once the
# recipe's distinguishing word has been dropped.
_GENERIC = frozenset(tokens(
    "fruit fruits vegetable vegetables oil sauce powder paste flour seed seeds nut nuts juice milk "
    "cheese stock meat leaf leaves bean beans syrup spice spices herb herbs extract sugar cream "
    "yogurt yoghurt butter drink mix noodles pasta bread cake biscuit roll green red white black "
    "brown yellow sweet hot ground whole fish berry berries mince mixed assorted"
))

# Whole-phrase rewrites applied before tokenising.
_PHRASES = [
    (r"\bfree[- ]range\b|\bfirm[- ]ripe\b", " "),
    (r"\bgarlic cloves?\b|\bcloves? (of )?garlic\b", "garlic"),
    (r"\bscallions?\b|\bgreen onions?\b", "spring onions"),
    (r"\ball[- ]purpose flour\b", "plain flour"),
    (r"\bground almonds?\b|\balmond meal\b", "almonds ground"),
    (r"\bextra[- ]virgin\b", "extra virgin"),
    (r"\bbicarbonate of soda\b|\bbicarb\b", "baking soda"),
    (r"\bdouble cream\b", "cream double"),
    (r"\bsingle cream\b", "cream single"),
    (r"\bself[- ]raising\b|\bself[- ]rising\b", "self raising"),
]
_PHRASE_RES = [(re.compile(rx, re.I), rep) for rx, rep in _PHRASES]

# ---------------------------------------------------------------------------
# Description side vocabulary
# ---------------------------------------------------------------------------

# Extra description words that don't change what the food is.
_DESC_NEUTRAL = frozenset(tokens(
    "raw fresh uncooked whole average all type types variety varieties flesh only edible "
    "portion meat mature seeds commercial unprepared unenriched enriched regular plain "
    "unsalted unsweetened natural include includes including with without and or in of "
    "from not skin peel peeled kernel kernels nfs ns as to solid solids drained frozen dry "
    "dried retail uk imported ripe year round bulb bulbs top tops untrimmed trimmed "
    "standard fortified unfortified pasteurised pasteurized homogenised salad cooking grade "
    "fluid loose prepacked pre packed form product products tap edible style prepared "
    "calcium sulfate sulphate magnesium chloride nigari boneless skinless commercially"
))

# Description words that mean a processed / different product.
_DESC_BAD = frozenset(tokens(
    "fried breaded breadcrumbs batter battered coated crumbed sweetened syrup sauce smoked "
    "pickled flavoured flavored dressing stuffed baby babyfood infant toddler imitation "
    "homemade takeaway recipe mix dessert candied glazed creamed candies beverage "
    "sandwich soup pie spread weighed shells stones stone pips burger nuggets "
    "salted filled fondant centres topping concentrate meatless home franks frankfurters snack bar "
    "drink substitute analogue meal ready instant pita"
))

# Food-class prefixes in descriptions ("Spices, cinnamon", "Cheese, Feta", "Nuts, cashew").
_CATEGORY_HEADS = frozenset(tokens("spices spice nuts herbs seeds cheese fish beverages oil"))

# The usual default variety: barely a difference when the recipe doesn't say.
_DESC_DEFAULTISH = frozenset(tokens("white standard old common button cultivated porridge rolled yellow medium whole long grain rashers back"))

_DESC_DIET = frozenset(tokens("reduced low lite light skimmed skim fat-free free diet lean protein"))

# Description words already scored through the parsed ``state``.
_STATE_TOKENS = frozenset(tokens("dried dry roasted roast toasted fried baked grilled steamed boiled cooked canned"))

_COOKED_STATES = frozenset({"boiled", "steamed", "cooked", "fried", "roasted", "grilled", "baked", "toasted"})


@dataclass(frozen=True)
class Match:
    description: str
    source: str
    source_id: str
    state: str
    category: str
    score: float
    values: Dict[str, Optional[float]]

    def entry(self) -> Dict[str, object]:
        """Shape compatible with curated FOOD_DATABASE entries."""
        out: Dict[str, object] = {k: (self.values.get(k) or 0) for k in _NUMERIC}
        out["carbs_total"] = round(float(out["carbs"] or 0) + float(out["fiber"] or 0), 1)
        out.update({
            "tags": [],
            "category": self.category or "other",
            "source": self.source,
            "source_id": self.source_id,
            "description": self.description,
            "state": self.state or "as_sold",  # no state word in the description: as sold
            "match_score": round(self.score, 3),
        })
        return out


class _Dataset:
    def __init__(self, path: str) -> None:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        cols = payload["columns"]
        ix = {c: i for i, c in enumerate(cols)}
        self.sources = payload.get("sources", {})
        self.rows: List[list] = payload["rows"]
        self.ix = ix
        self.tok: List[FrozenSet[str]] = []
        self.first: List[FrozenSet[str]] = []
        self.ntok: List[int] = []
        self.part_adjust: List[float] = []
        index: Dict[str, List[int]] = {}
        heads: set = set()
        di = ix["description"]
        for i, row in enumerate(self.rows):
            desc = row[di]
            toks = frozenset(tokens(desc))
            self.tok.append(toks)
            first = tokens(re.split(r"[,(]", desc, 1)[0])
            self.first.append(frozenset(first))
            if len(first) == 1:
                heads.add(first[0])
            self.ntok.append(len(toks))
            # "Potatoes, raw, skin" / "Bacon, fat only" is one part of the food, not the food.
            part_only = re.search(r",\s*(skins?|fat|rind|bones?)(\s+only)?\s*(,|$)", desc, re.I)
            with_skin = re.search(r"\b(meat and skin|with skin)\b", desc, re.I)
            self.part_adjust.append(-0.3 if part_only else (-0.05 if with_skin else 0.0))
            for t in toks:
                index.setdefault(t, []).append(i)
        self.index = {t: frozenset(v) for t, v in index.items()}
        # Words that name a food on their own ("Bacon", "Turkey", "Yogurt"): as an extra
        # word in a description they usually mean a different food.
        self.head_nouns = frozenset(heads - _DESC_NEUTRAL - _CATEGORY_HEADS - _DESC_DEFAULTISH)

    def value(self, i: int, col: str):
        return self.rows[i][self.ix[col]]


_LOCK = threading.Lock()
_DATA: Optional[_Dataset] = None
_LOAD_FAILED = False


def load() -> Optional[_Dataset]:
    """Load (once) and return the dataset; None if the artefact is missing/corrupt."""
    global _DATA, _LOAD_FAILED
    if _DATA is not None or _LOAD_FAILED:
        return _DATA
    with _LOCK:
        if _DATA is None and not _LOAD_FAILED:
            try:
                _DATA = _Dataset(DATA_PATH)
            except Exception:
                import logging

                logging.getLogger(__name__).exception("food dataset failed to load from %s", DATA_PATH)
                _LOAD_FAILED = True
    return _DATA


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _query_parts(text: str) -> Tuple[List[str], set]:
    """Identity tokens (in order) + state words from an ingredient phrase."""
    s = _fold(text)
    states = set()
    if re.search(r"\b(canned|tinned|tins?|cans?)\b", s):
        states.add("canned")
    s = re.sub(r"\([^)]*\)", " ", s)  # "(tin, drained)"
    s = re.split(r"\s+or\s+|\s*/\s*", s)[0]  # first choice of "x or y"
    s = s.split(",")[0]  # "garlic, crushed"
    s = re.sub(r"\b\d+([./]\d+)?\s*%?", " ", s)
    for rx, rep in _PHRASE_RES:
        s = rx.sub(rep, s)
    ident: List[str] = []
    for w in re.findall(r"[a-z]+", s):
        if w in _QUERY_STATE_WORDS:
            # Steers the state *and* stays an identity word: "baked beans", "smoked salmon".
            states.add(_QUERY_STATE_WORDS[w])
        t = _singular(w)
        if t in _QUERY_NOISE or len(t) < 2:
            continue
        if t not in ident:
            ident.append(t)
    return ident, states


_DRY_GOODS = frozenset({"grain", "legume", "nuts", "seasoning"})


def _state_adjust(state: str, want_cooked: bool, q_states: set, category: str = "") -> float:
    if state and state in q_states:
        return 0.1
    if want_cooked:
        if state == "fried":
            return -0.05  # cooked, but with added fat the line didn't ask for
        if state in _COOKED_STATES or state == "canned":
            return 0.1
        if state == "raw":
            return -0.15
        if state == "dried":
            return -0.25
        return 0.0
    if "dried" in q_states:
        return -0.2 if state in ("raw", "") else (-0.3 if state in _COOKED_STATES else 0.0)
    if state == "raw":
        return 0.08
    if state == "":
        return 0.03
    if state == "dried" and category in _DRY_GOODS:
        return 0.05  # dry pasta / pulses / spices: dried is how they're sold and weighed
    if state in ("dried", "frozen"):
        return -0.05
    if state == "canned":
        return -0.12
    return -0.3  # cooked / fried / roasted ... when the line is raw


def _score_row(
    ds: _Dataset, i: int, kept: Sequence[str], want_cooked: bool, q_states: set, base: float, generic_only: bool = False
) -> float:
    toks = ds.tok[i]
    alts = set()
    for t in kept:
        alts |= _SYNONYMS.get(t, frozenset((t,)))
    score = base
    head = ds.first[i]
    for t in toks - alts:
        if t in _DESC_NEUTRAL or t in _STATE_TOKENS or _QUERY_STATE_WORDS.get(t) in q_states:
            continue
        if t in _DESC_BAD:
            score -= 0.25
        elif t in _DESC_DIET:
            score -= 0.12
        elif t in _DESC_DEFAULTISH:
            score -= 0.02
        elif t in head:
            # Extra word in the food's own name: "Tofu yogurt", "Sweet potato", "Oat bran".
            score -= 0 if t in _CATEGORY_HEADS else 0.15
        elif t in ds.head_nouns:
            score -= 0.15  # names another food: "Bacon, turkey"
        elif len(t) <= 2:
            continue
        else:
            score -= 0.05
    score += ds.part_adjust[i]
    state = ds.value(i, "state") or ""
    if "canned" in q_states:
        score += 0.15 if state == "canned" else 0.0
    first = head - _DESC_NEUTRAL - _CATEGORY_HEADS - _DESC_DEFAULTISH
    if generic_only and not (first and first <= alts):
        return -1.0  # "whites" must not become "Cheese, white": a bare generic word needs an exact head
    if first and not (first & alts):
        score -= 0.2  # "Soup, tomato" / "Sandwich, chicken": the food isn't the head
    elif first and first <= alts:
        score += 0.05
    score += _state_adjust(state, want_cooked, q_states, ds.value(i, "category") or "")
    if ds.value(i, "source") == "cofid":
        score += 0.03
    return score


def _candidates(ds: _Dataset, kept: Sequence[str]) -> FrozenSet[int]:
    result: Optional[FrozenSet[int]] = None
    for t in kept:
        posting: FrozenSet[int] = frozenset()
        for alt in _SYNONYMS.get(t, frozenset((t,))):
            posting = posting | ds.index.get(alt, frozenset())
        result = posting if result is None else (result & posting)
        if not result:
            return frozenset()
    return result or frozenset()


USDA_SOURCES = frozenset({"usda_foundation", "usda_sr"})
COFID_SOURCES = frozenset({"cofid"})


def search(
    text: str, *, cooked: bool = False, min_score: float = MIN_SCORE, sources: Optional[FrozenSet[str]] = None
) -> Optional[Match]:
    """Best dataset match for an ingredient phrase, or None if not confident.

    ``sources`` limits the rows considered (e.g. ``USDA_SOURCES`` for US-style values)."""
    ds = load()
    if ds is None:
        return None
    ident, q_states = _query_parts(text)
    ident = ident[:8]  # bound the drop combinations for pathological input
    if not ident:
        return None

    def known(t: str) -> bool:
        return any(a in ds.index for a in _SYNONYMS.get(t, frozenset((t,))))

    unknown = [t for t in ident if not known(t)]
    words = [t for t in ident if known(t)]
    if not words or len(unknown) > len(words) or any(t in _UNDROPPABLE for t in unknown):
        return None
    base0 = 1.0 - 0.1 * len(unknown)

    best: Optional[Tuple[float, int, int]] = None  # (score, -ntok, row)
    max_drop = min(2, len(words) - 1)
    for drop in range(max_drop + 1):
        found_any = False
        for dropped in _combinations(len(words), drop):
            if any(words[k] in _UNDROPPABLE for k in dropped):
                continue
            kept = [w for k, w in enumerate(words) if k not in dropped]
            if all(w in _GENERIC for w in kept) and (dropped or unknown):
                continue  # "dragon fruit" -> any "fruit" is a guess, not a match
            cands = _candidates(ds, kept)
            if not cands:
                continue
            found_any = True  # (with ``sources`` set, possibly only rows of other sources)
            # Dropping the last word (usually the head noun) is a much bigger guess.
            base = base0 - 0.2 * drop - (0.3 if (len(words) - 1) in dropped else 0.0)
            generic_only = all(w in _GENERIC for w in kept)
            for i in cands:
                if sources is not None and ds.value(i, "source") not in sources:
                    continue
                s = _score_row(ds, i, kept, cooked, q_states, base, generic_only)
                key = (s, -ds.ntok[i], -i)
                if best is None or key > best:
                    best = key
        # Fewer drops always beat more drops when they found something decent.
        if found_any and best is not None and best[0] >= min_score:
            break
    if best is None or best[0] < min_score:
        return None
    i = -best[2]
    row = ds.rows[i]
    ix = ds.ix
    return Match(
        description=row[ix["description"]],
        source=row[ix["source"]],
        source_id=str(row[ix["source_id"]]),
        state=row[ix["state"]] or "",
        category=row[ix["category"]] or "",
        score=best[0],
        values={k: row[ix[k]] for k in _NUMERIC},
    )


def _combinations(n: int, k: int) -> List[FrozenSet[int]]:
    return [frozenset(c) for c in combinations(range(n), k)]
