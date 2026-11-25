"""
Keyword-based grocery aisle categorizer (ported from Android GroceryCategorizer).
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional

# display name -> (sort_order, keywords)
AISLE_DATA: list[tuple[str, int, list[str]]] = [
    ("Produce", 1, [
        "apple", "banana", "orange", "lemon", "lime", "grape", "strawberry", "blueberry",
        "raspberry", "mango", "pineapple", "watermelon", "cantaloupe", "peach", "pear",
        "plum", "cherry", "avocado", "tomato", "potato", "onion", "garlic", "ginger",
        "carrot", "celery", "broccoli", "cauliflower", "spinach", "lettuce", "kale",
        "cabbage", "cucumber", "zucchini", "squash", "bell pepper", "jalapeno", "mushroom",
        "corn", "asparagus", "eggplant", "beet", "radish", "sweet potato", "shallot",
        "scallion", "cilantro", "parsley", "basil", "mint", "dill", "thyme", "rosemary",
        "fruit", "vegetable", "salad", "greens", "herb",
    ]),
    ("Bakery", 2, [
        "bread", "bagel", "croissant", "muffin", "donut", "doughnut", "cake", "pie",
        "pastry", "roll", "bun", "loaf", "baguette", "sourdough", "pita", "naan",
        "tortilla", "wrap", "brioche", "garlic bread", "taco shell",
    ]),
    ("Dairy", 3, [
        "milk", "cheese", "yogurt", "butter", "cream", "sour cream", "cottage cheese",
        "cream cheese", "mozzarella", "cheddar", "parmesan", "feta", "ricotta",
        "half and half", "whipping cream", "heavy cream", "egg", "eggs", "ghee",
    ]),
    ("Meat & Seafood", 4, [
        "chicken", "beef", "pork", "lamb", "turkey", "duck", "steak", "ground beef",
        "bacon", "sausage", "ham", "prosciutto", "salami", "ribs", "shrimp", "salmon",
        "tuna", "cod", "tilapia", "crab", "lobster", "scallop", "fish", "seafood", "meat",
    ]),
    ("Deli", 5, [
        "deli", "lunch meat", "sliced turkey", "sliced ham", "roast beef", "pastrami",
        "rotisserie",
    ]),
    ("Frozen", 6, [
        "frozen", "ice cream", "gelato", "sorbet", "popsicle", "freezer",
    ]),
    ("Pasta & Grains", 7, [
        "pasta", "spaghetti", "penne", "rigatoni", "fettuccine", "macaroni", "lasagna",
        "noodle", "ramen", "rice", "quinoa", "couscous", "barley", "farro", "oat",
    ]),
    ("Canned Goods", 8, [
        "canned", "tomato sauce", "tomato paste", "tomato purée", "tomato puree", "passata",
        "diced tomato", "crushed tomato", "chopped tomatoes", "tinned", "tin of",
        "soup", "broth", "stock", "coconut milk", "chickpea", "black bean", "kidney bean",
    ]),
    ("Condiments & Sauces", 9, [
        "ketchup", "mustard", "mayonnaise", "mayo", "hot sauce", "salsa", "soy sauce",
        "teriyaki", "worcestershire", "bbq", "barbecue", "vinegar", "olive oil",
        "vegetable oil", "canola oil", "sesame oil", "dressing", "honey", "maple syrup",
        "jam", "jelly", "peanut butter", "tahini", "curry paste", "pesto",
    ]),
    ("Baking", 10, [
        "flour", "sugar", "brown sugar", "powdered sugar", "baking soda", "baking powder",
        "yeast", "vanilla", "cocoa", "cornstarch", "frosting", "icing",
    ]),
    ("Spices & Seasonings", 11, [
        "salt", "black pepper", "ground pepper", "pepper", "cinnamon", "cumin",
        "paprika", "oregano", "garlic powder", "onion powder", "chili powder",
        "cayenne", "turmeric", "curry", "nutmeg", "bay leaf", "spice", "seasoning",
    ]),
    ("Breakfast", 12, [
        "cereal", "oatmeal", "granola", "pancake", "waffle", "syrup",
    ]),
    ("Snacks", 13, [
        "chip", "chips", "popcorn", "pretzel", "cracker", "almond", "cashew",
        "peanut", "walnut", "trail mix", "granola bar", "candy", "chocolate", "snack",
    ]),
    ("Beverages", 14, [
        "water", "soda", "juice", "coffee", "tea", "wine", "beer", "sparkling",
        "seltzer", "almond milk", "oat milk", "soy milk",
    ]),
    ("Household", 15, [
        "paper towel", "toilet paper", "trash bag", "dish soap", "laundry",
        "aluminum foil", "plastic wrap", "ziplock",
    ]),
    ("Other", 99, []),
]

AISLE_SORT = {name: order for name, order, _ in AISLE_DATA}
AISLE_NAMES = [name for name, _order, _ in AISLE_DATA]


def categorize_grocery_item(item_name: str, overrides: Optional[Dict[str, str]] = None) -> str:
    """Return aisle display name for an ingredient/grocery item."""
    name = (item_name or "").lower().strip()
    if not name:
        return "Other"
    if overrides:
        # Prefer exact / substring override keys
        if name in overrides:
            return overrides[name]
        for key, aisle in overrides.items():
            if key and (key in name or name in key):
                return aisle
    # Most specific (longest) keyword wins across ALL aisles. First-match-in-aisle-order put
    # "coconut milk" in Dairy (via "milk"), "tomato purée" in Produce and "garlic bread" in Produce.
    best = None  # (keyword length, -sort order, aisle)
    for aisle_name, order, keywords in AISLE_DATA:
        if aisle_name == "Other":
            continue
        for keyword in keywords:
            if keyword in name:
                cand = (len(keyword), -order, aisle_name)
                if best is None or cand > best:
                    best = cand
    if best:
        return best[2]
    # Fallback: very short item names that are part of a keyword ("veg" in "vegetable")
    for aisle_name, _order, keywords in AISLE_DATA:
        for keyword in keywords:
            if len(name) > 2 and name in keyword:
                return aisle_name
    return "Other"


def aisle_sort_order(category_name: str) -> int:
    return AISLE_SORT.get(category_name or "Other", 99)


def assign_aisles(items: Iterable[dict], overrides: Optional[Dict[str, str]] = None) -> list[dict]:
    """Set category + sort_order on each item dict; return sorted list."""
    result = []
    for item in items:
        if overrides:
            category = categorize_grocery_item(item.get("name", ""), overrides)
        else:
            category = item.get("category") or categorize_grocery_item(item.get("name", ""))
        item = {**item, "category": category, "sort_order": aisle_sort_order(category)}
        result.append(item)
    result.sort(key=lambda i: (i.get("sort_order", 99), (i.get("name") or "").lower()))
    return result
