"""
Deterministic recipe URL scraping via open-source libraries.

Used before LLM fallback so URL imports avoid burning AI quota when
recipe-scrapers / extruct can parse the page.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_SOCIAL_HOST_HINTS = (
    "instagram.com",
    "tiktok.com",
    "facebook.com",
    "fb.watch",
    "youtube.com",
    "youtu.be",
    "twitter.com",
    "x.com",
)


def is_social_or_video_url(url: str) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return any(h == host or host.endswith("." + h) or h in (url or "").lower() for h in _SOCIAL_HOST_HINTS)


def _parse_servings(raw: Any, default: int = 4) -> int:
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return max(1, int(raw))
    match = re.search(r"(\d+)", str(raw))
    return max(1, int(match.group(1))) if match else default


def _parse_minutes(raw: Any) -> int:
    """Best-effort minutes from ISO-8601 duration or plain int/string."""
    if raw is None or raw == "":
        return 0
    if isinstance(raw, (int, float)):
        return max(0, int(raw))
    text = str(raw).strip()
    if re.fullmatch(r"\d+", text):
        return int(text)
    # PT1H30M / PT45M
    hours = re.search(r"(\d+)\s*H", text, re.I)
    mins = re.search(r"(\d+)\s*M", text, re.I)
    total = 0
    if hours:
        total += int(hours.group(1)) * 60
    if mins:
        total += int(mins.group(1))
    if total:
        return total
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def _split_ingredient_line(line: str) -> Dict[str, str]:
    """Prefer OSS ingredient parser; fall back to name-only."""
    text = (line or "").strip()
    if not text:
        return {"amount": "", "unit": "", "name": ""}
    try:
        from utils.ingredient_parse import parse_ingredient_line

        parsed = parse_ingredient_line(text)
        return {
            "amount": parsed.get("amount") or "",
            "unit": parsed.get("unit") or "",
            "name": parsed.get("name") or text,
        }
    except Exception:
        return {"amount": "", "unit": "", "name": text}


def _normalize_instructions(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in re.split(r"\n+", raw) if p.strip()]
        return parts
    if isinstance(raw, list):
        out: List[str] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                text = (item.get("text") or item.get("name") or "").strip()
                if text:
                    out.append(text)
        return out
    return []


def to_laro_recipe(
    *,
    title: str,
    ingredients: List[Any],
    instructions: List[Any],
    description: str = "",
    prep_time: Any = 0,
    cook_time: Any = 0,
    total_time: Any = 0,
    servings: Any = 4,
    image_url: str = "",
    source_url: str = "",
    source_author: str = "",
    tags: Optional[List[str]] = None,
    scrape_engine: str = "",
) -> Optional[Dict[str, Any]]:
    title = (title or "").strip()
    parsed_ings: List[Dict[str, str]] = []
    for ing in ingredients or []:
        if isinstance(ing, dict):
            name = (ing.get("name") or ing.get("ingredient") or "").strip()
            if not name and ing.get("text"):
                parsed_ings.append(_split_ingredient_line(str(ing["text"])))
            elif name:
                parsed_ings.append(
                    {
                        "amount": str(ing.get("amount") or ing.get("quantity") or ""),
                        "unit": str(ing.get("unit") or ""),
                        "name": name,
                    }
                )
        elif isinstance(ing, str) and ing.strip():
            parsed_ings.append(_split_ingredient_line(ing))

    steps = _normalize_instructions(instructions)
    if not title or (not parsed_ings and not steps):
        return None

    prep = _parse_minutes(prep_time)
    cook = _parse_minutes(cook_time)
    total = _parse_minutes(total_time)
    if not cook and total and prep and total >= prep:
        cook = total - prep
    elif not cook and total and not prep:
        cook = total

    recipe = {
        "title": title,
        "description": (description or "").strip(),
        "ingredients": parsed_ings,
        "instructions": steps,
        "prep_time": prep,
        "cook_time": cook,
        "servings": _parse_servings(servings),
        "image_url": image_url or "",
        "source_url": source_url or "",
        "tags": tags or [],
        "scrape_engine": scrape_engine,
    }
    if source_author:
        recipe["source_author"] = source_author
    return recipe


def scrape_with_recipe_scrapers(url: str, html: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Site-specific parsers from hhursev/recipe-scrapers."""
    if not url or is_social_or_video_url(url):
        return None
    try:
        from recipe_scrapers import scrape_html, scrape_me
    except Exception as e:
        logger.warning("recipe-scrapers unavailable: %s", e)
        return None

    scraper = None
    try:
        if html:
            scraper = scrape_html(html=html, org_url=url, supported_only=False)
        else:
            scraper = scrape_me(url, wild_mode=True)
    except Exception as e:
        logger.info("recipe-scrapers failed for %s: %s", url, e)
        return None

    try:
        title = scraper.title()
        ingredients = scraper.ingredients() or []
        try:
            instructions = scraper.instructions_list() or []
        except Exception:
            instructions = scraper.instructions() or ""
        image = ""
        try:
            image = scraper.image() or ""
        except Exception:
            image = ""
        author = ""
        try:
            author = scraper.author() or ""
        except Exception:
            author = ""
        description = ""
        try:
            description = scraper.description() or ""
        except Exception:
            description = ""
        yields = None
        try:
            yields = scraper.yields()
        except Exception:
            yields = None
        prep = cook = total = 0
        try:
            prep = scraper.prep_time() or 0
        except Exception:
            pass
        try:
            cook = scraper.cook_time() or 0
        except Exception:
            pass
        try:
            total = scraper.total_time() or 0
        except Exception:
            pass

        return to_laro_recipe(
            title=title,
            ingredients=ingredients,
            instructions=instructions,
            description=description,
            prep_time=prep,
            cook_time=cook,
            total_time=total,
            servings=yields,
            image_url=image,
            source_url=url,
            source_author=author,
            scrape_engine="recipe-scrapers",
        )
    except Exception as e:
        logger.info("recipe-scrapers normalize failed for %s: %s", url, e)
        return None


def scrape_with_extruct(url: str, html: str) -> Optional[Dict[str, Any]]:
    """schema.org Recipe via extruct (JSON-LD / microdata / RDFa)."""
    if not html or is_social_or_video_url(url):
        return None
    try:
        import extruct
        from w3lib.html import get_base_url
    except Exception as e:
        logger.warning("extruct unavailable: %s", e)
        return None

    try:
        base = get_base_url(html, url)
        data = extruct.extract(
            html,
            base_url=base,
            syntaxes=["json-ld", "microdata", "rdfa"],
            uniform=True,
        )
    except Exception as e:
        logger.info("extruct extract failed for %s: %s", url, e)
        return None

    candidates: List[dict] = []
    for bucket in (data or {}).values():
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            if not isinstance(item, dict):
                continue
            types = item.get("@type") or item.get("type") or ""
            if isinstance(types, list):
                type_l = " ".join(str(t) for t in types).lower()
            else:
                type_l = str(types).lower()
            if "recipe" in type_l:
                candidates.append(item)

    for item in candidates:
        title = item.get("name") or item.get("headline") or ""
        ingredients = item.get("recipeIngredient") or item.get("ingredients") or []
        instructions = item.get("recipeInstructions") or item.get("instructions") or []
        image = item.get("image") or ""
        if isinstance(image, list):
            image = image[0] if image else ""
        if isinstance(image, dict):
            image = image.get("url") or ""
        author = item.get("author") or ""
        if isinstance(author, list) and author:
            author = author[0]
        if isinstance(author, dict):
            author = author.get("name") or ""
        recipe = to_laro_recipe(
            title=str(title),
            ingredients=ingredients,
            instructions=instructions,
            description=str(item.get("description") or ""),
            prep_time=item.get("prepTime"),
            cook_time=item.get("cookTime"),
            total_time=item.get("totalTime"),
            servings=item.get("recipeYield"),
            image_url=str(image or ""),
            source_url=url,
            source_author=str(author or ""),
            scrape_engine="extruct",
        )
        if recipe and (recipe.get("ingredients") or recipe.get("instructions")):
            return recipe
    return None


def scrape_recipe_oss(url: str, html: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Try recipe-scrapers first, then extruct.
    Returns a Laro recipe dict or None (caller should fall back to AI).
    """
    if not url or is_social_or_video_url(url):
        return None

    recipe = scrape_with_recipe_scrapers(url, html=html)
    if recipe and (recipe.get("ingredients") or recipe.get("instructions")):
        logger.info(
            "OSS scrape via recipe-scrapers: %s (%s ings)",
            recipe.get("title"),
            len(recipe.get("ingredients") or []),
        )
        return recipe

    if html:
        recipe = scrape_with_extruct(url, html)
        if recipe and (recipe.get("ingredients") or recipe.get("instructions")):
            logger.info(
                "OSS scrape via extruct: %s (%s ings)",
                recipe.get("title"),
                len(recipe.get("ingredients") or []),
            )
            return recipe
    return None
