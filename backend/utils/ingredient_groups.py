"""
Ingredient sections ("For the sauce", "For the topping").

An ingredient carries an optional ``group`` (the section it belongs to). Older imports wrote the
section into the name instead ("Basil Pesto: almonds or cashews"); ``split_ingredient_group``
splits that legacy prefix off with the same rule as the web app's ``splitIngredientGroup``
(src/lib/ingredientGroups.js), so the API always returns a clean name plus its group.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Tuple

GROUP_RE = re.compile(r"^([A-Za-z][^:\d]{1,40}?):\s+(\S.*)$")
MAX_GROUP_LEN = 80


def clean_group(value: Any) -> str:
    """A section name: single spaces, no trailing colon, capped."""
    text = " ".join(str(value or "").split()).rstrip(":").strip()
    return text[:MAX_GROUP_LEN]


def split_ingredient_group(name: Any) -> Tuple[str, str]:
    """("Basil Pesto", "almonds or cashews") for "Basil Pesto: almonds or cashews"; ("", name)
    when the name has no section prefix."""
    text = "" if name is None else str(name)
    m = GROUP_RE.match(text)
    if not m:
        return "", text
    return clean_group(m.group(1)), m.group(2)


def with_group(ing: Dict[str, Any]) -> Dict[str, Any]:
    """The ingredient dict with ``group`` set and the name clean. An explicit group wins; a name
    that repeats it as a prefix ("Sauce: tahini" in section "Sauce") loses the prefix. ``group``
    is only present when non-empty, so ungrouped lines keep their old shape."""
    out = dict(ing)
    group = clean_group(out.pop("group", None) or out.pop("section", None) or "")
    out.pop("section", None)
    name = "" if out.get("name") is None else str(out.get("name"))
    prefix, rest = split_ingredient_group(name)
    if prefix and (not group or prefix.lower() == group.lower()):
        group, name = group or prefix, rest
    out["name"] = name
    if group:
        out["group"] = group
    return out


def legacy_name(ing: Dict[str, Any]) -> str:
    """The name as older recipes stored it ("Group: name"): keeps signatures and confirmed-line
    keys written before sections existed matching."""
    name = str(ing.get("name") or "")
    group = clean_group(ing.get("group"))
    return f"{group}: {name}" if group and name.strip() else name

