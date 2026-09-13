"""
Parse printable weekly meal-plan documents (PDF text / pasted plans)
into Laro recipes + day/meal schedule.

Designed for plans like:
  7-Day Simple High-Protein Meal Plan
  Weekly Schedule (Day | Snack 1 | Snack 2 | Dinner)
  Meal Breakdown with Ingredients / Method / Macros
  Shopping List
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


DAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

DAY_ALIASES = {name: i for i, name in enumerate(DAY_NAMES)}
DAY_ALIASES.update({name[:3]: i for i, name in enumerate(DAY_NAMES)})


def _reflow_word_per_line_pdf(text: str) -> str:
    """pypdf 6.17+ sometimes emits one token per line; rebuild readable text."""
    lines = [ln.strip() for ln in (text or "").split("\n")]
    nonempty = [ln for ln in lines if ln]
    if len(nonempty) < 40:
        return text
    # Only treat as word-per-line when most lines are a single token (no spaces).
    # Good PyMuPDF extracts have many short multi-word lines (schedule cells) and
    # must not be flattened.
    one_word = sum(1 for ln in nonempty if (" " not in ln) and len(ln) <= 24)
    avg_len = sum(len(ln) for ln in nonempty) / len(nonempty)
    if one_word / len(nonempty) < 0.6 or avg_len > 18:
        return text
    joined = " ".join(nonempty)
    # Put structural headings back on their own lines for the section splitter
    markers = [
        r"(?i)\b(weekly\s+schedule)\b",
        r"(?i)\b(meal\s+breakdown)\b",
        r"(?i)\b(shopping\s+list)\b",
        r"(?i)\b(preparation\s+tip)\b",
        r"(?i)\b(ingredients)\b",
        r"(?i)\b(method)\b",
        r"(?i)\b(macros?)\b",
        r"(?i)\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"(?i)\b(lunch|breakfast)\b",
        r"(?i)\b(snack\s*\d+)\b",
        r"(?i)\b(dinner\s*\d+)\b",
    ]
    for pat in markers:
        joined = re.sub(pat, lambda m: "\n" + m.group(0), joined)
    # "Lunch Carrot-Cake …" → "Lunch\nCarrot-Cake …" for multiline headings
    joined = re.sub(
        r"(?im)^(lunch|breakfast|dinner\s*\d*|snack\s*\d*)\s+([A-Z0-9])",
        r"\1\n\2",
        joined,
    )
    # Prefer "Snack 1 — Title" / "Dinner 1 — Title" when still inline
    joined = re.sub(
        r"(?i)\b(snack\s*\d+|dinner\s*\d+)\s+(?=[A-Z0-9])",
        lambda m: m.group(1) + " — ",
        joined,
    )
    return joined


def _norm_ws(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\t", " ")
    # PDF bullets often include zero-width space after ● (●\u200b)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    # Collapse page markers from PDF extractors
    text = re.sub(r"\n\s*--\s*\d+\s+of\s+\d+\s*--\s*\n", "\n", text, flags=re.I)
    # Many PDF extractors insert a space between every word (or glyph).
    # Collapse runs of spaces so "DINNER  1  —  Chicken" → "DINNER 1 — Chicken".
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = _reflow_word_per_line_pdf(text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _split_inline_bullets(block: str) -> List[str]:
    """Split a block where several '● item' entries share one line."""
    lines: List[str] = []
    for raw_ln in (block or "").split("\n"):
        raw_ln = raw_ln.strip()
        if not raw_ln:
            continue
        # Split on bullet characters that start a new ingredient
        parts = re.split(r"(?=[●•\*\u2022])", raw_ln)
        for part in parts:
            part = part.strip()
            if part:
                lines.append(part)
    return lines


def _split_inline_steps(block: str) -> List[str]:
    """Split '1. foo 2. bar 3. baz' jammed onto one or few lines."""
    text = re.sub(r"\s+", " ", (block or "").strip())
    if not text:
        return []
    # Prefer numbered step boundaries
    parts = re.split(r"(?=(?:^|\s)\d{1,2}[\.\)]\s+)", text)
    out: List[str] = []
    for part in parts:
        part = part.strip()
        part = re.sub(r"^\d{1,2}[\.\)]\s*", "", part).strip()
        if part:
            out.append(part)
    return out if out else ([text] if text else [])


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip(" -–—\t")
    # Reflowed PDFs often glue the blurb onto the title:
    # "Overnight Oats A high-volume, protein-dominant version..."
    cut = re.split(r"\s+(?=A\s+(?:high|simple|quick|protein|low|large)\b)", title, maxsplit=1)
    if len(cut) == 2 and len(cut[0]) >= 8:
        title = cut[0]
    cut = re.split(r"(?<=[a-z])\.\s+(?=[A-Z])", title, maxsplit=1)
    if len(cut) == 2 and len(cut[0]) >= 8:
        title = cut[0]
    return title.strip(" -–—\t")


# OCR / UI chrome that must never become meal titles (e.g. "window" snack).
_TITLE_JUNK = {
    "window",
    "windows",
    "page",
    "pages",
    "day",
    "days",
    "week",
    "weekly",
    "schedule",
    "snack",
    "snacks",
    "dinner",
    "dinners",
    "breakfast",
    "lunch",
    "meal",
    "meals",
    "plan",
    "kcal",
    "macros",
    "macro",
    "method",
    "ingredients",
    "servings",
    "serving",
    "total",
    "notes",
    "tip",
    "tips",
    "combined",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
}

_GENERIC_INSTRUCTIONS = {
    "prepare and serve as described in the meal plan.",
    "prepare and serve as described in the meal plan",
    "prepare and serve as described in the plan.",
    "prepare and serve as described in the plan",
}

_INGREDIENT_JUNK_NAMES = {
    "method",
    "methods",
    "macros",
    "macro",
    "ingredients",
    "ingredient",
    "instructions",
    "instruction",
    "directions",
    "steps",
    "step",
    "servings",
    "serving",
    "one",
    "two",
    "three",
    "as described",
}


def _is_plausible_meal_title(title: str) -> bool:
    """Reject OCR chrome / macro lines / single junk tokens like 'window'."""
    cleaned = _clean_title(title)
    if not cleaned:
        return False
    # Macro summary lines mis-parsed as titles (snack-window → "window macros: 438 kcal…")
    if re.search(r"\d+\s*kcal", cleaned, flags=re.I):
        return False
    if re.match(r"(?i)window\b", cleaned):
        return False
    if re.search(r"(?i)\bmacros?\b", cleaned) and re.search(
        r"(?i)\b(protein|carb|fat|kcal)\b", cleaned
    ):
        return False
    letters = re.sub(r"[^A-Za-z]+", "", cleaned)
    if len(letters) < 4:
        return False
    key = re.sub(r"[^a-z0-9\s]+", "", cleaned.lower()).strip()
    key = re.sub(r"\s+", " ", key)
    if key in _TITLE_JUNK:
        return False
    if re.fullmatch(r"(snack|dinner|breakfast|lunch)\s*\d*", key):
        return False
    tokens = [t for t in re.split(r"\s+", key) if t]
    if not tokens:
        return False
    if all(t in _TITLE_JUNK or t.isdigit() for t in tokens):
        return False
    return True


def _is_real_ingredient(item: Optional[Dict[str, str]]) -> bool:
    if not item:
        return False
    name = re.sub(r"\s+", " ", (item.get("name") or "").strip())
    if len(name) < 2:
        return False
    low = name.lower().rstrip(".")
    if low in _INGREDIENT_JUNK_NAMES or low in _TITLE_JUNK:
        return False
    if re.match(r"^\d{1,2}[\.\)]\s+", name):
        return False
    if re.match(r"^(method|macros|ingredients|instructions)\b", low):
        return False
    return True


def _is_generic_instruction(text: str) -> bool:
    t = re.sub(r"\s+", " ", (text or "").strip().lower()).rstrip(".")
    return t in {g.rstrip(".") for g in _GENERIC_INSTRUCTIONS} or t.startswith(
        "prepare and serve as described"
    )


def _meal_body_is_usable(
    ingredients: List[Dict[str, str]],
    instructions: List[str],
    nutrition: Optional[Dict[str, Optional[int]]] = None,
) -> bool:
    """Drop empty OCR stubs that would create hollow recipe cards."""
    real_ings = [i for i in ingredients if _is_real_ingredient(i)]
    real_steps = [
        s for s in (instructions or []) if (s or "").strip() and not _is_generic_instruction(s)
    ]
    cals = (nutrition or {}).get("calories")
    has_macros = isinstance(cals, int) and cals > 0
    if real_ings:
        return True
    if has_macros and real_steps:
        return True
    return False


def _parse_macros(block: str) -> Dict[str, Optional[int]]:
    """Parse lines like: 544 kcal | 42.1 g protein | 66.8 g carbohydrate | 12.8 g fat"""
    out = {"calories": None, "protein": None, "carbs": None, "fat": None}
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*kcal.*?(\d+(?:\.\d+)?)\s*g\s*protein.*?(\d+(?:\.\d+)?)\s*g\s*carb.*?(\d+(?:\.\d+)?)\s*g\s*fat",
        block,
        flags=re.I | re.S,
    )
    if not m:
        # Try looser pieces
        cal = re.search(r"(\d+(?:\.\d+)?)\s*kcal", block, flags=re.I)
        pro = re.search(r"(\d+(?:\.\d+)?)\s*g\s*protein", block, flags=re.I)
        carb = re.search(r"(\d+(?:\.\d+)?)\s*g\s*carb", block, flags=re.I)
        fat = re.search(r"(\d+(?:\.\d+)?)\s*g\s*fat", block, flags=re.I)
        if cal:
            out["calories"] = int(round(float(cal.group(1))))
        if pro:
            out["protein"] = int(round(float(pro.group(1))))
        if carb:
            out["carbs"] = int(round(float(carb.group(1))))
        if fat:
            out["fat"] = int(round(float(fat.group(1))))
        return out
    out["calories"] = int(round(float(m.group(1))))
    out["protein"] = int(round(float(m.group(2))))
    out["carbs"] = int(round(float(m.group(3))))
    out["fat"] = int(round(float(m.group(4))))
    return out


def _normalize_amount(amount: str) -> str:
    """Strip thousands separators: '1,400' → '1400'."""
    amount = (amount or "").strip()
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", amount):
        return amount.replace(",", "")
    return amount


def _parse_ingredient_line(line: str) -> Optional[Dict[str, str]]:
    line = line.strip()
    line = re.sub(r"^[●•\-\*\u2022]+\s*", "", line).strip()
    # Strip zero-width / PDF junk after bullets
    line = line.replace("\u200b", "").replace("\ufeff", "").strip()
    if not line or len(line) < 2:
        return None
    # Separators: em/en dash, colon, or spaced ASCII hyphen — never a glued hyphen
    # inside words like "5%-fat".
    sep = r"(?:[—–]|:|(?<!\S)-\s+|\s+-\s+)"
    # "Chicken breast — 140 g" / "0% Greek yoghurt: 300g" / "Olive oil — 8 g"
    m = re.match(
        rf"^(?P<name>.+?)\s*{sep}\s*(?P<amount>\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z%]+)?(?:\s+.*)?$",
        line,
    )
    if m:
        return {
            "name": re.sub(r"\s+", " ", m.group("name")).strip(),
            "amount": _normalize_amount(m.group("amount")),
            "unit": (m.group("unit") or "").strip(),
        }
    # "Paprika, garlic granules, salt and black pepper — as desired"
    m2 = re.match(rf"^(?P<name>.+?)\s*{sep}\s*(?P<rest>.+)$", line)
    if m2:
        rest = m2.group("rest").strip()
        if len(rest) > 40 or re.search(
            r"\b(seasonings|suitable|marinades|sauces|preparation|accounting)\b",
            f"{m2.group('name')} {rest}",
            flags=re.I,
        ):
            return None
        return {
            "name": re.sub(r"\s+", " ", m2.group("name")).strip(),
            "amount": rest,
            "unit": "",
        }
    return {"name": re.sub(r"\s+", " ", line).strip(), "amount": "", "unit": ""}


# Soft-wrapped PDF tip orphans that must never become shopping items
_SHOPPING_JUNK_NAMES = {
    "preparation",
    "significantly",
    "easier",
    "easier.",
    "added",
    "without",
    "accounting",
    "for",
    "them",
    "them.",
    "and",
    "can",
    "make",
    "are",
    "not",
    "to",
    "taste",
}


def _meal_type_from_heading(kind: str, index: Optional[int] = None) -> str:
    k = (kind or "").lower()
    if k.startswith("dinner"):
        return "Dinner"
    if k.startswith("breakfast"):
        return "Breakfast"
    if k.startswith("lunch"):
        return "Lunch"
    if k.startswith("snack"):
        # Keep distinguishable snack slots when numbered
        if index and index >= 1:
            return f"Snack {index}"
        m = re.search(r"(\d+)", kind)
        if m:
            return f"Snack {m.group(1)}"
        return "Snack"
    return kind.title() if kind else "Dinner"


def _days_from_served_line(line: str) -> List[int]:
    """'Served Monday, Tuesday and Friday' or 'Served every day' → day indexes 0=Mon."""
    low = line.lower()
    if "every day" in low or "each day" in low or "daily" in low:
        return list(range(7))
    found = []
    for name, idx in DAY_ALIASES.items():
        if re.search(rf"\b{re.escape(name)}\b", low):
            if idx not in found:
                found.append(idx)
    return found


@dataclass
class ParsedMeal:
    key: str
    title: str
    meal_type: str
    ingredients: List[Dict[str, str]] = field(default_factory=list)
    instructions: List[str] = field(default_factory=list)
    nutrition: Dict[str, Optional[int]] = field(default_factory=dict)
    description: str = ""
    servings: int = 1
    served_days: List[int] = field(default_factory=list)
    category: str = "Dinner"


@dataclass
class ParsedMealPlan:
    title: str = "Imported Meal Plan"
    daily_targets: str = ""
    meals: List[ParsedMeal] = field(default_factory=list)
    # schedule[day_index] = list of {meal_type, meal_key, title}
    schedule: List[List[Dict[str, str]]] = field(default_factory=list)
    shopping_list: List[Dict[str, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    parser: str = "structured"


def _clean_plan_title(title: str) -> str:
    """Keep the plan name; drop glued target / structure chrome from PDF reflow."""
    title = re.sub(r"\s+", " ", title or "").strip(" -–—\t")
    # "7-Day High-Protein Meal Plan Daily target: …" → stop before Daily target
    title = re.split(
        r"\s+(?=Daily\s+target\b)|(?=\s+\d[\d,]*\s*kcal\b)|(?=\s+Structure\b)",
        title,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" -–—\t")
    return title or "Imported Meal Plan"


def _clean_plan_targets(targets: str) -> str:
    """Keep kcal/protein target only — never trailing 'Structure:' UI leftovers."""
    targets = re.sub(r"\s+", " ", targets or "").strip(" -–—\t")
    if not targets:
        return ""
    # Drop everything from Structure / Weekly schedule onward
    targets = re.split(
        r"\bStructure\b|\bWeekly\s+schedule\b|\bMeal\s+breakdown\b|\bMeal\s+frequency\b",
        targets,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" -–—:\t")
    # Prefer a compact "Daily target: …" / "… kcal … protein" snippet
    m = re.search(
        r"(Daily\s+target\s*:\s*.{0,120}?)(?=\s+Structure\b|$)",
        targets,
        flags=re.I,
    )
    if m:
        return m.group(1).strip(" -–—:\t")
    m = re.search(
        r"(\d[\d,]*\s*kcal.{0,80}?\d[\d,]*\s*g\s*protein)",
        targets,
        flags=re.I,
    )
    if m:
        return m.group(1).strip()
    return targets[:160].strip()


def plan_source_note(title: str, targets: str = "") -> str:
    """Optional short attribution shown on imported recipe cards."""
    title = _clean_plan_title(title)
    targets = _clean_plan_targets(targets)
    if targets:
        return f"From: {title}. {targets}"
    return f"From: {title}" if title else ""


def _extract_plan_meta(text: str) -> Tuple[str, str]:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    title = "Imported Meal Plan"
    targets = ""
    for i, ln in enumerate(lines[:12]):
        if re.search(r"meal\s*plan", ln, flags=re.I) or re.search(r"\d+\s*[-–]?\s*day", ln, flags=re.I):
            title = ln
            break
        if i == 0 and len(ln) > 8:
            title = ln
    for ln in lines[:20]:
        if re.search(r"\bkcal\b|\bdaily\s+target\b|\d+\s*g\s*protein", ln, flags=re.I):
            targets = ln
            break
    return _clean_plan_title(title), _clean_plan_targets(targets)


def _split_meal_sections(text: str) -> List[Tuple[str, str, str]]:
    """
    Return list of (kind_label, title, body) for DINNER/SNACK/BREAKFAST/LUNCH sections.

    Supports:
      DINNER 1 — Air-Fryer Chicken…
      SNACK 1: Banana-Chip Yoghurt Crunch
      Lunch\\nCarrot-Cake Protein Overnight Oats
    Rejects glued false positives like "snack-window macros: …".
    """
    body = text
    m = re.search(r"meal\s+breakdown", text, flags=re.I)
    if m:
        body = text[m.end() :]
    stop = re.search(r"\n\s*shopping\s+list\b|\n\s*preparation\s+tip\b", body, flags=re.I)
    if stop:
        body = body[: stop.start()]

    # Em/en dash or colon only — never bare ASCII hyphen (breaks "snack-window").
    # Spaced ASCII hyphen "1 - Title" still allowed.
    inline = re.compile(
        r"(?P<label>(?:DINNER|SNACK|BREAKFAST|LUNCH)\s*\d*)\s*(?:[—–:]+|\s+-\s+)\s*(?P<title>[^\n]+)",
        flags=re.I,
    )
    # "Lunch\\nTitle" / "Dinner\\nTitle" when title is on the next line
    multiline = re.compile(
        r"(?P<label>(?:DINNER|BREAKFAST|LUNCH)(?:\s*\d+)?|SNACK\s*\d+)\s*\n\s*(?P<title>[A-Za-z][^\n]{2,90})",
        flags=re.I,
    )

    hits: List[Tuple[int, int, str, str]] = []
    for match in inline.finditer(body):
        title = _clean_title(match.group("title"))
        if _is_plausible_meal_title(title):
            hits.append((match.start(), match.end(), match.group("label").strip(), title))

    for match in multiline.finditer(body):
        # Skip if this heading overlaps an inline match (e.g. Dinner 1: already caught)
        if any(not (match.end() <= s or match.start() >= e) for s, e, *_ in hits):
            continue
        title = _clean_title(match.group("title"))
        # Skip section chrome like "Snacks" / "Dinners" picked as titles
        if not _is_plausible_meal_title(title):
            continue
        if re.match(r"(?i)^(ingredients|method|macros|served)\b", title):
            continue
        hits.append((match.start(), match.end(), match.group("label").strip(), title))

    hits.sort(key=lambda h: h[0])
    # De-dupe identical start positions (prefer longer/inline)
    deduped: List[Tuple[int, int, str, str]] = []
    for h in hits:
        if deduped and h[0] == deduped[-1][0]:
            continue
        # Drop a hit fully contained in previous heading span
        if deduped and h[0] < deduped[-1][1]:
            continue
        deduped.append(h)

    sections: List[Tuple[str, str, str]] = []
    for i, (start, end, label, title) in enumerate(deduped):
        body_end = deduped[i + 1][0] if i + 1 < len(deduped) else len(body)
        sections.append((label, title, body[end:body_end].strip()))
    return sections


def _parse_meal_body(body: str) -> Tuple[List[Dict[str, str]], List[str], Dict[str, Optional[int]], str, List[int], int]:
    served = []
    servings = 1
    description_bits = []
    ingredients: List[Dict[str, str]] = []
    instructions: List[str] = []
    nutrition: Dict[str, Optional[int]] = {}

    served_m = re.search(r"served\s+[^\n]+", body, flags=re.I)
    if served_m:
        served = _days_from_served_line(served_m.group(0))

    serv_m = re.search(
        r"ingredients\s*[—–\-:]?\s*(?:(\d+)|one|a)\s*serv",
        body,
        flags=re.I,
    )
    if serv_m:
        servings = int(serv_m.group(1)) if serv_m.group(1) else 1

    # Ingredients block (bullets may share the Ingredients line after PDF reflow)
    ing_m = re.search(
        r"ingredients\b(?:[^\n●•\u2022]{0,60})?(?P<block>.*?)(?=\bmethod\b|\bmacros\b|\Z)",
        body,
        flags=re.I | re.S,
    )
    if ing_m:
        for ln in _split_inline_bullets(ing_m.group("block")):
            item = _parse_ingredient_line(ln)
            if _is_real_ingredient(item):
                ingredients.append(item)

    # Method block (numbered steps may share the Method line after PDF reflow)
    method_m = re.search(
        r"method\b\s*(?P<block>.*?)(?=\bmacros\b|\Z)",
        body,
        flags=re.I | re.S,
    )
    if method_m:
        instructions = _split_inline_steps(method_m.group("block"))
        instructions = [
            s for s in instructions if s and not s.lower().startswith("macros")
        ]

    # "Macros" / "Macros:" may share the line with numbers
    macros_m = re.search(r"macros\s*:?\s*(?P<block>.{0,400})", body, flags=re.I | re.S)
    if macros_m:
        nutrition = _parse_macros(macros_m.group("block"))
        after = macros_m.group("block")
        note_lines = []
        for ln in after.split("\n")[1:]:
            if ln.strip() and not re.search(r"kcal|protein|carb|fat", ln, flags=re.I):
                note_lines.append(ln.strip())
        if note_lines:
            description_bits.extend(note_lines[:2])

    return ingredients, instructions, nutrition, " ".join(description_bits).strip(), served, servings


def _fold_alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _title_mentioned_in_blob(title: str, blob_fold: str) -> bool:
    """Fuzzy: meal title appears in a weekly-schedule day blob (PDF-wrapped)."""
    if not title or not blob_fold:
        return False
    folded = _fold_alnum(title)
    if len(folded) >= 8 and folded in blob_fold:
        return True

    stop = {
        "and", "with", "the", "for", "potatoes", "potato", "vegetables", "vegetable",
        "air", "fryer", "airfryer", "dinner", "lunch", "snack", "meal", "bowl", "peas",
        "cauliflower", "broccoli", "carrots", "carrot",
    }
    tokens = [
        t
        for t in re.split(r"[^a-z0-9]+", title.lower())
        if len(t) >= 3 and t not in stop
    ]
    if not tokens:
        return False

    def _token_in_blob(tok: str) -> bool:
        if tok in blob_fold:
            return True
        # Schedule shortens plurals: "meatballs" ↔ "meatball dinner"
        if tok.endswith("s") and len(tok) > 4 and tok[:-1] in blob_fold:
            return True
        if (tok + "s") in blob_fold:
            return True
        return False

    # Require protein / dish-defining tokens when present (stops chicken matching
    # salmon days just because both say "air-fryer").
    proteinish = {
        "chicken", "salmon", "beef", "turkey", "pork", "cod", "tuna", "prawn", "shrimp",
        "lamb", "meatball", "meatballs", "mince", "tofu", "skyr", "yoghurt", "yogurt",
        "oats", "overnight", "pear", "banana", "almond", "nut", "bar",
    }
    must = [t for t in tokens if t in proteinish or t.rstrip("s") in proteinish]
    if must and not any(_token_in_blob(t) for t in must):
        return False

    hits = sum(1 for t in tokens if _token_in_blob(t))
    if len(tokens) <= 2:
        return hits == len(tokens)
    return hits >= max(2, len(tokens) - 1)


def _infer_served_days_from_schedule(text: str, meals: List[ParsedMeal]) -> None:
    """Fill empty served_days from the weekly schedule grid when 'Served …' lines are absent."""
    m = re.search(
        r"weekly\s+schedule(.*?)(?=\n\s*meal\s+breakdown|\n\s*dinner\s*\d+\s*[—–\-: ]|\Z)",
        text,
        flags=re.I | re.S,
    )
    if not m:
        return
    block = m.group(1)
    # Split into day blobs
    day_pat = re.compile(
        r"(?P<day>Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
        flags=re.I,
    )
    starts = [(match.start(), DAY_ALIASES[match.group("day").lower()]) for match in day_pat.finditer(block)]
    if not starts:
        return
    day_blobs: Dict[int, str] = {}
    for i, (pos, day_idx) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(block)
        day_blobs[day_idx] = _fold_alnum(block[pos:end])

    for meal in meals:
        if meal.served_days:
            continue
        found = [
            d for d, blob in day_blobs.items() if _title_mentioned_in_blob(meal.title, blob)
        ]
        if found:
            meal.served_days = sorted(found)


def _parse_shopping_list(text: str) -> List[Dict[str, str]]:
    m = re.search(
        r"shopping\s+list\s*\n(?P<block>.*?)(?=\n\s*preparation\s+tip\b|\Z)",
        text,
        flags=re.I | re.S,
    )
    if not m:
        return []
    items = []
    for ln in _split_inline_bullets(m.group("block")):
        raw = (ln or "").strip()
        if not raw:
            continue
        had_bullet = bool(re.match(r"^[●•\*\u2022\-]", raw))
        # Skip prose tips embedded in the shopping section
        if re.search(
            r"frozen|seasonings can|perfectly suitable|calorie-containing|"
            r"marinades|provided calorie|can make\b",
            raw,
            flags=re.I,
        ):
            continue
        # Soft-wrapped tip orphans (no bullet, no "name — amount")
        cleaned = re.sub(r"^[●•\*\u2022\-]+\s*", "", raw).strip()
        if not had_bullet and not re.search(r"[—–\-]\s*(?:\d|as\s+desired)", cleaned, flags=re.I):
            continue
        item = _parse_ingredient_line(raw)
        if not item or not item.get("name"):
            continue
        name_key = item["name"].lower().strip()
        if name_key in _SHOPPING_JUNK_NAMES:
            continue
        # Spice bullets like "● Paprika" are fine; bare tip words are not
        if not item.get("amount") and not had_bullet:
            continue
        if len(name_key) < 3 and not item.get("amount"):
            continue
        items.append(item)
    return items


def _parse_weekly_schedule_grid(text: str) -> Dict[int, List[Dict[str, str]]]:
    """
    Best-effort parse of:
      Day Snack 1 Snack 2 Dinner
      Monday Greek Yoghurt... Banana & Almond... Air-Fryer Chicken...
    Returns day_index -> [{meal_type, title}]
    """
    schedule: Dict[int, List[Dict[str, str]]] = {i: [] for i in range(7)}
    # Find schedule section
    m = re.search(r"weekly\s+schedule(.*?)(?=\n\s*meal\s+breakdown|\n\s*dinner\s*\d+\s*[—–\-: ]|\Z)", text, flags=re.I | re.S)
    if not m:
        return schedule
    block = m.group(1)
    # Header columns
    header = None
    for ln in block.split("\n"):
        if re.search(r"\bday\b", ln, flags=re.I) and re.search(r"snack|dinner|lunch|breakfast", ln, flags=re.I):
            header = ln
            break
    cols = ["Snack 1", "Snack 2", "Dinner"]
    if header:
        # Detect ordered meal columns after Day
        found_cols = re.findall(r"(Snack\s*\d+|Breakfast|Lunch|Dinner)", header, flags=re.I)
        if found_cols:
            cols = []
            for c in found_cols:
                snack_m = re.match(r"snack\s*(\d+)", c, flags=re.I)
                if snack_m:
                    cols.append(f"Snack {snack_m.group(1)}")
                else:
                    cols.append(c.title())

    # Day rows may be wrapped across lines in PDF text — join until next day name
    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
    # Drop header-ish lines
    filtered = []
    for ln in lines:
        if re.match(r"^day\b", ln, flags=re.I):
            continue
        if re.match(r"^snack\b", ln, flags=re.I) and "dinner" in ln.lower():
            continue
        filtered.append(ln)

    current_day = None
    buf = []
    rows = []

    def flush():
        nonlocal buf, current_day
        if current_day is not None and buf:
            rows.append((current_day, " ".join(buf)))
        buf = []

    for ln in filtered:
        day_m = re.match(
            r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b[ \t]*(.*)$",
            ln,
            flags=re.I,
        )
        if day_m:
            flush()
            current_day = DAY_ALIASES[day_m.group(1).lower()]
            rest = day_m.group(2).strip()
            buf = [rest] if rest else []
        elif current_day is not None:
            buf.append(ln)
    flush()

    # Without reliable column separators, schedule grid is weak; meal "Served ..." lines are authoritative.
    # Still attempt crude split using known meal titles later.
    return schedule


def parse_meal_plan_text(raw: str) -> ParsedMealPlan:
    text = _norm_ws(raw or "")
    if len(text.strip()) < 40:
        raise ValueError("Meal plan text is too short to parse")

    title, targets = _extract_plan_meta(text)
    plan = ParsedMealPlan(title=title, daily_targets=targets, parser="structured")
    plan.shopping_list = _parse_shopping_list(text)

    sections = _split_meal_sections(text)
    if not sections:
        raise ValueError(
            "Could not find meal sections (expected headings like "
            "'DINNER 1 — …' or 'SNACK 1 — …'). Try a clearer PDF export or paste the meal breakdown."
        )

    title_index: Dict[str, str] = {}  # lower title -> key
    for label, meal_title, body in sections:
        if not _is_plausible_meal_title(meal_title):
            continue
        ingredients, instructions, nutrition, desc, served, servings = _parse_meal_body(body)
        if not _meal_body_is_usable(ingredients, instructions, nutrition):
            continue
        idx_m = re.search(r"(\d+)", label)
        idx = int(idx_m.group(1)) if idx_m else None
        meal_type = _meal_type_from_heading(re.sub(r"\s+", " ", label), idx)
        category = "Snack" if meal_type.startswith("Snack") else meal_type
        key = re.sub(r"[^a-z0-9]+", "-", f"{label}-{meal_title}".lower()).strip("-")
        # Dedupe identical titles
        tkey = meal_title.lower()
        if tkey in title_index:
            # Merge served days onto existing
            existing = next(m for m in plan.meals if m.key == title_index[tkey])
            for d in served:
                if d not in existing.served_days:
                    existing.served_days.append(d)
            continue

        meal = ParsedMeal(
            key=key,
            title=meal_title,
            meal_type=meal_type,
            ingredients=ingredients,
            instructions=instructions or ["Prepare and serve as described in the meal plan."],
            nutrition=nutrition,
            # Keep meal-body blurb only. Optional "From: <plan> …" attribution is
            # applied at import time when the user opts in (include_source_note).
            description=desc or "",
            servings=servings,
            served_days=served,
            category=category,
        )
        plan.meals.append(meal)
        title_index[tkey] = key

    # When meals lack "Served …" lines, map titles onto the weekly schedule grid
    _infer_served_days_from_schedule(text, plan.meals)

    # Build schedule from served_days (authoritative for this PDF style)
    schedule: List[List[Dict[str, str]]] = [[] for _ in range(7)]
    for meal in plan.meals:
        if meal.served_days:
            days = meal.served_days
        elif meal.category in {"Snack", "Lunch", "Breakfast"}:
            # Daily staples often omit Served lines
            days = list(range(7))
        else:
            # Don't spray dinners onto every day when the grid didn't match
            days = []
        for d in days:
            if 0 <= d < 7:
                schedule[d].append(
                    {
                        "meal_type": meal.meal_type if not meal.meal_type.startswith("Snack") else "Snack",
                        "meal_key": meal.key,
                        "title": meal.title,
                        "slot_label": meal.meal_type,
                    }
                )
    # Stable order: Breakfast, Lunch, Dinner, Snack
    order = {"Breakfast": 0, "Lunch": 1, "Dinner": 2, "Snack": 3}
    for d in range(7):
        schedule[d].sort(key=lambda x: (order.get(x["meal_type"], 9), x.get("slot_label") or "", x["title"]))
    plan.schedule = schedule

    tip = re.search(r"preparation\s+tip\s*\n(?P<body>.{0,800})", text, flags=re.I | re.S)
    if tip:
        tip_text = re.sub(r"\s+", " ", tip.group("body")).strip()
        if tip_text:
            plan.notes.append(tip_text[:500])

    if not plan.meals:
        raise ValueError("No meals could be parsed from the document")

    return plan


def parsed_plan_to_dict(plan: ParsedMealPlan) -> Dict[str, Any]:
    return {
        "title": plan.title,
        "daily_targets": plan.daily_targets,
        "parser": plan.parser,
        "notes": plan.notes,
        "meals": [
            {
                "key": m.key,
                "title": m.title,
                "meal_type": m.meal_type,
                "category": m.category,
                "servings": m.servings,
                "description": m.description,
                "ingredients": m.ingredients,
                "instructions": m.instructions,
                "nutrition": m.nutrition,
                "served_days": m.served_days,
            }
            for m in plan.meals
        ],
        "schedule": plan.schedule,
        "shopping_list": plan.shopping_list,
    }


def plan_meals_as_recipes(
    plan: ParsedMealPlan,
    *,
    include_source_note: bool = False,
) -> List[Dict[str, Any]]:
    """Convert structured meal-plan meals into recipe dicts for recipe-PDF import."""
    note = (
        plan_source_note(plan.title, plan.daily_targets)
        if include_source_note
        else ""
    )
    recipes: List[Dict[str, Any]] = []
    for m in plan.meals:
        tags = ["imported-meal-plan"]
        if m.meal_type.startswith("Snack"):
            tags.append("snack")
        description = (m.description or "").strip()
        if note:
            description = f"{note}\n\n{description}".strip() if description else note
        recipes.append(
            {
                "title": m.title,
                "description": description,
                "ingredients": m.ingredients,
                "instructions": m.instructions,
                "prep_time": 10,
                "cook_time": 25 if m.category == "Dinner" else 5,
                "servings": m.servings or 1,
                "category": m.category if m.category in {
                    "Breakfast", "Lunch", "Dinner", "Dessert", "Appetizer",
                    "Snack", "Beverage", "Meal Pack", "Other",
                } else ("Snack" if m.meal_type.startswith("Snack") else "Dinner"),
                "tags": tags,
                "image_url": "",
                "nutrition": m.nutrition or {},
            }
        )
    return recipes


def extract_text_from_pdf_bytes(data: bytes) -> str:
    """Extract PDF text; prefer PyMuPDF (layout-stable), fall back to pypdf."""
    text = ""
    try:
        import pymupdf

        doc = pymupdf.open(stream=data, filetype="pdf")
        try:
            text = "\n".join(page.get_text() for page in doc)
        finally:
            doc.close()
    except Exception:
        text = ""

    if len(text.strip()) < 40:
        try:
            from pypdf import PdfReader
            import io

            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except ImportError as e:
            raise ValueError(
                "PDF support is not installed on the server (pymupdf/pypdf). "
                "Paste the plan text instead."
            ) from e

    if len(text.strip()) < 40:
        raise ValueError("PDF contained almost no extractable text (it may be a scanned image).")
    return text
