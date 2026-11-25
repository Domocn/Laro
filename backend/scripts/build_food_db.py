#!/usr/bin/env python3
"""Build the bundled food-composition artefact ``backend/data/foods/foods.json.gz``.

Sources (download them yourself; they are NOT committed - hundreds of MB):

* UK CoFID 2021 - McCance and Widdowson's Composition of Foods Integrated Dataset
  https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid
  file ``McCance_Widdowsons_Composition_of_Foods_Integrated_Dataset_2021..xlsx``
  Open Government Licence v3.0.
* USDA FoodData Central - Foundation Foods (JSON) and SR Legacy (JSON)
  https://fdc.nal.usda.gov/download-datasets
  e.g. ``FoodData_Central_foundation_food_json_2026-04-30.json`` and
  ``FoodData_Central_sr_legacy_food_json_2018-04.json``. Public domain (CC0).

Usage::

    pip install openpyxl
    python backend/scripts/build_food_db.py \
        --cofid  path/to/McCance_Widdowsons_..._2021..xlsx \
        --fdc-foundation path/to/FoodData_Central_foundation_food_json_XXXX.json \
        --fdc-sr path/to/FoodData_Central_sr_legacy_food_json_2018-04.json

Every value is per 100 g edible portion:

* ``carbs`` is *available* carbohydrate. CoFID already reports it that way (fibre
  excluded). USDA reports carbohydrate "by difference", which includes fibre, so
  USDA carbs = by-difference minus total dietary fibre (clamped at 0).
* ``fiber`` - CoFID AOAC fibre where measured, else NSP (Englyst); USDA total
  dietary fibre (AOAC).
* ``salt`` - CoFID sodium x 2.5; USDA sodium x 2.5 (mg -> g).
* ``state`` is parsed from the description (raw / boiled / canned / dried ...).

Output is deterministic (sorted) so rebuilding with the same inputs gives an
identical file.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "..", "data", "foods", "foods.json.gz")

COLUMNS = [
    "description", "source", "source_id", "state", "category",
    "calories", "protein", "carbs", "fat", "fiber", "sugars", "saturates", "salt",
]

# USDA categories that are composite / restaurant / infant foods - they only cause
# wrong matches for recipe ingredients.
USDA_SKIP_CATEGORIES = {
    "Baby Foods",
    "Fast Foods",
    "Restaurant Foods",
    "Meals, Entrees, and Side Dishes",
    "American Indian/Alaska Native Foods",
}

_STATE_RULES = [
    # (state, regex) - first match wins, so the more specific processing comes first.
    ("fried", r"\b(fried|stir-fried|deep-fried|sauteed|sautéed)\b"),
    ("roasted", r"\b(roasted|roast)\b"),
    ("grilled", r"\b(grilled|broiled|barbecued)\b"),
    ("baked", r"\bbaked\b"),
    ("toasted", r"\btoasted\b"),
    ("steamed", r"\bsteamed\b"),
    ("boiled", r"\b(boiled|poached|simmered|stewed|braised)\b"),
    ("cooked", r"\b(cooked|microwaved|heated|dry heat|moist heat|prepared from recipe)\b"),
    ("canned", r"\b(canned|tinned|drained solids|in brine|in water|in syrup|in juice)\b"),
    ("dried", r"\b(dried|dehydrated|dry|powder|powdered)\b"),
    ("frozen", r"\b(frozen)\b"),
    ("raw", r"\b(raw|fresh|uncooked)\b"),
]
_STATE_RES = [(state, re.compile(rx, re.I)) for state, rx in _STATE_RULES]


def parse_state(description: str) -> str:
    """Best-effort physical state from a CoFID / USDA description."""
    text = description or ""
    # "unprepared"/"unheated" are as-sold, not cooked.
    text = re.sub(r"\b(unprepared|unheated|not prepared|uncooked)\b", "raw", text, flags=re.I)
    for state, rx in _STATE_RES:
        if rx.search(text):
            return state
    return ""


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s.upper() == "N":
        return None
    if s.lower() in ("tr", "trace"):
        return 0.0
    s = s.strip("()").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _r(value: Optional[float], nd: int = 1) -> Optional[float]:
    if value is None:
        return None
    out = round(float(value), nd)
    return int(out) if out == int(out) else out


# --- CoFID --------------------------------------------------------------------------

_COFID_GROUP_CATEGORY = {
    "A": "grain", "B": "dairy", "C": "protein", "D": "vegetable", "F": "fruit",
    "G": "nuts", "J": "protein", "M": "protein", "O": "fat", "P": "drink",
    "Q": "drink", "S": "sweet", "W": "condiment",
}


# CoFID names that mean something different from everyday recipe usage. Values are
# untouched; only the description is clarified so the matcher doesn't confuse them.
COFID_DESCRIPTION_FIXES = {
    # 22 kcal: the liquid inside a fresh coconut, not the tinned cooking ingredient
    # (that is 14-889 "Coconut milk, retail").
    "14-820": "Coconut water (CoFID: 'Coconut milk', liquid from fresh nut)",
}


def load_cofid(path: str) -> List[Dict[str, Any]]:
    import openpyxl  # build-time only dependency

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    def sheet_rows(prefix: str) -> Iterable[Dict[str, Any]]:
        ws = next(w for w in wb.worksheets if w.title.startswith(prefix))
        rows = ws.iter_rows(values_only=True)
        next(rows)  # human header
        codes = next(rows)  # short nutrient codes (WATER, PROT, ...)
        for row in rows:
            if not row or not row[0] or not row[1]:
                continue
            rec = {"code": str(row[0]).strip(), "name": str(row[1]).strip(), "group": str(row[3] or "").strip()}
            for code, val in zip(codes, row):
                if code:
                    rec[str(code).strip()] = val
            yield rec

    prox = {r["code"]: r for r in sheet_rows("1.3 ")}
    inorg = {r["code"]: r for r in sheet_rows("1.4 ")}
    out = []
    for code, r in prox.items():
        kcal = _num(r.get("KCALS"))
        prot = _num(r.get("PROT"))
        fat = _num(r.get("FAT"))
        carbs = _num(r.get("CHO"))
        if kcal is None or prot is None:
            continue
        fibre = _num(r.get("AOACFIB"))
        if fibre is None:
            fibre = _num(r.get("ENGFIB"))
        sodium = _num((inorg.get(code) or {}).get("NA"))
        name = COFID_DESCRIPTION_FIXES.get(code) or re.sub(r"\s+", " ", r["name"])
        out.append({
            "description": name,
            "source": "cofid",
            "source_id": code,
            "state": parse_state(name),
            "category": _COFID_GROUP_CATEGORY.get(r["group"][:1], ""),
            "calories": _r(kcal, 0),
            "protein": _r(prot),
            "carbs": _r(carbs or 0.0),
            "fat": _r(fat or 0.0),
            "fiber": _r(fibre),
            "sugars": _r(_num(r.get("TOTSUG"))),
            "saturates": _r(_num(r.get("SATFOD"))),
            "salt": _r(sodium * 2.5 / 1000.0, 2) if sodium is not None else None,
        })
    return out


# --- USDA FDC -----------------------------------------------------------------------

_USDA_CATEGORY = {
    "Vegetables and Vegetable Products": "vegetable",
    "Fruits and Fruit Juices": "fruit",
    "Poultry Products": "protein",
    "Beef Products": "protein",
    "Pork Products": "protein",
    "Lamb, Veal, and Game Products": "protein",
    "Finfish and Shellfish Products": "protein",
    "Sausages and Luncheon Meats": "protein",
    "Dairy and Egg Products": "dairy",
    "Legumes and Legume Products": "legume",
    "Cereal Grains and Pasta": "grain",
    "Baked Products": "grain",
    "Breakfast Cereals": "grain",
    "Nut and Seed Products": "nuts",
    "Fats and Oils": "fat",
    "Spices and Herbs": "seasoning",
    "Sweets": "sweet",
    "Soups, Sauces, and Gravies": "condiment",
    "Beverages": "drink",
    "Snacks": "snack",
}


def _usda_nutrients(food: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for fn in food.get("foodNutrients") or []:
        nut = fn.get("nutrient") or {}
        num = str(nut.get("number") or "")
        amt = fn.get("amount")
        if amt is None or not num:
            continue
        if nut.get("unitName") == "kJ" and num != "268":
            continue
        out.setdefault(num, float(amt))
    return out


def load_usda(path: str, source: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    foods = next(iter(data.values()))
    out = []
    for food in foods:
        if not isinstance(food, dict):
            continue
        desc = re.sub(r"\s+", " ", str(food.get("description") or "")).strip()
        cat = ((food.get("foodCategory") or {}).get("description") or "").strip()
        if not desc or cat in USDA_SKIP_CATEGORIES:
            continue
        # SR Legacy carries branded items whose brand is in capitals ("KRAFT ...").
        if re.search(r"\b[A-Z]{3,}\b", desc.replace("USDA", "").replace("NFS", "").replace("UHT", "")):
            continue
        n = _usda_nutrients(food)
        kcal = n.get("208") or n.get("958") or n.get("957")
        if kcal is None and n.get("268") is not None:
            kcal = n["268"] / 4.184
        prot = n.get("203")
        if kcal is None or prot is None:
            continue
        fat = n.get("204", n.get("298", 0.0))
        carbs_diff = n.get("205", n.get("205.2", 0.0))
        fibre = n.get("291")
        carbs = max(0.0, carbs_diff - (fibre or 0.0))
        sodium = n.get("307")
        out.append({
            "description": desc,
            "source": source,
            "source_id": str(food.get("fdcId")),
            "state": parse_state(desc),
            "category": _USDA_CATEGORY.get(cat, ""),
            "calories": _r(kcal, 0),
            "protein": _r(prot),
            "carbs": _r(carbs),
            "fat": _r(fat),
            "fiber": _r(fibre),
            "sugars": _r(n.get("269", n.get("269.3"))),
            "saturates": _r(n.get("606")),
            "salt": _r(sodium * 2.5 / 1000.0, 2) if sodium is not None else None,
        })
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cofid", required=True)
    ap.add_argument("--fdc-foundation", required=True)
    ap.add_argument("--fdc-sr", required=True)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    rows = load_cofid(args.cofid) + load_usda(args.fdc_foundation, "usda_foundation") + load_usda(args.fdc_sr, "usda_sr")
    order = {"cofid": 0, "usda_foundation": 1, "usda_sr": 2}
    rows.sort(key=lambda r: (order[r["source"]], r["description"].lower(), r["source_id"]))
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["source"]] = counts.get(r["source"], 0) + 1

    payload = {
        "version": 1,
        "columns": COLUMNS,
        "sources": {
            "cofid": "McCance and Widdowson's Composition of Foods Integrated Dataset 2021 (UK OHID/PHE), Open Government Licence v3.0",
            "usda_foundation": "USDA FoodData Central Foundation Foods " + _fdc_release(args.fdc_foundation) + ", public domain (CC0 1.0)",
            "usda_sr": "USDA FoodData Central SR Legacy 2018-04, public domain (CC0 1.0)",
        },
        "counts": counts,
        "rows": [[r[c] for c in COLUMNS] for r in rows],
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")
    with open(args.out, "wb") as fh:
        # mtime=0 keeps the gzip header deterministic.
        with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(raw)
    print(f"wrote {args.out}: {len(rows)} foods {counts}, {os.path.getsize(args.out) / 1024:.0f} KiB")
    return 0


def _fdc_release(path: str) -> str:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    return m.group(1) if m else ""


if __name__ == "__main__":
    sys.exit(main())
