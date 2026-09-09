"""
AI Router - AI-powered recipe operations
Heavy operations are processed via background job queue (arq)
"""
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from models import (
    ImportURLRequest, ImportTextRequest, AutoMealPlanRequest, ImportMealPlanRequest,
    ImportMealPlanUrlRequest, ImportFeedbackRequest,
    FridgeSearchRequest, ImageExtractionRequest, RecipeCreate, RecipeResponse, Ingredient
)
from dependencies import (
    get_current_user, call_llm, call_llm_with_image, call_llm_with_images, clean_llm_json,
    recipe_repository, cookbook_repository, meal_plan_repository, shopping_list_repository
)
from routers.prompts import get_user_prompt
from workers.jobs import enqueue_job
from utils.security import is_safe_external_url, sanitize_error_message
from utils.ai_quota import (
    require_ai_quota,
    consume_ai_quota,
    get_quota_status,
    is_premium_user,
)
from bs4 import BeautifulSoup
import json
import logging
import os
import re
from typing import Optional, List, Any

router = APIRouter(prefix="/ai", tags=["AI"])
logger = logging.getLogger(__name__)

# Conversational AI (chat + cooking assistant) stays on food/cooking only.
FOOD_TOPIC_SCOPE_RULE = """
Topic scope (strict — never break this):
- You ONLY answer questions about food, cooking, recipes, ingredients, kitchen
  equipment, meal planning, nutrition for meals, food safety, and related
  culinary topics.
- If the user asks about anything else (news, politics, coding, homework,
  relationships, sports scores, general trivia, etc.), do NOT answer the
  substance of the question. Reply briefly that you are Laro, a cooking
  assistant, and tell them to search Google instead.
- When redirecting, include a Google search link using this format:
  https://www.google.com/search?q=<url-encoded query>
- Do not invent answers outside food/cooking. Do not role-play as a general
  assistant. A short redirect is enough for off-topic requests.
""".strip()


def _with_food_topic_scope(system_prompt: str) -> str:
    base = (system_prompt or "").rstrip()
    return f"{base}\n\n{FOOD_TOPIC_SCOPE_RULE}"


async def call_llm_metered(
    client,
    system_prompt: str,
    user_prompt: str,
    user: dict,
    *,
    format_json: bool = False,
    max_tokens: int = 2000,
) -> str:
    """Call LLM after enforcing the free-tier AI quota; consume one use on success."""
    await require_ai_quota(user)
    usage_meta = {}
    result = await call_llm(
        client,
        system_prompt,
        user_prompt,
        user["id"],
        usage_meta=usage_meta,
        format_json=format_json,
        max_tokens=max_tokens,
    )
    # Only burn free credits for non-premium users on real (non-cached) calls
    if not is_premium_user(user) and not usage_meta.get("cached"):
        await consume_ai_quota(user["id"])
    return result


@router.get("/quota")
async def ai_quota(user: dict = Depends(get_current_user)):
    """Return remaining free AI uses (JSON-LD scrape does not count)."""
    return await get_quota_status(user)

async def extract_video_metadata(url: str) -> dict | None:
    """
    Extract video title/description from social URLs.

    Order: SocialFetch (IG/TikTok/YouTube/Facebook) → yt-dlp (cookies when set).
    """
    import asyncio
    import yt_dlp

    try:
        from services.socialfetch_media import detect_social_platform, resolve_social_media

        if detect_social_platform(url):
            social = await resolve_social_media(url)
            if social and (social.get("description") or social.get("title") or social.get("caption")):
                return {
                    "title": social.get("title") or "",
                    "description": social.get("description") or social.get("caption") or "",
                    "uploader": social.get("uploader") or "",
                    "duration": None,
                    "thumbnail": social.get("thumbnail") or "",
                }
    except Exception as e:
        logger.warning(f"Social media metadata resolve failed for {url}: {e}")

    def _extract():
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            "socket_timeout": 15,
        }
        opts.update(_yt_dlp_cookie_opts(url))
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                return {
                    "title": info.get("title") or info.get("fulltitle") or "",
                    "description": info.get("description") or "",
                    "uploader": info.get("uploader") or info.get("channel") or "",
                    "duration": info.get("duration"),
                    "thumbnail": info.get("thumbnail") or "",
                }
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for {url}: {e}")
            return None

    return await asyncio.to_thread(_extract)


def _yt_dlp_cookies_file_usable(path: str) -> bool:
    """True if path exists and has at least one non-comment cookie line."""
    import os

    if not path or not os.path.isfile(path) or os.path.getsize(path) <= 0:
        return False
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    return True
    except OSError:
        return False
    return False


def _yt_dlp_cookie_opts(url: str = "") -> dict:
    """
    Cookie options for yt-dlp.

    Instagram (and some TikTok) need a logged-in session. Configure either:
      YT_DLP_COOKIES_FILE=/secrets/yt-dlp-cookies.txt   # Netscape cookies.txt path
      YT_DLP_COOKIES='...netscape file contents...'     # inline (written to a temp file)

    Export cookies from a browser logged into Instagram (extension "Get cookies.txt
    LOCALLY" or yt-dlp --cookies-from-browser). See DEPLOY.md.
    """
    import os

    path = (os.getenv("YT_DLP_COOKIES_FILE") or "").strip()
    if _yt_dlp_cookies_file_usable(path):
        return {"cookiefile": path}

    inline = (os.getenv("YT_DLP_COOKIES") or "").strip()
    if inline:
        # Persist under /tmp so multiple yt-dlp calls in one process can reuse it.
        dest = "/tmp/laro-yt-dlp-cookies.txt"
        try:
            # Support base64-wrapped values (handy for single-line .env secrets).
            payload = inline
            if not inline.lstrip().startswith("#") and "\t" not in inline and " " not in inline[:80]:
                try:
                    import base64
                    decoded = base64.b64decode(inline, validate=True).decode("utf-8", "replace")
                    if "http" in decoded or ".instagram." in decoded or "# Netscape" in decoded:
                        payload = decoded
                except Exception:
                    payload = inline
            with open(dest, "w", encoding="utf-8") as f:
                f.write(payload if payload.endswith("\n") else payload + "\n")
            os.chmod(dest, 0o600)
            if _yt_dlp_cookies_file_usable(dest):
                return {"cookiefile": dest}
        except Exception as e:
            logger.warning(f"Failed to materialize YT_DLP_COOKIES: {e}")

    url_l = (url or "").lower()
    if any(s in url_l for s in ("instagram.com", "tiktok.com")):
        logger.warning(
            "yt-dlp has no Instagram/TikTok cookies — set YT_DLP_COOKIES_FILE "
            "(Netscape cookies.txt) or YT_DLP_COOKIES. Anonymous fetches usually fail."
        )
    return {}


def _looks_like_login_wall(text: str) -> bool:
    """Heuristic: scraped page is a social login/signup wall, not recipe content."""
    t = (text or "").lower()
    if not t:
        return True
    wall_markers = (
        "log in", "log into", "sign up", "create an account", "see photos and videos",
        "don't have an account", "forgot password", "instagram from facebook",
    )
    recipe_markers = ("ingredient", "tablespoon", "teaspoon", "preheat", "cup of", "minutes")
    wall_hits = sum(1 for m in wall_markers if m in t)
    recipe_hits = sum(1 for m in recipe_markers if m in t)
    return wall_hits >= 2 and recipe_hits == 0


def _is_social_reel_url(url: str) -> bool:
    u = (url or "").lower()
    if "tiktok.com" in u or "vm.tiktok.com" in u or "vt.tiktok.com" in u:
        return True
    if "facebook.com" in u or "fb.watch" in u or "fb.com" in u or "fb.gg" in u:
        return True
    if ("youtube.com" in u and "/shorts/" in u) or "youtu.be/" in u:
        return True
    if "instagram.com" in u and any(
        p in u for p in ("/reel/", "/reels/", "/tv/", "/p/", "/share/")
    ):
        return True
    if "instagr.am/" in u:
        return True
    return False


def parse_duration(duration_str: str) -> int:
    """Parse ISO 8601 duration to minutes"""
    if not duration_str:
        return 0
    hours = 0
    minutes = 0
    h_match = re.search(r'(\d+)H', duration_str)
    m_match = re.search(r'(\d+)M', duration_str)
    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
    return hours * 60 + minutes


def _is_recipe_type(item: dict) -> bool:
    """Check if a JSON-LD item is a Recipe, handling both string and list @type"""
    t = item.get("@type")
    if isinstance(t, str):
        return t == "Recipe"
    if isinstance(t, list):
        return "Recipe" in t
    return False


def extract_social_caption(soup) -> str:
    """
    Pull the caption/description from social posts (Instagram, TikTok, Facebook),
    where the recipe usually lives in the post caption rather than the page body.

    Reads OG/meta tags, which are served for public posts even when the page body
    is a login wall and yt-dlp (which needs auth cookies for Instagram) returns
    nothing. get_text() ignores <meta> tags, so this caption is otherwise lost.
    """
    parts = []
    for prop in ("og:title", "og:description"):
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            parts.append(tag["content"].strip())
    desc = soup.find("meta", attrs={"name": "description"})
    if desc and desc.get("content"):
        parts.append(desc["content"].strip())
    seen = []
    for p in parts:
        if p and p not in seen:
            seen.append(p)
    return "\n".join(seen)


def normalize_source_author(raw: Optional[str]) -> Optional[str]:
    """Normalize a creator handle, byline, or site name for attribution.

    Works for Instagram/TikTok handles (@chef → chef) and website authors /
    publishers / hostnames (e.g. "Smitten Kitchen", "bonappetit.com").
    """
    if not raw:
        return None
    if isinstance(raw, dict):
        raw = raw.get("name") or raw.get("@id") or ""
    if isinstance(raw, list) and raw:
        return normalize_source_author(raw[0])
    s = str(raw).strip()
    if not s:
        return None
    lower = s.lower()
    for host in ("instagram.com/", "tiktok.com/@", "www.tiktok.com/@", "facebook.com/"):
        if host in lower:
            s = s.rstrip("/").split("/")[-1]
            break
    s = s.lstrip("@").strip()
    # Drop URL noise / path leftovers
    if "/" in s and " " not in s:
        s = s.rstrip("/").split("/")[-1]
    if not s or len(s) > 120:
        return None
    # Reject sentences / captions mistaken for authors
    if s.count(" ") > 6:
        return None
    return s[:120] or None


def extract_schema_author(data: dict) -> Optional[str]:
    """Pull author / creator / publisher from a schema.org Recipe object."""
    for key in ("author", "creator", "publisher"):
        name = normalize_source_author(data.get(key))
        if name:
            return name
    return None


def extract_html_page_author(soup, url: str) -> Optional[str]:
    """Fallback attribution for recipe websites (meta author, site name, host)."""
    # Common recipe-card bylines (WPRM, schema microdata)
    candidates = []
    for class_name in (
        "wprm-recipe-author",
        "wprm-recipe-author-name",
        "author-name",
        "entry-author",
    ):
        candidates.append(soup.find(class_=class_name))
    candidates.append(soup.find(attrs={"itemprop": "author"}))
    for tag in candidates:
        if not tag:
            continue
        name_el = tag.find(attrs={"itemprop": "name"}) or tag.find("a") or tag
        text = name_el.get_text(" ", strip=True) if hasattr(name_el, "get_text") else None
        name = normalize_source_author(text)
        if name:
            return name
    for attrs in (
        {"name": "author"},
        {"property": "author"},
        {"name": "article:author"},
        {"property": "article:author"},
        {"property": "og:site_name"},
        {"name": "application-name"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            name = normalize_source_author(tag["content"])
            if name and name.lower() not in (
                "instagram",
                "tiktok",
                "facebook",
                "youtube",
                "pinterest",
            ):
                return name
    try:
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        if host and host not in (
            "instagram.com",
            "www.instagram.com",
            "tiktok.com",
            "vm.tiktok.com",
            "facebook.com",
            "fb.watch",
            "youtube.com",
            "youtu.be",
        ):
            return host
    except Exception:
        pass
    return None


def with_source_meta(payload: dict, url: str, author: Optional[str] = None) -> dict:
    """Attach source_url + source_author for Honeydew-style attribution."""
    out = dict(payload)
    out.setdefault("source_url", url)
    recipe = out.get("recipe")
    if not author and isinstance(recipe, dict):
        author = recipe.get("source_author")
    author = normalize_source_author(author)
    if author:
        out["source_author"] = author
        if isinstance(recipe, dict):
            recipe = dict(recipe)
            recipe["source_author"] = author
            recipe.setdefault("source_url", url)
            out["recipe"] = recipe
    return out


async def _creator_website_suggestion(
    author: Optional[str],
    *,
    caption: str = "",
    recipe_title: str = "",
) -> dict:
    """Best-effort: find the creator's recipe site to offer after a social import."""
    if not author:
        return {}
    try:
        from services.creator_website import resolve_creator_website

        info = await resolve_creator_website(
            author,
            caption=caption or "",
            recipe_title=recipe_title or "",
        )
        if not info:
            return {}
        out = {
            "creator_website": info.get("creator_website"),
            "creator_website_hint": info.get("creator_website_hint"),
        }
        if info.get("suggested_recipe_url"):
            out["suggested_recipe_url"] = info["suggested_recipe_url"]
        return {k: v for k, v in out.items() if v}
    except Exception as e:
        logger.warning("creator website lookup failed for %s: %s", author, e)
        return {}


def _dm_gate_meta(caption: str = "", author: Optional[str] = None) -> dict:
    """Flag DM / comment-to-receive recipe lead magnets for a client popup."""
    try:
        from services.creator_website import build_dm_gate_meta

        return build_dm_gate_meta(caption or "", handle=author)
    except Exception:
        return {}


def _import_extra_meta(
    author: Optional[str] = None,
    *,
    caption: str = "",
    recipe_title: str = "",
    site_meta: Optional[dict] = None,
) -> dict:
    """Merge creator-website offer + DM-gate explanation for import responses."""
    out = dict(site_meta or {})
    out.update(_dm_gate_meta(caption, author=author))
    return out


def extract_recipe_schema(html: str) -> dict:
    """Extract recipe data from JSON-LD schema (fast and accurate)"""
    pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

    for match in matches:
        try:
            data = json.loads(match)

            # Handle @graph format
            if isinstance(data, dict) and "@graph" in data:
                for item in data["@graph"]:
                    if isinstance(item, dict) and _is_recipe_type(item):
                        return parse_recipe_object(item)

            # Handle array format
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and _is_recipe_type(item):
                        return parse_recipe_object(item)

            # Handle direct Recipe object
            if isinstance(data, dict) and _is_recipe_type(data):
                return parse_recipe_object(data)

        except json.JSONDecodeError:
            continue

    return None


def _unescape_html(text: str) -> str:
    """Decode HTML entities like &amp; → &"""
    import html
    return html.unescape(text) if text else text


def parse_recipe_object(data: dict) -> dict:
    """Parse recipe schema object into our format"""
    # Parse ingredients
    ingredients = []
    raw_ingredients = data.get("recipeIngredient", [])
    for ing in raw_ingredients:
        if isinstance(ing, str):
            ingredients.append({"amount": "", "unit": "", "name": ing.strip()})

    # Parse instructions (handle both HowToStep and HowToSection formats)
    instructions = []
    raw_instructions = data.get("recipeInstructions", [])
    for inst in raw_instructions:
        if isinstance(inst, str):
            instructions.append(inst)
        elif isinstance(inst, dict):
            # Check if it's a HowToSection with nested steps
            if inst.get("@type") == "HowToSection" and "itemListElement" in inst:
                for step in inst.get("itemListElement", []):
                    if isinstance(step, str):
                        instructions.append(step)
                    elif isinstance(step, dict):
                        step_text = step.get("text", "") or step.get("name", "")
                        if step_text:
                            instructions.append(step_text)
            else:
                # Regular HowToStep
                text = inst.get("text", "") or inst.get("name", "")
                if text:
                    instructions.append(text)

    # Parse times
    prep_time = parse_duration(data.get("prepTime", ""))
    cook_time = parse_duration(data.get("cookTime", ""))
    total_time = parse_duration(data.get("totalTime", ""))

    # Parse image
    image = data.get("image", "")
    if isinstance(image, list):
        image = image[0] if image else ""
    elif isinstance(image, dict):
        image = image.get("url", "")

    # Parse servings
    servings = 4
    recipe_yield = data.get("recipeYield", "")
    if isinstance(recipe_yield, list):
        recipe_yield = recipe_yield[0] if recipe_yield else ""
    if recipe_yield:
        match = re.search(r'(\d+)', str(recipe_yield))
        if match:
            servings = int(match.group(1))

    # Parse category
    category = data.get("recipeCategory", "")
    if isinstance(category, list):
        category = category[0] if category else "Other"

    # Parse tags/keywords
    tags = []
    keywords = data.get("keywords", "")
    if isinstance(keywords, str) and keywords:
        tags = [k.strip() for k in keywords.split(",") if k.strip()]
    elif isinstance(keywords, list):
        tags = keywords

    # Parse nutrition when present (schema.org NutritionInformation)
    nutrition = None
    raw_nutrition = data.get("nutrition")
    if isinstance(raw_nutrition, dict):
        def _n(val):
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return int(round(float(val)))
            m = re.search(r"(\d+(?:\.\d+)?)", str(val).replace(",", ""))
            return int(round(float(m.group(1)))) if m else None

        nutrition = {
            "calories": _n(raw_nutrition.get("calories")),
            "protein": _n(raw_nutrition.get("proteinContent")),
            "carbs": _n(raw_nutrition.get("carbohydrateContent")),
            "fat": _n(raw_nutrition.get("fatContent")),
            "fiber": _n(raw_nutrition.get("fiberContent")),
            "sugar": _n(raw_nutrition.get("sugarContent")),
            "sodium": _n(raw_nutrition.get("sodiumContent")),
        }
        if all(v is None for v in nutrition.values()):
            nutrition = None

    result = {
        "title": _unescape_html(data.get("name", "Imported Recipe")),
        "description": _unescape_html(data.get("description", "")),
        "ingredients": ingredients,
        "instructions": [_unescape_html(s) for s in instructions],
        "prep_time": prep_time or (total_time // 2 if total_time else 0),
        "cook_time": cook_time or (total_time // 2 if total_time else 0),
        "servings": servings,
        "image_url": image,
        "category": category or "Other",
        "tags": tags,
    }
    schema_author = extract_schema_author(data)
    if schema_author:
        result["source_author"] = schema_author
    if nutrition:
        result["nutrition"] = nutrition
    return result


def extract_wprm_recipe(soup) -> dict:
    """Extract recipe from WordPress Recipe Maker (WPRM) HTML structure"""
    # Find WPRM recipe container
    recipe_container = soup.find(class_='wprm-recipe-container') or soup.find(class_='wprm-recipe')
    if not recipe_container:
        return None

    # Title
    title_el = recipe_container.find(class_='wprm-recipe-name')
    title = title_el.get_text(strip=True) if title_el else "Imported Recipe"

    # Description/Summary
    desc_el = recipe_container.find(class_='wprm-recipe-summary')
    description = desc_el.get_text(strip=True) if desc_el else ""

    # Ingredients
    ingredients = []
    ing_elements = recipe_container.find_all(class_='wprm-recipe-ingredient')
    for ing in ing_elements:
        amount_el = ing.find(class_='wprm-recipe-ingredient-amount')
        unit_el = ing.find(class_='wprm-recipe-ingredient-unit')
        name_el = ing.find(class_='wprm-recipe-ingredient-name')

        amount = amount_el.get_text(strip=True) if amount_el else ""
        unit = unit_el.get_text(strip=True) if unit_el else ""
        name = name_el.get_text(strip=True) if name_el else ing.get_text(strip=True)

        if name:
            ingredients.append({"amount": amount, "unit": unit, "name": name})

    # Instructions
    instructions = []
    inst_elements = recipe_container.find_all(class_='wprm-recipe-instruction')
    for inst in inst_elements:
        text_el = inst.find(class_='wprm-recipe-instruction-text')
        text = text_el.get_text(strip=True) if text_el else inst.get_text(strip=True)
        if text:
            instructions.append(text)

    # Times
    prep_time = 0
    cook_time = 0
    prep_el = recipe_container.find(class_='wprm-recipe-prep-time-minutes')
    cook_el = recipe_container.find(class_='wprm-recipe-cook-time-minutes')
    if prep_el:
        try:
            prep_time = int(prep_el.get_text(strip=True))
        except ValueError:
            pass
    if cook_el:
        try:
            cook_time = int(cook_el.get_text(strip=True))
        except ValueError:
            pass

    # Servings
    servings = 4
    servings_el = recipe_container.find(class_='wprm-recipe-servings')
    if servings_el:
        try:
            servings = int(servings_el.get_text(strip=True))
        except ValueError:
            pass

    # Image
    image_url = ""
    img_el = recipe_container.find(class_='wprm-recipe-image')
    if img_el:
        img_tag = img_el.find('img')
        if img_tag:
            image_url = img_tag.get('src', '') or img_tag.get('data-src', '')

    if not ingredients and not instructions:
        return None

    return {
        "title": title,
        "description": description,
        "ingredients": ingredients,
        "instructions": instructions,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "servings": servings,
        "image_url": image_url,
        "category": "Other",
        "tags": [],
    }


async def download_social_media(url: str, max_bytes: int = 80 * 1024 * 1024, trace=None):
    """
    Download a social reel's media for transcription / frame-read.

    Order:
      1. SocialFetch resolve (Instagram / TikTok / YouTube / Facebook) → CDN/presigned mp4
      2. yt-dlp with YT_DLP_COOKIES_FILE / YT_DLP_COOKIES when configured

    Returns (bytes, ext) or None.
    """
    import asyncio
    import glob
    import os
    import tempfile

    import yt_dlp

    def _t(step: str, level: str = "info", **data):
        if trace is not None:
            try:
                trace.step(step, level=level, **data)
            except Exception:
                pass

    try:
        from services.instagram_media import download_url_bytes
        from services.socialfetch_media import detect_social_platform, resolve_social_media

        platform = detect_social_platform(url)
        if platform:
            _t("social_resolve_start", platform=platform)
            social = await resolve_social_media(url)
            video_url = (social or {}).get("video_url")
            _t(
                "social_resolve_done",
                platform=platform,
                source=(social or {}).get("source") or "",
                has_video=bool(video_url),
                caption_chars=len(
                    ((social or {}).get("caption") or (social or {}).get("description") or "")
                ),
                author=(social or {}).get("uploader") or "",
            )
            if video_url:
                referer = {
                    "instagram": "https://www.instagram.com/",
                    "tiktok": "https://www.tiktok.com/",
                    "youtube": "https://www.youtube.com/",
                    "facebook": "https://www.facebook.com/",
                }.get(platform, "https://www.google.com/")
                _t("social_cdn_download_start", platform=platform)
                got = await download_url_bytes(video_url, max_bytes=max_bytes, referer=referer)
                if got:
                    logger.info(
                        "Downloaded %s media via %s (%s bytes)",
                        platform,
                        (social or {}).get("source"),
                        len(got[0]),
                    )
                    _t(
                        "social_cdn_download_done",
                        platform=platform,
                        source=(social or {}).get("source"),
                        bytes=len(got[0]),
                        ext=got[1],
                    )
                    return got
                _t("social_cdn_download_empty", level="warning", platform=platform)
    except Exception as e:
        logger.warning(f"Social media resolve/download failed for {url}: {e}")
        _t("social_resolve_error", level="warning", error=str(e)[:300])

    def _dl():
        try:
            with tempfile.TemporaryDirectory(prefix="laro_dl_") as tmp:
                opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "outtmpl": os.path.join(tmp, "media.%(ext)s"),
                    "socket_timeout": 20,
                    "max_filesize": max_bytes,
                    # Prefer a small mp4 so we can pull both frames and audio from it.
                    "format": "mp4/best[ext=mp4]/best",
                }
                opts.update(_yt_dlp_cookie_opts(url))
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.extract_info(url, download=True)
                files = glob.glob(os.path.join(tmp, "media.*"))
                if not files:
                    return None
                path = files[0]
                data = open(path, "rb").read()
                if not data:
                    return None
                return data, (os.path.splitext(path)[1] or ".mp4")
        except Exception as e:
            logger.warning(f"yt-dlp media download failed for {url}: {e}")
            return None

    _t("ytdlp_download_start")
    result = await asyncio.to_thread(_dl)
    if result:
        _t("ytdlp_download_done", bytes=len(result[0]), ext=result[1])
    else:
        _t("ytdlp_download_empty", level="warning")
    return result


REEL_EXTRACTION_RULES = """
This is a cooking reel / short video. Extract the FULL recipe as JSON.

Priority for quantities (highest first):
1) Spoken audio transcript (creators usually say exact grams / tbsp / tsp)
2) On-screen text in the video frames
3) Caption measurements
4) Creator website recipe (if provided) — use for the shared base batter when Whisper
   numbers look garbled (e.g. 15 g yogurt vs a written 50 g)

Hard rules:
- Put EVERY measured ingredient in ingredients[] with separate amount, unit, and name
  (e.g. amount="1", unit="tbsp", name="sweetener" — never bury the measure only in name).
- NEVER invent "to taste", "as needed", or omit an amount when a measure is spoken or shown.
- If you truly did not hear/see an amount, leave amount="" (do not guess "to taste").
- Include swirl / topping / mix-in amounts (butter, cinnamon, extra sweetener) as their own lines.
- Do NOT list temporary mix amounts like "2 tsp of the batter" as ingredients — only real foods.
- When the reel is a microwave / flavour VARIANT of a written pancake-bowl recipe, keep the
  written base batter amounts (egg, milk, yogurt, flour, protein, baking powder, base sweetener)
  if the transcript numbers are clearly garbled, but KEEP spoken amounts for swirl extras
  (melted butter, extra cinnamon, topping sweetener) and the microwave method/times.
- Prefer metric units (g, ml) when the creator or caption uses them; "1/4 cup" milk ≈ 60 ml.
- Instructions must be the method from THIS video (microwave vs oven, times, swirl technique).
- If the caption lists macros (calories / protein / carbs / fat), put them in nutrition.
- servings: usually 1 for single-serve bowls unless clearly stated otherwise.
- Only use what is shown, said, captioned, or confirmed by the linked written recipe.
- If the caption is just hype / hashtags (no ingredient list), treat the spoken transcript as
  the recipe source of truth — ignore missing caption amounts.
- Nutrition label asides are NOT cook amounts: if the speaker says macros like
  "100 grams, 71 calories, 16 grams of protein" and then "roughly 250 grams" into the
  air fryer / pan, use 250 g for that ingredient — the 100 g line is a per-100g label.
- Keep spice names as said (e.g. Chinese five-spice, not "firespice" if that was a
  transcription glitch you can reasonably correct).
- Finishing toppings spoken at the end (cucumber, spring onion, kimchi, sriracha,
  chilli oil, sesame, etc.) MUST appear in ingredients[] — do not stop after the
  main protein / noodles.
- Appliance settings spoken in the video (air fryer °C / °F and minutes, oven temp,
  microwave time) MUST appear in instructions[] — never omit "180 degrees for
  around 15 minutes" style details when they are in the transcript.
""".strip()


def _normalize_reel_ingredients(ingredients: list) -> list:
    """Ensure amount/unit/name are split when the model stuffed measures into name."""
    from utils.food_db import parse_ingredient_amount

    def _qty_str(q) -> str:
        if q is None:
            return ""
        if isinstance(q, float) and q.is_integer():
            return str(int(q))
        return str(q)

    out = []
    for ing in ingredients or []:
        if isinstance(ing, str):
            parsed = parse_ingredient_amount(ing)
            out.append(
                {
                    "amount": _qty_str(parsed.get("quantity")),
                    "unit": parsed.get("unit") or "",
                    "name": parsed.get("name") or ing,
                }
            )
            continue
        if not isinstance(ing, dict):
            continue
        amount = str(ing.get("amount") or "").strip()
        unit = str(ing.get("unit") or "").strip()
        name = str(ing.get("name") or "").strip()
        if (not amount or not unit) and name:
            blob = " ".join(p for p in (amount, unit, name) if p).strip()
            parsed = parse_ingredient_amount(blob)
            if parsed.get("quantity") is not None and not amount:
                amount = _qty_str(parsed["quantity"])
            if parsed.get("unit") and not unit:
                unit = parsed["unit"]
            if parsed.get("name"):
                name = parsed["name"]
        # Whisper / LLM glitches on common spice names
        name_l = name.lower()
        if "chinese" in name_l and ("fire" in name_l or name_l.strip() in ("chinese spice", "chinese")):
            name = "Chinese five-spice"
        out.append({"amount": amount, "unit": unit, "name": name})
    return out


def _recipe_mentions(recipe: dict, *needles: str) -> bool:
    blob = json.dumps(recipe or {}, ensure_ascii=False).lower()
    return any(n.lower() in blob for n in needles)


def _enrich_recipe_from_transcript(recipe: dict, transcript: str) -> dict:
    """
    Backfill finishing garnishes and appliance settings the LLM often drops
    even when they are clear in the Whisper transcript (audio-only reels).
    """
    if not isinstance(recipe, dict):
        return recipe
    text = (transcript or "").strip()
    if len(text) < 20:
        return recipe

    ings = list(recipe.get("ingredients") or [])
    insts = list(recipe.get("instructions") or [])
    names_blob = " ".join(
        (i.get("name") if isinstance(i, dict) else str(i) or "").lower() for i in ings
    )

    def _add_ing(amount: str, unit: str, name: str, *aliases: str):
        nonlocal ings, names_blob
        keys = (name.lower(),) + tuple(a.lower() for a in aliases)
        if any(k in names_blob for k in keys):
            return
        ings.append({"amount": amount, "unit": unit, "name": name})
        names_blob += " " + name.lower()

    # Measured "N grams of X" / "N g X"
    for m in re.finditer(
        r"(\d+(?:\.\d+)?)\s*(?:grams?|g)\s+(?:of\s+)?([a-z][a-z\s]{1,40}?)"
        r"(?=,|\.|and\s+a\s+|and\s+then|\s+and\s+a\s+spring|\s+once\s+|$)",
        text,
        flags=re.I,
    ):
        amt, raw_name = m.group(1), m.group(2).strip(" .,").lower()
        # Skip nutrition-label "100 grams, 71 calories" (name would be empty-ish / calories)
        if any(x in raw_name for x in ("calorie", "protein", "carb", "fat", "macro")):
            continue
        # Keep short food phrases
        raw_name = re.split(r"\b(?:in the|into|from|with|for the)\b", raw_name)[0].strip()
        if len(raw_name) < 3 or len(raw_name) > 40:
            continue
        if raw_name in ("grams", "gram"):
            continue
        # Don't re-add fish if we already have a cook weight (macros 100g line)
        if "fish" in raw_name and _recipe_mentions(recipe, "fish"):
            continue
        pretty = raw_name
        _add_ing(amt, "g", pretty, raw_name)

    # Unmeasured finishers commonly spoken at the end of gym-food reels
    finishers = (
        ("kimchi", ("kimchi",)),
        ("sriracha", ("sriracha", "saranch")),
        ("spring onion", ("spring onion", "spring onions", "green onion")),
        ("sesame seeds", ("sesame",)),
        ("chilli oil", ("chilli oil", "chili oil")),
    )
    lower = text.lower()
    for name, aliases in finishers:
        if any(a in lower for a in aliases):
            _add_ing("", "", name, *aliases)

    # Air fryer / oven temperature + time → instructions
    air = re.search(
        r"(?:air\s*fryer|oven).{0,80}?(\d{2,3})\s*(?:degrees?|°)\s*(?:c|celsius|f|fahrenheit)?"
        r".{0,40}?(\d{1,2})\s*(?:minutes?|mins?)",
        lower,
        flags=re.I | re.S,
    )
    if not air:
        air = re.search(
            r"(\d{2,3})\s*(?:degrees?|°)\s*(?:c|celsius)?\s*(?:for\s+)?(?:around\s+)?"
            r"(\d{1,2})\s*(?:minutes?|mins?)",
            lower,
            flags=re.I,
        )
    if air and not _recipe_mentions(recipe, air.group(1) + "°", f"{air.group(1)} degrees", f"{air.group(2)} minute"):
        temp, mins = air.group(1), air.group(2)
        # Prefer °C for spoken "180 degrees" on UK gym reels
        line = f"Air fry at {temp}°C for around {mins} minutes (from frozen if stated)."
        if "air fry" not in " ".join(str(s).lower() for s in insts):
            # Insert before final serve/combine if possible
            insert_at = max(0, len(insts) - 1) if insts else 0
            insts.insert(insert_at, line)
        else:
            # Patch existing air-fry step missing temp
            for i, s in enumerate(insts):
                sl = str(s).lower()
                if "air fry" in sl and temp not in sl:
                    insts[i] = f"{s.rstrip('.')} at {temp}°C for around {mins} minutes."
                    break

    # Chinese five-spice name fix already in normalize; also replace bad spice rows
    fixed_ings = []
    for ing in ings:
        if not isinstance(ing, dict):
            fixed_ings.append(ing)
            continue
        n = (ing.get("name") or "").lower()
        if "chinese" in n and ("fire" in n or n.strip() == "chinese spice"):
            ing = {**ing, "name": "Chinese five-spice"}
        fixed_ings.append(ing)

    recipe = {**recipe, "ingredients": fixed_ings, "instructions": insts}
    return recipe


def _soft_merge_base_amounts(
    recipe: dict,
    companion_ings: list | None = None,
    companion_text: str = "",
) -> dict:
    """
    When Whisper mishears base-batter grams, prefer matching amounts from the
    creator's written recipe for shared staples. Never overrides swirl extras
    (butter / topping sweetener / cinnamon-roll add-ins) from the reel.
    """
    if not isinstance(recipe, dict):
        return recipe
    ings = recipe.get("ingredients") or []
    if not ings:
        return recipe

    # Only correct these staples — not sweetener (reel often uses tbsp vs written tsp).
    allow = ("yogurt", "milk", "flour", "protein powder", "baking powder", "egg")

    written: dict[str, tuple[str, str, str]] = {}  # key -> (amount, unit, name)

    def _ingest_line(amount: str, unit: str, name: str):
        n = (name or "").lower()
        for key in allow:
            if key == "protein powder":
                if "protein" in n and "yogurt" not in n:
                    written[key] = (amount, unit, name)
            elif key in n:
                written[key] = (amount, unit, name)

    for raw in companion_ings or []:
        if isinstance(raw, dict):
            amt = str(raw.get("amount") or "").strip()
            unit = str(raw.get("unit") or "").strip()
            name = str(raw.get("name") or "").strip()
            if not amt and name:
                from utils.food_db import parse_ingredient_amount

                parsed = parse_ingredient_amount(name)
                if parsed.get("quantity") is not None:
                    q = parsed["quantity"]
                    amt = str(int(q)) if isinstance(q, float) and q.is_integer() else str(q)
                unit = unit or (parsed.get("unit") or "")
                name = parsed.get("name") or name
            if amt or name:
                _ingest_line(amt, unit, name)
        elif isinstance(raw, str):
            from utils.food_db import parse_ingredient_amount

            parsed = parse_ingredient_amount(raw)
            q = parsed.get("quantity")
            amt = ""
            if q is not None:
                amt = str(int(q)) if isinstance(q, float) and q.is_integer() else str(q)
            _ingest_line(amt, parsed.get("unit") or "", parsed.get("name") or raw)

    # Fallback: regex on companion markdown when structured ings missing
    if not written and companion_text:
        patterns = {
            "yogurt": r"(\d+(?:\.\d+)?)\s*(g|ml|cup|cups|tbsp|tsp)\s+[^\n]{0,40}yogurt",
            "milk": r"(\d+(?:\.\d+)?)\s*(g|ml|cup|cups|tbsp|tsp)\s+[^\n]{0,20}milk",
            "flour": r"(\d+(?:\.\d+)?)\s*(g|ml|cup|cups|tbsp|tsp)\s+[^\n]{0,20}flour",
            "protein powder": r"(\d+(?:\.\d+)?)\s*(g|ml|cup|cups|tbsp|tsp)\s+[^\n]{0,40}protein powder",
            "baking powder": r"(\d+/\d+|\d+(?:\.\d+)?)\s*(tsp|tbsp|g)\s+[^\n]{0,20}baking powder",
            "egg": r"(\d+)\s+(?:count\s+)?egg",
        }
        blob = companion_text.lower()
        for key, pat in patterns.items():
            m = re.search(pat, blob, flags=re.I)
            if m:
                written[key] = (
                    m.group(1),
                    m.group(2) if m.lastindex and m.lastindex >= 2 else "",
                    key,
                )

    if not written:
        return recipe

    def _num(s: str) -> float:
        s = (s or "").strip()
        if "/" in s and s.count("/") == 1:
            a, b = s.split("/")
            try:
                return float(a) / float(b)
            except Exception:
                return 0.0
        try:
            return float(s)
        except Exception:
            return 0.0

    out = []
    for ing in ings:
        if not isinstance(ing, dict):
            out.append(ing)
            continue
        name = (ing.get("name") or "").lower()
        if any(x in name for x in ("butter", "brown sugar", "monk fruit", "topping", "swirl")):
            out.append(ing)
            continue
        # Never overwrite spoken tbsp/tsp sweetener with written base sweetener
        if "sweetener" in name or "stevia" in name or "natvia" in name:
            out.append(ing)
            continue
        matched_key = None
        for key in written:
            if key == "protein powder":
                if "protein" in name and "yogurt" not in name:
                    matched_key = key
                    break
            elif key in name:
                matched_key = key
                break
        if not matched_key:
            out.append(ing)
            continue
        w_amt, w_unit, _ = written[matched_key]
        cur = _num(str(ing.get("amount") or ""))
        wr = _num(w_amt)
        if wr > 0 and (cur <= 0 or cur > wr * 2 or cur < wr * 0.5):
            fixed = dict(ing)
            fixed["amount"] = w_amt
            if w_unit:
                fixed["unit"] = w_unit
            out.append(fixed)
        else:
            out.append(ing)
    recipe["ingredients"] = out
    return recipe


def _attach_caption_nutrition(recipe: dict, caption: str) -> dict:
    """Fill nutrition from caption macros when the model omitted them."""
    existing = recipe.get("nutrition") if isinstance(recipe.get("nutrition"), dict) else {}
    nutrition = dict(existing or {})
    text = caption or ""

    # Instagram-style blocks: "Calories: 380" / "Protein: 32g"
    for key, pattern in (
        ("calories", r"(?:calories?|cals?)\s*[:=]?\s*(\d{2,4})\b"),
        ("protein", r"protein\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*g?\b"),
        ("carbs", r"carbs?\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*g?\b"),
        ("fat", r"fat\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*g?\b"),
        ("fiber", r"fib(?:re|er)\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*g?\b"),
    ):
        if nutrition.get(key) not in (None, "", 0):
            continue
        m = re.search(pattern, text, flags=re.I)
        if m:
            try:
                nutrition[key] = int(round(float(m.group(1))))
            except ValueError:
                pass

    try:
        from services.meal_product_import import scrape_macros_from_text

        scraped = scrape_macros_from_text(text)
        for key in ("calories", "protein", "carbs", "fat", "fiber"):
            if nutrition.get(key) in (None, "", 0) and scraped.get(key) not in (None, ""):
                nutrition[key] = scraped[key]
    except Exception:
        pass

    if any(nutrition.get(k) not in (None, "") for k in ("calories", "protein", "carbs", "fat")):
        recipe["nutrition"] = nutrition
    return recipe


async def _companion_recipe_context(author: Optional[str], caption: str, title: str = "") -> str:
    """Best-effort: fetch creator website recipe text to ground amounts."""
    try:
        from services.creator_website import resolve_creator_website
        import httpx
    except Exception:
        return ""
    try:
        info = await resolve_creator_website(author, caption=caption, recipe_title=title)
    except Exception:
        return ""
    if not info:
        return ""
    url = info.get("suggested_recipe_url") or ""
    website = info.get("creator_website") or ""
    if not url and not website:
        return ""

    async def _jina_text(client: httpx.AsyncClient, target: str) -> str:
        jr = await client.get(
            f"https://r.jina.ai/{target}",
            headers={"Accept": "text/plain", "User-Agent": "Mozilla/5.0"},
            timeout=35.0,
            follow_redirects=True,
        )
        body = (jr.text or "").strip()
        if "Just a moment" in body[:800]:
            return ""
        return body

    try:
        async with httpx.AsyncClient() as client:
            text = ""
            # Prefer a matched recipe page; else try on-site search for pancake bowls etc.
            targets: list[str] = []
            if url:
                targets.append(url)
            host = (website or url or "").rstrip("/")
            if host:
                # Stable fallbacks that often hit WPRM cards for this creator niche
                for q in (
                    "baked+protein+pancake+bowls",
                    "protein+pancake+bowls",
                ):
                    targets.append(f"{host}/?s={q}")
                targets.append(host)

            for target in targets:
                text = await _jina_text(client, target)
                if not text or len(text) < 400:
                    continue
                is_search = "/?s=" in target or "You searched for" in text[:500]
                if is_search:
                    host_only = (website or "").rstrip("/")
                    if not host_only and target.startswith("http"):
                        from urllib.parse import urlparse

                        host_only = f"{urlparse(target).scheme}://{urlparse(target).hostname}"
                    slug_hits = re.findall(
                        rf"{re.escape(host_only)}(/[a-z0-9][\w\-/]{{12,}}/?)",
                        text,
                        flags=re.I,
                    )
                    # Prefer exact base pancake-bowl posts over flavoured variants when
                    # the reel is a cinnamon-roll microwave riff on the viral base batter.
                    def _slug_score(slug: str) -> int:
                        low = slug.lower()
                        score = 0
                        if "baked-protein-pancake-bowls" in low and "double" not in low and "almond" not in low and "chocolate" not in low and "lemon" not in low:
                            score += 10
                        if "pancake" in low:
                            score += 2
                        if "bowl" in low:
                            score += 2
                        if "protein" in low:
                            score += 1
                        if any(x in low for x in ("double-chocolate", "almond-croissant", "lemon", "sticky-date")):
                            score -= 3
                        return score

                    ranked = sorted(set(slug_hits), key=_slug_score, reverse=True)
                    picked = ""
                    for slug in ranked:
                        low = slug.lower()
                        if any(
                            skip in low
                            for skip in (
                                "/category/",
                                "/tag/",
                                "/page/",
                                "/author/",
                                "/shop",
                                "/about",
                                "/blog",
                                "/untitled",
                            )
                        ):
                            continue
                        if _slug_score(slug) < 3:
                            continue
                        page = await _jina_text(client, host_only + slug)
                        if page and (
                            "ingredient" in page.lower()
                            or re.search(r"\d+\s*g\s+", page, flags=re.I)
                        ):
                            text = page
                            url = host_only + slug
                            picked = slug
                            break
                    if not picked:
                        text = ""
                        continue

                if len(text) > 400 and (
                    "ingredient" in text.lower()
                    or re.search(r"\d+\s*g\s+", text, flags=re.I)
                ):
                    break
                text = ""

            if not text:
                tip = info.get("creator_website_hint") or ""
                return f"Creator website (open for exact written amounts): {website or url}\nHint: {tip}"

            # Prefer the recipe card region (skip long nav / intro fluff).
            low = text.lower()
            cut = -1
            for marker in (
                "### ingredients",
                "## ingredients",
                "recipeingredient",
                "jump to recipe",
                "wprm-recipe",
                "1 egg",
                "50 g yogurt",
                "35 g flour",
            ):
                idx = low.find(marker)
                if idx >= 0 and (cut < 0 or idx < cut):
                    cut = idx
            if cut > 80:
                text = text[cut:]
            clipped = text[:7000]
            return (
                f"Creator written recipe page ({url or website}) — use amounts from here when they "
                f"match this video; prefer spoken/on-screen amounts when the reel is a "
                f"variant (e.g. microwave cinnamon swirl):\n{clipped}"
            )
    except Exception as e:
        logger.info("companion recipe fetch failed: %s", e)
        return f"Creator website: {website or url}"


async def extract_recipe_from_reel(url: str, caption: str, user: dict, trace=None) -> dict | None:
    """
    Provider-agnostic reel import: download the video, read on-screen text with the
    configured vision model (video frames) and add the spoken audio transcript when a
    Whisper-capable key is available, then extract a recipe. Works with any configured
    AI provider (ollama / anthropic / openai / gemini), not just OpenAI Whisper.

    Returns a recipe dict, or None if nothing usable could be produced.
    """
    import httpx

    from services.video_import import (
        extract_keyframes_base64,
        transcribe_media_bytes,
    )

    def _t(step: str, level: str = "info", **data):
        if trace is not None:
            try:
                trace.step(step, level=level, **data)
            except Exception:
                pass

    # Enrich thin captions via SocialFetch (same process as Instagram) when possible.
    if not caption or len(caption.strip()) < 40:
        try:
            from services.socialfetch_media import detect_social_platform, resolve_social_media

            if detect_social_platform(url):
                _t("caption_enrich_start", caption_chars=len(caption or ""))
                social = await resolve_social_media(url)
                if social:
                    richer = (social.get("caption") or social.get("description") or "").strip()
                    if len(richer) > len(caption or ""):
                        caption = richer
                        logger.info(
                            "Using %s caption (%s chars)",
                            social.get("source"),
                            len(caption),
                        )
                        _t(
                            "caption_enrich_done",
                            source=social.get("source"),
                            caption_chars=len(caption),
                        )
                    else:
                        _t("caption_enrich_unchanged", source=(social or {}).get("source"))
        except Exception as e:
            logger.warning(f"Caption enrich failed for {url}: {e}")
            _t("caption_enrich_error", level="warning", error=str(e)[:300])

    media = await download_social_media(url, trace=trace)
    if not media:
        logger.info(f"No downloadable media for reel {url}")
        from services.instagram_media import caption_looks_like_recipe

        # Many cooking reels never put the recipe in the caption — only on-screen /
        # spoken in the video. Don't burn AI quota guessing from a promo caption.
        if not caption_looks_like_recipe(caption or ""):
            logger.info("Reel caption is not recipe-like; need video share or downloader API")
            _t(
                "reel_no_media_no_recipe_caption",
                caption_chars=len(caption or ""),
            )
            return None

        _t("reel_caption_only_llm_start", caption_chars=len(caption or ""))
        system_prompt = await get_user_prompt(user["id"], "recipe_extraction")
        user_prompt = (
            "This is a cooking reel caption (video could not be downloaded). "
            "Extract the full recipe as JSON from the caption only. "
            "Only use what is actually written.\n\nCreator caption:\n" + caption
        )
        await require_ai_quota(user)
        usage_meta: dict = {}
        async with httpx.AsyncClient() as client:
            result = await call_llm(
                client, system_prompt, user_prompt, user["id"],
                usage_meta=usage_meta, format_json=True,
            )
        if not is_premium_user(user) and not usage_meta.get("cached"):
            await consume_ai_quota(user["id"])
        try:
            recipe = json.loads(clean_llm_json(result))
        except (json.JSONDecodeError, TypeError) as e:
            _t("reel_caption_only_llm_parse_fail", level="warning", error=str(e)[:200])
            return None
        title = (recipe.get("title") or "").strip()
        ings = recipe.get("ingredients") or []
        insts = recipe.get("instructions") or []
        if not title and not ings and not insts:
            _t("reel_caption_only_llm_empty")
            return None
        _t(
            "reel_caption_only_llm_done",
            title=title[:80],
            ingredients=len(ings),
            instructions=len(insts),
        )
        return recipe
    media_bytes, ext = media

    _t("frames_start", media_bytes=len(media_bytes), ext=ext)
    frames = await extract_keyframes_base64(media_bytes, ext, max_frames=12)
    _t("frames_done", frame_count=len(frames or []))
    _t("transcript_start")

    from services.instagram_media import caption_looks_like_recipe
    from services.whisper_finetune import (
        collection_enabled,
        save_finetune_sample,
        socialfetch_transcript_enabled,
    )

    caption_is_recipe = caption_looks_like_recipe(caption or "")
    collect = collection_enabled()
    whisper_text = ""
    audio_wav_path = None
    try:
        whisper_text, audio_wav_path = await transcribe_media_bytes(
            media_bytes, ext, return_audio_path=collect
        )
    except TypeError:
        # Older signature during hot-reload
        whisper_text = await transcribe_media_bytes(media_bytes, ext)
    transcript = whisper_text or ""
    _t("transcript_done", transcript_chars=len(transcript or ""), source="whisper")

    sf_text = ""
    use_sf = socialfetch_transcript_enabled(
        whisper_chars=len(transcript or ""),
        caption_is_recipe=caption_is_recipe,
    )
    if use_sf:
        try:
            from services.socialfetch_media import (
                detect_social_platform,
                fetch_socialfetch_transcript,
            )

            if detect_social_platform(url):
                sf_text = (await fetch_socialfetch_transcript(url)) or ""
                if sf_text:
                    _t("socialfetch_transcript_done", transcript_chars=len(sf_text))
                    # Prefer SF as extract source while bootstrapping labels.
                    if not transcript or len(sf_text) > len(transcript) * 1.05:
                        transcript = sf_text
                    elif sf_text.lower() not in transcript.lower():
                        transcript = (
                            transcript.rstrip()
                            + "\n\n[SocialFetch transcript]\n"
                            + sf_text
                        )
                    from services.video_import import cleanup_cooking_transcript

                    transcript = cleanup_cooking_transcript(transcript)
        except Exception as e:
            logger.info("SocialFetch transcript skipped: %s", e)

    # Persist (audio, label) for fine-tuning — SF/human labels beat raw Whisper.
    if collect and audio_wav_path is not None:
        try:
            label = (sf_text or transcript or whisper_text or "").strip()
            label_source = "socialfetch" if sf_text else "whisper"
            sample = save_finetune_sample(
                audio_wav_path=audio_wav_path,
                label_text=label,
                url=url,
                import_id=(getattr(trace, "import_id", None) or "") if trace else "",
                whisper_text=whisper_text or "",
                socialfetch_text=sf_text or "",
                label_source=label_source,
                platform="instagram" if "instagram" in (url or "").lower() else "",
            )
            if sample:
                _t("whisper_finetune_sample", sample_id=sample.get("id"), source=label_source)
        except Exception as e:
            logger.info("whisper finetune collect skipped: %s", e)
        finally:
            try:
                if audio_wav_path and audio_wav_path.exists():
                    audio_wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    logger.info(
        f"Reel media: {len(frames)} frames, transcript={len(transcript)} chars, caption={len(caption or '')} chars"
    )

    # Resolve creator handle for companion website grounding
    author = None
    try:
        from services.socialfetch_media import detect_social_platform, resolve_social_media

        if detect_social_platform(url):
            social = await resolve_social_media(url)
            if social:
                author = normalize_source_author(
                    social.get("uploader") or social.get("author")
                )
    except Exception:
        author = None

    companion = await _companion_recipe_context(author, caption or "", title="")
    if companion:
        _t("companion_recipe_context", chars=len(companion), author=author or "")

    context_parts = []
    if caption:
        if not caption_is_recipe and transcript:
            context_parts.append(
                "Creator caption (promo/hashtags only — NOT the recipe; "
                "prefer the spoken transcript for all amounts):\n" + caption
            )
        else:
            context_parts.append("Creator caption:\n" + caption)
    if transcript:
        if not caption_is_recipe:
            context_parts.append(
                "Spoken audio transcript (PRIMARY recipe source — caption has no ingredients):\n"
                + transcript
            )
        else:
            context_parts.append("Spoken audio transcript:\n" + transcript)
    if companion:
        context_parts.append(companion)
    context = "\n\n".join(context_parts) or "(no caption or transcript available)"
    audio_primary = bool(transcript and not caption_is_recipe)
    if audio_primary:
        _t("audio_primary_import", transcript_chars=len(transcript))

    if not frames and not caption and not transcript:
        _t("reel_no_frames_caption_transcript")
        return None

    system_prompt = await get_user_prompt(user["id"], "recipe_extraction")
    user_prompt = REEL_EXTRACTION_RULES + "\n\n" + context

    await require_ai_quota(user)
    usage_meta: dict = {}
    # Audio-primary reels: frames distract the model from spoken garnish / temps.
    use_frames = bool(frames) and not audio_primary
    _t(
        "reel_vision_llm_start",
        has_frames=use_frames,
        caption_chars=len(caption or ""),
        transcript_chars=len(transcript or ""),
        companion_chars=len(companion or ""),
        audio_primary=audio_primary,
    )
    async with httpx.AsyncClient() as client:
        if use_frames:
            result = await call_llm_with_image(
                client, system_prompt, user_prompt, frames, user["id"]
            )
        else:
            result = await call_llm(
                client, system_prompt, user_prompt, user["id"],
                usage_meta=usage_meta, format_json=True,
            )
    if not is_premium_user(user) and not usage_meta.get("cached"):
        await consume_ai_quota(user["id"])

    try:
        recipe = json.loads(clean_llm_json(result))
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Reel recipe JSON parse failed for {url}: {e}")
        _t("reel_vision_llm_parse_fail", level="warning", error=str(e)[:200])
        return None

    if isinstance(recipe, dict):
        recipe["ingredients"] = _normalize_reel_ingredients(recipe.get("ingredients") or [])
        recipe = _soft_merge_base_amounts(recipe, companion_text=companion or "")
        recipe = _attach_caption_nutrition(recipe, caption or "")
        if transcript:
            before_n = len(recipe.get("ingredients") or [])
            recipe = _enrich_recipe_from_transcript(recipe, transcript)
            _t(
                "transcript_enrich_done",
                ingredients_before=before_n,
                ingredients_after=len(recipe.get("ingredients") or []),
            )

    title = (recipe.get("title") or "").strip()
    ings = recipe.get("ingredients") or []
    insts = recipe.get("instructions") or []
    if not title and not ings and not insts:
        _t("reel_vision_llm_empty")
        return None
    _t(
        "reel_vision_llm_done",
        title=title[:80],
        ingredients=len(ings),
        instructions=len(insts),
        has_nutrition=bool(recipe.get("nutrition")),
    )
    return recipe


@router.post("/import-feedback")
async def submit_import_feedback(
    data: ImportFeedbackRequest,
    user: dict = Depends(get_current_user),
):
    """
    Rate an AI import and optionally send before/after corrections.

    Ratings: good | ok | bad. Corrections feed Whisper mishear learning when
    the same rename is seen repeatedly.
    """
    from database.repositories.import_feedback_repository import import_feedback_repository
    from services.import_learning import record_recipe_correction
    from services.import_log import ImportTrace

    rating = (data.rating or "").strip().lower()
    if rating not in ("good", "ok", "bad"):
        raise HTTPException(status_code=400, detail="rating must be good, ok, or bad")

    row = await import_feedback_repository.create_feedback(
        user_id=user["id"],
        rating=rating,
        import_id=data.import_id,
        source_url=data.source_url,
        import_mode=data.import_mode,
        recipe_id=data.recipe_id,
        note=data.note or "",
        original_recipe=data.original_recipe,
        corrected_recipe=data.corrected_recipe,
        platform=data.platform,
    )

    learned = {"learned": 0}
    if data.original_recipe and data.corrected_recipe and rating in ("ok", "bad"):
        learned = record_recipe_correction(
            original_recipe=data.original_recipe,
            corrected_recipe=data.corrected_recipe,
            import_id=data.import_id,
        )

    # If the user pasted a corrected spoken transcript in the note, upgrade the
    # fine-tune label for this import_id (best training signal).
    note = (data.note or "").strip()
    if data.import_id and len(note) > 80:
        try:
            from services.whisper_finetune import attach_corrected_label

            if attach_corrected_label(import_id=data.import_id, corrected_text=note):
                learned = {**learned, "whisper_label_updated": True}
        except Exception as e:
            logger.info("whisper label attach skipped: %s", e)

    # Correlate with import JSONL when import_id present
    try:
        trace = ImportTrace(
            "import-feedback",
            user_id=str(user.get("id") or ""),
            url=data.source_url,
            extra={"import_id": data.import_id or "", "rating": rating},
        )
        # Re-use caller's import_id in the log line when provided
        if data.import_id:
            trace.import_id = data.import_id
        trace.step(
            "user_feedback",
            rating=rating,
            note=(data.note or "")[:200],
            learned=learned.get("learned") or 0,
            has_correction=bool(data.corrected_recipe),
        )
        trace.finish("success", rating=rating)
    except Exception as e:
        logger.info("import feedback log skipped: %s", e)

    return {
        "status": "success",
        "id": row["id"],
        "rating": rating,
        "learned": learned,
    }


@router.get("/import-feedback/recent")
async def list_recent_import_feedback(
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """Admin: recent import quality ratings for improving extract heuristics."""
    if (user.get("role") or "").lower() not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    from database.repositories.import_feedback_repository import import_feedback_repository

    rows = await import_feedback_repository.recent(limit=limit)
    for r in rows:
        if hasattr(r.get("created_at"), "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
    return {"feedback": rows}


@router.post("/import-url")
async def import_recipe_from_url(
    request: Request,
    data: ImportURLRequest,
    user: dict = Depends(get_current_user)
):
    """
    Extract recipe from URL using AI (synchronous - returns recipe data for review)
    """
    import httpx
    from services.import_log import ImportTrace, recipe_summary

    # SSRF protection - block internal/private URLs
    url = data.url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    is_safe, error = is_safe_external_url(url)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error)

    # Drop IG share tracking params for fetch/cache; keep original in logs
    original_url = url
    if "instagram.com" in url.lower():
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        url = urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

    trace = ImportTrace(
        "import-url",
        user_id=str(user.get("id") or ""),
        url=url,
        extra={"original_url": original_url, "client": request.headers.get("user-agent", "")[:120]},
    )

    source_author: Optional[str] = None
    social_caption_enrich: str = ""

    def _ok(recipe=None, **extra):
        payload = {
            "status": "success",
            "source_url": url,
            "import_id": trace.import_id,
            **extra,
        }
        if recipe is not None:
            payload["recipe"] = recipe
        return with_source_meta(payload, url, source_author)

    try:
        # Fetch URL content with proper browser headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            # Prefer encodings httpx always decompresses. Requesting `br` can
            # yield undecoded brotli bodies (thin HTML, no JSON-LD / WPRM).
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        async with httpx.AsyncClient() as client:
            trace.step("fetch_html_start", url=url)
            response = await client.get(url, headers=headers, timeout=30.0, follow_redirects=True)
            html = response.text
            trace.step(
                "fetch_html_done",
                status=response.status_code,
                html_chars=len(html or ""),
                final_url=str(response.url),
            )

        def _meal_pack_recipe_from_page(page_html: str, page_text: str):
            """Huel RTD / shakes / pouches → recipe shape for the Recipes library."""
            try:
                from services.meal_product_import import (
                    enrich_products_with_page_macros,
                    extract_products_from_html,
                    normalize_product,
                    product_to_recipe,
                )
                products = [
                    p for p in (normalize_product(x) for x in extract_products_from_html(page_html)) if p
                ]
                if not products:
                    return None
                products = enrich_products_with_page_macros(products, page_text or "")
                return product_to_recipe(products[0])
            except Exception as e:
                logger.warning(f"Meal-pack recipe fallback failed: {e}")
                return None

        url_l = url.lower()

        # Resolve creator handle early (SocialFetch for IG / TikTok / YouTube / Facebook).
        try:
            from services.socialfetch_media import detect_social_platform, resolve_social_media

            if detect_social_platform(url):
                social = await resolve_social_media(url)
                if social:
                    source_author = normalize_source_author(
                        social.get("uploader") or social.get("author")
                    )
                    richer = (
                        social.get("caption")
                        or social.get("description")
                        or ""
                    ).strip()
                    if richer:
                        social_caption_enrich = richer
                    if source_author:
                        trace.step(
                            "source_author",
                            author=source_author,
                            via=social.get("source"),
                            platform=social.get("platform") or detect_social_platform(url),
                        )
        except Exception as e:
            logger.warning("source_author resolve failed: %s", e)

        def _adopt_recipe_author(recipe: Optional[dict], via: str = "schema") -> None:
            """Fill source_author from recipe/page metadata when still unknown."""
            nonlocal source_author
            if source_author or not recipe:
                return
            candidate = normalize_source_author(recipe.get("source_author"))
            if candidate:
                source_author = candidate
                trace.step("source_author", author=source_author, via=via)

        productish = any(
            k in url_l
            for k in (
                "huel",
                "/products/",
                "/product/",
                "ready-to-drink",
                "rtd",
                "hot-and-savoury",
                "hot-savoury",
            )
        )

        # First, try to extract Recipe JSON-LD schema (fast and accurate)
        recipe_data = extract_recipe_schema(html)
        if recipe_data:
            _adopt_recipe_author(recipe_data, via="json-ld")
            ing_count = len(recipe_data.get("ingredients", []))
            inst_count = len(recipe_data.get("instructions", []))
            logger.info(f"JSON-LD found: {recipe_data.get('title', 'Unknown')} - {ing_count} ingredients, {inst_count} instructions")

            if ing_count > 0 and inst_count > 0:
                # Full recipe found
                trace.finish("success", mode="json-ld", **recipe_summary(recipe_data))
                return _ok(recipe_data, used_ai=False)
            elif inst_count > 0:
                # Has instructions but no ingredients - still useful, return it
                logger.warning(f"JSON-LD has instructions but no ingredients, returning partial recipe")
                trace.finish("success", mode="json-ld-partial", **recipe_summary(recipe_data))
                return _ok(recipe_data, used_ai=False)
            else:
                logger.info(f"JSON-LD schema incomplete, trying HTML extraction")
                trace.step("json_ld_incomplete", ingredients=ing_count, instructions=inst_count)

        # Prefer meal-pack / RTD product pages (Huel etc.) before LLM — still a Recipe
        if productish:
            soup_early = BeautifulSoup(html, "html.parser")
            if not source_author:
                page_author = extract_html_page_author(soup_early, url)
                if page_author:
                    source_author = page_author
                    trace.step("source_author", author=source_author, via="html-meta-early")
            for element in soup_early(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            early_text = soup_early.get_text(separator="\n", strip=True)[:20000]
            pack_recipe = _meal_pack_recipe_from_page(html, early_text)
            if pack_recipe:
                logger.info(f"Imported meal pack as recipe: {pack_recipe.get('title')}")
                trace.finish("success", mode="meal_pack_early", **recipe_summary(pack_recipe))
                return _ok(pack_recipe, used_ai=False, import_mode="meal_pack", needs_macros=bool(pack_recipe.get("needs_macros")))

        # Second, try WPRM (WordPress Recipe Maker) HTML extraction
        soup = BeautifulSoup(html, 'html.parser')
        if not source_author:
            page_author = extract_html_page_author(soup, url)
            if page_author:
                source_author = page_author
                trace.step("source_author", author=source_author, via="html-meta")
        wprm_data = extract_wprm_recipe(soup)
        if wprm_data and wprm_data.get("ingredients") and wprm_data.get("instructions"):
            logger.info(f"Extracted recipe from WPRM HTML: {wprm_data.get('title', 'Unknown')}")
            trace.finish("success", mode="wprm", **recipe_summary(wprm_data))
            return _ok(wprm_data, used_ai=False)

        # Check if we got meaningful content from direct fetch
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        text_content = soup.get_text(separator='\n', strip=True)[:8000]
        logger.info(f"Extracted {len(text_content)} chars from HTML")

        # If JSON-LD and WPRM both failed, try Jina Reader for JS-rendered sites
        if not recipe_data and not wprm_data:
            logger.info(f"Thin content detected ({len(text_content)} chars), trying Jina Reader for rendered HTML")
            try:
                trace.step("jina_start", text_chars=len(text_content or ""))
                async with httpx.AsyncClient() as jina_client:
                    jina_resp = await jina_client.get(
                        f"https://r.jina.ai/{url}",
                        headers={"Accept": "text/html", "X-Return-Format": "html"},
                        timeout=30.0,
                        follow_redirects=True
                    )
                    if jina_resp.status_code == 200:
                        rendered_html = jina_resp.text
                        trace.step("jina_done", html_chars=len(rendered_html or ""))

                        # Retry JSON-LD on rendered HTML
                        recipe_data = extract_recipe_schema(rendered_html)
                        if recipe_data:
                            _adopt_recipe_author(recipe_data, via="jina-json-ld")
                            ing_count = len(recipe_data.get("ingredients", []))
                            inst_count = len(recipe_data.get("instructions", []))
                            logger.info(f"Jina JSON-LD found: {recipe_data.get('title', 'Unknown')} - {ing_count} ingredients, {inst_count} instructions")
                            if ing_count > 0:
                                trace.finish(
                                    "success",
                                    mode="jina-json-ld",
                                    **recipe_summary(recipe_data),
                                )
                                return _ok(recipe_data, used_ai=False)

                        # Retry WPRM on rendered HTML
                        rendered_soup = BeautifulSoup(rendered_html, 'html.parser')
                        if not source_author:
                            page_author = extract_html_page_author(rendered_soup, url)
                            if page_author:
                                source_author = page_author
                                trace.step("source_author", author=source_author, via="jina-html-meta")
                        wprm_data = extract_wprm_recipe(rendered_soup)
                        if wprm_data and wprm_data.get("ingredients") and wprm_data.get("instructions"):
                            logger.info(f"Jina WPRM found: {wprm_data.get('title', 'Unknown')}")
                            trace.finish(
                                "success",
                                mode="jina-wprm",
                                **recipe_summary(wprm_data),
                            )
                            return _ok(wprm_data, used_ai=False)

                        # Use Jina text for LLM fallback
                        for el in rendered_soup(['script', 'style', 'nav', 'footer', 'header']):
                            el.decompose()
                        jina_text = rendered_soup.get_text(separator='\n', strip=True)[:8000]
                        if len(jina_text) > len(text_content):
                            text_content = jina_text
                            logger.info(f"Using Jina text content ({len(text_content)} chars) for LLM")
                    else:
                        trace.step("jina_http", level="warning", status=jina_resp.status_code)
            except Exception as e:
                logger.warning(f"Jina Reader fallback failed: {e}")
                trace.step("jina_error", level="warning", error=str(e)[:300])

        logger.info(f"Trying yt-dlp as fallback for: {url}")
        trace.step("video_metadata_start")
        video_meta = await extract_video_metadata(url)
        if video_meta and (video_meta["title"] or video_meta["description"]):
            text_parts = []
            if video_meta["title"]:
                text_parts.append(f"Title: {video_meta['title']}")
            if video_meta["uploader"]:
                text_parts.append(f"By: {video_meta['uploader']}")
            if video_meta["description"]:
                text_parts.append(f"Description:\n{video_meta['description'][:6000]}")

            video_text = "\n".join(text_parts)
            logger.info(f"yt-dlp extracted {len(video_text)} chars of video metadata")
            if not source_author:
                source_author = normalize_source_author(video_meta.get("uploader"))
            trace.step(
                "video_metadata_done",
                chars=len(video_text),
                uploader=video_meta.get("uploader") or "",
                author=source_author or "",
                title=(video_meta.get("title") or "")[:80],
            )

            # Use video metadata if it has more content than the scraped HTML
            if len(video_text) > len(text_content):
                text_content = video_text
                logger.info("Using yt-dlp metadata over HTML text for LLM")
        else:
            trace.step("video_metadata_empty")

        # Social posts (Instagram/TikTok/Facebook): the recipe is usually in the
        # caption, which lives in OG/meta tags rather than the login-walled body
        # (and yt-dlp needs auth cookies for Instagram, so it returns nothing).
        social = any(
            s in url_l
            for s in ("instagram.com", "tiktok.com", "facebook.com", "fb.watch")
        )
        if social:
            caption = extract_social_caption(soup) or ""
            if caption and (
                len(caption) > len(text_content)
                or _looks_like_login_wall(text_content)
            ):
                text_content = caption
                logger.info(f"Using social caption ({len(caption)} chars) for LLM")
            trace.step(
                "social_caption",
                caption_chars=len(caption or ""),
                login_wall=_looks_like_login_wall(text_content),
            )

            # Reels are video. Login walls inflate text_content to thousands of
            # chars of junk HTML, so do NOT gate on len(text_content) < 250 —
            # always try media download for reel/video URLs (needs cookies).
            try_reel = _is_social_reel_url(url) or len(text_content.strip()) < 250
            if try_reel:
                logger.info(f"Reading reel video for {url}")
                trace.step("reel_extract_start", is_reel_url=_is_social_reel_url(url))
                try:
                    reel_recipe = await extract_recipe_from_reel(
                        url, caption, user, trace=trace
                    )
                except HTTPException as he:
                    trace.finish(
                        "error",
                        http_status=he.status_code,
                        detail=str(he.detail)[:300],
                    )
                    raise
                except Exception as e:
                    logger.warning(f"Reel extraction failed for {url}: {e}")
                    trace.step("reel_extract_error", level="warning", error=str(e)[:300])
                    reel_recipe = None
                if reel_recipe:
                    logger.info(f"Imported reel via vision/transcript: {reel_recipe.get('title')}")
                    cap_for_meta = social_caption_enrich or caption or ""
                    site_meta = await _creator_website_suggestion(
                        source_author,
                        caption=cap_for_meta,
                        recipe_title=(reel_recipe.get("title") or ""),
                    )
                    extra = _import_extra_meta(
                        source_author,
                        caption=cap_for_meta,
                        recipe_title=(reel_recipe.get("title") or ""),
                        site_meta=site_meta,
                    )
                    if site_meta:
                        trace.step(
                            "creator_website",
                            website=site_meta.get("creator_website"),
                            suggested=site_meta.get("suggested_recipe_url") or "",
                        )
                    if extra.get("dm_gated"):
                        trace.step("dm_gated_caption", level="info")
                    trace.finish("success", mode="reel", **recipe_summary(reel_recipe))
                    return _ok(
                        reel_recipe,
                        used_ai=True,
                        import_mode="reel",
                        **extra,
                    )
                # Video blocked + caption isn't a recipe → stop with an actionable error
                # instead of feeding OG/login-wall junk to the LLM.
                from services.instagram_media import caption_looks_like_recipe

                if not caption_looks_like_recipe(caption or text_content or ""):
                    cap_for_meta = social_caption_enrich or caption or ""
                    site_meta = await _creator_website_suggestion(
                        source_author,
                        caption=cap_for_meta,
                    )
                    extra = _import_extra_meta(
                        source_author,
                        caption=cap_for_meta,
                        site_meta=site_meta,
                    )
                    if site_meta:
                        trace.step(
                            "creator_website",
                            website=site_meta.get("creator_website"),
                            suggested=site_meta.get("suggested_recipe_url") or "",
                        )
                    msg = (
                        "This reel keeps the recipe in the video, not the caption — "
                        "and the server couldn't download the video. In Instagram, "
                        "tap Share → Laro and share the video file (or save the reel "
                        "and Import → Add video). Paste the caption only if it lists "
                        "ingredients and steps."
                    )
                    if site_meta.get("creator_website_hint"):
                        msg = f"{msg} {site_meta['creator_website_hint']}"
                    if extra.get("dm_gated_message"):
                        msg = f"{msg} {extra['dm_gated_message']}"
                    trace.finish(
                        "error",
                        http_status=422,
                        reason="reel_needs_video",
                        caption_chars=len(caption or text_content or ""),
                    )
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "message": msg,
                            **extra,
                        },
                    )

        logger.info(f"Using {len(text_content)} chars for LLM extraction")
        trace.step("llm_extract_start", text_chars=len(text_content or ""))

        # Before spending AI quota, try meal-pack extraction (works for Huel RTD pages)
        pack_recipe = _meal_pack_recipe_from_page(html, text_content)
        if pack_recipe and pack_recipe.get("title"):
            logger.info(f"Using meal-pack recipe fallback: {pack_recipe.get('title')}")
            trace.finish("success", mode="meal_pack", **recipe_summary(pack_recipe))
            return _ok(pack_recipe, used_ai=False, import_mode="meal_pack", needs_macros=bool(pack_recipe.get("needs_macros")))

        # Get user's custom prompt or default
        system_prompt = await get_user_prompt(user["id"], "recipe_extraction")

        # Call LLM for recipe extraction (counts against free AI quota)
        async with httpx.AsyncClient() as client:
            logger.info(f"Calling LLM for recipe extraction (user: {user['id']})")
            result = await call_llm_metered(
                client,
                system_prompt,
                f"Extract recipe from:\n{text_content}",
                user,
            )

        result = clean_llm_json(result)
        recipe_data = json.loads(result)

        # Guard: don't report success on an empty extraction. Instagram/TikTok reels
        # are video — if nothing scrapeable was found, the LLM returns a blank recipe.
        # Return a clear, actionable error instead of a silent empty "success".
        _title = (recipe_data.get("title") or "").strip()
        _ings = recipe_data.get("ingredients") or []
        _insts = recipe_data.get("instructions") or []
        if not _title and not _ings and not _insts:
            logger.info(f"LLM returned an empty recipe for {url}")
            trace.finish("error", http_status=422, reason="empty_llm_recipe")
            raise HTTPException(
                status_code=422,
                detail=(
                    "Couldn't read a recipe from that link. For Instagram/TikTok, share "
                    "the reel into Laro as a video (or paste the caption). Link-only "
                    "import needs a public reel the server can fetch."
                ),
            )

        logger.info(f"Successfully extracted recipe from URL: {recipe_data.get('title', 'Unknown')}")
        site_meta = {}
        cap_for_meta = social_caption_enrich or text_content or ""
        if social:
            site_meta = await _creator_website_suggestion(
                source_author,
                caption=cap_for_meta,
                recipe_title=_title,
            )
            if site_meta:
                trace.step(
                    "creator_website",
                    website=site_meta.get("creator_website"),
                    suggested=site_meta.get("suggested_recipe_url") or "",
                )
        extra = _import_extra_meta(
            source_author,
            caption=cap_for_meta,
            recipe_title=_title,
            site_meta=site_meta,
        )
        if extra.get("dm_gated"):
            trace.step("dm_gated_caption", level="info")
        trace.finish("success", mode="llm", **recipe_summary(recipe_data))

        return _ok(recipe_data, used_ai=True, **extra)

    except HTTPException as he:
        if "trace" in locals() and trace.status == "started":
            trace.finish(
                "error",
                http_status=getattr(he, "status_code", None),
                detail=str(getattr(he, "detail", ""))[:300],
            )
        # Surface correlating id for support / client logs without changing detail shape
        if "trace" in locals():
            headers = dict(getattr(he, "headers", None) or {})
            headers["X-Import-Id"] = trace.import_id
            he.headers = headers
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse recipe JSON: {e}")
        if "trace" in locals():
            trace.finish("error", http_status=422, reason="json_decode", error=str(e)[:200])
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not extract a recipe from that URL. "
                "For Huel RTD / shakes, open Import and paste the product page — "
                "or add it from Meal Planner → Import with macros."
            ),
            headers={"X-Import-Id": trace.import_id} if "trace" in locals() else None,
        )
    except httpx.TimeoutException:
        if "trace" in locals():
            trace.finish("error", http_status=408, reason="timeout")
        raise HTTPException(
            status_code=408,
            detail="URL took too long to respond. Try again.",
            headers={"X-Import-Id": trace.import_id} if "trace" in locals() else None,
        )
    except httpx.ConnectError:
        if "trace" in locals():
            trace.finish("error", http_status=503, reason="connect")
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the URL. Check the address and try again.",
            headers={"X-Import-Id": trace.import_id} if "trace" in locals() else None,
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching URL: {e.response.status_code}")
        if "trace" in locals():
            trace.finish("error", http_status=502, upstream=e.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"Website returned an error ({e.response.status_code}). Try a different URL.",
            headers={"X-Import-Id": trace.import_id} if "trace" in locals() else None,
        )
    except Exception as e:
        logger.error(f"Import URL failed: {e}")
        if "trace" in locals():
            trace.finish("error", http_status=500, error=sanitize_error_message(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import: {sanitize_error_message(e)}",
            headers={"X-Import-Id": trace.import_id} if "trace" in locals() else None,
        )


@router.post("/import-text")
async def import_recipe_from_text(
    request: Request,
    data: ImportTextRequest,
    user: dict = Depends(get_current_user)
):
    """
    Extract recipe from pasted text using AI (synchronous - returns recipe data for review)
    """
    import httpx
    from services.import_log import ImportTrace, recipe_summary

    text = (data.text or "")[:8000]
    trace = ImportTrace(
        "import-text",
        user_id=str(user.get("id") or ""),
        extra={
            "text_chars": len(text),
            "client": request.headers.get("user-agent", "")[:120],
        },
    )

    try:
        # Get user's custom prompt or default
        from routers.prompts import get_user_prompt
        system_prompt = await get_user_prompt(user["id"], "recipe_extraction")

        # Call LLM for recipe parsing (counts against free AI quota)
        async with httpx.AsyncClient() as client:
            logger.info(f"Calling LLM for text recipe parsing (user: {user['id']})")
            trace.step("llm_start", text_chars=len(text))
            result = await call_llm_metered(
                client,
                system_prompt,
                f"Parse this recipe (may be a social-media caption):\n{text}",
                user,
            )

        result = clean_llm_json(result)
        recipe_data = json.loads(result)

        logger.info(f"Successfully parsed recipe from text: {recipe_data.get('title', 'Unknown')}")
        trace.finish("success", **recipe_summary(recipe_data))

        return {
            "status": "success",
            "recipe": recipe_data,
            "used_ai": True,
            "import_id": trace.import_id,
        }

    except HTTPException as he:
        if "trace" in locals() and trace.status == "started":
            trace.finish(
                "error",
                http_status=getattr(he, "status_code", None),
                detail=str(getattr(he, "detail", ""))[:300],
            )
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse recipe JSON: {e}")
        if "trace" in locals():
            trace.finish("error", http_status=422, reason="json_decode", error=str(e)[:200])
        raise HTTPException(status_code=422, detail="Could not parse recipe from text. Please check the format.")
    except Exception as e:
        logger.error(f"Import text failed: {e}")
        if "trace" in locals():
            trace.finish("error", http_status=500, error=sanitize_error_message(e))
        raise HTTPException(status_code=500, detail=f"Failed to import: {sanitize_error_message(e)}")


@router.post("/import-video")
async def import_recipe_from_video(
    request: Request,
    user: dict = Depends(get_current_user),
    caption: str = Form(""),
    file: UploadFile | None = File(None),
):
    """
    Import a recipe from a social cooking video when the URL is login-walled.

    Accepts:
    - caption (recommended): paste the TikTok / Instagram / YouTube description
    - file (optional): mp4 / mov / webm — audio transcribed via Whisper when OPENAI_API_KEY is set

    Either caption or a transcribable video is required.
    """
    import httpx
    from services.import_log import ImportTrace, recipe_summary
    from services.video_import import build_recipe_source_text, MAX_VIDEO_BYTES

    video_bytes = None
    filename = None
    content_type = None
    if file is not None and file.filename:
        filename = file.filename
        content_type = file.content_type
        video_bytes = await file.read()
        if len(video_bytes) > MAX_VIDEO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Video too large (max {MAX_VIDEO_BYTES // (1024 * 1024)} MB)",
            )

    trace = ImportTrace(
        "import-video",
        user_id=str(user.get("id") or ""),
        extra={
            "caption_chars": len(caption or ""),
            "has_file": bool(filename),
            "filename": (filename or "")[:80],
            "content_type": (content_type or "")[:80],
            "video_bytes": len(video_bytes) if video_bytes else 0,
            "client": request.headers.get("user-agent", "")[:120],
        },
    )

    try:
        source_text, meta = await build_recipe_source_text(
            caption=caption,
            video_bytes=video_bytes,
            filename=filename,
            content_type=content_type,
        )
        trace.step(
            "source_built",
            source_chars=len(source_text or ""),
            had_caption=bool(meta.get("had_caption")),
            transcribed=bool(meta.get("transcribed")),
            frames=meta.get("frame_count") or meta.get("frames") or 0,
        )
    except ValueError as e:
        if "trace" in locals():
            trace.finish("error", http_status=400, error=str(e)[:300])
        raise HTTPException(status_code=400, detail=str(e))

    try:
        from routers.prompts import get_user_prompt
        system_prompt = await get_user_prompt(user["id"], "recipe_extraction")
        if meta.get("audio_primary"):
            # Same priority rules as Instagram reel URL import when caption is promo-only.
            user_prompt = REEL_EXTRACTION_RULES + "\n\n" + source_text
        else:
            user_prompt = (
                "Extract a complete cookable recipe from this social-video content. "
                "Prefer structured ingredients and numbered steps. "
                "If the caption and transcript disagree, prefer the clearer measurements.\n\n"
                f"{source_text}"
            )

        async with httpx.AsyncClient() as client:
            logger.info(
                "Calling LLM for video/caption recipe parse (user=%s caption=%s transcribed=%s audio_primary=%s)",
                user["id"],
                meta.get("had_caption"),
                meta.get("transcribed"),
                meta.get("audio_primary"),
            )
            trace.step("llm_start")
            result = await call_llm_metered(client, system_prompt, user_prompt, user)

        result = clean_llm_json(result)
        recipe_data = json.loads(result)
        logger.info("Video/caption import OK: %s", recipe_data.get("title", "Unknown"))
        trace.finish("success", **recipe_summary(recipe_data), sources=meta)

        return {
            "status": "success",
            "recipe": recipe_data,
            "used_ai": True,
            "import_mode": "video_caption",
            "sources": meta,
            "import_id": trace.import_id,
        }
    except HTTPException as he:
        if "trace" in locals() and trace.status == "started":
            trace.finish(
                "error",
                http_status=getattr(he, "status_code", None),
                detail=str(getattr(he, "detail", ""))[:300],
            )
        raise
    except json.JSONDecodeError as e:
        if "trace" in locals():
            trace.finish("error", http_status=422, reason="json_decode", error=str(e)[:200])
        raise HTTPException(
            status_code=422,
            detail="Could not parse a recipe from that caption/video. Add more caption text and try again.",
        )
    except Exception as e:
        logger.error("Import video failed: %s", e)
        if "trace" in locals():
            trace.finish("error", http_status=500, error=sanitize_error_message(e))
        raise HTTPException(status_code=500, detail=f"Failed to import: {sanitize_error_message(e)}")


def _normalize_auto_meal_plan_days(plan: list, days: int) -> list:
    """
    Normalize AI day indices to 0-based offsets within the week.

    Models often return days 1..7 instead of 0..6. If the minimum day value
    is >= 1 and nothing is 0, shift everything down so the first day is 0.
    """
    if not plan:
        return plan
    day_values = []
    for day_plan in plan:
        try:
            day_values.append(int(day_plan.get("day", day_plan.get("date_offset", 0))))
        except (TypeError, ValueError):
            day_values.append(0)
    if day_values and min(day_values) >= 1 and 0 not in day_values:
        shift = min(day_values)
        for day_plan, raw in zip(plan, day_values):
            day_plan["day"] = max(0, min(days - 1, raw - shift))
    else:
        for day_plan in plan:
            try:
                d = int(day_plan.get("day", day_plan.get("date_offset", 0)))
            except (TypeError, ValueError):
                d = 0
            day_plan["day"] = max(0, min(days - 1, d))
    for day_plan in plan:
        day_plan["date_offset"] = day_plan["day"]
    return plan


def _attach_auto_meal_plan_dates(plan: list, start_date) -> list:
    """Add absolute ISO dates so clients don't guess offsets from 'today'."""
    from datetime import timedelta
    for day_plan in plan:
        try:
            offset = int(day_plan.get("day", 0))
        except (TypeError, ValueError):
            offset = 0
        day_plan["day"] = offset
        day_plan["date_offset"] = offset
        day_plan["date"] = (start_date + timedelta(days=offset)).isoformat()
    return plan


async def _apply_auto_meal_plan_to_week(
    *,
    user: dict,
    plan: list,
    start_date,
    days: int,
    replace_week: bool,
) -> dict:
    """Persist generated meals into the target week; optionally clear first."""
    import uuid
    from datetime import datetime, timezone, timedelta

    household_id = user.get("household_id") or user["id"]
    end_date = start_date + timedelta(days=max(days - 1, 0))
    replaced = 0
    if replace_week:
        replaced = await meal_plan_repository.delete_in_date_range(
            household_id,
            start_date.isoformat(),
            end_date.isoformat(),
        )

    now = datetime.now(timezone.utc).isoformat()
    created = 0
    for day_plan in plan:
        try:
            offset = int(day_plan.get("day", 0))
        except (TypeError, ValueError):
            offset = 0
        meal_date = (start_date + timedelta(days=offset)).isoformat()
        for meal in day_plan.get("meals", []):
            recipe_id = meal.get("recipe_id")
            meal_type = meal.get("meal_type")
            if not recipe_id or not meal_type:
                continue
            plan_doc = {
                "id": str(uuid.uuid4()),
                "date": meal_date,
                "meal_type": meal_type,
                "recipe_id": recipe_id,
                "recipe_title": meal.get("recipe_title") or "",
                "notes": "",
                "adult_boost": (meal.get("adult_boost") or "").strip()[:500],
                "entry_type": "recipe",
                "household_id": household_id,
                "created_at": now,
            }
            await meal_plan_repository.create(plan_doc)
            created += 1

    return {
        "created": created,
        "replaced": replaced,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


@router.post("/auto-meal-plan")
async def auto_generate_meal_plan(
    request: Request,
    data: AutoMealPlanRequest,
    user: dict = Depends(get_current_user)
):
    """
    Auto-generate a meal plan for the week using AI.
    Runs synchronously for immediate response (v2).

    When apply=true (default), also writes meals into the week starting at
    start_date (or today), optionally clearing that date range first.
    """
    import httpx
    import random
    from datetime import datetime, timezone, timedelta

    days = data.days or 7
    if data.start_date:
        try:
            start_date = datetime.strptime(data.start_date[:10], "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")
    else:
        start_date = datetime.now(timezone.utc).date()

    logger.info(
        "Auto meal plan request: days=%s preferences=%s start_date=%s apply=%s replace_week=%s",
        days,
        data.preferences,
        start_date.isoformat(),
        data.apply,
        data.replace_week,
    )

    def fallback_plan(recipes_list: list, plan_days: int) -> dict:
        """Deterministic plan from the user's recipes when the LLM JSON fails."""
        meal_types = ["Breakfast", "Lunch", "Dinner"]
        pool = list(recipes_list)
        random.shuffle(pool)
        if not pool:
            return {
                "plan": [],
                "source": "fallback",
                "start_date": start_date.isoformat(),
                "end_date": (start_date + timedelta(days=max(plan_days - 1, 0))).isoformat(),
                "created": 0,
                "replaced": 0,
            }
        plan = []
        idx = 0
        for day in range(plan_days):
            meals = []
            for mt in meal_types:
                r = pool[idx % len(pool)]
                idx += 1
                meals.append({
                    "meal_type": mt,
                    "recipe_id": r["id"],
                    "recipe_title": r["title"],
                })
            plan.append({
                "day": day,
                "date_offset": day,
                "date": (start_date + timedelta(days=day)).isoformat(),
                "meals": meals,
            })
        return {
            "plan": plan,
            "source": "fallback",
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=max(plan_days - 1, 0))).isoformat(),
            "created": 0,
            "replaced": 0,
        }

    async def finalize(plan_data: dict) -> dict:
        plan = _normalize_auto_meal_plan_days(plan_data.get("plan") or [], days)
        plan = _attach_auto_meal_plan_dates(plan, start_date)
        plan_data["plan"] = plan
        plan_data.setdefault("source", "ai")
        plan_data["start_date"] = start_date.isoformat()
        plan_data["end_date"] = (start_date + timedelta(days=max(days - 1, 0))).isoformat()
        plan_data.setdefault("created", 0)
        plan_data.setdefault("replaced", 0)
        plan_data["applied"] = False
        if data.apply and plan:
            applied = await _apply_auto_meal_plan_to_week(
                user=user,
                plan=plan,
                start_date=start_date,
                days=days,
                replace_week=data.replace_week,
            )
            plan_data.update(applied)
            plan_data["applied"] = True
        return plan_data

    try:
        # Get user's recipes
        logger.info(f"Fetching recipes for meal plan generation (user: {user['id']})")
        recipes = await recipe_repository.find_by_household_or_author(
            author_id=user["id"],
            household_id=user.get("household_id"),
            limit=200
        )

        if len(recipes) < 3:
            raise HTTPException(
                status_code=400,
                detail="Need at least 3 recipes to generate a meal plan"
            )

        # Prepare recipe summary for LLM
        recipes_summary = [
            {
                "id": r["id"],
                "title": r["title"],
                "category": r.get("category", "Other")
            }
            for r in recipes[:30]
        ]

        # Get user's custom prompt or default
        system_prompt = await get_user_prompt(user["id"], "meal_planning")
        system_prompt = (
            (system_prompt or "").strip()
            + "\n\nReply with ONLY a valid JSON object. No markdown fences, no commentary."
            + "\nDay numbers MUST be 0-based: day 0 is the first day of the plan."
        )

        end_date = start_date + timedelta(days=max(days - 1, 0))
        from utils.preference_context import merge_preferences_into_free_text
        from utils.food_db import build_ai_food_context
        from dependencies import user_preferences_repository

        saved_prefs = await user_preferences_repository.find_by_user(user["id"])
        from utils.calendar_busy import load_busyness_for_prefs

        calendar_busyness = await load_busyness_for_prefs(
            saved_prefs, start_date=start_date, days=days
        )
        preference_text = merge_preferences_into_free_text(
            data.preferences,
            saved_prefs,
            start_date=start_date,
            days=days,
            calendar_busyness=calendar_busyness,
        )
        food_ctx = build_ai_food_context(
            saved_prefs,
            query=data.preferences or "meal plan",
            seed=f"{user['id']}:meal-plan:{start_date.isoformat()}",
            limit=14,
        )
        food_block = f"\n\n{food_ctx}" if food_ctx else ""
        user_prompt = f"""Create a {days}-day meal plan starting {start_date.isoformat()} (through {end_date.isoformat()}).
Preferences: {preference_text}{food_block}
Exclude recipes: {data.exclude_recipes or 'none'}

Available recipes:
{json.dumps(recipes_summary)}

Return a JSON object with this structure:
{{
  "plan": [
    {{
      "day": 0,
      "meals": [
        {{"meal_type": "Breakfast", "recipe_id": "id_here", "recipe_title": "title_here", "adult_boost": ""}},
        {{"meal_type": "Lunch", "recipe_id": "id_here", "recipe_title": "title_here", "adult_boost": "optional tip"}},
        {{"meal_type": "Dinner", "recipe_id": "id_here", "recipe_title": "title_here", "adult_boost": "optional tip"}}
      ]
    }}
  ]
}}

IMPORTANT: day MUST be 0-based. Day 0 = {start_date.isoformat()} (first day of this plan), day 1 = next day, through day {days - 1}. Do not use 1-based days. Use recipe IDs from the available recipes list.
Respect kid-friendly / FAMILY ONE-MEAL MODE / WFH lunch pacing, calendar evening busyness (quick/leftover on busy nights), and daily calorie/protein targets from Preferences when choosing meals.
Strictly honour any HARD EXCLUSION adult/kid veto lists in Preferences — never pick recipes that contain vetoed ingredients.
When FAMILY ONE-MEAL MODE is active: pick mild, recognizable, scalable recipes for shared family plates; fill adult_boost with a short tip (no "For adults:" prefix) such as extra chili, cheese, protein side, or spice at the table — especially for Lunch/Dinner. Leave adult_boost empty for Breakfast unless useful."""

        # Call LLM for meal plan generation (counts against free AI quota)
        async with httpx.AsyncClient() as client:
            logger.info(f"Calling LLM for meal plan generation (user: {user['id']})")
            result = await call_llm_metered(
                client,
                system_prompt,
                user_prompt,
                user,
                format_json=True,
                max_tokens=8000,
            )

        cleaned = clean_llm_json(result)
        if not cleaned:
            logger.error(
                "Meal plan LLM returned empty content (user=%s raw_len=%s raw_preview=%r); using fallback",
                user["id"],
                len(result or ""),
                (result or "")[:500],
            )
            return await finalize(fallback_plan(recipes_summary, days))

        try:
            plan_data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse meal plan JSON (user=%s): %s; cleaned_preview=%r raw_len=%s",
                user["id"],
                e,
                (cleaned or "")[:500],
                len(result or ""),
                exc_info=True,
            )
            return await finalize(fallback_plan(recipes_summary, days))

        if not isinstance(plan_data, dict) or not plan_data.get("plan"):
            logger.error(
                "Meal plan JSON missing plan key (user=%s); cleaned_preview=%r; using fallback",
                user["id"],
                (cleaned or "")[:500],
            )
            return await finalize(fallback_plan(recipes_summary, days))

        # Validate recipe IDs; swap invalid ones for a known recipe
        valid_ids = {r["id"] for r in recipes_summary}
        for day_plan in plan_data.get("plan", []):
            for meal in day_plan.get("meals", []):
                if meal.get("recipe_id") not in valid_ids:
                    fallback = random.choice(recipes_summary)
                    meal["recipe_id"] = fallback["id"]
                    meal["recipe_title"] = fallback["title"]
                boost = (meal.get("adult_boost") or "").strip()
                if boost.lower().startswith("for adults:"):
                    boost = boost[len("for adults:"):].strip()
                meal["adult_boost"] = boost[:500]

        logger.info(f"Successfully generated {days}-day meal plan (user: {user['id']})")
        plan_data.setdefault("source", "ai")
        return await finalize(plan_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Meal plan generation failed (user=%s): %s",
            user.get("id"),
            e,
            exc_info=True,
        )
        # Prefer a concrete message when sanitize collapses to the generic catch-all
        safe = sanitize_error_message(e)
        raw = " ".join(str(e).strip().split())[:240]
        detail_body = safe if safe != "An error occurred" else (raw or safe)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate meal plan: {detail_body}",
        )


@router.post("/import-meal-plan")
async def import_meal_plan_document(
    request: Request,
    data: ImportMealPlanRequest,
    user: dict = Depends(get_current_user),
):
    """
    Import a structured weekly meal-plan document (paste text or PDF-extracted text).

    Compatible with printable plans that include a weekly schedule, meal
    breakdowns (ingredients / method / macros), and an optional shopping list —
    e.g. high-protein 7-day plans with dinners + snacks.
    """
    import uuid
    from datetime import datetime, timezone, timedelta
    from utils.recipe_fields import nutrition_to_columns, prepare_recipe_for_response
    from services.meal_plan_import import (
        parse_meal_plan_text,
        parsed_plan_to_dict,
        plan_source_note,
    )

    text = (data.text or "").strip()
    if len(text) < 40:
        raise HTTPException(
            status_code=400,
            detail="Paste the meal plan text (or upload a text-based PDF) to import.",
        )

    try:
        parsed = parse_meal_plan_text(text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Meal plan parse failed: {e}")
        raise HTTPException(status_code=422, detail=f"Could not parse meal plan: {sanitize_error_message(e)}")

    source_note = ""
    if getattr(data, "include_source_note", False):
        source_note = plan_source_note(parsed.title, parsed.daily_targets)

    preview = parsed_plan_to_dict(parsed)
    if source_note:
        preview["source_note"] = source_note

    if not data.apply:
        return {"status": "preview", "plan": preview, "applied": False, "source_note": source_note or None}

    # Resolve start date (day 0 = Monday of imported plan)
    start = None
    if data.start_date:
        try:
            start = datetime.strptime(data.start_date[:10], "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")
    else:
        start = datetime.now(timezone.utc).date()

    household_id = user.get("household_id") or user["id"]
    now = datetime.now(timezone.utc).isoformat()

    if data.replace_week:
        end = start + timedelta(days=6)
        existing = await meal_plan_repository.find_by_household(
            household_id=household_id,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        for row in existing or []:
            try:
                await meal_plan_repository.delete_plan(row["id"])
            except Exception:
                continue

    # Create / reuse recipes
    key_to_recipe_id = {}
    created_recipes = []
    existing_recipes = await recipe_repository.find_by_household_or_author(
        author_id=user["id"],
        household_id=user.get("household_id"),
        limit=500,
    )
    by_title = {(r.get("title") or "").strip().lower(): r for r in (existing_recipes or [])}

    for meal in parsed.meals:
        title_key = meal.title.strip().lower()
        reused = by_title.get(title_key)
        if reused and reused.get("id"):
            key_to_recipe_id[meal.key] = reused["id"]
            continue

        recipe_id = str(uuid.uuid4())
        nutrition = meal.nutrition or {}
        description = (meal.description or "").strip()
        if source_note:
            description = (
                f"{source_note}\n\n{description}".strip()
                if description
                else source_note
            )
        recipe_doc = {
            "id": recipe_id,
            "title": meal.title,
            "description": description,
            "ingredients": meal.ingredients,
            "instructions": meal.instructions,
            "prep_time": 10,
            "cook_time": 25 if meal.category == "Dinner" else 5,
            "servings": meal.servings or 1,
            "category": meal.category or "Other",
            "tags": ["imported-meal-plan", "needs-review", parsed.title[:40]],
            "image_url": "",
            "author_id": user["id"],
            # Match meal-plan scoping: solo users use their user id as household key
            "household_id": user.get("household_id") or user["id"],
            "created_at": now,
            "updated_at": now,
            "dietary_tags": [],
            "difficulty": "easy",
            **nutrition_to_columns(
                {
                    "calories": nutrition.get("calories"),
                    "protein": nutrition.get("protein"),
                    "carbs": nutrition.get("carbs"),
                    "fat": nutrition.get("fat"),
                }
            ),
        }
        await recipe_repository.create(recipe_doc)
        key_to_recipe_id[meal.key] = recipe_id
        by_title[title_key] = recipe_doc
        created_recipes.append(prepare_recipe_for_response(recipe_doc))

    # Create meal plan slots
    created_slots = []
    for day_offset, slots in enumerate(parsed.schedule):
        date_str = (start + timedelta(days=day_offset)).isoformat()
        for slot in slots:
            recipe_id = key_to_recipe_id.get(slot["meal_key"])
            if not recipe_id:
                continue
            plan_id = str(uuid.uuid4())
            plan_doc = {
                "id": plan_id,
                "date": date_str,
                "meal_type": slot.get("meal_type") or "Dinner",
                "recipe_id": recipe_id,
                "recipe_title": slot.get("title") or "",
                "notes": slot.get("slot_label") or "",
                "entry_type": "recipe",
                "household_id": household_id,
                "created_at": now,
            }
            await meal_plan_repository.create(plan_doc)
            created_slots.append(plan_doc)

    shopping_list = None
    if data.create_shopping_list and parsed.shopping_list:
        list_id = str(uuid.uuid4())
        items = []
        for i, ing in enumerate(parsed.shopping_list):
            amount = ing.get("amount") or ""
            unit = ing.get("unit") or ""
            qty = None
            try:
                qty = float(amount) if amount and re.match(r"^\d+(\.\d+)?$", str(amount)) else None
            except Exception:
                qty = None
            items.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": ing.get("name") or "Item",
                    "quantity": qty,
                    "amount": amount,
                    "unit": unit,
                    "category": "Other",
                    "checked": False,
                    "sort_order": i,
                }
            )
        shopping_doc = {
            "id": list_id,
            "name": f"{parsed.title} — shopping",
            "items": items,
            "household_id": household_id,
            "created_at": now,
            "updated_at": now,
        }
        await shopping_list_repository.create(shopping_doc)
        shopping_list = shopping_doc

    logger.info(
        f"Imported meal plan '{parsed.title}' for user {user['id']}: "
        f"{len(created_recipes)} new recipes, {len(created_slots)} slots"
    )

    return {
        "status": "success",
        "applied": True,
        "plan": preview,
        "start_date": start.isoformat(),
        "recipes_created": len(created_recipes),
        "recipes_reused": len(parsed.meals) - len(created_recipes),
        "slots_created": len(created_slots),
        "shopping_list_id": shopping_list["id"] if shopping_list else None,
        "created_recipes": created_recipes,
    }


async def _read_uploaded_pdf_bytes(request: Request):
    """Shared multipart PDF bytes (field name: `file`, max 12MB). Returns (bytes, form)."""
    form = await request.form()
    upload = form.get("file")
    if upload is None:
        raise HTTPException(status_code=400, detail="Missing PDF file (field name: file)")

    raw = await upload.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty PDF upload")
    if len(raw) > 12_000_000:
        raise HTTPException(status_code=400, detail="PDF too large (max 12MB)")
    return raw, form


def _pdf_bytes_to_text(raw: bytes) -> str:
    from services.meal_plan_import import extract_text_from_pdf_bytes

    try:
        return extract_text_from_pdf_bytes(raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


async def _resolve_cookbook_for_user(user: dict, cookbook_id: Optional[str]):
    """Validate optional cookbook_id for attach-on-import. Returns cookbook doc or None."""
    if not cookbook_id:
        return None
    cookbook = await cookbook_repository.find_by_id(cookbook_id)
    if not cookbook:
        raise HTTPException(status_code=404, detail="Cookbook not found")
    if cookbook["user_id"] != user["id"]:
        if not user.get("household_id") or cookbook.get("household_id") != user["household_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to use this cookbook")
    return cookbook


async def _import_recipes_from_scanned_pdf(
    request: Request,
    user: dict,
    raw: bytes,
    *,
    apply: bool = False,
    cookbook_id: Optional[str] = None,
) -> dict:
    """
    Image-only PDF → render pages → vision OCR (multi-recipe JSON).
    Caps pages (SCANNED_PDF_MAX_PAGES, default 5) and consumes free AI quota once.
    """
    import httpx
    from config import settings
    from services.scanned_pdf import (
        DEFAULT_MAX_SCANNED_PAGES,
        render_pdf_pages_to_jpeg_base64,
    )
    from services.recipe_pdf_import import (
        MULTI_RECIPE_PDF_PROMPT,
        dedupe_recipes,
        mark_recipe_for_review,
        normalize_recipe_title,
        parse_llm_recipes_payload,
    )

    cookbook = await _resolve_cookbook_for_user(user, cookbook_id)
    max_pages = int(getattr(settings, "scanned_pdf_max_pages", DEFAULT_MAX_SCANNED_PAGES) or DEFAULT_MAX_SCANNED_PAGES)
    max_pages = max(1, min(max_pages, 10))

    try:
        images, total_pages = render_pdf_pages_to_jpeg_base64(raw, max_pages=max_pages)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not images:
        raise HTTPException(
            status_code=422,
            detail="Could not render PDF pages for OCR. Try photographing pages instead.",
        )

    truncated = total_pages > len(images)
    user_prompt = (
        f"These are {len(images)} page image(s) from a scanned cookbook/recipe PDF"
        f" (PDF has {total_pages} page(s) total"
        + (f"; only the first {len(images)} were OCR'd" if truncated else "")
        + "). Extract EVERY distinct recipe visible. Do not invent missing pages."
    )

    await require_ai_quota(user)
    http_client = getattr(getattr(request, "app", None), "state", None)
    http_client = getattr(http_client, "http_client", None)
    try:
        if http_client is None:
            async with httpx.AsyncClient() as client:
                result = await call_llm_with_images(
                    client, MULTI_RECIPE_PDF_PROMPT, user_prompt, images, user["id"]
                )
        else:
            result = await call_llm_with_images(
                http_client, MULTI_RECIPE_PDF_PROMPT, user_prompt, images, user["id"]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scanned PDF vision OCR failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to OCR scanned PDF: {sanitize_error_message(e)}",
        )

    if not is_premium_user(user):
        await consume_ai_quota(user["id"])

    try:
        parsed = parse_llm_recipes_payload(json.loads(clean_llm_json(result)))
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to parse scanned PDF OCR JSON: {e}")
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not extract recipes from this scanned PDF. "
                "Try fewer/clearer pages, or photograph them via Quick Add → Photos."
            ),
        )

    if not parsed:
        raise HTTPException(
            status_code=422,
            detail="No recipes found in the scanned PDF pages. Try clearer scans or Photo import.",
        )

    # Tag as OCR + review; attach cookbook when provided
    for r in parsed:
        tags = list(r.get("tags") or [])
        for t in ("needs-review", "imported-pdf", "scanned-pdf"):
            if t not in tags:
                tags.append(t)
        r["tags"] = tags
        if cookbook:
            r["cookbook_id"] = cookbook["id"]
            r["source_type"] = "cookbook"

    existing = await recipe_repository.find_by_household_or_author(
        author_id=user["id"],
        household_id=user.get("household_id"),
        limit=500,
    )
    existing_titles = {
        normalize_recipe_title(r.get("title") or "") for r in (existing or [])
    }
    existing_titles.discard("")
    recipes, skipped = dedupe_recipes(parsed, existing_titles)
    recipes = [mark_recipe_for_review(r) for r in recipes]

    base = {
        "kind": "recipes",
        "source": "scanned_pdf",
        "skipped": skipped,
        "needs_review": True,
        "used_ai": True,
        "ocr": True,
        "pages_ocrd": len(images),
        "pages_total": total_pages,
        "pages_truncated": truncated,
        "sections_detected": len(recipes),
        "cookbook": {"id": cookbook["id"], "title": cookbook["title"]} if cookbook else None,
    }
    if not recipes:
        return {
            **base,
            "status": "success",
            "applied": False,
            "recipe_count": 0,
            "recipes": [],
            "recipe": None,
            "message": "All recipes from this scanned PDF already exist or were duplicates.",
        }

    if not apply:
        msg = f"OCR'd {len(images)} page(s)"
        if truncated:
            msg += f" of {total_pages} (cap {max_pages})"
        return {
            **base,
            "status": "preview",
            "applied": False,
            "recipe_count": len(recipes),
            "recipes": recipes,
            "recipe": recipes[0] if len(recipes) == 1 else None,
            "message": f"{msg} — review before saving.",
        }

    from utils.subscription import assert_can_create_recipes
    import uuid
    from datetime import datetime, timezone
    from utils.recipe_fields import nutrition_to_columns, prepare_recipe_for_response

    await assert_can_create_recipes(user, recipe_repository, len(recipes))
    now = datetime.now(timezone.utc).isoformat()
    created = []
    for recipe in recipes:
        recipe_id = str(uuid.uuid4())
        nutrition = recipe.get("nutrition") or {}
        doc = {
            "id": recipe_id,
            "title": recipe["title"],
            "description": recipe.get("description") or "",
            "ingredients": recipe.get("ingredients") or [],
            "instructions": recipe.get("instructions") or [],
            "prep_time": int(recipe.get("prep_time") or 0),
            "cook_time": int(recipe.get("cook_time") or 0),
            "servings": int(recipe.get("servings") or 4),
            "category": recipe.get("category") or "Other",
            "tags": list(recipe.get("tags") or []),
            "image_url": recipe.get("image_url") or "",
            "author_id": user["id"],
            "household_id": user.get("household_id") or user["id"],
            "created_at": now,
            "updated_at": now,
            "dietary_tags": [],
            "difficulty": "easy",
            "source_type": "cookbook" if cookbook else "scanned_pdf",
            **nutrition_to_columns(nutrition if isinstance(nutrition, dict) else {}),
        }
        if cookbook:
            doc["cookbook_id"] = cookbook["id"]
        await recipe_repository.create(doc)
        created.append(prepare_recipe_for_response(doc))

    return {
        **base,
        "status": "success",
        "applied": True,
        "recipe_count": len(created),
        "recipes": created,
        "recipe": created[0] if len(created) == 1 else None,
        "message": f"Added {len(created)} recipe(s) from scanned PDF (marked for review).",
    }


async def _import_recipes_from_pdf_bytes(
    request: Request,
    user: dict,
    raw: bytes,
    *,
    apply: bool = False,
    cookbook_id: Optional[str] = None,
) -> dict:
    """Text-layer PDF when possible; otherwise scanned-page vision OCR."""
    from services.scanned_pdf import extract_text_or_scan_meta

    text, is_scanned = extract_text_or_scan_meta(raw)
    if is_scanned or text is None:
        return await _import_recipes_from_scanned_pdf(
            request, user, raw, apply=apply, cookbook_id=cookbook_id
        )
    result = await _import_recipes_from_pdf_text(
        request, user, text, apply=apply, cookbook_id=cookbook_id
    )
    return result


async def _import_recipes_from_pdf_text(
    request: Request,
    user: dict,
    text: str,
    *,
    apply: bool = False,
    cookbook_id: Optional[str] = None,
) -> dict:
    """
    Shared recipe/meal-plan→recipes PDF extraction.
    Detects weekly meal-plan structure and converts meals to recipes when possible.
    """
    import uuid
    import httpx
    from datetime import datetime, timezone
    from utils.recipe_fields import nutrition_to_columns, prepare_recipe_for_response
    from services.recipe_pdf_import import (
        MULTI_RECIPE_PDF_PROMPT,
        dedupe_recipes,
        mark_recipe_for_review,
        normalize_recipe_title,
        parse_llm_recipes_payload,
        split_recipe_text_chunks,
    )
    from services.meal_plan_url_import import looks_like_structured_meal_plan
    from services.meal_plan_import import parse_meal_plan_text, plan_meals_as_recipes

    cookbook = await _resolve_cookbook_for_user(user, cookbook_id)

    if len((text or "").strip()) < 40:
        raise HTTPException(
            status_code=422,
            detail="PDF text is too short to parse. Try a clearer text PDF or paste the content.",
        )

    parsed = []
    used_ai = True
    chunks = []
    source = "recipes"
    if looks_like_structured_meal_plan(text):
        try:
            plan = parse_meal_plan_text(text)
            parsed = plan_meals_as_recipes(plan)
            used_ai = False
            chunks = [m.title for m in plan.meals]
            source = "meal_plan"
            logger.info(
                "Parsed meal-plan PDF as %s recipe(s) for user %s",
                len(parsed),
                user["id"],
            )
        except ValueError as e:
            logger.info("Structured meal-plan parse skipped: %s", e)

    if not parsed:
        chunks = split_recipe_text_chunks(text)
        if len(chunks) > 1:
            numbered = "\n\n".join(
                f"=== RECIPE SECTION {i + 1} ===\n{chunk[:4000]}"
                for i, chunk in enumerate(chunks[:20])
            )
            user_prompt = (
                f"This PDF has {min(len(chunks), 20)} separated sections. "
                f"Extract each as its own recipe (do not merge sections):\n\n{numbered}"
            )
        else:
            user_prompt = (
                "Extract every distinct recipe in this document as separate objects "
                f"(do not merge dishes):\n\n{text[:14000]}"
            )

        try:
            async with httpx.AsyncClient() as client:
                logger.info(
                    "Parsing recipe PDF (%s section(s)) for user %s",
                    len(chunks),
                    user["id"],
                )
                result = await call_llm_metered(
                    client, MULTI_RECIPE_PDF_PROMPT, user_prompt, user
                )
            result = clean_llm_json(result)
            parsed = parse_llm_recipes_payload(json.loads(result))
            source = "recipes"
        except HTTPException:
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse multi-recipe PDF JSON: {e}")
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not separate recipes from that PDF. "
                    "Try a clearer text PDF, or use Meal Plan → PDF for weekly plans."
                ),
            )
        except Exception as e:
            logger.error(f"Recipe PDF import failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to import: {sanitize_error_message(e)}"
            )

    if not parsed:
        raise HTTPException(
            status_code=422,
            detail="No recipes found in that PDF. Check it is a text-based document.",
        )

    existing = await recipe_repository.find_by_household_or_author(
        author_id=user["id"],
        household_id=user.get("household_id"),
        limit=500,
    )
    existing_titles = {
        normalize_recipe_title(r.get("title") or "") for r in (existing or [])
    }
    existing_titles.discard("")

    recipes, skipped = dedupe_recipes(parsed, existing_titles)
    kind = "recipes"
    base = {
        "kind": kind,
        "source": source,
        "skipped": skipped,
        "needs_review": True,
        "used_ai": used_ai,
        "sections_detected": len(chunks),
    }
    if not recipes:
        return {
            **base,
            "status": "success",
            "applied": False,
            "recipe_count": 0,
            "recipes": [],
            "recipe": None,
            "message": "All recipes in this PDF already exist or were duplicates.",
        }

    recipes = [mark_recipe_for_review(r) for r in recipes]
    if cookbook:
        for r in recipes:
            r["cookbook_id"] = cookbook["id"]
            r["source_type"] = "cookbook"

    if not apply:
        return {
            **base,
            "status": "preview",
            "applied": False,
            "recipe_count": len(recipes),
            "recipes": recipes,
            "recipe": recipes[0] if len(recipes) == 1 else None,
            "cookbook": {"id": cookbook["id"], "title": cookbook["title"]} if cookbook else None,
        }

    from utils.subscription import assert_can_create_recipes
    await assert_can_create_recipes(user, recipe_repository, len(recipes))

    now = datetime.now(timezone.utc).isoformat()
    created = []
    for recipe in recipes:
        recipe_id = str(uuid.uuid4())
        nutrition = recipe.get("nutrition") or {}
        doc = {
            "id": recipe_id,
            "title": recipe["title"],
            "description": recipe.get("description") or "",
            "ingredients": recipe.get("ingredients") or [],
            "instructions": recipe.get("instructions") or [],
            "prep_time": int(recipe.get("prep_time") or 0),
            "cook_time": int(recipe.get("cook_time") or 0),
            "servings": int(recipe.get("servings") or 4),
            "category": recipe.get("category") or "Other",
            "tags": list(recipe.get("tags") or []),
            "image_url": recipe.get("image_url") or "",
            "author_id": user["id"],
            "household_id": user.get("household_id") or user["id"],
            "created_at": now,
            "updated_at": now,
            "dietary_tags": [],
            "difficulty": "easy",
            **nutrition_to_columns(nutrition if isinstance(nutrition, dict) else {}),
        }
        if cookbook:
            doc["cookbook_id"] = cookbook["id"]
            doc["source_type"] = "cookbook"
        await recipe_repository.create(doc)
        created.append(prepare_recipe_for_response(doc))

    return {
        **base,
        "status": "success",
        "applied": True,
        "recipe_count": len(created),
        "recipes": created,
        "recipe": created[0] if len(created) == 1 else None,
        "cookbook": {"id": cookbook["id"], "title": cookbook["title"]} if cookbook else None,
        "message": f"Added {len(created)} recipe(s) marked for review.",
    }


@router.post("/import-recipe-pdf")
async def import_recipe_pdf(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Upload a recipe PDF (text-layer or scanned/image-only) or weekly meal-plan PDF.

    Multipart: `file`. Optional: apply=true, cookbook_id.
    Scanned PDFs are OCR'd via vision (page cap + AI quota).
    """
    raw, form = await _read_uploaded_pdf_bytes(request)
    apply = str(form.get("apply", "false")).lower() in ("1", "true", "yes")
    cookbook_id = (form.get("cookbook_id") or "").strip() or None
    return await _import_recipes_from_pdf_bytes(
        request, user, raw, apply=apply, cookbook_id=cookbook_id
    )


@router.post("/import-pdf")
async def import_pdf(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Unified PDF import for recipes and weekly meal plans.

    Form fields:
      file (required), context=auto|recipes|meal_plan,
      apply, start_date, replace_week, create_shopping_list, cookbook_id
    """
    from services.meal_plan_url_import import looks_like_structured_meal_plan
    from services.scanned_pdf import extract_text_or_scan_meta

    raw, form = await _read_uploaded_pdf_bytes(request)
    context = (form.get("context") or "auto").strip().lower()
    apply = str(form.get("apply", "true")).lower() not in ("0", "false", "no")
    cookbook_id = (form.get("cookbook_id") or "").strip() or None

    text, is_scanned = extract_text_or_scan_meta(raw)
    if is_scanned or text is None:
        # Image-only PDFs always go through recipe OCR (not meal-plan schedule)
        result = await _import_recipes_from_scanned_pdf(
            request, user, raw, apply=apply, cookbook_id=cookbook_id
        )
        return result

    is_plan = looks_like_structured_meal_plan(text)

    want_schedule = context == "meal_plan" or (
        context == "auto" and is_plan and form.get("start_date")
    )
    # Meal Plan UI always prefers schedule when structure matches
    if context == "meal_plan" and is_plan:
        want_schedule = True
    if context == "recipes":
        want_schedule = False

    # Meal Plan uploads: try structured schedule even if the heuristic is unsure
    # (printable plans vary — Lunch / Dinner 1: / weekly grid without "Served").
    if context == "meal_plan" and not want_schedule:
        try:
            from services.meal_plan_import import parse_meal_plan_text

            parse_meal_plan_text(text)
            want_schedule = True
            is_plan = True
        except Exception:
            pass

    if want_schedule and is_plan:
        payload = ImportMealPlanRequest(
            text=text,
            start_date=form.get("start_date") or None,
            apply=apply,
            replace_week=str(form.get("replace_week", "true")).lower() not in ("0", "false", "no"),
            create_shopping_list=str(form.get("create_shopping_list", "false")).lower()
            in ("1", "true", "yes"),
            include_source_note=str(form.get("include_source_note", "false")).lower()
            in ("1", "true", "yes"),
        )
        try:
            result = await import_meal_plan_document(request, payload, user)
            if isinstance(result, dict):
                result = {**result, "kind": "meal_plan"}
            return result
        except HTTPException as e:
            # Fall through to recipes if paste/PDF isn't actually a weekly plan
            if context != "meal_plan" or e.status_code not in (400, 422):
                raise
            logger.info("Meal-plan schedule parse failed; falling back to recipes: %s", e.detail)

    # Recipes path (cookbook PDF, or meal plan imported as recipes)
    result = await _import_recipes_from_pdf_text(
        request, user, text, apply=apply, cookbook_id=cookbook_id
    )
    if isinstance(result, dict) and context == "meal_plan" and result.get("kind") == "recipes":
        result = {
            **result,
            "message": (
                result.get("message")
                or "This PDF looked like recipes (not a weekly schedule). "
                "Added them to your library — drag onto the planner as needed."
            ),
        }
    return result


@router.post("/import-meal-plan-pdf")
async def import_meal_plan_pdf(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Upload a meal-plan or recipe PDF (multipart: `file`).

    Weekly plans are scheduled onto the week. Cookbook/recipe PDFs (text or scanned)
    fall back to importing recipes into the library.
    """
    from services.meal_plan_url_import import looks_like_structured_meal_plan
    from services.scanned_pdf import extract_text_or_scan_meta

    raw, form = await _read_uploaded_pdf_bytes(request)
    cookbook_id = (form.get("cookbook_id") or "").strip() or None
    text, is_scanned = extract_text_or_scan_meta(raw)

    apply = str(form.get("apply", "true")).lower() not in ("0", "false", "no")
    replace_week = str(form.get("replace_week", "true")).lower() not in ("0", "false", "no")
    create_shopping = str(form.get("create_shopping_list", "false")).lower() in (
        "1",
        "true",
        "yes",
    )

    # Prefer scheduling whenever parse succeeds — heuristic alone misses some PDFs.
    if not is_scanned and text:
        should_try_schedule = looks_like_structured_meal_plan(text)
        if not should_try_schedule:
            try:
                from services.meal_plan_import import parse_meal_plan_text

                parse_meal_plan_text(text)
                should_try_schedule = True
            except Exception:
                should_try_schedule = False
        if should_try_schedule:
            payload = ImportMealPlanRequest(
                text=text,
                start_date=form.get("start_date") or None,
                apply=apply,
                replace_week=replace_week,
                create_shopping_list=create_shopping,
                include_source_note=str(form.get("include_source_note", "false")).lower()
                in ("1", "true", "yes"),
            )
            try:
                result = await import_meal_plan_document(request, payload, user)
                if isinstance(result, dict):
                    result = {**result, "kind": "meal_plan"}
                return result
            except HTTPException as e:
                if e.status_code not in (400, 422):
                    raise
                logger.info(
                    "import-meal-plan-pdf schedule failed; falling back to recipes: %s",
                    e.detail,
                )

    if is_scanned or text is None:
        result = await _import_recipes_from_scanned_pdf(
            request, user, raw, apply=apply, cookbook_id=cookbook_id
        )
    else:
        result = await _import_recipes_from_pdf_text(
            request, user, text, apply=apply, cookbook_id=cookbook_id
        )
    if isinstance(result, dict):
        result = {
            **result,
            "kind": "recipes",
            "message": (
                "This PDF did not look like a weekly meal plan, so recipes were "
                f"imported instead ({result.get('recipe_count') or 0}). "
                "Add them to the week from Recipes if needed."
            ),
        }
    return result


@router.post("/import-meal-plan-url")
async def import_meal_plan_from_url(
    request: Request,
    data: ImportMealPlanUrlRequest,
    user: dict = Depends(get_current_user),
):
    """
    Import meal packs from a product URL (Huel shakes/RTD/pouches) or from
    user-confirmed products with macros.

    Preview: url + apply=false → products with online macros when found,
    needs_macros=true when calories are still missing.
    Apply: products=[...] with macros filled in (url optional).
    """
    import uuid
    import httpx
    from datetime import datetime, timezone, timedelta
    from utils.recipe_fields import nutrition_to_columns, prepare_recipe_for_response
    from services.meal_plan_url_import import looks_like_structured_meal_plan
    from services.meal_plan_import import parse_meal_plan_text
    from services.meal_product_import import (
        MEAL_PRODUCT_PROMPT,
        enrich_products_with_page_macros,
        extract_products_from_html,
        fetch_product_page,
        meal_type_for_kind,
        normalize_product,
        parse_llm_products,
        product_needs_macros,
    )

    def _products_from_request(items) -> list:
        out = []
        for item in items or []:
            raw = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            nutrition = {
                "calories": raw.pop("calories", None),
                "protein": raw.pop("protein", None),
                "carbs": raw.pop("carbs", None),
                "fat": raw.pop("fat", None),
                "fiber": raw.pop("fiber", None),
                "sugar": raw.pop("sugar", None),
                "sodium": raw.pop("sodium", None),
            }
            raw["nutrition"] = nutrition
            prod = normalize_product(raw)
            if prod:
                prod["needs_macros"] = product_needs_macros(prod)
                out.append(prod)
        return out

    def _preview_payload(products, source_url=None, used_ai=False, status="preview"):
        missing = [p["title"] for p in products if product_needs_macros(p)]
        return {
            "status": status,
            "applied": False,
            "plan": {
                "title": products[0]["title"] if len(products) == 1 else f"{len(products)} meal packs",
                "import_mode": "meal_packs",
                "products": [
                    {
                        "title": p["title"],
                        "kind": p.get("kind"),
                        "description": p.get("description") or "",
                        "ingredients": p.get("ingredients") or [],
                        "instructions": p.get("instructions") or [],
                        "tags": p.get("tags") or [],
                        "image_url": p.get("image_url") or "",
                        "servings": p.get("servings") or 1,
                        "nutrition": p.get("nutrition"),
                        "meal_type": p.get("meal_type"),
                        "needs_macros": product_needs_macros(p),
                        "calories": (p.get("nutrition") or {}).get("calories"),
                        "protein": (p.get("nutrition") or {}).get("protein"),
                        "carbs": (p.get("nutrition") or {}).get("carbs"),
                        "fat": (p.get("nutrition") or {}).get("fat"),
                    }
                    for p in products
                ],
            },
            "source_url": source_url,
            "used_ai": used_ai,
            "import_mode": "meal_packs",
            "needs_macros": len(missing) > 0,
            "missing_macros": missing,
        }

    async def _apply_products(products, source_url=None, used_ai=False):
        household_id = user.get("household_id") or user["id"]
        now = datetime.now(timezone.utc).isoformat()
        if data.start_date:
            try:
                start = datetime.strptime(data.start_date[:10], "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")
        else:
            start = datetime.now(timezone.utc).date()

        existing_recipes = await recipe_repository.find_by_household_or_author(
            author_id=user["id"],
            household_id=user.get("household_id"),
            limit=500,
        )
        by_title = {(r.get("title") or "").strip().lower(): r for r in (existing_recipes or [])}

        created_recipes = []
        product_meta = []

        for prod in products:
            title_key = prod["title"].strip().lower()
            reused = by_title.get(title_key)
            if reused and reused.get("id"):
                # Update nutrition if user supplied macros and existing had none
                nutrition = prod.get("nutrition") or {}
                if nutrition.get("calories") is not None:
                    try:
                        cols = nutrition_to_columns(nutrition)
                        await recipe_repository.update_recipe(reused["id"], cols)
                    except Exception:
                        pass
                product_meta.append(
                    (reused["id"], prod.get("meal_type") or "Snack", prod["title"])
                )
                continue

            recipe_id = str(uuid.uuid4())
            nutrition = prod.get("nutrition") or {}
            recipe_doc = {
                "id": recipe_id,
                "title": prod["title"],
                "description": prod.get("description") or "",
                "ingredients": prod.get("ingredients") or [],
                "instructions": prod.get("instructions") or [],
                "prep_time": 2,
                "cook_time": 5 if prod.get("kind") == "pouch" else 0,
                "servings": prod.get("servings") or 1,
                "category": prod.get("category") or "Meal Pack",
                "tags": prod.get("tags") or ["meal-pack"],
                "image_url": prod.get("image_url") or "",
                "author_id": user["id"],
                "household_id": user.get("household_id"),
                "created_at": now,
                "updated_at": now,
                "dietary_tags": [],
                "difficulty": "easy",
                "source_url": source_url or "",
                **nutrition_to_columns(
                    {
                        "calories": nutrition.get("calories"),
                        "protein": nutrition.get("protein"),
                        "carbs": nutrition.get("carbs"),
                        "fat": nutrition.get("fat"),
                        "fiber": nutrition.get("fiber"),
                        "sugar": nutrition.get("sugar"),
                        "sodium": nutrition.get("sodium"),
                    }
                ),
            }
            await recipe_repository.create(recipe_doc)
            by_title[title_key] = recipe_doc
            created_recipes.append(prepare_recipe_for_response(recipe_doc))
            product_meta.append(
                (
                    recipe_id,
                    prod.get("meal_type") or meal_type_for_kind(prod.get("kind")),
                    prod["title"],
                )
            )

        created_slots = []
        if data.schedule and product_meta:
            if data.replace_week:
                end = start + timedelta(days=6)
                existing = await meal_plan_repository.find_by_household(
                    household_id=household_id,
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                )
                for row in existing or []:
                    try:
                        await meal_plan_repository.delete_plan(row["id"])
                    except Exception:
                        continue

            for day_offset in range(7):
                recipe_id, meal_type, title = product_meta[day_offset % len(product_meta)]
                plan_doc = {
                    "id": str(uuid.uuid4()),
                    "date": (start + timedelta(days=day_offset)).isoformat(),
                    "meal_type": meal_type or "Snack",
                    "recipe_id": recipe_id,
                    "recipe_title": title,
                    "notes": "Imported meal pack",
                    "entry_type": "recipe",
                    "household_id": household_id,
                    "created_at": now,
                }
                await meal_plan_repository.create(plan_doc)
                created_slots.append(plan_doc)

        shopping_list = None
        if data.create_shopping_list and products:
            items = [
                {
                    "id": str(uuid.uuid4()),
                    "name": prod["title"],
                    "quantity": 1,
                    "amount": "1",
                    "unit": "pack",
                    "category": "Other",
                    "checked": False,
                    "sort_order": i,
                }
                for i, prod in enumerate(products)
            ]
            shopping_doc = {
                "id": str(uuid.uuid4()),
                "name": "Meal packs — shopping",
                "items": items,
                "household_id": household_id,
                "created_at": now,
                "updated_at": now,
            }
            await shopping_list_repository.create(shopping_doc)
            shopping_list = shopping_doc

        preview = _preview_payload(products, source_url=source_url, used_ai=used_ai)["plan"]
        return {
            "status": "success",
            "applied": True,
            "plan": preview,
            "start_date": start.isoformat(),
            "recipes_created": len(created_recipes),
            "recipes_reused": len(products) - len(created_recipes),
            "slots_created": len(created_slots),
            "shopping_list_id": shopping_list["id"] if shopping_list else None,
            "created_recipes": created_recipes,
            "source_url": source_url,
            "used_ai": used_ai,
            "import_mode": "meal_packs",
            "needs_macros": False,
        }

    # ---- Apply path with user-confirmed products (manual macros or edited preview) ----
    if data.products:
        products = _products_from_request(data.products)
        if not products:
            raise HTTPException(status_code=400, detail="No valid meal packs in products list")
        if data.apply:
            missing = [p["title"] for p in products if product_needs_macros(p)]
            if missing:
                return {
                    **_preview_payload(products, source_url=data.url, used_ai=False, status="needs_macros"),
                    "detail": (
                        "Enter calories for: " + ", ".join(missing[:5]) +
                        (f" (+{len(missing)-5} more)" if len(missing) > 5 else "")
                    ),
                }
            return await _apply_products(products, source_url=data.url, used_ai=False)
        return _preview_payload(products, source_url=data.url, used_ai=False)

    if not (data.url or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Paste a product URL, or add a pack with title + calories manually.",
        )

    # ---- Fetch from URL ----
    try:
        html, page_text, source_url = await fetch_product_page(data.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="That website took too long to respond.")
    except Exception as e:
        logger.error(f"Meal URL fetch failed: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch that page: {sanitize_error_message(e)}",
        )

    if looks_like_structured_meal_plan(page_text):
        try:
            parse_meal_plan_text(page_text)
            payload = ImportMealPlanRequest(
                text=page_text,
                start_date=data.start_date,
                apply=data.apply,
                replace_week=data.replace_week,
                create_shopping_list=data.create_shopping_list,
                include_source_note=bool(getattr(data, "include_source_note", False)),
            )
            result = await import_meal_plan_document(request, payload, user)
            if isinstance(result, dict):
                result = {
                    **result,
                    "source_url": source_url,
                    "used_ai": False,
                    "import_mode": "meal_plan",
                    "needs_macros": False,
                }
            return result
        except ValueError:
            pass

    used_ai = False
    products = [normalize_product(p) for p in extract_products_from_html(html)]
    products = [p for p in products if p]

    if not products:
        used_ai = True
        try:
            async with httpx.AsyncClient() as client:
                raw = await call_llm_metered(
                    client,
                    MEAL_PRODUCT_PROMPT,
                    (
                        f"Source URL: {source_url}\n\n"
                        f"Extract meal packs / shakes / pouches / RTD products from:\n\n"
                        f"{page_text[:14000]}"
                    ),
                    user,
                )
            products = parse_llm_products(raw)
        except HTTPException:
            raise
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not extract meal packs from that page. "
                    "Try a Huel product URL, or add the pack manually with macros."
                ),
            )
        except Exception as e:
            logger.error(f"Meal product AI extract failed: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"Could not extract meal packs: {sanitize_error_message(e)}",
            )

    if not products:
        raise HTTPException(
            status_code=422,
            detail=(
                "No meal packs found online. Add one manually with a name and calories, "
                "or try a specific Huel product page."
            ),
        )

    products = enrich_products_with_page_macros(products, page_text)
    preview = _preview_payload(products, source_url=source_url, used_ai=used_ai)

    # Always return preview when macros are missing so the client can ask the user
    if preview["needs_macros"]:
        preview["status"] = "needs_macros"
        return preview

    if not data.apply:
        return preview

    return await _apply_products(products, source_url=source_url, used_ai=used_ai)


@router.post("/fridge-search")
async def fridge_search(
    request: Request,
    data: FridgeSearchRequest,
    user: dict = Depends(get_current_user)
):
    """
    Find recipes matching available ingredients using AI
    """
    import httpx
    from routers.prompts import get_user_prompt

    try:
        ingredients_str = ", ".join(data.ingredients)

        # Get user's recipes
        logger.info(f"Fetching recipes for fridge search (user: {user['id']})")
        all_recipes = await recipe_repository.find_by_household_or_author(
            author_id=user["id"],
            household_id=user.get("household_id"),
            limit=500
        )

        # Get user's custom prompt or default
        system_prompt = await get_user_prompt(user["id"], "fridge_search")
        from utils.preference_context import load_user_prefs_and_food_context

        pref_ctx = await load_user_prefs_and_food_context(
            user["id"],
            pantry_items=data.ingredients,
            query=f"fridge recipe ideas: {ingredients_str}",
        )
        pref_block = f"\n\n{pref_ctx}" if pref_ctx else ""

        # Build prompt based on available recipes
        if len(all_recipes) == 0 and data.search_online:
            user_prompt = (
                f"I have these ingredients: {ingredients_str}. Suggest a unique recipe I can make "
                f"using food-database building blocks when relevant; estimate protein per serving."
                f"{pref_block}"
            )
        else:
            recipes_info = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "ingredients": [
                        i.get("name", i) if isinstance(i, dict) else i
                        for i in r.get("ingredients", [])
                    ][:10]
                }
                for r in all_recipes[:25]
            ]

            user_prompt = f"""Available ingredients: {ingredients_str}

Existing recipes:
{json.dumps(recipes_info) if recipes_info else "No existing recipes yet."}

Find matching recipes{" and suggest a new unique recipe grounded in the food database macros" if data.search_online else ""}.{pref_block}"""

        # Call LLM for fridge search (counts against free AI quota)
        async with httpx.AsyncClient() as client:
            logger.info(f"Calling LLM for fridge search (user: {user['id']})")
            result = await call_llm_metered(client, system_prompt, user_prompt, user)

        if not result or len(result.strip()) == 0:
            logger.warning("LLM returned empty response for fridge search")
            return {
                "status": "success",
                "matching_recipes": [],
                "suggestions": [],
                "ai_recipe_suggestion": None,
                "warning": "AI returned empty response"
            }

        result = clean_llm_json(result)
        ai_result = json.loads(result)

        # Get full recipe data for matches
        matching_recipes = [
            r for r in all_recipes
            if r["id"] in ai_result.get("matching_recipe_ids", [])
        ]

        return {
            "status": "success",
            "matching_recipes": matching_recipes,
            "suggestions": ai_result.get("suggestions", []),
            "ai_recipe_suggestion": ai_result.get("ai_suggestion") or ai_result.get("ai_recipe_suggestion")
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse fridge search JSON: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except Exception as e:
        logger.error(f"Fridge search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Fridge search failed: {sanitize_error_message(e)}")


# =============================================================================
# COOKING AI ASSISTANT
# =============================================================================

from pydantic import BaseModel
from typing import Optional, List, Any


class CookingAssistantRequest(BaseModel):
    recipe_id: Optional[str] = None
    recipe_title: Optional[str] = None
    current_step: Optional[int] = None
    current_instruction: Optional[str] = None
    ingredients: Optional[List[str]] = None
    question: str
    create_recipe: Optional[bool] = False  # If true, user wants a new recipe


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []
    session_id: Optional[str] = None  # Persist turn into chat memory when set / created
    # Optional recipe the user is viewing — scopes answers to that dish
    recipe_id: Optional[str] = None
    recipe_title: Optional[str] = None
    recipe_description: Optional[str] = None
    ingredients: Optional[List[Any]] = None
    instructions: Optional[List[Any]] = None


class ChatSessionReportRequest(BaseModel):
    subject: Optional[str] = None
    details: Optional[str] = None  # Extra notes from the user about the bug
    platform: Optional[str] = "web"
    app_version: Optional[str] = None


def _chat_title_from_message(message: str) -> str:
    text = (message or "").strip().replace("\n", " ")
    if not text:
        return "New chat"
    return (text[:80] + ("…" if len(text) > 80 else ""))


async def _resolve_chat_session(user: dict, session_id: Optional[str], first_message: str):
    """Load an owned session or create a new one titled from the first user message."""
    from database.repositories.ai_chat_repository import ai_chat_session_repository

    if session_id:
        session = await ai_chat_session_repository.find_by_id_for_user(session_id, user["id"])
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session
    return await ai_chat_session_repository.create_session(
        user["id"],
        title=_chat_title_from_message(first_message),
    )


async def _persist_chat_turn(session: dict, user: dict, user_message: str, assistant_message: str):
    from database.repositories.ai_chat_repository import (
        ai_chat_session_repository,
        ai_chat_message_repository,
    )

    await ai_chat_message_repository.append(
        session_id=session["id"],
        user_id=user["id"],
        role="user",
        content=user_message,
    )
    await ai_chat_message_repository.append(
        session_id=session["id"],
        user_id=user["id"],
        role="assistant",
        content=assistant_message,
    )
    title = None
    if (session.get("title") or "").strip() in ("", "New chat"):
        title = _chat_title_from_message(user_message)
    await ai_chat_session_repository.touch(
        session["id"], user_id=user["id"], title=title
    )


@router.get("/chat-sessions")
async def list_chat_sessions(user: dict = Depends(get_current_user)):
    """List the user's saved AI chat sessions (newest first)."""
    from database.repositories.ai_chat_repository import ai_chat_session_repository

    sessions = await ai_chat_session_repository.list_for_user(user["id"])
    return {
        "sessions": [
            {
                "id": s["id"],
                "title": s.get("title") or "New chat",
                "created_at": s.get("created_at").isoformat()
                if hasattr(s.get("created_at"), "isoformat")
                else s.get("created_at"),
                "updated_at": s.get("updated_at").isoformat()
                if hasattr(s.get("updated_at"), "isoformat")
                else s.get("updated_at"),
            }
            for s in sessions
        ]
    }


@router.post("/chat-sessions")
async def create_chat_session(user: dict = Depends(get_current_user)):
    """Start a blank chat session (memory)."""
    from database.repositories.ai_chat_repository import ai_chat_session_repository

    session = await ai_chat_session_repository.create_session(user["id"])
    return {
        "id": session["id"],
        "title": session["title"],
        "created_at": session["created_at"].isoformat()
        if hasattr(session["created_at"], "isoformat")
        else session["created_at"],
        "updated_at": session["updated_at"].isoformat()
        if hasattr(session["updated_at"], "isoformat")
        else session["updated_at"],
        "messages": [],
    }


@router.get("/chat-sessions/{session_id}")
async def get_chat_session(session_id: str, user: dict = Depends(get_current_user)):
    """Load one chat session with messages for review."""
    from database.repositories.ai_chat_repository import (
        ai_chat_session_repository,
        ai_chat_message_repository,
    )

    session = await ai_chat_session_repository.find_by_id_for_user(session_id, user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    messages = await ai_chat_message_repository.list_for_session(
        session_id, user_id=user["id"]
    )
    return {
        "id": session["id"],
        "title": session.get("title") or "New chat",
        "created_at": session.get("created_at").isoformat()
        if hasattr(session.get("created_at"), "isoformat")
        else session.get("created_at"),
        "updated_at": session.get("updated_at").isoformat()
        if hasattr(session.get("updated_at"), "isoformat")
        else session.get("updated_at"),
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "created_at": m.get("created_at").isoformat()
                if hasattr(m.get("created_at"), "isoformat")
                else m.get("created_at"),
            }
            for m in messages
        ],
    }


@router.delete("/chat-sessions/{session_id}")
async def delete_chat_session(session_id: str, user: dict = Depends(get_current_user)):
    from database.repositories.ai_chat_repository import ai_chat_session_repository

    ok = await ai_chat_session_repository.delete_for_user(session_id, user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"status": "deleted", "id": session_id}


@router.post("/chat-sessions/{session_id}/report")
async def report_chat_session_bug(
    session_id: str,
    data: ChatSessionReportRequest,
    user: dict = Depends(get_current_user),
):
    """
    Open a support ticket that includes the full chat transcript so bugs
    in AI replies can be reviewed with context.
    """
    import uuid
    from datetime import datetime, timezone
    from database.repositories.ai_chat_repository import (
        ai_chat_session_repository,
        ai_chat_message_repository,
    )
    from database.repositories.support_ticket_repository import (
        support_ticket_repository,
        support_ticket_message_repository,
    )
    from routers.support import _generate_ticket_number, _notify_ticket_created, _serialize_ticket

    session = await ai_chat_session_repository.find_by_id_for_user(session_id, user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    messages = await ai_chat_message_repository.list_for_session(
        session_id, user_id=user["id"]
    )
    if not messages:
        raise HTTPException(status_code=400, detail="Chat is empty — send a message before reporting")

    lines = []
    for m in messages:
        role = (m.get("role") or "unknown").upper()
        lines.append(f"{role}: {m.get('content') or ''}")
    transcript = "\n\n".join(lines)
    if len(transcript) > 9000:
        transcript = transcript[:9000] + "\n\n…[transcript truncated]"

    user_notes = (data.details or "").strip()
    description = (
        f"Bug report from AI chat.\n"
        f"Session: {session.get('title') or session_id}\n"
        f"Session ID: {session_id}\n\n"
    )
    if user_notes:
        description += f"User notes:\n{user_notes}\n\n"
    description += f"--- Chat transcript ---\n{transcript}"

    subject = (data.subject or "").strip() or f"AI chat bug: {session.get('title') or 'conversation'}"
    subject = subject[:300]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ticket_id = str(uuid.uuid4())
    ticket_number = await _generate_ticket_number()
    ticket = {
        "id": ticket_id,
        "ticket_number": ticket_number,
        "user_id": user["id"],
        "category": "bug",
        "subject": subject,
        "description": description,
        "status": "open",
        "priority": "normal",
        "app_version": (data.app_version or "")[:50] or None,
        "platform": (data.platform or "web")[:50] or None,
        "device_info": f"ai_chat_session_id={session_id}"[:8000],
        "admin_notes": None,
        "resolution": None,
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    }
    await support_ticket_repository.insert(ticket)
    await support_ticket_message_repository.insert(
        {
            "id": str(uuid.uuid4()),
            "ticket_id": ticket_id,
            "user_id": user["id"],
            "is_staff": False,
            "body": description,
            "created_at": now,
        }
    )
    await _notify_ticket_created(ticket, user)
    return {
        "status": "reported",
        "ticket": _serialize_ticket(ticket),
        "session_id": session_id,
    }


@router.post("/chat")
async def chat(
    request: Request,
    data: ChatRequest,
    user: dict = Depends(get_current_user)
):
    """General AI chat assistant for cooking questions (metered; persists to chat memory)."""
    import httpx

    system_prompt = _with_food_topic_scope(
        """You are Laro, a friendly and knowledgeable AI cooking assistant. You help users with:
- Recipe ideas and suggestions
- Cooking techniques and tips
- Ingredient substitutions
- Meal planning advice
- Kitchen equipment recommendations
- Food safety guidance
- Nutrition information

Be conversational, helpful, and encouraging. Keep responses concise but informative.
When suggesting recipes, provide brief overviews rather than full recipes unless specifically asked.
If asked to create a full recipe, format it clearly with ingredients and steps.
When the user has preferred recipe websites, bias new recipe ideas toward those sources' styles
(do not invent paywalled full article text).
When a food database block is provided, invent unique recipes from those foods and their macros,
and estimate protein/calories from the listed per-100g values (approximate — not medical advice).

Formatting rules (important — replies are shown in a small chat bubble):
- Prefer short paragraphs and numbered lists (1. 2. 3.) or simple bullets.
- Do NOT use markdown horizontal rules (--- or ***).
- Do NOT draw lines of dashes or decorative separators.
- Keep bold (**like this**) sparingly; avoid walls of dashes or ASCII tables."""
    )

    from utils.preference_context import load_user_prefs_and_food_context

    pref_ctx = await load_user_prefs_and_food_context(
        user["id"],
        query=data.message,
    )
    if pref_ctx:
        system_prompt = system_prompt + "\n\n" + pref_ctx

    # When the user opened chat from a recipe page, keep answers grounded there
    if data.recipe_title or data.recipe_id:
        ing_lines = []
        for item in (data.ingredients or [])[:20]:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = " ".join(
                    str(x).strip()
                    for x in (item.get("amount"), item.get("unit"), item.get("name"))
                    if x is not None and str(x).strip()
                )
            else:
                text = str(item or "").strip()
            if text:
                ing_lines.append(f"- {text}")
        steps = []
        for i, step in enumerate((data.instructions or [])[:8], 1):
            if isinstance(step, dict):
                text = step.get("text") or step.get("instruction") or step.get("step") or ""
            else:
                text = step
            text = str(text or "").strip()
            if text:
                steps.append(f"{i}. {text}")
        system_prompt += (
            "\n\nThe user is currently viewing this recipe. Prefer answering about it "
            "unless they clearly ask about something else.\n"
            f"Recipe: {data.recipe_title or data.recipe_id or 'Unknown'}\n"
            f"Description: {(data.recipe_description or '').strip() or '(none)'}\n"
            f"Ingredients:\n{chr(10).join(ing_lines) if ing_lines else '(none listed)'}\n"
            f"Method (abbrev.):\n{chr(10).join(steps) if steps else '(none listed)'}"
        )

    # Build conversation context from history
    context_messages = []
    if data.history:
        for msg in data.history[-6:]:  # Last 6 messages for context
            context_messages.append(f"{msg.role}: {msg.content}")

    context = "\n".join(context_messages) if context_messages else ""
    user_message = f"Previous conversation:\n{context}\n\nUser: {data.message}" if context else data.message

    try:
        async with httpx.AsyncClient() as client:
            result = await call_llm_metered(
                client,
                system_prompt,
                user_message,
                user,
            )

        session = await _resolve_chat_session(user, data.session_id, data.message)
        try:
            await _persist_chat_turn(session, user, data.message, result)
        except Exception as persist_err:
            logger.warning(f"Chat memory persist failed: {persist_err}")

        return {
            "response": result,
            "status": "success",
            "session_id": session["id"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat request")


@router.post("/cooking-assistant")
async def cooking_assistant(
    request: Request,
    data: CookingAssistantRequest,
    user: dict = Depends(get_current_user)
):
    """AI assistant for cooking questions during cook mode"""

    # Check if user is asking for a recipe creation
    recipe_keywords = [
        "make me a recipe", "create a recipe", "give me a recipe",
        "suggest a recipe", "recipe for", "how do i make", "how to make",
        "what can i make with", "cook with", "recipe using"
    ]
    wants_recipe = data.create_recipe or any(
        keyword in data.question.lower() for keyword in recipe_keywords
    )

    if wants_recipe:
        # Recipe creation mode
        system_prompt = _with_food_topic_scope(
            """You are a helpful cooking assistant that creates recipes.
When asked for a recipe, respond with BOTH:
1. A friendly message about the recipe
2. A JSON recipe block that can be saved

Format your response like this:
[Your friendly message about the recipe]

```recipe
{
    "title": "Recipe Title",
    "description": "Brief description",
    "ingredients": [
        {"name": "ingredient", "amount": "1", "unit": "cup"}
    ],
    "instructions": [
        "Step 1 instruction",
        "Step 2 instruction"
    ],
    "prep_time": 15,
    "cook_time": 30,
    "servings": 4,
    "category": "Dinner",
    "tags": ["tag1", "tag2"]
}
```

Guidelines:
- Always include the recipe JSON block when creating/suggesting recipes
- Use realistic measurements and clear instructions
- Choose category from: Breakfast, Lunch, Dinner, Dessert, Appetizer, Snack, Beverage, Other
- When a food database block is provided, use those foods as building blocks and estimate
  nutrition (protein/calories) from the listed per-100g macros; invent unique combinations
- Be encouraging and helpful in your message!
- Nutrition figures are approximate planning estimates, not medical advice"""
        )

        context = f"""User Request: {data.question}

If they mention specific ingredients, incorporate them. Create a complete, practical recipe.
If this request is not about food or cooking, do not create a recipe — redirect to Google."""
    else:
        # Regular cooking assistant mode
        system_prompt = _with_food_topic_scope(
            """You are a helpful cooking assistant embedded in a recipe app.
You help users while they are actively cooking. Be concise, practical, and friendly.

Guidelines:
- Give short, actionable answers (2-4 sentences max)
- Focus on the current cooking context
- Suggest substitutions when asked
- Explain techniques simply
- Provide timing guidance
- Be encouraging!
- Do NOT use markdown horizontal rules (---) or decorative dashes

If asked about substitutions, consider:
- Dietary restrictions
- What's commonly available
- How it affects the dish

Current context:"""
        )

        context = f"""
Recipe: {data.recipe_title or 'Unknown'}
Current Step: {data.current_step or 'N/A'}
Instruction: {data.current_instruction or 'N/A'}
Ingredients: {', '.join(data.ingredients[:10]) if data.ingredients else 'N/A'}

User Question: {data.question}"""

    from utils.preference_context import (
        load_user_prefs_and_food_context,
        wants_family_one_meal,
    )
    from dependencies import user_preferences_repository as _prefs_repo

    pref_ctx = await load_user_prefs_and_food_context(
        user["id"],
        pantry_items=data.ingredients,
        query=data.question,
        include_food_db=bool(wants_recipe),
    )
    if pref_ctx:
        system_prompt = system_prompt + "\n\n" + pref_ctx
    if wants_recipe:
        try:
            _saved = await _prefs_repo.find_by_user(user["id"])
        except Exception:
            _saved = None
        if wants_family_one_meal(_saved):
            system_prompt = (
                system_prompt
                + "\n\nWhen creating recipes for this household, prefer mild "
                "family-friendly dishes and include the tag \"family-friendly\" "
                "in the recipe JSON tags array. Optionally add an \"adult_boost\" "
                "string field with a short tip for adults (extra chili, cheese, "
                "protein side) — do not change the kid-suitable base recipe."
            )

    try:
        # Prefer injected client; fall back to a short-lived one
        http_client = getattr(getattr(request, "app", None), "state", None)
        http_client = getattr(http_client, "http_client", None)
        if http_client is None:
            import httpx
            async with httpx.AsyncClient() as client:
                result = await call_llm_metered(client, system_prompt, context, user)
        else:
            result = await call_llm_metered(http_client, system_prompt, context, user)

        if not result or len(result.strip()) == 0:
            return {"answer": "I'm having trouble thinking right now. Try asking in a different way!"}

        response = {"answer": result.strip()}

        # Try to extract recipe JSON if present
        if "```recipe" in result:
            try:
                import re
                recipe_match = re.search(r'```recipe\s*([\s\S]*?)\s*```', result)
                if recipe_match:
                    recipe_json = recipe_match.group(1).strip()
                    recipe_data = json.loads(recipe_json)
                    response["recipe"] = recipe_data
                    # Clean the answer to remove the JSON block for display
                    clean_answer = re.sub(r'```recipe[\s\S]*?```', '', result).strip()
                    response["answer"] = clean_answer
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to parse recipe JSON from response: {e}")

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cooking assistant error: {e}")
        return {"answer": f"Sorry, I couldn't help with that. Make sure AI is configured in Settings -> AI."}


# =============================================================================
# IMAGE EXTRACTION FOR COOKBOOK PAGES
# =============================================================================

import uuid
from datetime import datetime, timezone


@router.post("/extract-from-images")
async def extract_recipe_from_images(
    request: Request,
    data: ImageExtractionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Extract recipe from cookbook page images using AI vision.

    Supports single or multiple images (for multi-page recipes) — ALL images are
    sent to the vision model in one call. Returns extracted recipe data ready to save.
    """
    if not data.images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    if len(data.images) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images allowed per extraction")

    cookbook = await _resolve_cookbook_for_user(user, data.cookbook_id)

    system_prompt = """You are a recipe extraction assistant. Extract recipe information from cookbook page images.

Your task is to carefully read the cookbook page(s) and extract all recipe information.

Return a JSON object with this EXACT structure:
{
    "title": "Recipe Title",
    "description": "Brief description of the dish",
    "ingredients": [
        {"name": "ingredient name", "amount": "1", "unit": "cup"},
        {"name": "another ingredient", "amount": "2", "unit": "tbsp"}
    ],
    "instructions": [
        "First step instruction",
        "Second step instruction"
    ],
    "prep_time": 15,
    "cook_time": 30,
    "servings": 4,
    "category": "Dinner",
    "tags": ["tag1", "tag2"]
}

Guidelines:
- Extract ALL ingredients with amounts and units
- Keep instructions as separate steps (numbered if possible)
- Estimate times if not explicitly stated
- Choose category from: Breakfast, Lunch, Dinner, Dessert, Appetizer, Snack, Beverage, Other
- Add relevant tags (cuisine type, dietary info, etc.)
- If text is hard to read, do your best to interpret it
- For multi-page images, combine all information into one recipe
- Read EVERY provided page image; do not ignore later pages

Return ONLY the JSON object, no additional text or markdown."""

    n = len(data.images)
    if n == 1:
        user_prompt = "Please extract the recipe from this cookbook page image."
    else:
        user_prompt = (
            f"Please extract the recipe from these {n} cookbook page images "
            f"(pages 1–{n} in order). Combine all information into a single recipe."
        )

    try:
        # Image OCR extraction counts against free AI quota (one use for the batch)
        await require_ai_quota(user)
        http_client = getattr(getattr(request, "app", None), "state", None)
        http_client = getattr(http_client, "http_client", None)
        if http_client is None:
            import httpx
            async with httpx.AsyncClient() as client:
                result = await call_llm_with_images(
                    client, system_prompt, user_prompt, data.images, user["id"]
                )
        else:
            result = await call_llm_with_images(
                http_client, system_prompt, user_prompt, data.images, user["id"]
            )
        if not is_premium_user(user):
            await consume_ai_quota(user["id"])

        # Clean and parse JSON response
        cleaned = clean_llm_json(result)
        recipe_data = json.loads(cleaned)

        # Validate required fields
        if not recipe_data.get("title"):
            raise HTTPException(
                status_code=422,
                detail="Could not extract recipe title from image. Please try with a clearer image."
            )

        # Build recipe response
        recipe_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Format ingredients
        ingredients = []
        for ing in recipe_data.get("ingredients", []):
            if isinstance(ing, dict):
                ingredients.append(Ingredient(
                    name=ing.get("name", ""),
                    amount=str(ing.get("amount", "")),
                    unit=ing.get("unit", "")
                ))
            elif isinstance(ing, str):
                ingredients.append(Ingredient(name=ing, amount="", unit=""))

        tags = list(recipe_data.get("tags") or [])
        for t in ("needs-review", "imported-photo"):
            if t not in tags:
                tags.append(t)

        # Build full recipe document
        recipe_doc = {
            "id": recipe_id,
            "title": recipe_data.get("title", "Untitled Recipe"),
            "description": recipe_data.get("description", ""),
            "ingredients": [i.model_dump() for i in ingredients],
            "instructions": recipe_data.get("instructions", []),
            "prep_time": recipe_data.get("prep_time", 0),
            "cook_time": recipe_data.get("cook_time", 0),
            "servings": recipe_data.get("servings", 4),
            "category": recipe_data.get("category", "Other"),
            "tags": tags,
            "image_url": "",
            "author_id": user["id"],
            "household_id": user.get("household_id"),
            "source_type": "cookbook" if cookbook else "photo",
            "cookbook_id": data.cookbook_id,
            "cookbook_page": data.cookbook_page,
            "created_at": now,
            "updated_at": now,
            "needs_review": True,
            "images_processed": n,
        }

        # Return extracted data (not saved yet - client will confirm)
        return {
            "status": "success",
            "message": f"Recipe extracted from {n} image(s)",
            "needs_review": True,
            "images_processed": n,
            "recipe": {
                **RecipeResponse(
                    id=recipe_id,
                    title=recipe_doc["title"],
                    description=recipe_doc["description"],
                    ingredients=ingredients,
                    instructions=recipe_doc["instructions"],
                    prep_time=recipe_doc["prep_time"],
                    cook_time=recipe_doc["cook_time"],
                    servings=recipe_doc["servings"],
                    category=recipe_doc["category"],
                    tags=recipe_doc["tags"],
                    image_url=recipe_doc["image_url"],
                    author_id=recipe_doc["author_id"],
                    household_id=recipe_doc["household_id"],
                    created_at=now,
                    updated_at=now,
                    is_favorite=False
                ).model_dump(),
                "cookbook_id": data.cookbook_id,
                "cookbook_page": data.cookbook_page,
                "source_type": recipe_doc["source_type"],
                "needs_review": True,
            },
            "cookbook": {
                "id": cookbook["id"],
                "title": cookbook["title"]
            } if cookbook else None,
            "page_number": data.cookbook_page
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        raise HTTPException(
            status_code=422,
            detail="Could not extract recipe from image. The AI response was not valid. Please try with a clearer image."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image extraction error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract recipe from image: {sanitize_error_message(e)}"
        )
