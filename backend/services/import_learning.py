"""
Learn from user import corrections so transcript cleanup keeps improving.

Stores repeated mishear → correct pairs under uploads/import-learning/
and merges them into Whisper cleanup without an extra LLM call.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
_lock = threading.Lock()

# Promote a learned fix into active cleanup after this many independent hits.
_PROMOTE_AFTER = 2


def _learning_dir() -> Path:
    base = os.getenv("IMPORT_LEARNING_DIR", "").strip()
    if base:
        path = Path(base)
    else:
        path = Path(os.getenv("UPLOAD_DIR", "uploads")) / "import-learning"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fixes_path() -> Path:
    return _learning_dir() / "transcript_fixes.json"


def load_learned_transcript_fixes(*, min_count: int = _PROMOTE_AFTER) -> list[tuple[str, str]]:
    """Return (regex_pattern, replacement) pairs promoted from user corrections."""
    path = _fixes_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to read learned transcript fixes: %s", e)
        return []
    out: list[tuple[str, str]] = []
    for row in data.get("fixes") or []:
        if not isinstance(row, dict):
            continue
        if int(row.get("count") or 0) < min_count:
            continue
        bad = (row.get("bad") or "").strip()
        good = (row.get("good") or "").strip()
        if not bad or not good or bad.lower() == good.lower():
            continue
        # Escape as literal word/phrase match
        pat = r"\b" + re.escape(bad) + r"\b"
        out.append((pat, good))
    return out


def _norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _ingredient_names(recipe: Optional[dict]) -> list[str]:
    if not isinstance(recipe, dict):
        return []
    names = []
    for ing in recipe.get("ingredients") or []:
        if isinstance(ing, dict):
            n = (ing.get("name") or "").strip()
        else:
            n = str(ing or "").strip()
        if n:
            names.append(n)
    return names


def record_recipe_correction(
    *,
    original_recipe: Optional[dict],
    corrected_recipe: Optional[dict],
    import_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Diff ingredient names and bump counters for likely Whisper mishears.
    Returns summary of updates applied.
    """
    before = {_norm_name(n): n for n in _ingredient_names(original_recipe)}
    after_names = _ingredient_names(corrected_recipe)
    after = {_norm_name(n): n for n in after_names}

    # Renames: only trust a clear 1→1 swap. Multi-add/remove is recipe completeness,
    # not a Whisper mishear (pairing fish→kimchi would poison the model).
    removed = [before[k] for k in before if k not in after]
    added = [after[k] for k in after if k not in before]
    pairs: list[tuple[str, str]] = []
    if len(removed) == 1 and len(added) == 1:
        pairs.append((removed[0], added[0]))
    elif removed and added:
        # Similar token rename only (shared prefix / edit distance-ish)
        for bad in removed:
            bl = _norm_name(bad)
            best = None
            for good in added:
                gl = _norm_name(good)
                if bl == gl:
                    continue
                if len(bl) >= 4 and (bl[:4] == gl[:4] or bl in gl or gl in bl):
                    best = good
                    break
            if best:
                pairs.append((bad, best))

    if not pairs:
        return {"learned": 0, "pairs": []}

    path = _fixes_path()
    with _lock:
        data: dict[str, Any] = {"fixes": []}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {"fixes": []}
        fixes = list(data.get("fixes") or [])
        learned = 0
        for bad, good in pairs:
            key_bad = _norm_name(bad)
            key_good = _norm_name(good)
            if not key_bad or not key_good or key_bad == key_good:
                continue
            found = None
            for row in fixes:
                if _norm_name(row.get("bad") or "") == key_bad and _norm_name(
                    row.get("good") or ""
                ) == key_good:
                    found = row
                    break
            if found:
                found["count"] = int(found.get("count") or 0) + 1
                if import_id:
                    ids = list(found.get("import_ids") or [])
                    if import_id not in ids:
                        ids.append(import_id)
                    found["import_ids"] = ids[-20:]
            else:
                fixes.append(
                    {
                        "bad": bad,
                        "good": good,
                        "count": 1,
                        "import_ids": [import_id] if import_id else [],
                    }
                )
            learned += 1
        data["fixes"] = fixes
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"learned": learned, "pairs": [{"bad": a, "good": b} for a, b in pairs]}
