"""
Import prepared meal packs / shakes / RTD / pouches from product websites
(Huel, similar meal-replacement brands, collection pages).

Not for weekly printable meal-plan PDFs — those stay on meal_plan_import.py.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from utils.security import is_safe_external_url

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MEAL_PRODUCT_PROMPT = """You extract prepared meal products from a brand or shop page.

Focus on ready-to-drink shakes, powder shakes, Hot & Savoury pouches, bars,
complete meal packs, and similar meal-replacement items — NOT weekly meal-plan
schedules and NOT long cook-from-scratch recipes.

Return ONLY valid JSON (no markdown fences):
{
  "source_name": "Brand or page name",
  "products": [
    {
      "title": "Product name",
      "description": "Short blurb",
      "kind": "shake|pouch|bar|rtd|meal|other",
      "ingredients": [{"amount": "1", "unit": "bottle", "name": "Chocolate RTD"}],
      "instructions": ["Shake well", "Serve cold"],
      "servings": 1,
      "nutrition": {"calories": 400, "protein": 20, "carbs": 37, "fat": 13},
      "tags": ["huel", "meal-pack"]
    }
  ]
}

Rules:
- One entry per distinct product / flavour you can identify.
- Prefer per-serving macros (kcal, protein g, carbs g, fat g) ONLY when clearly stated on the page.
- If macros are missing or unclear, set nutrition fields to null — never invent calories.
- If the page is a single product, return one item.
- If the page is a collection, return up to 12 distinct products.
- Invent minimal prep steps when the page only says "add water" / "shake".
- Skip merch, apparel, accessories, and non-food items.
"""


def scrape_macros_from_text(text: str) -> Dict[str, Optional[int]]:
    """
    Pull per-serving macros from product page copy (Huel nutrition panels, etc.).
    Prefers patterns near Energy / kcal / protein labels.
    """
    out: Dict[str, Optional[int]] = {
        "calories": None,
        "protein": None,
        "carbs": None,
        "fat": None,
        "fiber": None,
        "sugar": None,
        "sodium": None,
    }
    if not text:
        return out
    blob = text.replace("\u00a0", " ")

    # Calories: "400 kcal", "400kcal", "Energy 1674 kJ / 400 kcal"
    cal = re.search(
        r"(?:energy[^0-9]{0,40})?(?:(\d{2,4})\s*kJ\s*[\/\|]\s*)?(\d{2,4})\s*k(?:cal|cals)\b",
        blob,
        flags=re.I,
    )
    if cal:
        out["calories"] = int(cal.group(2))
    else:
        cal2 = re.search(r"\b(\d{2,4})\s*calories\b", blob, flags=re.I)
        if cal2:
            out["calories"] = int(cal2.group(1))

    def _macro(label_patterns: str) -> Optional[int]:
        m = re.search(
            rf"(\d{{1,3}}(?:\.\d+)?)\s*g\s*(?:of\s+)?(?:{label_patterns})\b",
            blob,
            flags=re.I,
        )
        if m:
            return int(round(float(m.group(1))))
        m2 = re.search(
            rf"(?:{label_patterns})\s*[:\-]?\s*(\d{{1,3}}(?:\.\d+)?)\s*g\b",
            blob,
            flags=re.I,
        )
        if m2:
            return int(round(float(m2.group(1))))
        return None

    out["protein"] = _macro(r"protein")
    out["carbs"] = _macro(r"carbohydrates?|carbs?|total\s+carb")
    out["fat"] = _macro(r"fat|total\s+fat")
    out["fiber"] = _macro(r"fib(?:re|er)")
    out["sugar"] = _macro(r"sugars?")
    sodium = re.search(r"(\d{1,5})\s*mg\s*(?:of\s+)?sodium\b", blob, flags=re.I)
    if sodium:
        out["sodium"] = int(sodium.group(1))
    return out


def merge_nutrition(
    primary: Optional[Dict[str, Optional[int]]],
    fallback: Optional[Dict[str, Optional[int]]],
) -> Dict[str, Optional[int]]:
    base = {
        "calories": None,
        "protein": None,
        "carbs": None,
        "fat": None,
        "fiber": None,
        "sugar": None,
        "sodium": None,
    }
    for src in (primary or {}, fallback or {}):
        for k in base:
            if base[k] is None and src.get(k) is not None:
                try:
                    base[k] = int(round(float(src[k])))
                except (TypeError, ValueError):
                    pass
    return base


def product_needs_macros(product: Dict[str, Any]) -> bool:
    nutrition = product.get("nutrition") or {}
    return nutrition.get("calories") is None


def enrich_products_with_page_macros(
    products: List[Dict[str, Any]], page_text: str
) -> List[Dict[str, Any]]:
    """Fill missing macros from page text when a single product page is scraped."""
    page_macros = scrape_macros_from_text(page_text)
    enriched = []
    for prod in products:
        nutrition = merge_nutrition(prod.get("nutrition"), None)
        # For a single product page, page-level macros apply to that product.
        # For collections, only fill if the product still has no calories and
        # its title appears near a macro block (best-effort).
        if nutrition.get("calories") is None:
            if len(products) == 1:
                nutrition = merge_nutrition(nutrition, page_macros)
            else:
                title = (prod.get("title") or "")[:40]
                if title and title.lower() in page_text.lower():
                    # Slice a window around the title for local macros
                    idx = page_text.lower().find(title.lower())
                    window = page_text[max(0, idx - 80) : idx + 600]
                    nutrition = merge_nutrition(nutrition, scrape_macros_from_text(window))
                if nutrition.get("calories") is None:
                    # last resort: page macros only if clearly one nutrition panel
                    cal_hits = len(re.findall(r"\b\d{2,4}\s*k(?:cal|cals)\b", page_text, flags=re.I))
                    if cal_hits == 1:
                        nutrition = merge_nutrition(nutrition, page_macros)
        prod = {**prod, "nutrition": nutrition, "needs_macros": product_needs_macros({"nutrition": nutrition})}
        enriched.append(prod)
    return enriched


def normalize_product_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    is_safe, error = is_safe_external_url(url)
    if not is_safe:
        raise ValueError(error or "URL is not allowed")
    return url


def _html_to_text(html: str, limit: int = 20000) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        element.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:limit]


def _parse_nutrition_block(block: Any) -> Dict[str, Optional[int]]:
    """Parse schema.org NutritionInformation or a plain dict into Laro macros."""
    out: Dict[str, Optional[int]] = {
        "calories": None,
        "protein": None,
        "carbs": None,
        "fat": None,
        "fiber": None,
        "sugar": None,
        "sodium": None,
    }
    if not isinstance(block, dict):
        return out

    def _num(val: Any, unit_hint: str = "") -> Optional[int]:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return int(round(float(val)))
        s = str(val)
        m = re.search(r"(\d+(?:\.\d+)?)", s.replace(",", ""))
        if not m:
            return None
        n = float(m.group(1))
        # sodium often mg
        if "sodium" in unit_hint and "g" in s.lower() and "mg" not in s.lower():
            n = n * 1000
        return int(round(n))

    out["calories"] = _num(block.get("calories") or block.get("energy"))
    out["protein"] = _num(block.get("proteinContent") or block.get("protein"))
    out["carbs"] = _num(
        block.get("carbohydrateContent")
        or block.get("carbs")
        or block.get("totalCarbohydrate")
    )
    out["fat"] = _num(block.get("fatContent") or block.get("fat") or block.get("totalFat"))
    out["fiber"] = _num(block.get("fiberContent") or block.get("fiber"))
    out["sugar"] = _num(block.get("sugarContent") or block.get("sugar"))
    out["sodium"] = _num(block.get("sodiumContent") or block.get("sodium"), "sodium")
    return out


def _guess_kind(title: str, description: str = "") -> str:
    blob = f"{title} {description}".lower()
    if any(k in blob for k in ("ready to drink", "ready-to-drink", "rtd", "bottle")):
        return "rtd"
    if "bar" in blob:
        return "bar"
    if any(k in blob for k in ("hot & savoury", "hot and savoury", "pouch", "savoury")):
        return "pouch"
    if any(k in blob for k in ("shake", "powder", "black edition", "essential")):
        return "shake"
    return "meal"


def _product_from_schema(obj: dict) -> Optional[Dict[str, Any]]:
    types = obj.get("@type")
    type_list = types if isinstance(types, list) else [types]
    type_list = [str(t).lower() for t in type_list if t]
    if not any("product" in t for t in type_list):
        # Some pages nest Product under Offer
        if "name" not in obj:
            return None

    name = (obj.get("name") or "").strip()
    if not name or len(name) < 2:
        return None

    description = obj.get("description") or ""
    if isinstance(description, list):
        description = " ".join(str(x) for x in description)
    description = str(description).strip()[:500]

    nutrition = _parse_nutrition_block(obj.get("nutrition") or {})
    # Also look for additionalProperty macros
    for prop in obj.get("additionalProperty") or []:
        if not isinstance(prop, dict):
            continue
        pname = str(prop.get("name") or "").lower()
        pval = prop.get("value")
        if "calor" in pname and nutrition["calories"] is None:
            nutrition["calories"] = _parse_nutrition_block({"calories": pval})["calories"]
        elif "protein" in pname and nutrition["protein"] is None:
            nutrition["protein"] = _parse_nutrition_block({"protein": pval})["protein"]

    image = obj.get("image") or ""
    if isinstance(image, list):
        image = image[0] if image else ""
    if isinstance(image, dict):
        image = image.get("url") or ""

    kind = _guess_kind(name, description)
    instructions = {
        "rtd": ["Shake well if needed.", "Serve chilled."],
        "shake": ["Add one serving to a shaker with water or milk.", "Shake until smooth."],
        "pouch": ["Add boiling water to the fill line.", "Stir, cover, and wait 5 minutes."],
        "bar": ["Open and eat."],
        "meal": ["Prepare according to pack instructions."],
        "other": ["Prepare according to pack instructions."],
    }.get(kind, ["Prepare according to pack instructions."])

    serving_label = {
        "rtd": ("1", "bottle", name),
        "shake": ("1", "serving", name),
        "pouch": ("1", "pouch", name),
        "bar": ("1", "bar", name),
    }.get(kind, ("1", "serving", name))

    return {
        "title": name[:120],
        "description": description,
        "kind": kind,
        "ingredients": [
            {"amount": serving_label[0], "unit": serving_label[1], "name": serving_label[2]}
        ],
        "instructions": instructions,
        "servings": 1,
        "nutrition": nutrition,
        "image_url": str(image)[:500] if image else "",
        "tags": ["meal-pack", kind],
    }


def extract_products_from_html(html: str) -> List[Dict[str, Any]]:
    """Pull Product (+ nutrition) nodes from JSON-LD."""
    soup = BeautifulSoup(html or "", "html.parser")
    products: List[Dict[str, Any]] = []
    seen = set()

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        nodes: List[Any] = []
        if isinstance(data, list):
            nodes.extend(data)
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                nodes.extend(data["@graph"])
            else:
                nodes.append(data)

        for node in nodes:
            if not isinstance(node, dict):
                continue
            # ProductGroup / ItemList
            if str(node.get("@type") or "").lower() in ("itemlist", "collectionpage"):
                for el in node.get("itemListElement") or []:
                    if isinstance(el, dict):
                        item = el.get("item") if isinstance(el.get("item"), dict) else el
                        if isinstance(item, dict):
                            prod = _product_from_schema(item)
                            if prod and prod["title"].lower() not in seen:
                                seen.add(prod["title"].lower())
                                products.append(prod)
                continue

            prod = _product_from_schema(node)
            if prod and prod["title"].lower() not in seen:
                # Require some signal it's food-ish or has nutrition
                has_macros = any(
                    prod["nutrition"].get(k) for k in ("calories", "protein", "carbs", "fat")
                )
                blob = f"{prod['title']} {prod['description']}".lower()
                foodish = any(
                    k in blob
                    for k in (
                        "huel",
                        "shake",
                        "meal",
                        "calorie",
                        "protein",
                        "pouch",
                        "nutrition",
                        "rtd",
                        "complete",
                    )
                )
                if has_macros or foodish:
                    seen.add(prod["title"].lower())
                    products.append(prod)

    return products[:12]


async def fetch_product_page(url: str, timeout: float = 30.0) -> Tuple[str, str, str]:
    """
    Returns (html, plain_text, canonical_url).
    Uses Jina when the direct HTML is thin (common on JS storefronts).
    """
    url = normalize_product_url(url)
    html = ""
    text = ""

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                url, headers=BROWSER_HEADERS, timeout=timeout, follow_redirects=True
            )
            if resp.status_code < 400:
                html = resp.text or ""
                text = _html_to_text(html)
        except Exception as e:
            logger.warning("Product URL fetch failed for %s: %s", url, e)

        if len(text) < 400 or not extract_products_from_html(html):
            try:
                jina_resp = await client.get(
                    f"https://r.jina.ai/{url}",
                    headers={"Accept": "text/html", "X-Return-Format": "html"},
                    timeout=timeout,
                    follow_redirects=True,
                )
                if jina_resp.status_code == 200 and jina_resp.text:
                    jhtml = jina_resp.text
                    jtext = _html_to_text(jhtml)
                    if len(jtext) > len(text):
                        html, text = jhtml, jtext
                    elif not html:
                        html, text = jhtml, jtext
            except Exception as e:
                logger.warning("Jina product fetch failed for %s: %s", url, e)

    if len(text.strip()) < 60 and not html:
        raise ValueError(
            "Could not read that product page. Use a public product or collection URL."
        )
    return html, text, url


def meal_type_for_kind(kind: str) -> str:
    kind = (kind or "other").lower()
    if kind in ("shake", "rtd", "bar"):
        return "Breakfast"
    if kind == "pouch":
        return "Dinner"
    return "Snack"


def category_for_kind(kind: str) -> str:
    """RTD/shakes/pouches are still first-class recipes under Meal Pack."""
    return "Meal Pack"


def product_to_recipe(prod: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a prepared meal pack / RTD / shake into Laro's recipe shape
    so it saves into the Recipes library like any other recipe.
    """
    kind = (prod.get("kind") or "meal").lower()
    nutrition = prod.get("nutrition") or {}
    tags = list(prod.get("tags") or [])
    for t in ("meal-pack", kind, "rtd" if kind == "rtd" else None):
        if t and t not in tags:
            tags.append(t)
    return {
        "title": prod.get("title") or "Meal pack",
        "description": prod.get("description") or "",
        "ingredients": prod.get("ingredients")
        or [{"amount": "1", "unit": "serving", "name": prod.get("title") or "Meal pack"}],
        "instructions": prod.get("instructions")
        or ["Prepare according to pack instructions."],
        "prep_time": int(prod.get("prep_time") or 2),
        "cook_time": int(prod.get("cook_time") or (5 if kind == "pouch" else 0)),
        "servings": int(prod.get("servings") or 1),
        "category": category_for_kind(kind),
        "tags": tags,
        "image_url": prod.get("image_url") or "",
        "nutrition": {
            "calories": nutrition.get("calories"),
            "protein": nutrition.get("protein"),
            "carbs": nutrition.get("carbs"),
            "fat": nutrition.get("fat"),
            "fiber": nutrition.get("fiber"),
            "sugar": nutrition.get("sugar"),
            "sodium": nutrition.get("sodium"),
        },
        "is_meal_pack": True,
        "needs_macros": product_needs_macros(prod),
        "kind": kind,
    }


def normalize_product(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = str(raw.get("title") or raw.get("name") or "").strip()
    if len(title) < 2:
        return None
    nutrition = raw.get("nutrition") or {}
    if not isinstance(nutrition, dict):
        nutrition = {}
    nutrition = _parse_nutrition_block(nutrition)
    kind = str(raw.get("kind") or _guess_kind(title, str(raw.get("description") or "")))
    ingredients = raw.get("ingredients") or []
    if not isinstance(ingredients, list) or not ingredients:
        ingredients = [{"amount": "1", "unit": "serving", "name": title}]
    clean_ings = []
    for ing in ingredients[:20]:
        if isinstance(ing, str):
            clean_ings.append({"amount": "", "unit": "", "name": ing.strip()})
        elif isinstance(ing, dict) and ing.get("name"):
            clean_ings.append(
                {
                    "amount": str(ing.get("amount") or ""),
                    "unit": str(ing.get("unit") or ""),
                    "name": str(ing.get("name")),
                }
            )
    instructions = raw.get("instructions") or []
    if isinstance(instructions, str):
        instructions = [instructions]
    instructions = [str(s).strip() for s in instructions if str(s).strip()][:12]
    if not instructions:
        instructions = ["Prepare according to pack instructions."]

    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t) for t in tags if t][:12]
    if "meal-pack" not in tags:
        tags.insert(0, "meal-pack")
    if kind not in tags:
        tags.append(kind)

    try:
        servings = int(raw.get("servings") or 1)
    except (TypeError, ValueError):
        servings = 1

    return {
        "title": title[:120],
        "description": str(raw.get("description") or "")[:500],
        "kind": kind,
        "ingredients": clean_ings,
        "instructions": instructions,
        "servings": max(1, servings),
        "nutrition": nutrition,
        "image_url": str(raw.get("image_url") or "")[:500],
        "tags": tags,
        "category": "Meal Pack",
        "meal_type": meal_type_for_kind(kind),
    }


def parse_llm_products(raw: str) -> List[Dict[str, Any]]:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()
    data = json.loads(raw)
    items = []
    if isinstance(data, dict):
        items = data.get("products") or data.get("meals") or data.get("items") or []
        if not items and data.get("title"):
            items = [data]
    elif isinstance(data, list):
        items = data
    out = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        prod = normalize_product(item)
        if not prod:
            continue
        key = prod["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(prod)
    return out[:12]
