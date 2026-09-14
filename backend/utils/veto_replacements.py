"""
Detect recipe ingredients that hit adult/kid veto lists and suggest replacements.

Matching reuses food_db normalization + fuzzy/substring veto logic.
Suggestions prefer a curated swap map, then same-category food_db entries.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from utils.food_db import (
    FOOD_DATABASE,
    _dietary_flags,
    _normalize_name,
    _passes_diet_filters,
    _veto_match,
    find_food,
)
from utils.preference_context import adult_veto_ingredients, kid_veto_ingredients

IngredientLike = Union[str, Dict[str, Any]]

# Curated preference swaps (normalized key → list of (replacement, reason))
# Keys are matched with the same fuzzy logic as veto tokens.
CURATED_SWAPS: Dict[str, List[Tuple[str, str]]] = {
    "mushroom": [
        ("zucchini", "Similar bite and absorbs sauce well"),
        ("eggplant", "Meaty texture for sautés and stews"),
        ("bell pepper", "Mild vegetable with good colour"),
    ],
    "cilantro": [
        ("parsley", "Fresh herb without the soapy note"),
        ("basil", "Bright aromatic for many cuisines"),
        ("mint", "Cool herb for salads and sauces"),
    ],
    "coriander": [
        ("parsley", "Fresh herb swap for leaves"),
        ("cumin", "Warm spice when seeds are the issue"),
    ],
    "olive": [
        ("capers", "Briny punch in smaller amounts"),
        ("sun-dried tomato", "Savoury Mediterranean note"),
        ("pickle", "Tangy bite for salads and toppings"),
    ],
    "anchovy": [
        ("soy sauce", "Umami depth without fish"),
        ("miso", "Savoury paste for dressings and sauces"),
        ("worcestershire sauce", "Classic umami substitute (check diet)"),
    ],
    "liver": [
        ("chicken breast", "Mild lean protein"),
        ("lean beef mince", "Hearty red-meat swap"),
        ("turkey breast", "Lean poultry alternative"),
    ],
    "blue cheese": [
        ("feta", "Tangy crumbly cheese"),
        ("goat cheese", "Creamy tang without blue mould"),
        ("parmesan", "Salty hard cheese for finishing"),
    ],
    "broccoli": [
        ("green beans", "Mild green vegetable kids often accept"),
        ("zucchini", "Soft texture when cooked"),
        ("carrot", "Familiar sweet vegetable"),
    ],
    "pea": [
        ("green beans", "Crunchy green alternative"),
        ("corn", "Sweet vegetable many kids prefer"),
        ("edamame", "Protein-rich green swap if soy is OK"),
    ],
    "onion": [
        ("shallot", "Milder allium flavour"),
        ("leek", "Gentle onion-like base"),
        ("celery", "Aromatic base without onion"),
    ],
    "garlic": [
        ("ginger", "Warm aromatic for stir-fries"),
        ("asafoetida", "Onion/garlic-like note in tiny amounts"),
        ("chive", "Mild allium finish"),
    ],
    "mayonnaise": [
        ("greek yogurt", "Tangy creamy binder"),
        ("avocado", "Rich spread for sandwiches"),
        ("hummus", "Savoury plant-based spread"),
    ],
    "mustard": [
        ("yogurt", "Mild creamy binder"),
        ("horseradish", "Sharp kick when appropriate"),
    ],
    "eggplant": [
        ("zucchini", "Similar cook methods"),
        ("portobello mushroom", "Meaty vegetable steaks"),
        ("bell pepper", "Roast-friendly swap"),
    ],
    "aubergine": [
        ("zucchini", "Similar cook methods"),
        ("bell pepper", "Roast-friendly swap"),
    ],
    "spinach": [
        ("kale", "Hearty leafy green"),
        ("swiss chard", "Mild leafy alternative"),
        ("lettuce", "Fresh green for cold dishes"),
    ],
    "tomato": [
        ("red bell pepper", "Sweet red vegetable"),
        ("carrot", "Sweet base for sauces when blended"),
    ],
    "pork": [
        ("chicken thigh", "Juicy poultry alternative"),
        ("turkey breast", "Leaner poultry swap"),
        ("tofu", "Plant protein if diet allows"),
    ],
    "butter": [
        ("olive oil", "Savoury cooking fat"),
        ("coconut oil", "Plant fat for baking and frying"),
        ("ghee", "Butter-like flavour, often lactose-light"),
    ],
    "milk": [
        ("oat milk", "Neutral plant milk for cooking"),
        ("almond milk", "Light dairy-free option"),
        ("soy milk", "Higher-protein plant milk"),
    ],
    "egg": [
        ("flax egg", "1 tbsp ground flax + 3 tbsp water for baking"),
        ("chia egg", "1 tbsp chia + 3 tbsp water as binder"),
        ("aquafaba", "Whipped chickpea liquid for light bakes"),
    ],
    "eggs": [
        ("flax egg", "1 tbsp ground flax + 3 tbsp water for baking"),
        ("chia egg", "1 tbsp chia + 3 tbsp water as binder"),
        ("aquafaba", "Whipped chickpea liquid for light bakes"),
    ],
    "flour": [
        ("almond flour", "Lower-carb baking swap"),
        ("oat flour", "Whole-grain alternative"),
        ("gluten-free flour blend", "1:1 style GF bake mix"),
    ],
    "sugar": [
        ("honey", "Natural sweetener (use a little less)"),
        ("maple syrup", "Liquid sweetener for baking and sauces"),
        ("coconut sugar", "Less refined granular sweetener"),
    ],
    "cream": [
        ("coconut cream", "Rich dairy-free alternative"),
        ("greek yogurt", "Tangy lighter swap when thinned"),
        ("cashew cream", "Blend soaked cashews with water"),
    ],
    "cheese": [
        ("nutritional yeast", "Cheesy plant-based flavour"),
        ("feta", "Tangy crumbly cheese"),
        ("cottage cheese", "Mild high-protein swap"),
    ],
    "shrimp": [
        ("chicken breast", "Mild protein swap"),
        ("firm tofu", "Plant protein with similar cube shape"),
        ("chickpeas", "Hearty plant protein"),
    ],
    "prawn": [
        ("chicken breast", "Mild protein swap"),
        ("firm tofu", "Plant protein alternative"),
    ],
    "fish": [
        ("chicken breast", "Mild lean protein"),
        ("tofu", "Plant protein alternative"),
        ("chickpeas", "Hearty plant protein"),
    ],
    "coconut": [
        ("almond milk", "Neutral dairy-free liquid"),
        ("oat milk", "Creamy dairy-free liquid"),
        ("olive oil", "Cooking fat without coconut flavour"),
    ],
    # Baking / bowl binders & natural sweeteners — match by cooking function
    "banana": [
        ("applesauce", "Same moisture + mild sweetness for baking and bowls"),
        ("pumpkin puree", "Soft binder with gentle flavour"),
        ("greek yogurt", "Creamy binder with more protein"),
    ],
    "mashed banana": [
        ("applesauce", "Classic 1:1 mash swap for moisture and bind"),
        ("pumpkin puree", "Soft puree binder for bowls and bakes"),
        ("sweet potato puree", "Naturally sweet mash alternative"),
    ],
    "applesauce": [
        ("mashed banana", "Same moisture and bind in baking"),
        ("pumpkin puree", "Soft fruit/veg puree swap"),
        ("greek yogurt", "Creamy binder when fruit is not needed"),
    ],
}


# Cooking-function roles → swaps. Used when an ingredient's job matters more
# than its grocery category (e.g. mashed banana is a binder, not "any fruit").
INGREDIENT_ROLES: Dict[str, List[str]] = {
    "banana": ["binder", "sweetener", "moisture"],
    "mashed banana": ["binder", "sweetener", "moisture"],
    "applesauce": ["binder", "sweetener", "moisture"],
    "apple sauce": ["binder", "sweetener", "moisture"],
    "pumpkin puree": ["binder", "moisture"],
    "sweet potato puree": ["binder", "sweetener", "moisture"],
    "greek yogurt": ["binder", "moisture", "dairy"],
    "yogurt": ["binder", "moisture", "dairy"],
    "egg": ["binder", "leavening"],
    "eggs": ["binder", "leavening"],
    "flax egg": ["binder"],
    "chia egg": ["binder"],
    "oil": ["fat"],
    "olive oil": ["fat"],
    "butter": ["fat"],
    "sugar": ["sweetener"],
    "honey": ["sweetener"],
    "maple syrup": ["sweetener"],
}

ROLE_SWAPS: Dict[str, List[Tuple[str, str]]] = {
    "binder": [
        ("applesauce", "Provides moisture and bind like mashed fruit"),
        ("mashed banana", "Classic bake/bowl binder"),
        ("pumpkin puree", "Soft puree that holds mixtures together"),
        ("greek yogurt", "Creamy binder with protein"),
        ("flax egg", "Plant binder for baking (1 tbsp flax + 3 tbsp water)"),
    ],
    "moisture": [
        ("applesauce", "Adds moisture without changing structure much"),
        ("pumpkin puree", "Moist puree for bowls and bakes"),
        ("greek yogurt", "Adds moisture and body"),
    ],
    "sweetener": [
        ("honey", "Natural liquid sweetener"),
        ("maple syrup", "Liquid sweetener for bowls and baking"),
        ("applesauce", "Mild fruit sweetness with moisture"),
        ("mashed banana", "Natural fruit sweetness"),
    ],
    "fat": [
        ("olive oil", "Savoury cooking fat"),
        ("coconut oil", "Plant fat for baking and frying"),
        ("butter", "Classic rich fat"),
        ("avocado", "Soft fat for spreads and bowls"),
    ],
    "leavening": [
        ("flax egg", "Binder with some lift in bakes"),
        ("chia egg", "Gel binder alternative to egg"),
        ("baking powder", "Chemical lift when eggs are for rise only"),
    ],
    "dairy": [
        ("oat milk", "Neutral plant milk"),
        ("coconut cream", "Rich dairy-free creaminess"),
        ("soy milk", "Higher-protein plant milk"),
    ],
}


def _ingredient_name(item: IngredientLike) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        name = item.get("name") or item.get("ingredient") or ""
        return str(name).strip()
    return str(item or "").strip()


def _normalize_list(items: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in items or []:
        n = _normalize_name(str(raw))
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def match_veto_token(ingredient_name: str, veto_tokens: Sequence[str]) -> Optional[str]:
    """Return the veto token that matches this ingredient, if any."""
    norm = _normalize_name(ingredient_name)
    if not norm:
        return None
    # Prefer longest matching veto token for specificity
    best = None
    best_len = -1
    for token in veto_tokens:
        if _veto_match(norm, token) and len(token) > best_len:
            best = token
            best_len = len(token)
    return best


def _roles_for(ingredient_name: str) -> List[str]:
    """Resolve cooking-function roles for an ingredient name."""
    candidates = [
        _normalize_name(ingredient_name),
    ]
    norm = _normalize_name(ingredient_name)
    if norm:
        # Drop leading prep words: "mashed banana" already keyed; also try core noun
        for prefix in ("mashed ", "pureed ", "chopped ", "sliced ", "fresh ", "ripe "):
            if norm.startswith(prefix) and len(norm) > len(prefix) + 2:
                candidates.append(norm[len(prefix) :])
        if " " in norm:
            candidates.append(norm.split()[-1])  # banana from "mashed banana"
    seen = set()
    roles: List[str] = []
    for key in candidates:
        if not key or key in seen:
            continue
        seen.add(key)
        if key in INGREDIENT_ROLES:
            for role in INGREDIENT_ROLES[key]:
                if role not in roles:
                    roles.append(role)
            continue
        for map_key, map_roles in INGREDIENT_ROLES.items():
            if _veto_match(key, map_key) or _veto_match(map_key, key):
                for role in map_roles:
                    if role not in roles:
                        roles.append(role)
                break
    return roles


def _functional_swaps_for(ingredient_name: str) -> List[Tuple[str, str]]:
    """Curated swaps based on cooking function (binder, sweetener, …)."""
    out: List[Tuple[str, str]] = []
    seen = set()
    for role in _roles_for(ingredient_name):
        for name, reason in ROLE_SWAPS.get(role, []):
            norm = _normalize_name(name)
            if not norm or norm in seen:
                continue
            # Don't suggest the ingredient as its own swap
            if _veto_match(norm, _normalize_name(ingredient_name)) or _veto_match(
                _normalize_name(ingredient_name), norm
            ):
                continue
            seen.add(norm)
            out.append((name, f"{reason} ({role})"))
    return out


def _curated_for(matched_veto: str, ingredient_name: str) -> List[Tuple[str, str]]:
    candidates = [
        _normalize_name(matched_veto),
        _normalize_name(ingredient_name),
    ]
    # Also try singular/plural stems and first/last word
    for c in list(candidates):
        if c.endswith("s") and len(c) > 3:
            candidates.append(c[:-1])
        if " " in c:
            candidates.append(c.split()[0])
            candidates.append(c.split()[-1])
        for prefix in ("mashed ", "pureed ", "chopped ", "sliced ", "fresh ", "ripe "):
            if c.startswith(prefix) and len(c) > len(prefix) + 2:
                candidates.append(c[len(prefix) :])
    seen = set()
    for key in candidates:
        if not key or key in seen:
            continue
        seen.add(key)
        if key in CURATED_SWAPS:
            return list(CURATED_SWAPS[key])
        for map_key, swaps in CURATED_SWAPS.items():
            if _veto_match(key, map_key) or _veto_match(map_key, key):
                return list(swaps)
    return []


def _category_for(ingredient_name: str) -> Optional[str]:
    found = find_food(ingredient_name)
    if found:
        return found[1].get("category")
    return None


def suggest_replacements(
    ingredient_name: str,
    *,
    matched_veto: str,
    prefs: Optional[dict] = None,
    limit: int = 3,
    exclude_names: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Build ranked replacement suggestions for a vetoed ingredient.

    Order: curated swaps first, then same-category food_db foods (diet + veto filtered).
    """
    prefs = prefs or {}
    flags = _dietary_flags(prefs)
    adult = set(_normalize_list(adult_veto_ingredients(prefs)))
    kid = set(_normalize_list(kid_veto_ingredients(prefs)))
    blocked = adult | kid
    exclude = {_normalize_name(x) for x in (exclude_names or []) if x}
    exclude |= {_normalize_name(ingredient_name), _normalize_name(matched_veto)}
    exclude |= blocked

    suggestions: List[Dict[str, Any]] = []
    seen = set()

    def _add(name: str, reason: str, source: str, category: Optional[str] = None) -> None:
        norm = _normalize_name(name)
        if not norm or norm in seen or norm in exclude:
            return
        # Skip if suggestion itself is vetoed
        if any(_veto_match(norm, v) for v in blocked):
            return
        entry = FOOD_DATABASE.get(norm)
        if entry and not _passes_diet_filters(norm, entry, flags):
            return
        # Prefer explicit category; only resolve via find_food for known DB names
        # (avoids "eggplant" → matching "egg")
        cat = category
        if cat is None and entry:
            cat = entry.get("category")
        elif cat is None and norm in FOOD_DATABASE:
            cat = FOOD_DATABASE[norm].get("category")
        seen.add(norm)
        display = name if (name in FOOD_DATABASE or not name.islower()) else name
        suggestions.append(
            {
                "name": display,
                "reason": reason,
                "category": cat,
                "source": source,
            }
        )

    for name, reason in _curated_for(matched_veto, ingredient_name):
        entry = FOOD_DATABASE.get(_normalize_name(name))
        _add(name, reason, "curated", entry.get("category") if entry else None)
        if len(suggestions) >= limit:
            return suggestions[:limit]

    # Function-based swaps (binder / sweetener / …) beat random same-aisle fruits
    for name, reason in _functional_swaps_for(ingredient_name):
        entry = FOOD_DATABASE.get(_normalize_name(name))
        _add(name, reason, "function", entry.get("category") if entry else None)
        if len(suggestions) >= limit:
            return suggestions[:limit]

    category = _category_for(ingredient_name) or _category_for(matched_veto)
    if category:
        # Prefer high-protein / pantry-tagged peers in the same category
        peers: List[Tuple[float, str, Dict[str, Any]]] = []
        for db_name, entry in FOOD_DATABASE.items():
            if entry.get("category") != category:
                continue
            if _normalize_name(db_name) in exclude:
                continue
            if any(_veto_match(db_name, v) for v in blocked):
                continue
            if not _passes_diet_filters(db_name, entry, flags):
                continue
            tags = set(entry.get("tags") or [])
            score = 0.0
            if "high-protein" in tags:
                score += 2
            if "pantry" in tags:
                score += 1
            score += float(entry.get("protein") or 0) / 50.0
            peers.append((score, db_name, entry))
        peers.sort(key=lambda x: (-x[0], x[1]))
        for _, db_name, entry in peers:
            _add(
                db_name,
                f"Same category ({category}) alternative from food database",
                "food_db",
                entry.get("category"),
            )
            if len(suggestions) >= limit:
                break

    return suggestions[:limit]


def suggest_ingredient_substitutions(
    ingredient_name: str,
    prefs: Optional[dict] = None,
    *,
    limit: int = 5,
    exclude_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Honeydew-style open substitutions for any ingredient (not only veto hits).

    Uses the same curated + food_db ranking as veto swaps.
    """
    name = (ingredient_name or "").strip()
    if not name:
        return {"ingredient": "", "suggestions": []}
    suggestions = suggest_replacements(
        name,
        matched_veto=name,
        prefs=prefs,
        limit=limit,
        exclude_names=exclude_names,
    )
    return {
        "ingredient": name,
        "suggestions": suggestions,
        "category": _category_for(name),
        "roles": _roles_for(name),
    }


def check_ingredients_for_vetoes(
    ingredients: Sequence[IngredientLike],
    prefs: Optional[dict],
    *,
    suggestion_limit: int = 3,
) -> Dict[str, Any]:
    """
    Scan ingredients against adult + (active) kid veto lists.

    Returns:
      {
        hits: [{ingredient, ingredient_index, matched_veto, list, severity}],
        replacements: [{..., suggestions: [...]}],
        has_hits: bool,
      }
    """
    prefs = prefs or {}
    adult_tokens = _normalize_list(adult_veto_ingredients(prefs))
    kid_tokens = _normalize_list(kid_veto_ingredients(prefs))

    hits: List[Dict[str, Any]] = []
    replacements: List[Dict[str, Any]] = []

    for idx, raw in enumerate(ingredients or []):
        name = _ingredient_name(raw)
        if not name:
            continue

        matched_lists: List[Tuple[str, str]] = []  # (list_name, token)
        adult_hit = match_veto_token(name, adult_tokens)
        if adult_hit:
            matched_lists.append(("adult", adult_hit))
        kid_hit = match_veto_token(name, kid_tokens)
        if kid_hit:
            matched_lists.append(("kid", kid_hit))

        if not matched_lists:
            continue

        # One replacement row per ingredient; note all lists that hit
        primary_list, primary_token = matched_lists[0]
        hit = {
            "ingredient": name,
            "ingredient_index": idx,
            "matched_veto": primary_token,
            "list": primary_list,
            "lists": [m[0] for m in matched_lists],
            "severity": "preference",
        }
        hits.append(hit)

        suggestions = suggest_replacements(
            name,
            matched_veto=primary_token,
            prefs=prefs,
            limit=suggestion_limit,
        )
        replacements.append(
            {
                **hit,
                "suggestions": suggestions,
            }
        )

    return {
        "hits": hits,
        "replacements": replacements,
        "has_hits": len(hits) > 0,
    }
