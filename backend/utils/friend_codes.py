"""Friend / referral codes: food word + number (e.g. TOMATO 44)."""
from __future__ import annotations

import random
import re
import string

# Short, readable food words (max length keeps codes under VARCHAR(20) with " NN")
FOOD_WORDS = (
    "TOMATO",
    "BASIL",
    "LEMON",
    "GARLIC",
    "ONION",
    "THYME",
    "MINT",
    "CHILI",
    "OLIVE",
    "RICE",
    "PASTA",
    "CURRY",
    "HONEY",
    "APPLE",
    "MANGO",
    "PEACH",
    "COCOA",
    "SAGE",
    "DILL",
    "CORN",
    "BEAN",
    "TOFU",
    "KALE",
    "SOUP",
    "STEW",
    "BREAD",
    "BUN",
    "COD",
    "TUNA",
    "LAMB",
    "HERB",
    "SPICE",
    "SAFFRON",
    "GINGER",
    "NORI",
    "MISO",
    "TOAST",
    "CAKE",
    "TACO",
    "RAMEN",
    "UDON",
    "PIZZA",
    "SUSHI",
    "BERRY",
    "GRAPE",
    "PLUM",
    "FIG",
    "DATE",
    "OAT",
    "WHEAT",
    "YEAST",
    "CREAM",
    "BUTTER",
    "CHIVE",
    "PARSLEY",
    "CUMIN",
    "PAPRIKA",
)


def generate_friend_code(_name: str = "") -> str:
    """Return a code like ``TOMATO 44`` (food word + 2-digit number)."""
    word = random.choice(FOOD_WORDS)
    number = random.randint(10, 99)
    return f"{word} {number}"


def normalize_friend_code(raw: str) -> str:
    """
    Canonical form for lookup: ``WORD NN`` (uppercase, single space).

    Accepts ``tomato 44``, ``TOMATO44``, ``tomato#44``, legacy ``CHEF#1234``.
    """
    if not raw or not str(raw).strip():
        return ""

    text = str(raw).strip().upper().replace("#", " ")
    text = " ".join(text.split())

    if " " in text:
        parts = text.split()
        if len(parts) >= 2:
            word = "".join(c for c in parts[0] if c.isalpha())
            digits = "".join(c for c in parts[1] if c.isdigit())
            if word and digits:
                return f"{word} {digits}"

    compact = "".join(c for c in text if c.isalnum())
    match = re.match(r"^([A-Z]+)(\d{2,4})$", compact)
    if match:
        return f"{match.group(1)} {match.group(2)}"

    return compact


def friend_code_lookup_variants(raw: str) -> list[str]:
    """Distinct stored forms to try (new food codes + legacy NAME#1234)."""
    variants: list[str] = []
    seen: set[str] = set()

    def add(code: str) -> None:
        if code and code not in seen:
            seen.add(code)
            variants.append(code)

    stripped = str(raw or "").strip().upper()
    add(stripped)
    normalized = normalize_friend_code(raw)
    add(normalized)
    if "#" in stripped:
        add(stripped.replace("#", " "))
    if normalized and " " in normalized:
        word, digits = normalized.split(" ", 1)
        add(f"{word}{digits}")
        add(f"{word}#{digits}")
    return variants
