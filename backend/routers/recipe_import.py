"""
Recipe Import Router - Import recipes from multiple platforms
Supports: AllRecipes, Food Network, BBC Good Food, Epicurious, Tasty,
NYT Cooking, Bon Appetit, Serious Eats, Budget Bytes, Delish, and generic Recipe Schema
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
from dependencies import get_current_user, recipe_repository, recipe_version_repository
from utils.activity_logger import log_action
from utils.security import is_safe_external_url
from datetime import datetime, timezone
import uuid
import re
import json
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import", tags=["Recipe Import"])

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
}

# =============================================================================
# MODELS
# =============================================================================

class ImportRequest(BaseModel):
    url: str

class BulkImportRequest(BaseModel):
    urls: List[str]

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

def parse_recipe_schema(html: str) -> dict:
    """Extract recipe data from JSON-LD schema"""
    pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

    for match in matches:
        try:
            data = json.loads(match)

            if isinstance(data, dict) and "@graph" in data:
                for item in data["@graph"]:
                    if item.get("@type") == "Recipe":
                        return parse_recipe_object(item)

            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Recipe":
                        return parse_recipe_object(item)

            if isinstance(data, dict) and data.get("@type") == "Recipe":
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
                instructions.append(text)

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
        "title": data.get("name", "Imported Recipe"),
        "description": data.get("description", ""),
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

async def fetch_recipe_from_url(url: str, http_client) -> dict:
    """Fetch and parse recipe from URL"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = await http_client.get(url, headers=headers, follow_redirects=True, timeout=15.0)
        response.raise_for_status()

        html = response.text
        recipe_data = parse_recipe_schema(html)

        if recipe_data:
            recipe_data["source_url"] = url
            return recipe_data

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

    now = datetime.now(timezone.utc).isoformat()
    recipe = {
        "id": str(uuid.uuid4()),
        "author_id": user["id"],
        "household_id": user.get("household_id"),
        "created_at": now,
        "updated_at": now,
        "is_favorite": False,
        "times_cooked": 0,
        "current_version": 1,
        "imported_from": platform_info["name"] if platform_info else "Web",
        **recipe_data
    }

    await recipe_repository.create(recipe)

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
                now = datetime.now(timezone.utc).isoformat()
                recipe = {
                    "id": str(uuid.uuid4()),
                    "author_id": user["id"],
                    "household_id": user.get("household_id"),
                    "created_at": now,
                    "updated_at": now,
                    "is_favorite": False,
                    "times_cooked": 0,
                    "current_version": 1,
                    **recipe_data
                }
                recipe["source_url"] = url

                await recipe_repository.create(recipe)
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

@router.post("/text")
async def import_from_text(
    request: Request,
    data: ImportFromTextRequest,
    user: dict = Depends(get_current_user)
):
    """Parse recipe from plain text using AI"""
    from routers.ai import call_llm

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
        result = await call_llm(
            request.app.state.http_client,
            system_prompt,
            data.text,
            user["id"]
        )

        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r'^```\w*\n?', '', result)
            result = re.sub(r'\n?```$', '', result)

        recipe_data = json.loads(result)

        if data.title:
            recipe_data["title"] = data.title

        now = datetime.now(timezone.utc).isoformat()
        recipe = {
            "id": str(uuid.uuid4()),
            "author_id": user["id"],
            "household_id": user.get("household_id"),
            "created_at": now,
            "updated_at": now,
            "is_favorite": False,
            "times_cooked": 0,
            "current_version": 1,
            "imported_from": "Text",
            **recipe_data
        }

        await recipe_repository.create(recipe)

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
