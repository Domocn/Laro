"""
Recipe Import Router - Import recipes from multiple platforms
Supports: AllRecipes, Food Network, BBC Good Food, Epicurious, Tasty,
NYT Cooking, Bon Appetit, Serious Eats, Budget Bytes, Delish, and generic Recipe Schema
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
from dependencies import (
    get_current_user,
    recipe_repository,
    recipe_version_repository,
    meal_plan_repository,
)
from utils.activity_logger import log_action
from utils.security import is_safe_external_url
from datetime import datetime, timezone
import uuid
import re
import json
import html
import httpx
import logging

logger = logging.getLogger(__name__)

from services.recipe_macros_jobs import schedule_recipe_macros

router = APIRouter(prefix="/import", tags=["Recipe Import"])


def _row(recipe: dict) -> dict:
    """Split "100g flour" lines like the AI import does, then keep only real recipe columns."""
    try:
        from routers.ai import _split_ingredient_amounts
        recipe = _split_ingredient_amounts(recipe)
    except Exception:
        pass
    from utils.recipe_fields import recipe_row_for_insert
    return recipe_row_for_insert(recipe)


# =============================================================================
# SUPPORTED PLATFORMS
# =============================================================================

SUPPORTED_PLATFORMS = {
    "allrecipes.com": {"name": "AllRecipes", "logo": "🍳", "selector": "recipe-schema"},
    "foodnetwork.com": {"name": "Food Network", "logo": "📺", "selector": "recipe-schema"},
    "bbcgoodfood.com": {"name": "BBC Good Food", "logo": "🇬🇧", "selector": "recipe-schema"},
    "epicurious.com": {"name": "Epicurious", "logo": "🍽️", "selector": "recipe-schema"},
    "tasty.co": {"name": "Tasty", "logo": "😋", "selector": "recipe-schema"},
    "cooking.nytimes.com": {"name": "NYT Cooking", "logo": "📰", "selector": "recipe-schema"},
    "bonappetit.com": {"name": "Bon Appétit", "logo": "👨‍🍳", "selector": "recipe-schema"},
    "seriouseats.com": {"name": "Serious Eats", "logo": "🔬", "selector": "recipe-schema"},
    "budgetbytes.com": {"name": "Budget Bytes", "logo": "💰", "selector": "recipe-schema"},
    "delish.com": {"name": "Delish", "logo": "😍", "selector": "recipe-schema"},
    "simplyrecipes.com": {"name": "Simply Recipes", "logo": "🥗", "selector": "recipe-schema"},
    "skinnytaste.com": {"name": "Skinnytaste", "logo": "🥦", "selector": "recipe-schema"},
    "minimalistbaker.com": {"name": "Minimalist Baker", "logo": "🌱", "selector": "recipe-schema"},
    "halfbakedharvest.com": {"name": "Half Baked Harvest", "logo": "🌾", "selector": "recipe-schema"},
    "pinchofyum.com": {"name": "Pinch of Yum", "logo": "🤤", "selector": "recipe-schema"},
    "pinchofnom.com": {"name": "Pinch of Nom", "logo": "🍽️", "selector": "recipe-schema"},
    "mealime.com": {"name": "Mealime", "logo": "🥗", "selector": "recipe-schema"},
}

# =============================================================================
# MODELS
# =============================================================================

class ImportRequest(BaseModel):
    url: str

class BulkImportRequest(BaseModel):
    urls: List[str]

class MigrateRequest(BaseModel):
    text: str
    source: Optional[str] = "mealime"


class PlanMigratedWeekRequest(BaseModel):
    recipe_ids: List[str]
    meal_type: Optional[str] = "dinner"
    start_date: Optional[str] = None
    days: Optional[int] = 5

class ImportFromTextRequest(BaseModel):
    text: str
    title: Optional[str] = None

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return match.group(1) if match else ""

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


def parse_recipe_schema(html: str) -> dict:
    """Extract recipe data from JSON-LD schema"""
    pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

    for match in matches:
        try:
            data = json.loads(match)

            if isinstance(data, dict) and "@graph" in data:
                for item in data["@graph"]:
                    if isinstance(item, dict) and _is_recipe_type(item):
                        return parse_recipe_object(item)

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and _is_recipe_type(item):
                        return parse_recipe_object(item)

            if isinstance(data, dict) and _is_recipe_type(data):
                return parse_recipe_object(data)

        except json.JSONDecodeError:
            continue

    return None

def parse_recipe_object(data: dict) -> dict:
    """Parse recipe schema object into our format"""
    ingredients = []
    raw_ingredients = data.get("recipeIngredient", [])
    for ing in raw_ingredients:
        if isinstance(ing, str):
            match = re.match(r'^([\d./\s]+)?\s*(\w+)?\s*(.+)$', ing.strip())
            if match:
                amount, unit, name = match.groups()
                ingredients.append({
                    "amount": (amount or "").strip(),
                    "unit": (unit or "").strip() if unit and unit.lower() in ['cup', 'cups', 'tbsp', 'tsp', 'oz', 'lb', 'g', 'kg', 'ml', 'l'] else "",
                    "name": ing.strip()
                })
            else:
                ingredients.append({"amount": "", "unit": "", "name": ing})

    instructions = []
    raw_instructions = data.get("recipeInstructions", [])
    for inst in raw_instructions:
        if isinstance(inst, str):
            instructions.append(inst)
        elif isinstance(inst, dict):
            text = inst.get("text", "") or inst.get("name", "")
            if text:
                instructions.append(html.unescape(text))

    prep_time = parse_duration(data.get("prepTime", ""))
    cook_time = parse_duration(data.get("cookTime", ""))
    total_time = parse_duration(data.get("totalTime", ""))

    image = data.get("image", "")
    if isinstance(image, list):
        image = image[0] if image else ""
    elif isinstance(image, dict):
        image = image.get("url", "")

    servings = 4
    recipe_yield = data.get("recipeYield", "")
    if isinstance(recipe_yield, list):
        recipe_yield = recipe_yield[0] if recipe_yield else ""
    if recipe_yield:
        match = re.search(r'(\d+)', str(recipe_yield))
        if match:
            servings = int(match.group(1))

    return {
        "title": html.unescape(data.get("name", "Imported Recipe") or "Imported Recipe"),
        "description": html.unescape(data.get("description", "") or ""),
        "ingredients": ingredients,
        "instructions": instructions,
        "prep_time": prep_time or (total_time // 2 if total_time else 15),
        "cook_time": cook_time or (total_time // 2 if total_time else 15),
        "servings": servings,
        "image_url": image,
        "cuisine": data.get("recipeCuisine", ""),
        "category": data.get("recipeCategory", ""),
        "tags": data.get("keywords", "").split(",") if isinstance(data.get("keywords"), str) else [],
        "source_url": "",
        "author": data.get("author", {}).get("name", "") if isinstance(data.get("author"), dict) else str(data.get("author", "")),
    }

def _meal_pack_recipe_from_html(html: str, url: str) -> Optional[dict]:
    """
    Huel RTD / shakes / pouches are still first-class Recipes (category Meal Pack).
    Strips client-only flags before persistence.
    """
    try:
        from bs4 import BeautifulSoup
        from services.meal_product_import import (
            enrich_products_with_page_macros,
            extract_products_from_html,
            normalize_product,
            product_to_recipe,
        )

        products = [
            p for p in (normalize_product(x) for x in extract_products_from_html(html)) if p
        ]
        if not products:
            return None
        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        page_text = soup.get_text(separator="\n", strip=True)[:20000]
        products = enrich_products_with_page_macros(products, page_text)
        recipe = product_to_recipe(products[0])
        for key in ("is_meal_pack", "needs_macros", "kind"):
            recipe.pop(key, None)
        recipe["source_url"] = url
        recipe["category"] = recipe.get("category") or "Meal Pack"
        recipe["imported_as"] = "meal_pack"
        return recipe
    except Exception as e:
        logger.warning(f"Meal-pack recipe fallback failed for {url}: {e}")
        return None


async def fetch_recipe_from_url(url: str, http_client) -> dict:
    """Fetch and parse recipe from URL (includes RTD/meal-pack → Recipes)."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = await http_client.get(url, headers=headers, follow_redirects=True, timeout=15.0)
        response.raise_for_status()

        html = response.text
        recipe_data = parse_recipe_schema(html)
        has_full_recipe = bool(
            recipe_data
            and recipe_data.get("ingredients")
            and recipe_data.get("instructions")
        )

        url_l = (url or "").lower()
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

        # Product / RTD pages → Recipes under Meal Pack (even with no cook steps)
        if productish or not has_full_recipe:
            pack = _meal_pack_recipe_from_html(html, url)
            if pack:
                return pack

        if recipe_data:
            recipe_data["source_url"] = url
            if not recipe_data.get("category"):
                recipe_data["category"] = "Other"
            return recipe_data

        # Open-source scrapers before giving up (no AI on this path)
        try:
            from services.oss_recipe_scrape import scrape_recipe_oss

            oss = scrape_recipe_oss(url, html)
            if oss and (oss.get("ingredients") or oss.get("instructions")):
                oss["source_url"] = url
                if not oss.get("category"):
                    oss["category"] = "Other"
                return oss
        except Exception as e:
            logger.info("OSS scrape in recipe_import failed for %s: %s", url, e)

        return None
    except Exception as e:
        logger.error(f"Error fetching recipe from {url}: {e}", exc_info=True)
        return None

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/platforms")
async def list_supported_platforms():
    """List all supported recipe platforms"""
    platforms = []
    for domain, info in SUPPORTED_PLATFORMS.items():
        platforms.append({
            "domain": domain,
            "name": info["name"],
            "logo": info["logo"],
            "example_url": f"https://www.{domain}/recipes/..."
        })

    return {
        "platforms": platforms,
        "total": len(platforms),
        "note": "Any site with Recipe Schema (JSON-LD) is also supported!"
    }

@router.post("/url")
async def import_from_url(
    request: Request,
    data: ImportRequest,
    user: dict = Depends(get_current_user)
):
    """Import a recipe from a URL"""
    url = data.url.strip()

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # SSRF protection - block internal/private URLs
    is_safe, error = is_safe_external_url(url)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error)

    # Instagram / TikTok / Facebook need the AI path (same as Android POST /ai/import-url).
    try:
        from services.socialfetch_media import detect_social_platform

        if detect_social_platform(url):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Instagram, TikTok, and Facebook links use AI import "
                    "(same as the Android app). Open Import Recipe or POST /ai/import-url."
                ),
            )
    except HTTPException:
        raise
    except Exception:
        pass

    domain = extract_domain(url)
    platform_info = None

    for platform_domain, info in SUPPORTED_PLATFORMS.items():
        if platform_domain in domain:
            platform_info = info
            break

    recipe_data = await fetch_recipe_from_url(url, request.app.state.http_client)

    if not recipe_data:
        raise HTTPException(
            status_code=400,
            detail="Could not parse recipe from URL. Make sure it's a valid recipe page."
        )

    from utils.subscription import assert_can_create_recipes
    await assert_can_create_recipes(user, recipe_repository, 1)

    now = datetime.now(timezone.utc).isoformat()
    recipe = {
        "id": str(uuid.uuid4()),
        "author_id": user["id"],
        "household_id": user.get("household_id"),
        "created_at": now,
        "updated_at": now,
        **recipe_data
    }

    await recipe_repository.create(_row(recipe))
    schedule_recipe_macros([recipe["id"]], user)  # line macros + totals, after the response

    await recipe_version_repository.create({
        "id": str(uuid.uuid4()),
        "recipe_id": recipe["id"],
        "version": 1,
        "data": recipe_data,
        "change_note": f"Imported from {recipe['source_url']}",
        "created_by": user["id"],
        "created_at": now
    })

    # Log recipe import
    await log_action(
        user, "recipe_imported", request,
        target_type="recipe",
        target_id=recipe["id"],
        details={"title": recipe["title"], "source": platform_info["name"] if platform_info else "Web", "url": url}
    )

    return {
        "message": "Recipe imported successfully",
        "recipe": recipe,
        "platform": platform_info["name"] if platform_info else "Unknown"
    }

@router.post("/bulk")
async def bulk_import(
    request: Request,
    data: BulkImportRequest,
    user: dict = Depends(get_current_user)
):
    """Import multiple recipes from URLs"""
    results = {
        "successful": [],
        "failed": []
    }

    for url in data.urls[:20]:
        try:
            url = url.strip()
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # SSRF protection - block internal/private URLs
            is_safe, error = is_safe_external_url(url)
            if not is_safe:
                results["failed"].append({"url": url, "error": error})
                continue

            recipe_data = await fetch_recipe_from_url(url, request.app.state.http_client)

            if recipe_data:
                from utils.subscription import assert_can_create_recipes
                await assert_can_create_recipes(user, recipe_repository, 1)

                now = datetime.now(timezone.utc).isoformat()
                recipe = {
                    "id": str(uuid.uuid4()),
                    "author_id": user["id"],
                    "household_id": user.get("household_id"),
                    "created_at": now,
                    "updated_at": now,
                    **recipe_data
                }
                recipe["source_url"] = url

                await recipe_repository.create(_row(recipe))
                schedule_recipe_macros([recipe["id"]], user)  # line macros + totals, after the response
                results["successful"].append({
                    "url": url,
                    "title": recipe["title"],
                    "id": recipe["id"]
                })

                # Log each successful import
                await log_action(
                    user, "recipe_imported", request,
                    target_type="recipe",
                    target_id=recipe["id"],
                    details={"title": recipe["title"], "url": url}
                )
            else:
                results["failed"].append({
                    "url": url,
                    "error": "Could not parse recipe"
                })
        except Exception as e:
            results["failed"].append({
                "url": url,
                "error": str(e)
            })

    return {
        "message": f"Imported {len(results['successful'])} of {len(data.urls)} recipes",
        "results": results
    }


@router.get("/migrate/status")
async def migrate_status(user: dict = Depends(get_current_user)):
    """How many closing-app copies a free account can still bring over."""
    from utils.free_limits import (
        CLOSING_APP_MIGRATION_UNTIL,
        CLOSING_APP_RECIPE_ALLOWANCE,
        closing_app_recipe_limit,
        closing_app_window_open,
        recipe_limit,
    )

    current = await recipe_repository.count({"author_id": user["id"]})
    limit = closing_app_recipe_limit(user)
    remaining = max(0, limit - current) if limit < 10_000 else 10_000
    return {
        "mealime_shutdown": "2026-10-21",
        "window_until": CLOSING_APP_MIGRATION_UNTIL.date().isoformat(),
        "window_open": closing_app_window_open(),
        "allowance": CLOSING_APP_RECIPE_ALLOWANCE,
        "free_recipe_limit": recipe_limit(user),
        "current_recipes": current,
        "remaining": remaining,
    }


@router.post("/migrate")
async def migrate_closing_apps(
    request: Request,
    data: MigrateRequest,
    user: dict = Depends(get_current_user),
):
    """Import recipes from a shutting-down app (Mealime names or public URLs)."""
    from services.mealime_migrate import (
        extract_any_url,
        leftover_paste,
        load_catalog,
        recipe_payload_for_save,
        resolve_name,
        source_type_for_url,
        split_paste,
    )
    from utils.free_limits import closing_app_recipe_limit
    from utils.subscription import assert_can_create_recipes

    lines = split_paste(data.text)
    if not lines:
        raise HTTPException(
            status_code=400,
            detail="Paste recipe names or public links (Mealime, Samsung Food, Whisk, Pepperplate).",
        )

    # Keep each request short enough for a browser/app timeout.
    batch = lines[:15]
    catalog = []
    needs_names = any(
        not (line.lower().startswith("http://") or line.lower().startswith("https://"))
        and not extract_any_url(line)
        for line in batch
    )
    if needs_names:
        try:
            catalog = await load_catalog(request.app.state.http_client)
        except Exception as e:
            logger.warning("Mealime catalog fetch failed: %s", e)
            catalog = []

    results = {"successful": [], "failed": [], "skipped": []}
    limit = closing_app_recipe_limit(user)

    for idx, line in enumerate(batch):
        url = extract_any_url(line)
        if not url:
            stripped = line.strip()
            if stripped.lower().startswith(("http://", "https://")):
                url = stripped
            else:
                match = resolve_name(stripped, catalog)
                if match:
                    url = match["url"]
                else:
                    results["failed"].append({
                        "input": line,
                        "error": "Could not match that name. Paste the public recipe link instead.",
                    })
                    continue

        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url

        is_safe, error = is_safe_external_url(url)
        if not is_safe:
            results["failed"].append({"input": line, "url": url, "error": error})
            continue

        try:
            await assert_can_create_recipes(
                user, recipe_repository, 1, limit_override=limit
            )
        except HTTPException as cap:
            results["skipped"].append({
                "input": line,
                "url": url,
                "error": cap.detail if isinstance(cap.detail, str) else str(cap.detail),
            })
            results["skipped"].extend(
                {"input": rest, "error": "Stopped at the free-plan recipe cap."}
                for rest in batch[idx + 1:]
            )
            break

        try:
            recipe_data = await fetch_recipe_from_url(url, request.app.state.http_client)
            if not recipe_data or not (
                recipe_data.get("ingredients") or recipe_data.get("instructions")
            ):
                results["failed"].append({
                    "input": line,
                    "url": url,
                    "error": "That page did not expose a recipe we could copy.",
                })
                continue

            now = datetime.now(timezone.utc).isoformat()
            payload = recipe_payload_for_save(recipe_data, url)
            payload["source_type"] = source_type_for_url(url)
            remote_cover = payload.get("image_url") or ""
            if str(remote_cover).startswith("http"):
                from utils.image_store import stash_remote_cover
                local = await stash_remote_cover(
                    request.app.state.http_client, remote_cover, prefix="migrate"
                )
                if local:
                    payload["image_url"] = local
            recipe = {
                "id": str(uuid.uuid4()),
                "author_id": user["id"],
                "household_id": user.get("household_id"),
                "created_at": now,
                "updated_at": now,
                **payload,
            }
            await recipe_repository.create(_row(recipe))
            schedule_recipe_macros([recipe["id"]], user)  # line macros + totals, after the response
            results["successful"].append({
                "input": line,
                "url": url,
                "title": recipe.get("title"),
                "id": recipe["id"],
            })
            await log_action(
                user, "recipe_imported", request,
                target_type="recipe",
                target_id=recipe["id"],
                details={"title": recipe.get("title"), "url": url, "source": "closing_app"},
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Closing-app import failed for %s: %s", url, e)
            results["failed"].append({"input": line, "url": url, "error": str(e)})

    processed = len(batch)
    remaining_count = max(0, len(lines) - processed)
    remaining_text = leftover_paste(lines, processed)
    return {
        "message": (
            f"Imported {len(results['successful'])} of {processed} recipes"
            + (f" ({remaining_count} still in this paste — we will continue)" if remaining_count else "")
        ),
        "processed": processed,
        "remaining_in_paste": remaining_count,
        "remaining_text": remaining_text,
        "results": results,
    }


@router.post("/migrate/plan-week")
async def plan_migrated_week(
    request: Request,
    data: PlanMigratedWeekRequest,
    user: dict = Depends(get_current_user),
):
    """Fill empty dinner slots this week with just-imported recipes (Mealime-style)."""
    from datetime import date, timedelta
    from services.mealime_migrate import assign_week_dinners
    from database.websocket_manager import ws_manager, EventType

    ids = [rid for rid in (data.recipe_ids or []) if rid][:14]
    if not ids:
        raise HTTPException(status_code=400, detail="Pick at least one imported recipe.")

    owned = []
    for rid in ids:
        recipe = await recipe_repository.find_by_id(rid)
        if recipe and recipe.get("author_id") == user["id"]:
            owned.append(recipe)
    if not owned:
        raise HTTPException(status_code=404, detail="Those recipes are not in your kitchen.")

    meal_type = (data.meal_type or "dinner").lower().strip() or "dinner"
    if data.start_date:
        try:
            start = date.fromisoformat(data.start_date[:10])
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD.")
    else:
        start = datetime.now(timezone.utc).date()
    days = data.days or 5

    household_id = user.get("household_id") or user["id"]
    end = (start + timedelta(days=max(days, 1) - 1)).isoformat()
    existing = await meal_plan_repository.find_by_household(
        household_id, start.isoformat(), end
    )
    occupied = {
        str(row.get("date"))[:10]
        for row in existing
        if (row.get("meal_type") or "").lower() == meal_type
    }
    slots = assign_week_dinners(
        [r["id"] for r in owned], occupied, start, days=days
    )
    created = []
    now = datetime.now(timezone.utc).isoformat()
    by_id = {r["id"]: r for r in owned}
    for day, recipe_id in slots:
        recipe = by_id[recipe_id]
        plan_id = str(uuid.uuid4())
        plan_doc = {
            "id": plan_id,
            "date": day,
            "meal_type": meal_type,
            "recipe_id": recipe_id,
            "recipe_title": recipe.get("title") or "Imported recipe",
            "notes": "",
            "adult_boost": "",
            "entry_type": "recipe",
            "household_id": household_id,
            "created_at": now,
        }
        await meal_plan_repository.create(plan_doc)
        created.append({
            "id": plan_id,
            "date": day,
            "meal_type": meal_type,
            "recipe_id": recipe_id,
            "recipe_title": plan_doc["recipe_title"],
        })
        await log_action(
            user, "meal_plan_created", request,
            target_type="meal_plan",
            target_id=plan_id,
            details={"date": day, "source": "closing_app_migrate"},
        )
        try:
            await ws_manager.broadcast_to_household_or_user(
                user_id=user["id"],
                household_id=user.get("household_id"),
                event_type=EventType.MEAL_PLAN_CREATED,
                data={"id": plan_id, "date": day},
            )
        except Exception:
            pass

    leftover_ids = [r["id"] for r in owned if r["id"] not in {s[1] for s in slots}]
    return {
        "message": (
            f"Planned {len(created)} {meal_type}s this week"
            if created
            else "Those dinner slots are already filled."
        ),
        "planned": created,
        "skipped_recipe_ids": leftover_ids,
    }


@router.post("/text")
async def import_from_text(
    request: Request,
    data: ImportFromTextRequest,
    user: dict = Depends(get_current_user)
):
    """Parse recipe from plain text using AI (counts against free AI quota)."""
    from routers.ai import call_llm_metered

    system_prompt = """You are a recipe parser. Extract recipe information from the given text and return a JSON object with these fields:
- title: string
- description: string (1-2 sentences)
- ingredients: array of {amount, unit, name}
- instructions: array of strings (step by step)
- prep_time: number (minutes)
- cook_time: number (minutes)
- servings: number
- tags: array of strings

Return ONLY valid JSON, no other text."""

    try:
        result = await call_llm_metered(
            request.app.state.http_client,
            system_prompt,
            data.text,
            user,
        )

        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```\w*\n?', '', result)
            result = re.sub(r'\n?```$', '', result)

        recipe_data = json.loads(result)

        if data.title:
            recipe_data["title"] = data.title

        from utils.subscription import assert_can_create_recipes
        await assert_can_create_recipes(user, recipe_repository, 1)

        now = datetime.now(timezone.utc).isoformat()
        recipe = {
            "id": str(uuid.uuid4()),
            "author_id": user["id"],
            "household_id": user.get("household_id"),
            "created_at": now,
            "updated_at": now,
            **recipe_data
        }

        await recipe_repository.create(_row(recipe))
        schedule_recipe_macros([recipe["id"]], user)  # line macros + totals, after the response

        # Log text import
        await log_action(
            user, "recipe_imported", request,
            target_type="recipe",
            target_id=recipe["id"],
            details={"title": recipe["title"], "source": "Text"}
        )

        return {
            "message": "Recipe parsed and saved",
            "recipe": recipe
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Could not parse recipe from text. Try a clearer format.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
