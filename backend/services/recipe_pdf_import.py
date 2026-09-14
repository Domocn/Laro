"""
Split text-based recipe PDFs into individual, non-overlapping recipes.

Used by POST /ai/import-recipe-pdf. Each recipe is tagged needs-review so the
user can confirm before treating it as finished.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple


NEEDS_REVIEW_TAG = "needs-review"
IMPORTED_PDF_TAG = "imported-pdf"

# Markers that usually start a new recipe in multi-recipe PDFs / cookbooks
_CHUNK_START = re.compile(
    r"(?:"
    r"^\s*(?:recipe\s*(?:#|no\.?|number)?\s*\d+)\b"
    r"|^\s*(?:DINNER|SNACK|BREAKFAST|LUNCH)\s*\d*\s*[—–\-:]+\s+.+$"
    r"|^\s*\d{1,2}[\.\)]\s+[A-Z][^\n]{2,80}$"
    r"|^\s*#{1,3}\s+.+$"
    r"|^\s*[A-Z][A-Za-z0-9'’&\-\s]{3,60}\s*$"
    r")",
    re.I | re.M,
)

_INGREDIENTS_HEAD = re.compile(r"^\s*ingredients?\s*:?\s*$", re.I | re.M)
_METHOD_HEAD = re.compile(
    r"^\s*(?:method|instructions?|directions?|steps?)\s*:?\s*$", re.I | re.M
)


def normalize_recipe_title(title: str) -> str:
    t = (title or "").strip().lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def split_recipe_text_chunks(text: str, max_chunks: int = 25) -> List[str]:
    """
    Split PDF text into non-overlapping recipe chunks.

    Prefer explicit Recipe N / numbered headings; fall back to form-feed /
    blank-line + Ingredients boundaries. Chunks never share character ranges.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n\s*--\s*\d+\s+of\s+\d+\s*--\s*\n", "\n", text, flags=re.I)
    text = text.strip()
    if not text:
        return []

    # Hard page breaks from some extractors
    if "\f" in text:
        pages = [p.strip() for p in text.split("\f") if p.strip()]
        if len(pages) > 1 and all(len(p) > 80 for p in pages[:3]):
            # Only treat as separate recipes if each page looks recipe-like
            recipeish = [
                p
                for p in pages
                if _INGREDIENTS_HEAD.search(p) or _METHOD_HEAD.search(p)
            ]
            if len(recipeish) >= 2:
                return recipeish[:max_chunks]

    starts: List[int] = []
    for m in _CHUNK_START.finditer(text):
        # Only keep starts that look like recipe titles (followed by ingredients soon)
        window = text[m.start() : m.start() + 800]
        if _INGREDIENTS_HEAD.search(window) or _METHOD_HEAD.search(window) or "ingredient" in window.lower():
            # Avoid matching the first Ingredients line itself as a title
            if _INGREDIENTS_HEAD.match(m.group(0)) or _METHOD_HEAD.match(m.group(0)):
                continue
            starts.append(m.start())

    # Deduplicate starts that are too close (< 40 chars) — keep earliest
    compact: List[int] = []
    for s in starts:
        if not compact or s - compact[-1] >= 40:
            compact.append(s)
    starts = compact

    if len(starts) >= 2:
        chunks: List[str] = []
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(text)
            chunk = text[start:end].strip()
            if len(chunk) >= 40:
                chunks.append(chunk)
            if len(chunks) >= max_chunks:
                break
        if len(chunks) >= 2:
            return chunks

    # Split on double newlines before an Ingredients heading
    parts = re.split(r"\n{2,}(?=\s*ingredients?\s*:?\s*\n)", text, flags=re.I)
    if len(parts) >= 2:
        # Reattach: each part after the first starts with Ingredients — prepend prior title lines
        rebuilt: List[str] = []
        # First part may be intro + recipe 1 without leading Ingredients split
        if parts[0].strip():
            rebuilt.append(parts[0].strip())
        for p in parts[1:]:
            p = p.strip()
            if p:
                rebuilt.append(p)
        # If first chunk is only a cover page (< ingredients), drop if tiny
        rebuilt = [c for c in rebuilt if len(c) >= 40]
        if len(rebuilt) >= 2:
            return rebuilt[:max_chunks]

    return [text]


def mark_recipe_for_review(recipe: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure recipe carries needs-review tag + flag for client UIs."""
    out = dict(recipe or {})
    tags = list(out.get("tags") or [])
    for t in (NEEDS_REVIEW_TAG, IMPORTED_PDF_TAG):
        if t not in tags:
            tags.append(t)
    out["tags"] = tags
    out["needs_review"] = True
    return out


def dedupe_recipes(
    recipes: List[Dict[str, Any]],
    existing_titles: Optional[Set[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Drop overlapping / duplicate titles within the batch and vs existing library.
    Returns (kept, skipped[{title, reason}]).
    """
    existing = set(existing_titles or set())
    seen: Set[str] = set()
    kept: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    for raw in recipes or []:
        title = (raw.get("title") or "").strip() or "Untitled Recipe"
        key = normalize_recipe_title(title)
        if not key:
            skipped.append({"title": title, "reason": "empty_title"})
            continue
        if key in seen:
            skipped.append({"title": title, "reason": "duplicate_in_pdf"})
            continue
        if key in existing:
            skipped.append({"title": title, "reason": "already_in_library"})
            continue
        seen.add(key)
        recipe = mark_recipe_for_review({**raw, "title": title})
        kept.append(recipe)

    return kept, skipped


def parse_llm_recipes_payload(data: Any) -> List[Dict[str, Any]]:
    """Normalize LLM JSON into a list of recipe dicts."""
    if data is None:
        return []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if isinstance(data.get("recipes"), list):
            items = data["recipes"]
        elif data.get("title"):
            items = [data]
        else:
            items = []
    else:
        items = []

    out: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if len(title) < 2:
            continue
        ingredients = item.get("ingredients") or []
        instructions = item.get("instructions") or []
        if isinstance(ingredients, str):
            ingredients = [{"amount": "", "unit": "", "name": ingredients}]
        if isinstance(instructions, str):
            instructions = [instructions]
        out.append(
            {
                "title": title,
                "description": item.get("description") or "",
                "ingredients": ingredients,
                "instructions": instructions,
                "prep_time": int(item.get("prep_time") or 0),
                "cook_time": int(item.get("cook_time") or 0),
                "servings": int(item.get("servings") or 4),
                "category": item.get("category") or "Other",
                "tags": list(item.get("tags") or []),
                "image_url": item.get("image_url") or "",
                "nutrition": item.get("nutrition")
                if isinstance(item.get("nutrition"), dict)
                else {},
            }
        )
    return out


MULTI_RECIPE_PDF_PROMPT = """You are a recipe extraction assistant. The user uploaded a PDF that may contain ONE or MANY recipes.
Extract EVERY distinct recipe as its own object. Do NOT merge recipes. Do NOT repeat the same dish twice.
If content overlaps, assign each ingredient/instruction to only one recipe (no overlapping ownership).
Return ONLY valid JSON (no markdown):
{
  "recipes": [
    {
      "title": "Recipe Name",
      "description": "Brief description",
      "ingredients": [{"name": "ingredient", "amount": "1", "unit": "cup"}],
      "instructions": ["Step 1", "Step 2"],
      "prep_time": 15,
      "cook_time": 30,
      "servings": 4,
      "category": "Dinner",
      "tags": [],
      "nutrition": {"calories": null, "protein": null, "carbs": null, "fat": null}
    }
  ]
}
Categories: Breakfast, Lunch, Dinner, Dessert, Appetizer, Snack, Beverage, Meal Pack, Other.
If only one recipe is present, return an array of length 1."""
