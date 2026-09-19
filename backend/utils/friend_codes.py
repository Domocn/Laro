"""Friend / referral codes: food word + number (e.g. TOMATO 44)."""
from __future__ import annotations

import random
import re

# Readable food words (keep each word ≤ ~12 chars so " WORD NN" fits VARCHAR(20))
FOOD_WORDS = (
    # Produce
    "TOMATO",
    "POTATO",
    "CARROT",
    "CELERY",
    "SPINACH",
    "BROCCOLI",
    "CABBAGE",
    "PEPPER",
    "CHARD",
    "BEET",
    "RADISH",
    "TURNIP",
    "SQUASH",
    "ZUCCHINI",
    "CUCUMBER",
    "AVOCADO",
    "EGGPLANT",
    "ASPARAGUS",
    "ARTICHOKE",
    "LEEK",
    "SHALLOT",
    "SCALLION",
    "WATERCRESS",
    "ARUGULA",
    "ENDIVE",
    "FENNEL",
    "OKRA",
    "YAM",
    "PARSNIP",
    "RUTABAGA",
    "KALE",
    "CORN",
    "PEA",
    "BEAN",
    "LENTIL",
    "CHICKPEA",
    # Fruit
    "APPLE",
    "BANANA",
    "ORANGE",
    "LEMON",
    "LIME",
    "GRAPE",
    "BERRY",
    "CHERRY",
    "PEACH",
    "PLUM",
    "PEAR",
    "MANGO",
    "PAPAYA",
    "KIWI",
    "FIG",
    "DATE",
    "APRICOT",
    "COCONUT",
    "PINEAPPLE",
    "MELON",
    "RHUBARB",
    "POMEGRANATE",
    "PASSIONFRUIT",
    "GUAVA",
    "LYCHEE",
    "PERSIMMON",
    "CRANBERRY",
    "BLUEBERRY",
    "RASPBERRY",
    "BLACKBERRY",
    "STRAWBERRY",
    # Herbs & spices
    "BASIL",
    "MINT",
    "THYME",
    "SAGE",
    "DILL",
    "PARSLEY",
    "CILANTRO",
    "ROSEMARY",
    "OREGANO",
    "TARRAGON",
    "CHIVE",
    "HERB",
    "SPICE",
    "SAFFRON",
    "PAPRIKA",
    "CUMIN",
    "CORIANDER",
    "CARDAMOM",
    "CLOVE",
    "NUTMEG",
    "CINNAMON",
    "TURMERIC",
    "GINGER",
    "GARLIC",
    "ONION",
    "CHILI",
    "HORSERADISH",
    "WASABI",
    "VANILLA",
    "ANISE",
    "FENUGREEK",
    "SUMAC",
    "HARISSA",
    "BERBERE",
    # Proteins
    "CHICKEN",
    "TURKEY",
    "DUCK",
    "BEEF",
    "PORK",
    "LAMB",
    "VEAL",
    "BACON",
    "HAM",
    "SAUSAGE",
    "SALMON",
    "TUNA",
    "COD",
    "TROUT",
    "HADDOCK",
    "MACKEREL",
    "SARDINE",
    "ANCHOVY",
    "SHRIMP",
    "PRAWN",
    "CRAB",
    "LOBSTER",
    "SCALLOP",
    "MUSSEL",
    "CLAM",
    "OYSTER",
    "TOFU",
    "TEMPEH",
    "SEITAN",
    "EGG",
    # Dairy & pantry
    "CHEESE",
    "YOGURT",
    "CREAM",
    "BUTTER",
    "MILK",
    "GHEE",
    "HONEY",
    "MAPLE",
    "SUGAR",
    "SALT",
    "FLOUR",
    "RICE",
    "PASTA",
    "NOODLE",
    "QUINOA",
    "BARLEY",
    "OAT",
    "WHEAT",
    "RYE",
    "BULGUR",
    "COUSCOUS",
    "POLENTA",
    "GRITS",
    "YEAST",
    "VINEGAR",
    "MUSTARD",
    "KETCHUP",
    "MAYO",
    "TAHINI",
    "MISO",
    "NORI",
    "OLIVE",
    "CAPER",
    "PICKLE",
    "CHUTNEY",
    "RELISH",
    "JAM",
    "COCOA",
    "CHOCOLATE",
    # Dishes & formats
    "SOUP",
    "STEW",
    "CURRY",
    "BROTH",
    "SALAD",
    "SANDWICH",
    "BURGER",
    "WRAP",
    "TACO",
    "BURRITO",
    "NACHO",
    "QUESADILLA",
    "PIZZA",
    "CALZONE",
    "RISOTTO",
    "GNOCCHI",
    "LASAGNA",
    "RAMEN",
    "UDON",
    "SOBA",
    "PHO",
    "DUMPLING",
    "WONTON",
    "GYOZA",
    "BIBIMBAP",
    "KIMCHI",
    "BULGOGI",
    "SUSHI",
    "SASHIMI",
    "TEMPURA",
    "TERIYAKI",
    "SATAY",
    "PADTHAI",
    "BIRYANI",
    "DAL",
    "NAAN",
    "SAMOSA",
    "FALAFEL",
    "HUMMUS",
    "SHAWARMA",
    "KEBAB",
    "TAGINE",
    "PAELLA",
    "GAZPACHO",
    "TORTILLA",
    "EMPANADA",
    "AREPA",
    "POKE",
    "BOWL",
    "SKILLET",
    "CASSEROLE",
    "GRATIN",
    "TART",
    "PIE",
    "CAKE",
    "COOKIE",
    "BROWNIE",
    "MUFFIN",
    "SCONE",
    "BREAD",
    "BAGEL",
    "BUN",
    "CROISSANT",
    "BRIOCHE",
    "PRETZEL",
    "WAFFLE",
    "PANCAKE",
    "CREPE",
    "TOAST",
    "GRANOLA",
    "PORRIDGE",
    "SMOOTHIE",
    "LATTE",
    "ESPRESSO",
    "MOCHA",
    "MATCHA",
    "BOBA",
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
