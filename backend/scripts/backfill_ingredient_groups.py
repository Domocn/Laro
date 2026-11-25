"""
One-off: move legacy "Basil Pesto: almonds" ingredient-name prefixes into ``group``.

Older cookbook / PDF imports wrote a sub-recipe's heading into each ingredient name. The API
already splits these on read (utils/ingredient_groups.py), but stored rows keep the prefix, so
anything reading the raw column (pantry matching, AI context, exports) still sees it. This
rewrites, per recipe:

  - ``ingredients``                         "Sauce: tahini" -> {"name": "tahini", "group": "Sauce"}
  - ``adaptations.versions[*].ingredients`` the same
  - ``adaptations.low_fodmap.swaps[*].from`` "Sauce: garlic" -> "garlic"
  - ``adaptations.confirmed_lines``         keys of grouped lines re-keyed to the clean line text

Line order and count never change, so ``ingredient_macros`` (index-aligned) stays valid.

Dry run by default (prints counts and samples, writes nothing):

    cd backend && DATABASE_URL=postgresql://... python scripts/backfill_ingredient_groups.py
    cd backend && DATABASE_URL=postgresql://... python scripts/backfill_ingredient_groups.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ingredient_groups import split_ingredient_group, with_group  # noqa: E402


def _split_list(items: Any) -> Tuple[Any, int, List[str]]:
    """(new list, lines changed, samples) for one ingredient list; non-lists come back as-is."""
    if not isinstance(items, list):
        return items, 0, []
    out, changed, samples = [], 0, []
    for item in items:
        if isinstance(item, dict):
            new = with_group(item)
            if not item.get("group") and new.get("group"):
                changed += 1
                samples.append(f"{item.get('name')!r} -> group={new['group']!r} name={new['name']!r}")
                out.append(new)
            else:
                out.append(item)
        elif isinstance(item, str):
            group, name = split_ingredient_group(item)
            if group:
                changed += 1
                samples.append(f"{item!r} -> group={group!r} name={name!r}")
                out.append({"name": name, "amount": "", "unit": "", "group": group})
            else:
                out.append(item)
        else:
            out.append(item)
    return out, changed, samples


def _loads(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
    return value


def _rekey_confirmed(recipe: Dict[str, Any], adaptations: Dict[str, Any]) -> int:
    """Move confirmations stored under a grouped line's pre-sections key to its clean key."""
    from services.confirmed_lines import confirm_key, line_variants, recipe_lists

    confirmed = adaptations.get("confirmed_lines")
    if not isinstance(confirmed, dict) or not confirmed:
        return 0
    moved = 0
    for name, lf, ings in recipe_lists({**recipe, "adaptations": adaptations}):
        for ing in ings:
            variants = line_variants(ing)
            if len(variants) < 2:
                continue
            new_key, old_key = confirm_key(variants[0], name, lf), confirm_key(variants[1], name, lf)
            if old_key in confirmed and new_key not in confirmed:
                confirmed[new_key] = confirmed.pop(old_key)
                moved += 1
    return moved


def backfill_recipe(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """{"ingredients"?, "adaptations"?, "stats", "samples"} for one recipe row, or None when
    nothing needs changing. Pure: the caller decides whether to write."""
    stats = {"lines": 0, "version_lines": 0, "swaps": 0, "confirmed": 0}
    samples: List[str] = []
    update: Dict[str, Any] = {}

    ingredients = _loads(row.get("ingredients"))
    new_ings, n, s = _split_list(ingredients)
    if n:
        stats["lines"] += n
        samples += s
        update["ingredients"] = new_ings

    adaptations = _loads(row.get("adaptations"))
    if isinstance(adaptations, dict):
        adapt = json.loads(json.dumps(adaptations))  # deep copy
        touched = False
        for version in adapt.get("versions") or []:
            if isinstance(version, dict):
                new_v, n, s = _split_list(version.get("ingredients"))
                if n:
                    version["ingredients"] = new_v
                    stats["version_lines"] += n
                    samples += [f"[{version.get('name')}] {x}" for x in s]
                    touched = True
        for swap in ((adapt.get("low_fodmap") or {}).get("swaps") or []):
            if isinstance(swap, dict) and isinstance(swap.get("from"), str):
                group, name = split_ingredient_group(swap["from"].strip())
                if group:
                    swap["from"] = name
                    stats["swaps"] += 1
                    touched = True
        moved = _rekey_confirmed(row, adapt)
        if moved:
            stats["confirmed"] += moved
            touched = True
        if touched:
            update["adaptations"] = adapt

    if not update:
        return None
    return {**update, "stats": stats, "samples": samples}


async def main(apply: bool, limit_samples: int) -> None:
    import asyncpg

    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Set DATABASE_URL")
    conn = await asyncpg.connect(url)
    try:
        rows = await conn.fetch("SELECT id, title, ingredients, adaptations FROM recipes")
        totals = {"recipes": 0, "lines": 0, "version_lines": 0, "swaps": 0, "confirmed": 0}
        shown = 0
        for record in rows:
            row = dict(record)
            result = backfill_recipe(row)
            if not result:
                continue
            totals["recipes"] += 1
            for k, v in result["stats"].items():
                totals[k] += v
            if shown < limit_samples:
                shown += 1
                print(f"- {row['title']} ({row['id']})")
                for line in result["samples"][:6]:
                    print(f"    {line}")
            if apply:
                sets, args = [], []
                for col in ("ingredients", "adaptations"):
                    if col in result:
                        args.append(json.dumps(result[col], ensure_ascii=False))
                        sets.append(f"{col} = ${len(args)}")
                args.append(row["id"])
                await conn.execute(f"UPDATE recipes SET {', '.join(sets)} WHERE id = ${len(args)}", *args)
        print(f"\nScanned {len(rows)} recipes; {totals['recipes']} need changes: "
              f"{totals['lines']} lines, {totals['version_lines']} version lines, "
              f"{totals['swaps']} Low FODMAP swaps, {totals['confirmed']} checked lines re-keyed.")
        print("Applied." if apply else "Dry run: nothing written (pass --apply to write).")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    parser.add_argument("--dry-run", action="store_true", help="explicit dry run (the default)")
    parser.add_argument("--samples", type=int, default=20, help="recipes to print samples for")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply and not args.dry_run, limit_samples=args.samples))
