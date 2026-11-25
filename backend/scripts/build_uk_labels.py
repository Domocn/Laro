#!/usr/bin/env python3
"""Build ``backend/data/foods/uk_labels.json``: UK supermarket label medians for processed foods.

For processed / branded foods the generic composition tables (CoFID, USDA) describe a
homemade or American recipe that differs from what UK shoppers actually buy (houmous is
~280 kcal on a UK label vs 166 for USDA "homemade"; tinned beans are labelled drained).
This script asks Open Food Facts for UK products in each category, filters out the
wrong kind of product (cooked pouches, ready meals, flavoured / reduced variants ...),
and stores the per-100 g median of every nutrient across >= MIN_PRODUCTS products.

Source: Open Food Facts, https://world.openfoodfacts.org - database under the Open
Database Licence (ODbL 1.0), contents under the Database Contents Licence (DbCL 1.0).
Attribution lives in ``backend/data/foods/NOTICE.md``.

Usage (network required; uses the Open Food Facts search service, takes a few minutes)::

    python backend/scripts/build_uk_labels.py            # writes backend/data/foods/uk_labels.json
    python backend/scripts/build_uk_labels.py --only houmous,kimchi --dry-run

Carbohydrate on a UK / EU label is *available* carbohydrate (fibre listed separately), the
same basis as the bundled CoFID dataset. Values are label averages for meal planning, not
medical advice.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "..", "data", "foods", "uk_labels.json")
SEARCH_URL = "https://search.openfoodfacts.org/search"  # Open Food Facts search service
USER_AGENT = "Laro-uk-labels/1.0 (app@laro.food)"
MIN_PRODUCTS = 8
PAGE_SIZE = 100
SEARCH_PAUSE_S = 3.0  # be gentle with the shared OFF search service

NUTRIENTS = {  # our key -> OFF nutriment key (per 100 g)
    "calories": "energy-kcal_100g",
    "protein": "proteins_100g",
    "carbs": "carbohydrates_100g",
    "fat": "fat_100g",
    "fiber": "fiber_100g",
    "sugars": "sugars_100g",
    "saturates": "saturated-fat_100g",
    "salt": "salt_100g",
}

# Product categories that are never a plain ingredient.
BAD_CATEGORIES = {
    "en:meals", "en:prepared-meals", "en:ready-meals", "en:microwave-meals", "en:sandwiches",
    "en:salads", "en:pizzas", "en:soups", "en:snacks", "en:crisps", "en:sweet-snacks",
}
# Words in a product name that mean it is cooked / a meal / a different product.
COMMON_EXCLUDE = r"\b(cooked|microwave|ready to eat|ready meal|pouch|steam|salad|sandwich|wrap kit|meal kit|snack pot|pot noodle)\b"

# Each spec: key (what lookups return), aliases (recipe wording that maps here), searches
# (OFF full-text queries, UK only), include (regex the product name must match), exclude
# (regex that rejects the product name), kcal (sane per-100 g range: rejects prepared-value
# labels and data-entry slips), cooked_only (only for lines that say tinned / drained / cooked).
SPECS: List[Dict[str, Any]] = [
    {"key": "houmous", "category": "condiment",
     "aliases": ["houmous", "hummus", "humus", "hommus", "houmus", "classic houmous", "classic hummus"],
     "searches": ["houmous", "hummus"],
     "include": r"\b(houmous|hummus|houmus)\b",
     "exclude": r"\b(reduced|light|lighter|lemon|coriander|pepper|chilli|caramel|chocolate|beetroot|pesto|"
                r"garlic|jalapeno|harissa|olive|chips|crisps|snack|dip pot|carrot|pots|topped|edamame|"
                r"sweet potato|piri|caramelised|onion|spicy|smoked|extra)\b",
     "kcal": (180, 400)},
    {"key": "kimchi", "category": "vegetable",
     "aliases": ["kimchi", "kimchee", "cabbage kimchi", "vegan kimchi"],
     "searches": ["kimchi"],
     "include": r"\bkimchi\b",
     "exclude": r"\b(noodle|ramen|rice|sauce|crisps|soup|seasoning|paste|dumpling|gyoza|fried|mayo|ketchup|"
                r"hot sauce|chips|stew|kimbap|pancake)\b",
     "kcal": (10, 90)},
    {"key": "dairy-free butter", "category": "dairy-alt",
     "aliases": ["dairy-free butter", "dairy free butter", "vegan butter", "plant butter", "plant-based butter",
                 "plant based butter", "dairy-free block", "vegan block", "vegan baking block",
                 "dairy-free baking block", "plant butter block", "non-dairy butter"],
     "searches": ["plant butter block", "vegan block", "plant based butter", "dairy free block"],
     "include": r"\b(block|butter)\b",
     "exclude": r"\b(spread|light|lighter|peanut|almond|cashew|nut|cocoa|shea|garlic|chocolate|biscuit|"
                r"cookie|cake|squeezy|spreadable|soft|salted caramel|seed|seeds)\b",
     "kcal": (550, 760)},
    {"key": "dairy-free spread", "category": "dairy-alt",
     "aliases": ["dairy-free spread", "dairy free spread", "vegan spread", "plant spread", "plant-based spread",
                 "dairy-free margarine", "vegan margarine", "non-dairy spread"],
     "searches": ["dairy free spread", "vegan spread", "plant based spread"],
     "include": r"\b(spread|margarine)\b",
     "exclude": r"\b(light|lighter|peanut|almond|cashew|nut|hazelnut|cocoa|chocolate|yeast|marmite|houmous|"
                r"hummus|sandwich|pate|cheese|jam|honey|olive|block|butter)\b",
     "kcal": (300, 760)},
    {"key": "dairy-free cheese", "category": "dairy-alt",
     "aliases": ["dairy-free cheese", "dairy free cheese", "vegan cheese", "plant-based cheese", "plant based cheese",
                 "dairy-free cheddar", "vegan cheddar", "dairy-free grated cheese", "vegan grated cheese",
                 "non-dairy cheese"],
     "searches": ["vegan cheese block", "dairy free cheese", "plant based cheddar", "vegan cheddar"],
     "include": r"\b(cheese|cheddar|chedda|cheeze|block|grated|style)\b",
     "exclude": r"\b(cream cheese|soft|spread|slices|sauce|pizza|mac|crackers|snack|feta|halloumi|"
                r"parmesan|parmigiano|mozzarella|mozza|cheesecake|cake|toastie|sandwich|puffs|nachos|"
                r"burger|onion|chilli|smoked|garlic|herbs|chive|cranberry|blue|brie|camembert)\b",
     "kcal": (180, 400)},
    {"key": "oat milk", "category": "dairy-alt",
     "aliases": ["oat milk", "oat drink", "oatmilk", "oat milk drink", "barista oat milk", "oat m*lk"],
     "searches": ["oat drink", "oat milk"],
     "include": r"\boat\b",
     "exclude": r"\b(chocolate|choc|coffee|latte|vanilla|strawberry|banana|protein|cream|yog|yogurt|"
                r"yoghurt|custard|ice|mocha|caramel|cappuccino|biscuit|porridge|bar|flapjack|cold brew|"
                r"matcha|chai|skinny|light|lighter|semi)\b",
     "kcal": (30, 75)},
    {"key": "almond milk", "category": "dairy-alt",
     "aliases": ["almond milk", "almond drink", "unsweetened almond milk", "unsweetened almond drink",
                 "almond milk unsweetened"],
     "searches": ["almond drink unsweetened", "almond milk unsweetened", "almond drink"],
     "include": r"\balmond\b",
     "exclude": r"\b(chocolate|choc|coffee|latte|vanilla|strawberry|banana|protein|yog|yogurt|yoghurt|"
                r"cream|butter|flour|ground|whole|flaked|roasted|cookie|biscuit|bar|sweetened|original|"
                r"barista|ice|caramel|coconut|cashew|oat)\b",
     "kcal": (8, 40)},
    {"key": "soy milk", "category": "dairy-alt",
     "aliases": ["soy milk", "soya milk", "soya drink", "soy drink", "unsweetened soy milk",
                 "unsweetened soya milk", "unsweetened soya drink", "soy milk unsweetened"],
     "searches": ["soya drink unsweetened", "soya milk unsweetened", "soya drink"],
     "include": r"\b(soya|soy)\b",
     "exclude": r"\b(chocolate|choc|coffee|latte|vanilla|strawberry|banana|protein|yog|yogurt|yoghurt|"
                r"cream|sauce|mince|chunks|dessert|custard|barista|sweetened|original|light|lighter|"
                r"ice|caramel|bean|beans|edamame)\b",
     "kcal": (25, 55)},
    {"key": "coconut drink", "category": "dairy-alt",
     "aliases": ["coconut drink", "coconut milk drink", "coconut milk alternative", "unsweetened coconut drink"],
     "searches": ["coconut drink", "coconut milk drink"],
     "include": r"\bcoconut\b.*\b(drink|milk alternative|dairy free)\b|\bdrink\b.*\bcoconut\b",
     "exclude": r"\b(chocolate|coffee|latte|vanilla|strawberry|banana|protein|yog|yogurt|yoghurt|cream|"
                r"water|tinned|tin|can|cooking|rum|cocktail|pineapple|mango|lime|matcha|almond|rice|oat|"
                r"barista)\b",
     "kcal": (10, 40)},
    {"key": "coconut milk", "category": "dairy-alt",
     "aliases": ["coconut milk", "tinned coconut milk", "canned coconut milk", "full-fat coconut milk",
                 "full fat coconut milk", "tin coconut milk", "can coconut milk", "tin of coconut milk",
                 "can of coconut milk"],
     "searches": ["coconut milk tin", "coconut milk"],
     "include": r"\bcoconut milk\b",
     "exclude": r"\b(light|lighter|reduced|lite|low fat|drink|alternative|powder|yog|yogurt|yoghurt|"
                r"chocolate|ice|condensed|curry|soup|sauce|kefir|barista|chilled|longlife|dairy free milk|"
                r"organic unsweetened drink|rice)\b",
     "kcal": (140, 230)},
    {"key": "light coconut milk", "category": "dairy-alt",
     "aliases": ["light coconut milk", "reduced fat coconut milk", "reduced-fat coconut milk", "lite coconut milk",
                 "low fat coconut milk", "lighter coconut milk", "tinned light coconut milk",
                 "canned light coconut milk"],
     "searches": ["light coconut milk", "reduced fat coconut milk"],
     "include": r"\b(light|lighter|reduced|lite|low fat)\b.*\bcoconut milk\b|\bcoconut milk\b.*\b(light|lighter|reduced|lite|low fat)\b",
     "exclude": r"\b(drink|alternative|powder|yog|yogurt|yoghurt|chocolate|ice|condensed|curry|soup|sauce)\b",
     "kcal": (40, 110)},
    {"key": "coconut yoghurt", "category": "dairy-alt",
     "aliases": ["coconut yoghurt", "coconut yogurt", "plain coconut yoghurt", "natural coconut yoghurt",
                 "coconut yoghurt alternative", "coconut yogurt alternative"],
     "searches": ["coconut yoghurt", "coconut yogurt"],
     "include": r"\bcoconut\b.*\b(yoghurt|yogurt|yog|alternative)\b",
     "exclude": r"\b(mango|strawberry|raspberry|blueberry|vanilla|chocolate|passion|lemon|cherry|peach|"
                r"berries|berry|granola|bites|coated|clusters|bar|kefir|greek style yogurt with|pineapple|"
                r"cashew|almond|oat|soya|soy|dessert|ice|frozen)\b",
     "kcal": (60, 220)},
    {"key": "pesto", "category": "condiment",
     "aliases": ["pesto", "green pesto", "basil pesto", "pesto alla genovese", "genovese pesto", "pesto genovese",
                 "jar pesto", "fresh pesto"],
     "searches": ["green pesto", "basil pesto"],
     "include": r"\bpesto\b",
     "exclude": r"\b(red|rosso|tomato|sun ?dried|vegan|free from|reduced|light|lighter|chilli|rocket|wild garlic|"
                r"kale|pasta|gnocchi|chicken|sandwich|houmous|hummus|dressing|crisps|pepper|olive|walnut|"
                r"spinach|aubergine|pistachio|lemon|coriander)\b",
     "kcal": (300, 600)},
    {"key": "thai curry paste", "category": "condiment",
     "aliases": ["thai curry paste", "thai green curry paste", "thai red curry paste", "green curry paste",
                 "red curry paste", "thai green paste", "thai red paste", "massaman curry paste",
                 "yellow curry paste", "thai yellow curry paste", "panang curry paste"],
     "searches": ["thai green curry paste", "thai red curry paste"],
     "include": r"\b(curry paste|green paste|red paste)\b",
     "exclude": r"\b(sauce|kit|meal|noodle|soup|ready|pot|cooking sauce|stir fry|tikka|korma|madras|balti|"
                r"jalfrezi|rogan|vindaloo|tandoori|biryani|bhuna|garam)\b",
     "kcal": (40, 260)},
    {"key": "curry paste", "category": "condiment",
     "aliases": ["curry paste", "tikka paste", "tikka masala paste", "tikka curry paste", "korma paste",
                 "korma curry paste", "madras paste", "madras curry paste", "balti paste", "balti curry paste",
                 "rogan josh paste", "rogan josh curry paste", "jalfrezi paste", "jalfrezi curry paste",
                 "tandoori paste", "vindaloo paste", "vindaloo curry paste", "biryani paste", "garam masala paste",
                 "indian curry paste", "mild curry paste", "medium curry paste", "hot curry paste"],
     "searches": ["tikka masala curry paste", "korma curry paste", "madras curry paste", "balti curry paste",
                  "rogan josh curry paste"],
     "include": r"\b(curry paste|paste)\b",
     "exclude": r"\b(thai|green|red curry|massaman|panang|laksa|sauce|kit|meal|noodle|soup|ready|pot|"
                r"cooking sauce|stir fry|garlic paste|ginger paste|tomato|chilli paste|lemongrass)\b",
     "kcal": (150, 650)},
    {"key": "gochujang", "category": "condiment",
     "aliases": ["gochujang", "gochujang paste", "korean chilli paste", "korean chili paste", "korean red pepper paste",
                 "gochujang chilli paste"],
     "searches": ["gochujang"],
     "include": r"\bgochujang\b|\bkorean (hot )?(red )?(chilli|chili|pepper) paste\b",
     "exclude": r"\b(sauce|mayo|mayonnaise|ketchup|crisps|noodle|ramen|marinade|dressing|glaze|chips|"
                r"seasoning|honey|chicken|stir fry|squeezy|bbq)\b",
     "kcal": (150, 330)},
    {"key": "tamari", "category": "condiment",
     "aliases": ["tamari", "tamari soy sauce", "gluten-free tamari", "gluten free tamari", "tamari sauce",
                 "reduced salt tamari"],
     "searches": ["tamari"],
     "include": r"\btamari\b",
     "exclude": r"\b(almond|almonds|seeds|nuts|cashew|crackers|rice cakes|roasted|toasted|mix|snack|"
                r"crisps|dressing|marinade|noodle)\b",
     "kcal": (40, 160)},
    {"key": "soy sauce", "category": "condiment",
     "aliases": ["soy sauce", "soya sauce", "light soy sauce", "light soy", "naturally brewed soy sauce",
                 "reduced salt soy sauce", "low sodium soy sauce", "shoyu", "japanese soy sauce"],
     "searches": ["soy sauce", "light soy sauce"],
     "include": r"\b(soy|soya)\b.*\bsauce\b|\bshoyu\b",
     "exclude": r"\b(dark|sweet|kecap|mushroom|teriyaki|garlic|chilli|ginger|honey|noodle|noodles|stir fry|"
                r"marinade|dressing|rice|crackers|crisps|seaweed|oyster|hoisin|sesame|beans|chicken|edamame|"
                r"seeds|almond|nuts|cashew|sushi kit|tamari)\b",
     "kcal": (20, 130)},
    {"key": "miso paste", "category": "condiment",
     "aliases": ["miso", "miso paste", "white miso", "white miso paste", "brown miso", "brown miso paste",
                 "red miso", "red miso paste", "shiro miso", "sweet white miso", "yellow miso", "barley miso",
                 "genmai miso"],
     "searches": ["miso paste", "white miso"],
     "include": r"\bmiso\b",
     "exclude": r"\b(soup|instant|noodle|ramen|dressing|sauce|crisps|caramel|butter|marinade|glaze|"
                r"mayo|seasoning|rice|cracker|chips|pot)\b",
     "kcal": (120, 300)},
    {"key": "tahini", "category": "pantry",
     "aliases": ["tahini", "tahina", "tahini paste", "sesame paste", "light tahini", "dark tahini", "sesame seed paste"],
     "searches": ["tahini"],
     "include": r"\b(tahini|tahina|sesame paste|sesame seed paste)\b",
     "exclude": r"\b(houmous|hummus|dressing|sauce|halva|halwa|bar|cookie|chocolate|caramel|cacao|cocoa|"
                r"dip|honey)\b",
     "kcal": (520, 720)},
    {"key": "firm tofu", "category": "protein",
     "aliases": ["firm tofu", "extra firm tofu", "extra-firm tofu", "tofu", "tofu block", "plain tofu",
                 "organic tofu", "naked tofu", "original tofu"],
     "searches": ["firm tofu", "tofu block", "organic tofu"],
     "include": r"\btofu\b",
     "exclude": r"\b(silken|smoked|marinated|teriyaki|puffs|puffed|pieces|bites|chunks|cubes|fried|"
                r"breaded|crispy|sweet chilli|sesame|chilli|katsu|curry|salad|noodle|soup|dessert|"
                r"pudding|skin|egg|basil|pepper|herb|garlic|tikka|bbq|korean|sriracha|ginger|seasoned|"
                r"flavoured|spicy|tandoori|lemon|mushroom|pesto|black pepper)\b",
     "kcal": (70, 200)},
    {"key": "silken tofu", "category": "protein",
     "aliases": ["silken tofu", "soft tofu", "soft silken tofu", "firm silken tofu"],
     "searches": ["silken tofu"],
     "include": r"\bsilken\b|\bsoft tofu\b",
     "exclude": r"\b(dessert|pudding|smoked|marinated)\b",
     "kcal": (35, 100)},
    {"key": "chickpeas (cooked)", "category": "legume", "cooked_only": True, "state": "canned",
     "aliases": ["chickpeas", "chickpea", "chick peas", "chick pea", "garbanzo beans"],
     "searches": ["chickpeas in water", "chick peas in water"],
     "include": r"\bchick ?peas?\b",
     "exclude": r"\b(dried|curry|houmous|hummus|crisps|snack|roasted|crunchy|puffs|flour|pasta|falafel|"
                r"spiced|spicy|salad|soup|masala|chana|pouch|ready|tomato sauce|piri|bbq|sea salt|"
                r"organic dried|bites|chips)\b",
     "kcal": (70, 180)},
    {"key": "kidney beans (cooked)", "category": "legume", "cooked_only": True, "state": "canned",
     "aliases": ["kidney beans", "kidney bean", "red kidney beans", "red kidney bean"],
     "searches": ["red kidney beans in water", "kidney beans in water"],
     "include": r"\bkidney beans?\b",
     "exclude": r"\b(dried|chilli sauce|in chilli|chilli|curry|salad|soup|mixed|pouch|ready|rice|"
                r"organic dried|spicy|cajun|bbq)\b",
     "kcal": (60, 160)},
    {"key": "black beans (cooked)", "category": "legume", "cooked_only": True, "state": "canned",
     "aliases": ["black beans", "black bean", "black turtle beans", "turtle beans"],
     "searches": ["black beans in water", "black turtle beans in water"],
     "include": r"\bblack (turtle )?beans?\b",
     "exclude": r"\b(dried|sauce|chilli|curry|salad|soup|mixed|pouch|ready|rice|spicy|cajun|bbq|"
                r"refried|chipotle|smoky|mexican|burrito|garlic)\b",
     "kcal": (60, 160)},
    {"key": "butter beans (cooked)", "category": "legume", "cooked_only": True, "state": "canned",
     "aliases": ["butter beans", "butter bean", "lima beans", "lima bean"],
     "searches": ["butter beans in water"],
     "include": r"\bbutter beans?\b",
     "exclude": r"\b(dried|sauce|chilli|curry|salad|soup|mixed|pouch|ready|tomato|spicy|giant|gigantes|"
                r"smoky|garlic)\b",
     "kcal": (50, 140)},
    {"key": "cannellini beans (cooked)", "category": "legume", "cooked_only": True, "state": "canned",
     "aliases": ["cannellini beans", "cannellini bean", "white beans", "white bean"],
     "searches": ["cannellini beans in water"],
     "include": r"\bcannellini\b",
     "exclude": r"\b(dried|sauce|chilli|curry|salad|soup|mixed|pouch|ready|tomato|spicy|smoky|garlic|herb)\b",
     "kcal": (50, 140)},
    {"key": "breadcrumbs", "category": "grain",
     "aliases": ["breadcrumbs", "dried breadcrumbs", "dry breadcrumbs", "golden breadcrumbs", "panko",
                 "panko breadcrumbs", "dried white breadcrumbs", "bread crumbs", "dried bread crumbs",
                 "toasted breadcrumbs"],
     "searches": ["breadcrumbs", "panko breadcrumbs"],
     "include": r"\b(breadcrumbs?|bread crumbs?|panko)\b",
     "exclude": r"\b(chicken|fish|cod|haddock|prawns?|scampi|mushrooms|cheese|coated|fillets?|goujons|"
                r"nuggets|stuffing|gluten free|gluten-free|seasoned|herb|garlic|lemon|chilli|cauliflower|"
                r"sausage|veg|vegetable|aubergine|bites|kievs?|escalope|katsu)\b",
     "kcal": (320, 420)},
    {"key": "fresh breadcrumbs", "category": "grain",
     # Fresh breadcrumbs are blitzed bread, so their label is a sliced white loaf's.
     "aliases": ["fresh breadcrumbs", "fresh white breadcrumbs", "fresh bread crumbs", "fresh white bread crumbs",
                 "fresh brown breadcrumbs", "fresh wholemeal breadcrumbs"],
     "searches": ["white bread medium sliced", "white bread thick sliced"],
     "include": r"\bwhite\b.*\b(bread|loaf)\b|\b(bread|loaf)\b.*\bwhite\b",
     "exclude": r"\b(rolls?|baps?|buns?|bagels?|pitta|naan|wraps?|tortilla|gluten|seeded|seeds|half|50/50|"
                r"protein|sourdough|brioche|crumpets?|muffins?|garlic|ciabatta|baguette|focaccia|"
                r"toastie|thins|sub|batch|farmhouse|tiger|bloomer|cob|danish|milk|sandwich thins|"
                r"high fibre|oatmeal|soft white rolls|crumbs)\b",
     "kcal": (200, 290)},
    {"key": "baking powder", "category": "baking",
     "aliases": ["baking powder", "gluten-free baking powder", "gluten free baking powder"],
     "searches": ["baking powder"],
     "include": r"\bbaking powder\b",
     "exclude": r"\b(mix|cake|bread|pancake|scone|cookie|cocoa|soda)\b",
     "kcal": (20, 200)},
    {"key": "mayonnaise", "category": "condiment",
     "aliases": ["mayonnaise", "mayo", "real mayonnaise", "full-fat mayonnaise", "full fat mayonnaise",
                 "classic mayonnaise", "real mayo"],
     "searches": ["real mayonnaise", "mayonnaise"],
     "include": r"\b(mayonnaise|mayo)\b",
     "exclude": r"\b(light|lighter|reduced|low|lite|vegan|plant|free from|egg free|garlic|chilli|"
                r"sriracha|lemon|wasabi|chipotle|truffle|herb|pepper|sandwich|coleslaw|potato salad|"
                r"burger|aioli|kimchi|gochujang|curry|mustard|smoked|bacon|tartare|dip|squeezy dip|"
                r"avocado|olive oil|50%|extra light|dressing|salad cream)\b",
     "kcal": (550, 780)},
    {"key": "ketchup", "category": "condiment",
     "aliases": ["ketchup", "tomato ketchup", "tomato sauce ketchup"],
     "searches": ["tomato ketchup"],
     "include": r"\bketchup\b",
     "exclude": r"\b(reduced|no added|less|zero|light|50%|lighter|sugar free|sweetener|chilli|curry|"
                r"smoky|bbq|sriracha|kimchi|gochujang|mushroom|garlic|truffle|jalapeno|hot|spicy|"
                r"mayo|crisps|veggie|vegetable|beetroot|banana)\b",
     "kcal": (80, 160)},
    {"key": "stock cube", "category": "pantry",
     "aliases": ["stock cube", "stock cubes", "vegetable stock cube", "vegetable stock cubes", "chicken stock cube",
                 "chicken stock cubes", "beef stock cube", "beef stock cubes", "bouillon cube", "bouillon cubes",
                 "veg stock cube", "vegan stock cube", "lamb stock cube", "fish stock cube"],
     "searches": ["stock cubes", "vegetable stock cubes", "chicken stock cubes", "beef stock cubes"],
     "include": r"\b(stock cubes?|bouillon cubes?|cubes?)\b",
     "exclude": r"\b(pot|pots|jelly|liquid|fresh|concentrate|gravy|granules|powder|reduced salt|low salt|"
                r"less salt|25% less|30% less|salt reduced|ice)\b",
     "kcal": (150, 450)},
    {"key": "stock powder", "category": "pantry",
     "aliases": ["stock powder", "vegetable stock powder", "chicken stock powder", "bouillon powder",
                 "vegetable bouillon powder", "swiss vegetable bouillon powder", "vegan bouillon powder",
                 "veg stock powder", "beef stock powder"],
     # Not plain "bouillon" / "vegetable bouillon": recipes use those words for the made-up liquid too.
     "searches": ["vegetable bouillon powder", "stock powder"],
     "include": r"\b(bouillon|stock)\b.*\b(powder|bouillon)\b|\bbouillon\b",
     "exclude": r"\b(cube|cubes|pot|pots|jelly|liquid|fresh|concentrate|gravy|granules|reduced salt|low salt|"
                r"less salt|25% less|30% less|salt reduced|ready to use)\b",
     "kcal": (150, 450)},
    {"key": "puff pastry", "category": "grain",
     "aliases": ["puff pastry", "ready rolled puff pastry", "ready-rolled puff pastry", "all butter puff pastry",
                 "all-butter puff pastry", "puff pastry sheet", "ready rolled puff pastry sheet",
                 "frozen puff pastry", "vegan puff pastry"],
     "searches": ["ready rolled puff pastry", "puff pastry block"],
     "include": r"\bpuff pastry\b",
     "exclude": r"\b(light|lighter|reduced|sausage|rolls?|tarts?|pie|pies|slices?|bake|bakes|cheese|"
                r"twists|straws|vol au vent|vol-au-vent|cases|apple|turnover|croissant|chicken|steak)\b",
     "kcal": (300, 470)},
    {"key": "cocoa powder", "category": "pantry",
     # CoFID cocoa powder (312 kcal) is ~17% under what UK tins state (~375 kcal).
     "aliases": ["cocoa powder", "cocoa", "unsweetened cocoa powder", "cocoa powder unsweetened", "cacao powder",
                 "raw cacao powder", "dutch process cocoa", "dutch-process cocoa powder", "baking cocoa"],
     "searches": ["cocoa powder", "cacao powder"],
     "include": r"\b(cocoa|cacao)\b",
     "exclude": r"\b(drinking|hot chocolate|instant|sugar|nibs|butter|mix|milk|bar|chocolate drink|protein|"
                r"orange|mint|beans|flavour)\b",
     "kcal": (300, 450)},
    {"key": "gluten-free wraps", "category": "grain",
     "aliases": ["gluten-free wraps", "gluten free wraps", "gluten-free wrap", "gluten free wrap",
                 "gluten-free tortilla wraps", "gluten free tortilla wraps", "gluten-free tortillas",
                 "gluten free tortillas", "gluten-free tortilla", "gluten free tortilla"],
     "searches": ["gluten free wraps", "gluten free tortilla wraps"],
     "include": r"\b(wraps?|tortillas?)\b",
     "exclude": r"\b(chips|crisps|chicken|filled|kit|lunch|sandwich|meal|nachos|corn chips|taco shells?|"
                r"boats?|bowl|mini)\b",
     "kcal": (200, 360)},
    {"key": "gluten-free bread", "category": "grain",
     "aliases": ["gluten-free bread", "gluten free bread", "gluten-free white bread", "gluten free white bread",
                 "gluten-free sliced bread", "gluten free sliced bread", "gluten-free loaf", "gluten free loaf"],
     "searches": ["gluten free white bread", "gluten free bread loaf"],
     "include": r"\b(bread|loaf)\b",
     "exclude": r"\b(rolls?|baps?|buns?|bagels?|pitta|naan|wraps?|tortilla|crumbs|breadcrumbs|stuffing|mix|"
                r"flour|brioche|crumpets?|muffins?|garlic|ciabatta|baguette|focaccia|thins|fruit|teacake|"
                r"pizza|sticks|toasties|crackers|crispbread|ginger|banana|malt)\b",
     "kcal": (180, 320)},
]

_FIELDS = "code,product_name,product_name_en,brands,categories_tags,nutriments,nutrition_data_per,nutrition_data_prepared"


def _fetch(terms: str, page: int = 1) -> List[Dict[str, Any]]:
    words = " AND ".join(re.findall(r"[a-z0-9]+", terms.lower()))
    query = urllib.parse.urlencode({
        "q": f'{words} AND countries_tags:"en:united-kingdom"',  # relevance-ranked
        "page_size": PAGE_SIZE, "page": page, "fields": _FIELDS,
    })
    req = urllib.request.Request(f"{SEARCH_URL}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp).get("hits") or []
        except Exception as exc:  # network / rate limit: back off and retry
            print(f"   retry {attempt + 1} for {terms!r}: {exc}", file=sys.stderr)
            time.sleep(15 * (attempt + 1))
    return []


def _name(prod: Dict[str, Any]) -> str:
    return str(prod.get("product_name_en") or prod.get("product_name") or "").strip()


def _brand(prod: Dict[str, Any]) -> str:
    brands = prod.get("brands") or ""
    if isinstance(brands, list):
        brands = brands[0] if brands else ""
    return str(brands).split(",")[0].strip()


def _accept(spec: Dict[str, Any], prod: Dict[str, Any]) -> Optional[Dict[str, float]]:
    name = _name(prod)
    low = name.lower()
    if not name or not re.search(spec["include"], low):
        return None
    if re.search(COMMON_EXCLUDE, low) or (spec.get("exclude") and re.search(spec["exclude"], low)):
        return None
    if set(prod.get("categories_tags") or []) & BAD_CATEGORIES:
        return None
    per = str(prod.get("nutrition_data_per") or "100g").lower()
    if per not in ("100g", ""):
        return None  # per-serving only: OFF's _100g values are derived and less reliable
    nut = prod.get("nutriments") or {}
    vals: Dict[str, float] = {}
    for key, off_key in NUTRIENTS.items():
        v = nut.get(off_key)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0:
            vals[key] = float(v)
    kcal = vals.get("calories")
    lo, hi = spec["kcal"]
    if kcal is None or not (lo <= kcal <= hi):
        return None
    if any(k not in vals for k in ("protein", "carbs", "fat")):
        return None
    if vals["protein"] + vals["carbs"] + vals["fat"] > 101:
        return None  # data-entry slip
    return vals


def _median(values: List[float]) -> Optional[float]:
    return round(statistics.median(values), 1) if values else None


def build_one(spec: Dict[str, Any]) -> Dict[str, Any]:
    seen_codes = set()
    seen_names = set()
    rows: List[Dict[str, float]] = []
    examples: List[str] = []
    for terms in spec["searches"]:
        for prod in _fetch(terms) + _fetch(terms, page=2):
            code = prod.get("code")
            if code in seen_codes:
                continue
            seen_codes.add(code)
            vals = _accept(spec, prod)
            if vals is None:
                continue
            ident = (re.sub(r"\W+", " ", (_name(prod) + " " + _brand(prod)).lower()).strip(),
                     round(vals["calories"]))
            if ident in seen_names:
                continue  # same product listed under several barcodes
            seen_names.add(ident)
            rows.append(vals)
            if len(examples) < 5:
                examples.append(f"{_brand(prod)} {_name(prod)}".strip()[:60])
        time.sleep(SEARCH_PAUSE_S)
    out: Dict[str, Any] = {"products": len(rows), "examples": examples}
    for key in NUTRIENTS:
        vals = [r[key] for r in rows if key in r]
        # Fibre is optional on UK labels: only report it when enough labels state it.
        out[key] = _median(vals) if len(vals) >= max(3, len(rows) // 3) else None
        if key not in ("fiber", "sugars", "saturates", "salt"):
            out[key] = _median(vals)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--only", default="", help="comma-separated keys to (re)build; others are kept from --out")
    ap.add_argument("--dry-run", action="store_true", help="print results, don't write")
    args = ap.parse_args(argv)

    only = {k.strip() for k in args.only.split(",") if k.strip()}
    existing: Dict[str, Any] = {}
    if only and os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as fh:
            existing = json.load(fh).get("foods", {})

    foods: Dict[str, Any] = {}
    skipped: List[str] = []
    for spec in SPECS:
        key = spec["key"]
        if only and key not in only:
            if key in existing:
                foods[key] = existing[key]
            continue
        print(f"-> {key}", flush=True)
        result = build_one(spec)
        print(f"   n={result['products']} kcal={result['calories']} P={result['protein']} C={result['carbs']} "
              f"F={result['fat']} fibre={result['fiber']}  e.g. {result['examples'][:2]}", flush=True)
        if result["products"] < MIN_PRODUCTS:
            print(f"   SKIPPED: fewer than {MIN_PRODUCTS} products", flush=True)
            skipped.append(key)
            if key in existing:
                foods[key] = existing[key]
            continue
        foods[key] = {
            "aliases": spec["aliases"],
            "category": spec["category"],
            "state": spec.get("state", "as_sold"),
            "cooked_only": bool(spec.get("cooked_only")),
            **{k: result[k] for k in NUTRIENTS},
            "products": result["products"],
            "search": spec["searches"],
            "examples": result["examples"],
        }

    payload = {
        "source": "Open Food Facts (https://world.openfoodfacts.org), products sold in the United Kingdom",
        "licence": "Open Database Licence (ODbL 1.0); contents Database Contents Licence (DbCL 1.0)",
        "built": _dt.date.today().isoformat(),
        "method": (f"Per-100 g median of label values across >= {MIN_PRODUCTS} UK products per food, filtered "
                   "by product name and category (no cooked pouches, ready meals or flavoured variants). "
                   "Carbohydrate is available carbohydrate (UK/EU labelling). Built by "
                   "backend/scripts/build_uk_labels.py."),
        "foods": foods,
    }
    if skipped:
        print("Skipped (too few products):", ", ".join(skipped), flush=True)
    if args.dry_run:
        print(json.dumps(payload, indent=1)[:4000])
        return 0
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False, sort_keys=False)
        fh.write("\n")
    print(f"wrote {len(foods)} foods to {os.path.abspath(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
