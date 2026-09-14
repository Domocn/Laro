"""
Background Tasks for Heavy Operations
Powered by Celery (distributed task queue)
"""
import json
import logging
import httpx
from bs4 import BeautifulSoup
from typing import Optional
from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, name='import_recipe_from_url_task')
def import_recipe_from_url_task(
    self,
    url: str,
    user_id: str,
    household_id: Optional[str] = None
) -> dict:
    """
    Background task: Import recipe from URL using AI

    Heavy operations:
    - HTTP request to fetch URL
    - HTML parsing and cleanup
    - LLM call for recipe extraction

    Returns recipe data that can be saved by the caller
    """
    # Import here to avoid circular imports at module level
    import asyncio
    from dependencies import call_llm, clean_llm_json
    from routers.prompts import get_user_prompt
    from utils.ai_quota import meter_ai_for_user_id, consume_ai_quota_if_free
    from fastapi import HTTPException

    async def _process():
        try:
            user = await meter_ai_for_user_id(user_id)

            # Fetch URL content
            async with httpx.AsyncClient() as client:
                logger.info(f"Fetching URL for import: {url}")
                response = await client.get(url, timeout=30.0, follow_redirects=True)
                html = response.text

            # Parse HTML and extract text
            soup = BeautifulSoup(html, 'html.parser')
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()

            text_content = soup.get_text(separator='\n', strip=True)[:3000]

            # Get user's custom prompt or default
            system_prompt = await get_user_prompt(user_id, "recipe_extraction")

            # Call LLM for recipe extraction
            usage_meta = {}
            async with httpx.AsyncClient() as client:
                logger.info(f"Calling LLM for recipe extraction (user: {user_id})")
                result = await call_llm(
                    client,
                    system_prompt,
                    f"Extract recipe from:\n{text_content}",
                    user_id,
                    usage_meta=usage_meta,
                )
            await consume_ai_quota_if_free(user, usage_meta)

            result = clean_llm_json(result)
            recipe_data = json.loads(result)

            logger.info(f"Successfully extracted recipe from URL: {recipe_data.get('title', 'Unknown')}")

            return {
                "status": "success",
                "recipe_data": recipe_data
            }

        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
            return {
                "status": "error",
                "error": detail.get("message") or str(e.detail),
                "error_code": detail.get("error"),
                "upgrade_required": detail.get("upgrade_required", False),
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse recipe JSON: {e}")
            return {
                "status": "error",
                "error": f"Failed to parse recipe data: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Import URL task failed: {e}")
            return {
                "status": "error",
                "error": f"Failed to import recipe: {str(e)}"
            }

    # Run async code in sync context
    return asyncio.run(_process())


@app.task(bind=True, name='import_recipe_from_text_task')
def import_recipe_from_text_task(
    self,
    text: str,
    user_id: str,
    household_id: Optional[str] = None
) -> dict:
    """
    Background task: Parse recipe from pasted text using AI

    Heavy operations:
    - LLM call for recipe parsing

    Returns recipe data that can be saved by the caller
    """
    import asyncio
    from dependencies import call_llm, clean_llm_json
    from routers.prompts import get_user_prompt
    from utils.ai_quota import meter_ai_for_user_id, consume_ai_quota_if_free
    from fastapi import HTTPException

    async def _process():
        try:
            user = await meter_ai_for_user_id(user_id)

            # Get user's custom prompt or default
            system_prompt = await get_user_prompt(user_id, "recipe_extraction")

            # Call LLM for recipe parsing
            usage_meta = {}
            async with httpx.AsyncClient() as client:
                logger.info(f"Calling LLM for text recipe parsing (user: {user_id})")
                result = await call_llm(
                    client,
                    system_prompt,
                    f"Parse this recipe:\n{text[:3000]}",
                    user_id,
                    usage_meta=usage_meta,
                )
            await consume_ai_quota_if_free(user, usage_meta)

            result = clean_llm_json(result)
            recipe_data = json.loads(result)

            logger.info(f"Successfully parsed recipe from text: {recipe_data.get('title', 'Unknown')}")

            return {
                "status": "success",
                "recipe_data": recipe_data
            }

        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
            return {
                "status": "error",
                "error": detail.get("message") or str(e.detail),
                "error_code": detail.get("error"),
                "upgrade_required": detail.get("upgrade_required", False),
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse recipe JSON: {e}")
            return {
                "status": "error",
                "error": f"Failed to parse recipe: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Import text task failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    return asyncio.run(_process())


@app.task(bind=True, name='generate_meal_plan_task')
def generate_meal_plan_task(
    self,
    days: int,
    preferences: Optional[str],
    exclude_recipes: Optional[list],
    user_id: str,
    household_id: Optional[str] = None
) -> dict:
    """
    Background task: Auto-generate meal plan using AI

    Heavy operations:
    - Fetch user's recipes from database
    - LLM call for meal plan generation

    Returns meal plan data
    """
    import asyncio
    from dependencies import call_llm, clean_llm_json, recipe_repository
    from routers.prompts import get_user_prompt
    from utils.ai_quota import meter_ai_for_user_id, consume_ai_quota_if_free
    from fastapi import HTTPException

    async def _process():
        try:
            user = await meter_ai_for_user_id(user_id)

            # Get user's recipes
            logger.info(f"Fetching recipes for meal plan generation (user: {user_id})")
            recipes = await recipe_repository.find_by_household_or_author(
                author_id=user_id,
                household_id=household_id,
                limit=200
            )

            if len(recipes) < 3:
                return {
                    "status": "error",
                    "error": "Need at least 3 recipes to generate a meal plan"
                }

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
            system_prompt = await get_user_prompt(user_id, "meal_planning")
            from utils.preference_context import merge_preferences_into_free_text
            from utils.food_db import build_ai_food_context
            from dependencies import user_preferences_repository

            saved_prefs = await user_preferences_repository.find_by_user(user_id)
            from datetime import date as date_cls
            from utils.calendar_busy import load_busyness_for_prefs

            plan_start = date_cls.today()
            calendar_busyness = await load_busyness_for_prefs(
                saved_prefs, start_date=plan_start, days=days
            )
            preference_text = merge_preferences_into_free_text(
                preferences,
                saved_prefs,
                start_date=plan_start,
                days=days,
                calendar_busyness=calendar_busyness,
            )
            food_ctx = build_ai_food_context(
                saved_prefs,
                query=preferences or "meal plan",
                seed=f"{user_id}:meal-plan-worker",
                limit=14,
            )
            food_block = f"\n\n{food_ctx}" if food_ctx else ""

            user_prompt = f"""Create a {days}-day meal plan starting {plan_start.isoformat()}.
Preferences: {preference_text}{food_block}
Exclude recipes: {exclude_recipes or 'none'}

Available recipes:
{json.dumps(recipes_summary)}

Respect kid-friendly / WFH lunch pacing, calendar evening busyness (quick/leftover on busy nights), and daily calorie/protein targets from Preferences when choosing meals.
Strictly honour any HARD EXCLUSION adult/kid veto lists in Preferences — never pick recipes that contain vetoed ingredients."""

            # Call LLM for meal plan generation
            usage_meta = {}
            async with httpx.AsyncClient() as client:
                logger.info(f"Calling LLM for meal plan generation (user: {user_id})")
                result = await call_llm(
                    client, system_prompt, user_prompt, user_id, usage_meta=usage_meta
                )
            await consume_ai_quota_if_free(user, usage_meta)

            result = clean_llm_json(result)
            plan_data = json.loads(result)

            logger.info(f"Successfully generated {days}-day meal plan (user: {user_id})")

            return {
                "status": "success",
                "plan_data": plan_data
            }

        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
            return {
                "status": "error",
                "error": detail.get("message") or str(e.detail),
                "error_code": detail.get("error"),
                "upgrade_required": detail.get("upgrade_required", False),
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse meal plan JSON: {e}")
            return {
                "status": "error",
                "error": "Failed to generate meal plan"
            }
        except Exception as e:
            logger.error(f"Meal plan generation task failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    return asyncio.run(_process())


@app.task(bind=True, name='fridge_search_task')
def fridge_search_task(
    self,
    ingredients: list[str],
    search_online: bool,
    user_id: str,
    household_id: Optional[str] = None
) -> dict:
    """
    Background task: Find recipes matching available ingredients

    Heavy operations:
    - Fetch user's recipes from database
    - LLM call for matching and suggestions

    Returns matching recipes and AI suggestions
    """
    import asyncio
    from dependencies import call_llm, clean_llm_json, recipe_repository
    from routers.prompts import get_user_prompt
    from utils.ai_quota import meter_ai_for_user_id, consume_ai_quota_if_free
    from fastapi import HTTPException

    async def _process():
        try:
            user = await meter_ai_for_user_id(user_id)

            ingredients_str = ", ".join(ingredients)

            # Get user's recipes
            logger.info(f"Fetching recipes for fridge search (user: {user_id})")
            all_recipes = await recipe_repository.find_by_household_or_author(
                author_id=user_id,
                household_id=household_id,
                limit=500
            )

            # Get user's custom prompt or default
            system_prompt = await get_user_prompt(user_id, "fridge_search")
            from utils.preference_context import load_user_prefs_and_food_context

            pref_ctx = await load_user_prefs_and_food_context(
                user_id,
                pantry_items=ingredients,
                query=f"fridge recipe ideas: {ingredients_str}",
            )
            pref_block = f"\n\n{pref_ctx}" if pref_ctx else ""

            # Build prompt based on available recipes
            if len(all_recipes) == 0 and search_online:
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

Find matching recipes{" and suggest a new unique recipe grounded in the food database macros" if search_online else ""}.{pref_block}"""

            # Call LLM for fridge search
            usage_meta = {}
            async with httpx.AsyncClient() as client:
                logger.info(f"Calling LLM for fridge search (user: {user_id})")
                result = await call_llm(
                    client, system_prompt, user_prompt, user_id, usage_meta=usage_meta
                )
            await consume_ai_quota_if_free(user, usage_meta)

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

            logger.info(f"Fridge search found {len(matching_recipes)} matches (user: {user_id})")

            return {
                "status": "success",
                "matching_recipes": matching_recipes,
                "suggestions": ai_result.get("suggestions", []),
                "ai_recipe_suggestion": ai_result.get("ai_suggestion")
            }

        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
            return {
                "status": "error",
                "error": detail.get("message") or str(e.detail),
                "error_code": detail.get("error"),
                "upgrade_required": detail.get("upgrade_required", False),
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse fridge search JSON: {e}")
            return {
                "status": "success",  # Still return success but with empty results
                "matching_recipes": [],
                "suggestions": [],
                "ai_recipe_suggestion": None,
                "warning": "AI response was not valid JSON"
            }
        except Exception as e:
            logger.error(f"Fridge search task failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    return asyncio.run(_process())


# ---------------------------------------------------------------------------
# Scheduled reminders (Celery Beat)
# ---------------------------------------------------------------------------

@app.task(name='workers.tasks.run_reminder_sweep')
def run_reminder_sweep() -> dict:
    """Periodic sweep for meal / shopping / weekly-plan reminders."""
    import asyncio
    from services.reminders import run_all_reminder_sweeps

    return asyncio.run(run_all_reminder_sweeps())


@app.task(name='workers.tasks.sync_uk_open_prices_task')
def sync_uk_open_prices_task(force: bool = False) -> dict:
    """
    Refresh the local UK Open Prices (GBP) catalog for offline cost estimates.
    Scheduled every 12h by Celery Beat; safe to invoke manually.
    """
    import asyncio
    from services.uk_open_prices import sync_uk_open_prices

    result = asyncio.run(sync_uk_open_prices(force=force))
    logger.info("UK Open Prices sync task finished: %s", result)
    return result
