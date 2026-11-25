"""
Split text-based recipe PDFs into individual, non-overlapping recipes.

Used by POST /ai/import-recipe-pdf. Each recipe is tagged needs-review so the
user can confirm before treating it as finished.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from utils.ingredient_groups import legacy_name, with_group


NEEDS_REVIEW_TAG = "needs-review"
IMPORTED_PDF_TAG = "imported-pdf"

# Explicit recipe starts. Do NOT use IGNORECASE on the Title-Case line:
# wrapped words like "fudge" would otherwise look like a new dish.
_CHUNK_START = re.compile(
    r"(?:"
    r"^\s*(?i:recipe\s*(?:#|no\.?|number)?\s*\d+)\b"
    r"|^\s*(?i:DINNER|SNACK|BREAKFAST|LUNCH)\s*\d*\s*[—–\-:]+\s+.+$"
    r"|^\s*\d{1,2}[\.\)]\s+[A-Z][^\n]{8,80}$"
    r"|^\s*#{1,3}\s+.+$"
    r"|^\s*[A-Z][A-Za-z0-9'’&][A-Za-z0-9'’&\-\s]{8,80}\s*$"
    r")",
    re.M,
)

_INGREDIENTS_HEAD = re.compile(r"^\s*ingredients?\s*:?\s*$", re.I | re.M)
_METHOD_HEAD = re.compile(
    r"^\s*(?:method|instructions?|directions?|steps?|notes?)\s*:?\s*$",
    re.I | re.M,
)
_SECTION_HEAD_LINE = re.compile(
    r"^\s*(?:ingredients?|method|instructions?|directions?|steps?|notes?|nutrition|serves?|yield)\s*:?\s*$",
    re.I | re.M,
)


def normalize_recipe_title(title: str) -> str:
    t = (title or "").strip().lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


_QUANTITY_RE = re.compile(r"\d+\s?(?:g|kg|ml|l|tsp|tbsp|cups?|oz|lb)\b", re.I)
_COMPONENT_HEADINGS = {
    "FILLING", "SAUCE", "DOUGH", "DRESSING", "TOPPING", "ICING", "GLAZE", "MARINADE", "BATTER",
    "SYRUP", "FROSTING", "MIX-INS", "CRUMBLE", "BASE", "COATING", "SEASONING", "BASTE", "SERVE", "TOP",
}
_CAPTION_RE = re.compile(r"^(?:LEFT|RIGHT|TOP|BOTTOM|ABOVE|BELOW|OPPOSITE)\b[^:]{0,20}:.*?(?=[A-Z][A-Z'’\-]+(?:\s+[A-Z'’\-]+){1,})")


_CAPS_LINE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 ,&'’+\-–—()/.!]*$")


def caps_title_candidates(text: str) -> List[str]:
    """
    ALL-CAPS heading lines (wrapped lines joined) that look like dish titles.
    Cookbooks print each recipe's name this way; the list anchors the AI so it
    returns one recipe per dish instead of merging or splitting them.
    Sub-part headings (SAUCE, DOUGH, MIX-INS…) are left out.
    """
    titles: List[str] = []
    run: List[str] = []

    def flush():
        if run:
            title = " ".join(run).strip(" :-–—")
            words = re.findall(r"[A-Za-z'’]{2,}", title)
            last = words[-1].upper() if words else ""
            if len(words) >= 2 and last not in _COMPONENT_HEADINGS and not title.endswith(":"):
                titles.append(re.sub(r"\s+", " ", title))
            run.clear()

    for raw in (text or "").splitlines():
        line = raw.strip().replace("�", " ").strip()
        if line and not line.isdigit() and _CAPS_LINE_RE.match(line) and re.search(r"[A-Z]{3}", line):
            run.append(line)
        else:
            flush()
    flush()
    seen, out = set(), []
    for t in titles:
        k = normalize_recipe_title(t)
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


def page_starts_recipe(page_text: str) -> bool:
    """A cookbook page that opens a new recipe: ALL-CAPS title at the top plus quantities."""
    text = " ".join((page_text or "").split())
    if len(text) < 300 or not _QUANTITY_RE.search(text):
        return False
    text = re.sub(r"^\d{1,3}\s+", "", text)  # page number
    text = _CAPTION_RE.sub("", text)  # "LEFT: Photo caption" before the title
    title = []
    for token in text.split()[:12]:
        if token.endswith(":"):  # "TO SERVE:" style sub-heading
            return False
        if token in ("&", "+") or (re.search(r"[A-Z]", token) and token.upper() == token and not re.match(r"\d", token)):
            title.append(token)
        else:
            break
    words = [w for w in title if re.search(r"[A-Z]{2}", w)]
    if len(words) < 2:
        return False
    # "CINNAMON SUGAR FILLING 70g…" is part of a recipe, not a new one.
    return words[-1].strip("'’-").upper() not in _COMPONENT_HEADINGS


def group_pages_at_recipe_starts(page_texts: List[str], max_pages: int = 10) -> List[Tuple[int, int]]:
    """
    Group pages into (start, end) ranges of at most ~max_pages that only ever
    break where a new recipe starts, so no recipe is cut in half.
    Falls back to fixed-size ranges when no recipe starts are detected.
    """
    n = len(page_texts)
    starts = [i for i, t in enumerate(page_texts) if page_starts_recipe(t)]
    if not starts:
        return [(a, min(n, a + max_pages)) for a in range(0, n, max_pages)]
    cuts = sorted({0, *starts, n})
    groups: List[Tuple[int, int]] = []
    a = 0
    for i in range(1, len(cuts)):
        if cuts[i] - a > max_pages and cuts[i - 1] > a:
            groups.append((a, cuts[i - 1]))
            a = cuts[i - 1]
    groups.append((a, n))
    return groups


def pack_recipe_sections(text: str, max_chars: int = 5000) -> List[str]:
    """
    All of the text, in sections of at most ~max_chars, broken at recipe
    boundaries where split_recipe_text_chunks finds them. Unlike calling the
    chunker directly, nothing past its chunk cap is dropped and no section is
    longer than the prompt keeps.
    """
    pieces: List[str] = []
    for chunk in split_recipe_text_chunks(text, max_chunks=10_000) or [text]:
        while len(chunk) > max_chars:  # one huge "recipe": cut at the last line break that fits
            cut = chunk.rfind("\n", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            pieces.append(chunk[:cut])
            chunk = chunk[cut:].lstrip("\n")
        if chunk.strip():
            pieces.append(chunk)
    sections: List[str] = []
    for piece in pieces:
        if sections and len(sections[-1]) + len(piece) + 2 <= max_chars:
            sections[-1] = f"{sections[-1]}\n\n{piece}"
        else:
            sections.append(piece)
    return sections


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
        heading = m.group(0).strip()
        if _SECTION_HEAD_LINE.match(heading):
            continue
        # Wrapped leftover from the previous line ("proper\nfudge") is not a title.
        before = text[: m.start()].rstrip()
        if before:
            prev = before.split("\n")[-1].strip()
            if prev and prev[-1] not in ".!?:":
                continue
        words = [w for w in re.split(r"\s+", heading) if w]
        if len(words) < 2 and not re.match(r"(?i)recipe\s*\d", heading):
            continue
        # Numbered cook steps ("2. Bake at 150C.") are not new recipes.
        if re.match(r"^\d{1,2}[\.\)]\s+", heading):
            prior = text[: m.start()]
            last_head = None
            for hm in _SECTION_HEAD_LINE.finditer(prior):
                last_head = hm.group(0)
            if last_head and re.search(
                r"(?i)method|instruction|direction|step|note", last_head
            ):
                continue
            if heading.rstrip().endswith((".", "!", "?")):
                continue
        window = text[m.start() : m.start() + 800]
        if _INGREDIENTS_HEAD.search(window) or _METHOD_HEAD.search(window) or "ingredient" in window.lower():
            starts.append(m.start())

    # Deduplicate starts that are too close (< 40 chars) — keep earliest
    compact: List[int] = []
    for s in starts:
        if not compact or s - compact[-1] >= 40:
            compact.append(s)
    starts = compact

    if len(starts) >= 2:
        chunks: List[str] = []
        # Text before the first detected heading is often a whole recipe whose title the
        # pattern missed (e.g. "50\nHONEY CHILLI CAULIFLOWER"); never throw it away.
        lead = text[: starts[0]].strip()
        if len(lead) >= 40:
            chunks.append(lead)
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


def mark_recipe_for_review(
    recipe: Dict[str, Any],
    *,
    import_tag: str = IMPORTED_PDF_TAG,
) -> Dict[str, Any]:
    """Ensure recipe carries needs-review tag + flag for client UIs."""
    out = dict(recipe or {})
    tags = list(out.get("tags") or [])
    for t in (NEEDS_REVIEW_TAG, import_tag):
        if t and t not in tags:
            tags.append(t)
    out["tags"] = tags
    out["needs_review"] = True
    return out


def dedupe_recipes(
    recipes: List[Dict[str, Any]],
    existing_titles: Optional[Set[str]] = None,
    *,
    import_tag: str = IMPORTED_PDF_TAG,
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
        recipe = mark_recipe_for_review({**raw, "title": title}, import_tag=import_tag)
        kept.append(recipe)

    return kept, skipped


def _first_int(value: Any, default: int) -> int:
    """'1+', '4-6', '20 min' -> first whole number; anything else -> default."""
    if isinstance(value, (int, float)):
        return int(value)
    m = re.search(r"\d+", str(value or ""))
    return int(m.group()) if m else default


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
        # Sub-part lines carry their heading in "group"; an older-style "Sauce: tahini" name
        # prefix is split into it too (utils/ingredient_groups.py).
        ingredients = [with_group(i) if isinstance(i, dict) else i for i in _as_list(ingredients)]
        if isinstance(instructions, str):
            instructions = [instructions]
        out.append(
            {
                "title": title,
                "description": item.get("description") or "",
                "ingredients": ingredients,
                "instructions": instructions,
                "prep_time": _first_int(item.get("prep_time"), 0),
                "cook_time": _first_int(item.get("cook_time"), 0),
                "servings": _first_int(item.get("servings"), 4) or 4,
                "category": item.get("category") or "Other",
                "tags": list(item.get("tags") or []),
                "image_url": item.get("image_url") or "",
                "nutrition": item.get("nutrition")
                if isinstance(item.get("nutrition"), dict)
                else {},
                "adaptations": _adaptations_from_item(item),
            }
        )
    return [complete_versions(r) for r in out]


def _adaptations_from_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """AI replies put the swap list at "low_fodmap", named versions at "versions" and the
    page's tips / timing / storage notes at "notes" (or all already under "adaptations")."""
    from utils.recipe_fields import normalize_adaptations

    raw = item.get("adaptations") if isinstance(item.get("adaptations"), dict) else {}
    return normalize_adaptations({
        "low_fodmap": raw.get("low_fodmap") or item.get("low_fodmap"),
        "versions": raw.get("versions") or item.get("versions"),
        "page_notes": raw.get("page_notes") or item.get("notes") or item.get("page_notes"),
    })


def complete_versions(recipe: Dict[str, Any]) -> Dict[str, Any]:
    """
    Versions must be whole recipes, but the AI often lists only what a version
    adds ("Pomegranate": just the arils). Picking it would then hide the pasta and
    pesto. Put the base ingredients / steps in front of add-on-only versions.
    """
    adaptations = recipe.get("adaptations") if isinstance(recipe.get("adaptations"), dict) else None
    if not adaptations or not adaptations.get("versions"):
        return recipe
    base_ings = _as_list(recipe.get("ingredients"))
    base_steps = [str(s) for s in _as_list(recipe.get("instructions"))]

    name = _ing_key
    base_names = {name(i) for i in base_ings}
    fixed = []
    for version in adaptations["versions"]:
        v = dict(version)
        ings = _as_list(v.get("ingredients"))
        shared = sum(1 for i in ings if name(i) in base_names)
        if base_ings and shared < len(base_names) / 2:
            v["ingredients"] = base_ings + [i for i in ings if name(i) not in base_names]
        steps = [str(s) for s in _as_list(v.get("instructions"))]
        if base_steps and len(steps) < len(base_steps) and not any(s in base_steps for s in steps):
            v["instructions"] = base_steps + steps
        fixed.append(v)
    return {**recipe, "adaptations": {**adaptations, "versions": fixed}}


def _merge_adaptations(base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Fill missing adaptation parts of base from extra (Low FODMAP swaps, versions);
    page notes from both are kept, in order."""
    out = dict(base or {})
    for key, value in (extra or {}).items():
        if key == "page_notes" and value:
            out[key] = list(out.get(key) or []) + [n for n in value if n not in (out.get(key) or [])]
        elif value and not out.get(key):
            out[key] = value
    return out or None


def versions_found(recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """[{"recipe": "Pesto Pasta", "versions": ["Chicken Schnitzel", ...]}] for import summaries."""
    out = []
    for recipe in recipes or []:
        adaptations = recipe.get("adaptations") if isinstance(recipe.get("adaptations"), dict) else {}
        names = [v.get("name") for v in adaptations.get("versions") or [] if isinstance(v, dict)]
        if names:
            out.append({"recipe": recipe.get("title") or "Recipe", "versions": names})
    return out


# "Pesto Pasta — Chicken Schnitzel", "Hot Cross Buns - Chocolate Orange" (spaced hyphen only,
# so "Stir-Fry" stays whole).
_VERSION_TITLE_RE = re.compile(r"^(?P<base>.+?)\s*(?:[—–]|\s-\s)\s*(?P<name>.+)$")


def _split_version_title(title: str) -> Optional[Tuple[str, str]]:
    m = _VERSION_TITLE_RE.match((title or "").strip())
    if not m:
        return None
    base, name = m.group("base").strip(), m.group("name").strip()
    if len(base) < 2 or not name or re.search(r"(?i)fodmap", name):
        return None
    return base, name


def fold_recipe_versions(recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fold "Dish — Version" recipes that share the same base title into ONE recipe whose own
    ingredients/steps are the first one (or a plain "Dish" recipe) and the rest go to
    ``adaptations.versions`` with full lists. A lone "Dish — Something" keeps its title.
    """
    from utils.recipe_fields import MAX_RECIPE_VERSIONS, normalize_adaptations

    groups: Dict[str, List[int]] = {}
    for i, recipe in enumerate(recipes or []):
        split = _split_version_title(recipe.get("title") or "")
        key = normalize_recipe_title(split[0] if split else (recipe.get("title") or ""))
        if key:
            groups.setdefault(key, []).append(i)

    drop: Set[int] = set()
    out = list(recipes or [])
    for idxs in groups.values():
        dashed = [i for i in idxs if _split_version_title(out[i].get("title") or "")]
        plain = [i for i in idxs if i not in dashed]
        if len(dashed) + len(plain) < 2 or not dashed or len(plain) > 1:
            continue
        head_i = plain[0] if plain else dashed[0]
        head = dict(out[head_i])
        base_title, head_name = _split_version_title(head.get("title") or "") or (head.get("title"), None)
        existing = normalize_adaptations(head.get("adaptations")) or {}
        versions = list(existing.get("versions") or [])
        for i in idxs:
            if i == head_i:
                continue
            other = out[i]
            _, name = _split_version_title(other.get("title") or "")
            other_notes = (normalize_adaptations(other.get("adaptations")) or {}).get("page_notes") or []
            versions.append({
                "name": name,
                "ingredients": _as_list(other.get("ingredients")),
                "instructions": _as_list(other.get("instructions")),
                "notes": "\n".join([other.get("description") or ""] + other_notes).strip(),
                # The page's own printed macros for this version (kept by version_macros).
                "nutrition": other.get("nutrition") if isinstance(other.get("nutrition"), dict) else None,
            })
            versions.extend((normalize_adaptations(other.get("adaptations")) or {}).get("versions") or [])
            if not existing.get("low_fodmap"):
                existing = _merge_adaptations(existing, {"low_fodmap": (other.get("adaptations") or {}).get("low_fodmap")}) or {}
            drop.add(i)
        head["title"] = base_title
        if head_name and not head.get("description"):
            head["description"] = f"Original version: {head_name}."
        head["adaptations"] = normalize_adaptations({**existing, "versions": versions[:MAX_RECIPE_VERSIONS]})
        out[head_i] = head
    return [r for i, r in enumerate(out) if i not in drop]


def _recipe_has_body(recipe: Dict[str, Any]) -> bool:
    ings = recipe.get("ingredients") or []
    steps = recipe.get("instructions") or []
    if isinstance(ings, str):
        ings = [ings] if ings.strip() else []
    if isinstance(steps, str):
        steps = [steps] if steps.strip() else []
    return bool(ings) or bool(steps)


def coalesce_incomplete_recipes(recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    PDF wrap + LLM sometimes emit a title-only stub plus the real body titled
    with the leftover wrap word (e.g. full name vs "fudge"). Keep one recipe.
    """
    if not recipes or len(recipes) == 1:
        return recipes
    with_body = [r for r in recipes if _recipe_has_body(r)]
    stubs = [r for r in recipes if not _recipe_has_body(r)]
    if len(with_body) == 1 and stubs:
        kept = dict(with_body[0])
        body_key = normalize_recipe_title(kept.get("title") or "")
        best_title = kept.get("title") or ""
        for stub in stubs:
            st = (stub.get("title") or "").strip()
            sk = normalize_recipe_title(st)
            if not sk:
                continue
            if sk in body_key or body_key in sk or body_key.endswith(sk) or sk.endswith(body_key):
                if len(st) > len(best_title):
                    best_title = st
        kept["title"] = best_title
        return [kept]
    if with_body:
        return with_body
    return recipes


_GENERIC_TITLE_RE = re.compile(
    r"^(recipe )?section \d+$|^(ingredients?|method|steps?|instructions?|directions|notes?|tips?|untitled( recipe)?)$"
)


def _singular_key(title: str) -> str:
    """'Red Lentil Wraps' and 'Red Lentil Wrap' are the same dish."""
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
                    for w in normalize_recipe_title(title).split())


def _title_tokens(title: str) -> set:
    t = re.sub(r"\([^)]*\)", " ", title or "")
    return set(normalize_recipe_title(t).split())


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _ing_key(ing: Any) -> str:
    """Repeat-check key for an ingredient: its section counts ("salt" in the dough and "salt" in
    the filling are different lines)."""
    return normalize_recipe_title(legacy_name(ing) if isinstance(ing, dict) else str(ing))


def _absorb(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Append extra's ingredients/steps to base, skipping exact repeats."""
    out = dict(base)
    seen = {_ing_key(i) for i in _as_list(out.get("ingredients"))}
    ings = list(_as_list(out.get("ingredients")))
    for ing in _as_list(extra.get("ingredients")):
        key = _ing_key(ing)
        if key and key not in seen:
            seen.add(key)
            ings.append(ing)
    steps = list(_as_list(out.get("instructions")))
    have = {normalize_recipe_title(str(x)) for x in steps}
    for step in _as_list(extra.get("instructions")):
        if normalize_recipe_title(str(step)) not in have:
            steps.append(step)
    out["ingredients"], out["instructions"] = ings, steps
    for key in ("description", "prep_time", "cook_time", "servings"):
        if not out.get(key) and extra.get(key):
            out[key] = extra[key]
    out["adaptations"] = _merge_adaptations(out.get("adaptations"), extra.get("adaptations"))
    return out


def merge_section_fragments(recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Batched PDF extraction can split one recipe across sections: a body titled
    "RECIPE SECTION 11" / "Method", or the same dish repeated with a shorter
    title ("Shawarma-Style Tofu Wrap" after "Shawarma-Style Tofu Frites Wrap"),
    or leftover steps with no ingredients that the AI gave a made-up title
    ("Bread the Tofu", "Recovery Bake"). Fold those into the recipe just before
    them; steps-only leftovers with nothing before them (the tail of a recipe
    from the previous upload) are dropped.
    """
    out: List[Dict[str, Any]] = []
    for recipe in recipes or []:
        title = (recipe.get("title") or "").strip()
        steps_only = not _as_list(recipe.get("ingredients"))
        # Same dish again later on (method on a later page): one recipe, not two.
        same_title = next(
            (i for i, r in enumerate(out) if title and _singular_key(r.get("title") or "") == _singular_key(title)),
            None,
        )
        if same_title is not None:
            out[same_title] = _absorb(out[same_title], recipe)
            continue
        if out and re.search(r"(?i)fodmap", title):
            # "Dish (Low FODMAP)" split off by the AI: keep it as the dish's adaptation note.
            swaps = [str(s) for s in _as_list(recipe.get("instructions"))]
            swaps += [str(i.get("name") if isinstance(i, dict) else i) for i in _as_list(recipe.get("ingredients"))]
            if swaps:
                prev = dict(out[-1])
                prev["instructions"] = _as_list(prev.get("instructions")) + ["Low FODMAP adaptation: " + "; ".join(swaps)]
                prev["adaptations"] = _merge_adaptations(prev.get("adaptations"), recipe.get("adaptations"))
                out[-1] = prev
            continue
        if out:
            prev = out[-1]
            generic = not title or bool(_GENERIC_TITLE_RE.match(normalize_recipe_title(title)))
            a, b = _title_tokens(prev.get("title") or ""), _title_tokens(title)
            same_dish = bool(a and b) and (a <= b or b <= a)
            if generic or same_dish or steps_only:
                prev_size = len(_as_list(prev.get("ingredients")))
                if same_dish and len(_as_list(recipe.get("ingredients"))) > prev_size:
                    out[-1] = _absorb(recipe, prev)
                else:
                    out[-1] = _absorb(prev, recipe)
                continue
        elif steps_only:
            continue
        out.append(recipe)
    return out


MULTI_RECIPE_PDF_PROMPT = """You are a recipe extraction assistant. The user uploaded a PDF that may contain ONE or MANY recipes.
Extract EVERY distinct recipe as its own object. Do NOT merge different dishes.
Do NOT split one recipe because its title wrapped onto two lines.
Do NOT treat section headings (Ingredients, Steps, Notes) or leftover wrap words as new recipes.
A section with steps but no ingredient list is the rest of the recipe before it: add those steps to that recipe, never make it a new recipe.
If only one recipe is present, return an array of length 1.
If content overlaps, assign each ingredient/instruction to only one recipe (no overlapping ownership).
Return ONLY valid JSON (no markdown):
{
  "recipes": [
    {
      "title": "Recipe Name",
      "description": "One short plain line describing the dish",
      "ingredients": [{"name": "ingredient", "amount": "1", "unit": "cup"}],
      "instructions": ["Step 1", "Step 2"],
      "prep_time": 15,
      "cook_time": 30,
      "servings": 4,
      "category": "Dinner",
      "tags": [],
      "nutrition": {"calories": null, "protein": null, "carbs": null, "fat": null},
      "notes": ["Allow 3–6 hours for the lentils to soak.", "Makes 6 wraps.", "To serve: …", "Keeps 3 days in the fridge."],
      "low_fodmap": null,
      "versions": []
    }
  ]
}
Categories: Breakfast, Lunch, Dinner, Dessert, Appetizer, Snack, Beverage, Meal Pack, Other.
Sub-parts of one dish (a sauce, filling, dough, frosting, marinade) stay inside that dish's recipe: list their ingredients and steps there.
Keep each sub-part's heading: put it in "group" on its ingredients (never in "name"), e.g. {"name": "tahini", "amount": "2", "unit": "tbsp", "group": "Sauce"},
and prefix its steps with it, e.g. "Sauce: Whisk the tahini…". Leave "group" out for the dish's main ingredients.
Keep EVERYTHING practical on the recipe's page — nothing practical may be dropped:
- "description" is ONE short plain line describing the dish (max 20 words, write it yourself). Do NOT copy the
  intro / headnote / author's story — leave that backstory out entirely;
- timing or soaking notes ("Allow 3–6 hours for the lentils to soak"), tips, make-ahead / storage notes, "TO SERVE" /
  serving suggestions, yield text ("Makes 6 wraps") and any other side notes go in "notes" as a list of strings,
  in page order, close to word for word (leave it [] when there are none). Only text printed with THAT recipe:
  never add notes about the book, its author or its back cover, and never invent a note;
- a yield like "Makes 6 wraps" / "Serves 4" also sets "servings" (6 / 4).
Dietary adaptation notes (e.g. "Low FODMAP: garlic + onion adaption…", vegan / gluten-free swaps) belong to the recipe they follow:
keep the full note in that recipe's "notes", starting with its name (e.g. "Low FODMAP adaptation: …"). Never make it a separate recipe.
When a recipe has a Low FODMAP note, ALSO set "low_fodmap" on that recipe (otherwise leave it null):
"low_fodmap": {"swaps": [{"from": "garlic", "to": "garlic-infused oil"}], "notes": "anything else the note says, e.g. portion limits"}
"from" is the ingredient name as written in the ingredient list; "to" is what to use instead.
If the note only says "garlic adaption" / "onion adaption" without details, use the standard swaps:
garlic -> garlic-infused oil; onion -> green tops of spring onions or leek.
Named versions of the SAME dish (a shared base with "— Version name" headings, or a "Variations:" / "Try it with…" list,
e.g. "Pesto Pasta" with Chicken Schnitzel / Salted Tomato and Feta / Pomegranate versions) are ONE recipe:
its own title, ingredients and instructions are the base (or first) version, and every other version goes in
"versions": [{"name": "Salted Tomato and Feta", "ingredients": [...], "instructions": [...], "notes": ""}]
Each version lists its FULL ingredients and instructions (base items included), not just the differences. Otherwise leave "versions" empty.
Different dishes that merely share a sub-recipe (one bun dough used for both Cinnamon Buns and Coffee Scrolls) stay SEPARATE recipes,
each with the shared dough included. Several different cakes or dishes on one page or spread are separate recipes, not versions.
If only one recipe is present, return an array of length 1."""

LOW_FODMAP_TAG = "low-fodmap-option"


def tag_dietary_adaptations(recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tag recipes that carry a Low FODMAP adaptation so users can filter for them."""
    for recipe in recipes:
        page_notes = (recipe.get("adaptations") or {}).get("page_notes") if isinstance(recipe.get("adaptations"), dict) else None
        steps = " ".join(str(s) for s in _as_list(recipe.get("instructions")) + list(page_notes or []))
        has_swaps = bool((recipe.get("adaptations") or {}).get("low_fodmap"))
        if has_swaps or re.search(r"(?i)low[\s-]*fodmap", steps + " " + str(recipe.get("description") or "")):
            tags = list(recipe.get("tags") or [])
            if LOW_FODMAP_TAG not in tags:
                tags.append(LOW_FODMAP_TAG)
            recipe["tags"] = tags
    return recipes


# Standard Low FODMAP swaps used when a note only says "garlic adaption" / "onion adaption".
STANDARD_FODMAP_SWAPS = {
    "garlic": "garlic-infused oil",
    "onion": "green tops of spring onions or leek",
}
_FODMAP_NOTE_RE = re.compile(r"^\s*low[\s-]*fodmap(?:\s+adaptations?|\s+option|\s+version)?\s*[:\-–—]\s*", re.I)
_SWAP_PATTERNS = (
    # "swap garlic for garlic oil", "replace onion with leek greens"
    (re.compile(r"(?i)\b(?:swap|replace|substitute)\s+(?:the\s+)?(.+?)\s+(?:for|with)\s+(.+)"), 1, 2),
    # "use garlic oil instead of garlic"
    (re.compile(r"(?i)^(?:use\s+)?(.+?)\s+instead\s+of\s+(?:the\s+)?(.+)"), 2, 1),
    # "garlic -> garlic-infused oil"
    (re.compile(r"(.+?)\s*(?:->|→|=>)\s*(.+)"), 1, 2),
)
_NAMES_ONLY_NOTE = re.compile(r"(?i)^[\w\s+&,/'-]*\badapt(?:at)?ions?\b[\s.!]*$")


def _clean_swap_term(text: str) -> str:
    return re.sub(r"^(?:the|some|a|an)\s+", "", text.strip(" .,:;!\"'()"), flags=re.I).strip()


def fodmap_adaptation_from_note(note: str) -> Optional[Dict[str, Any]]:
    """Rule-based parse of a "Low FODMAP adaptation: …" note into {"low_fodmap": {...}}.

    Picks up explicit swaps ("swap X for Y", "Y instead of X", "X -> Y") and falls back to the
    standard garlic / onion swaps when the note just names them. The note text becomes the notes
    unless it only lists adaptation names ("garlic + onion adaption").
    """
    from utils.recipe_fields import normalize_adaptations

    text = _FODMAP_NOTE_RE.sub("", str(note or "")).strip()
    if not text:
        return None
    swaps: List[Dict[str, str]] = []
    for part in re.split(r"[;\n]|\.\s+|,\s+(?=(?:swap|replace|substitute|use)\b)", text):
        part = part.strip()
        for pattern, src_group, dst_group in _SWAP_PATTERNS:
            m = pattern.search(part)
            if not m:
                continue
            src, dst = _clean_swap_term(m.group(src_group)), _clean_swap_term(m.group(dst_group))
            if src and dst and len(src.split()) <= 5 and len(dst.split()) <= 10:
                swaps.append({"from": src, "to": dst})
            break
    lower = text.lower()
    have = " ".join(s["from"].lower() for s in swaps)
    if "garlic" in lower and "garlic" not in have:
        swaps.append({"from": "garlic", "to": STANDARD_FODMAP_SWAPS["garlic"]})
    if re.search(r"(?<!spring )\bonions?\b", lower) and "onion" not in have:
        swaps.append({"from": "onion", "to": STANDARD_FODMAP_SWAPS["onion"]})
    notes = "" if _NAMES_ONLY_NOTE.match(text) else text
    return normalize_adaptations({"low_fodmap": {"swaps": swaps, "notes": notes}})


def plan_fodmap_backfill(recipes: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    """(recipe_id, adaptations) for recipes that carry a "Low FODMAP adaptation: …" step
    but no saved adaptations yet. The step itself is left alone."""
    out: List[Tuple[str, Dict[str, Any]]] = []
    for recipe in recipes or []:
        existing = recipe.get("adaptations")
        if isinstance(existing, str):
            from utils.recipe_fields import normalize_adaptations

            existing = normalize_adaptations(existing)
        if isinstance(existing, dict) and existing.get("low_fodmap"):
            continue
        steps = [str(s) for s in _as_list(recipe.get("instructions"))]
        if isinstance(existing, dict):
            steps += [str(s) for s in existing.get("page_notes") or []]
        notes = [s for s in steps if _FODMAP_NOTE_RE.match(s)]
        if not notes or not recipe.get("id"):
            continue
        adaptations = fodmap_adaptation_from_note(notes[-1])
        if adaptations:
            # Keep anything else already saved (e.g. named versions).
            out.append((recipe["id"], {**(existing if isinstance(existing, dict) else {}), **adaptations}))
    return out

IMPORTED_PHOTO_TAG = "imported-photo"

# Cap for Quick Add → Photos (many cookbook pages / separate dishes).
MAX_PHOTO_EXTRACT_IMAGES = 20
# Vision calls stay reliable when batched (token + image limits).
PHOTO_EXTRACT_BATCH_SIZE = 5

MULTI_RECIPE_IMAGES_PROMPT = """You are a recipe extraction assistant. The user uploaded cookbook / recipe page PHOTO(S).
Each image may be a different recipe OR consecutive pages of the same recipe.
Extract EVERY distinct recipe as its own object. Do NOT invent recipes that are not visible.
Rules:
- If an image is a complete recipe on its own, make it its own object.
- If consecutive images clearly continue THE SAME recipe (e.g. ingredients then instructions), combine into ONE object.
- Do NOT merge different dishes into one recipe.
- Do NOT repeat the same dish twice.
- Prefer the printed title (strip leading numbers like "1." or "10.").
- Ignore reverse-side bleed-through, spiral binding holes, shadows, hands, and table clutter.
- Include nutrition fields when printed on the page (calories, protein, carbs/fat/fiber/sugar as numbers when possible).
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
      "category": "Breakfast",
      "tags": [],
      "nutrition": {"calories": null, "protein": null, "carbs": null, "fat": null, "fiber": null, "sugar": null}
    }
  ]
}
Categories: Breakfast, Lunch, Dinner, Dessert, Appetizer, Snack, Beverage, Meal Pack, Other.
Ingredients of a sub-part (a sauce, filling, dough, topping, dressing) get that heading in "group", e.g. {"name": "tahini", "amount": "2", "unit": "tbsp", "group": "Sauce"}; never put the heading in "name". Leave "group" out for the main ingredients.
If only one recipe is present, return an array of length 1."""
