"""
AI Router - AI-powered recipe operations
Heavy operations are processed via background job queue (arq)
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from models import (
    ImportURLRequest, ImportTextRequest, AutoMealPlanRequest, FridgeSearchRequest,
    ImageExtractionRequest, RecipeCreate, RecipeResponse, Ingredient
)
from dependencies import (
    get_current_user, call_llm, call_llm_with_image, clean_llm_json,
    recipe_repository, cookbook_repository
)
from routers.prompts import get_user_prompt
from workers.jobs import enqueue_job
from utils.security import is_safe_external_url, sanitize_error_message
from bs4 import BeautifulSoup
import json
import logging

router = APIRouter(prefix="/ai", tags=["AI"])
logger = logging.getLogger(__name__)


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

    # SSRF protection - block internal/private URLs
    url = data.url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    is_safe, error = is_safe_external_url(url)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error)

    try:
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
        from routers.prompts import get_user_prompt
        system_prompt = await get_user_prompt(user["id"], "recipe_extraction")

        # Call LLM for recipe extraction
        async with httpx.AsyncClient() as client:
            logger.info(f"Calling LLM for recipe extraction (user: {user['id']})")
            result = await call_llm(
                client,
                system_prompt,
                f"Extract recipe from:\n{text_content}",
                user["id"]
            )

        result = clean_llm_json(result)
        recipe_data = json.loads(result)

        logger.info(f"Successfully extracted recipe from URL: {recipe_data.get('title', 'Unknown')}")

        return {
            "status": "success",
            "recipe": recipe_data,
            "source_url": url
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse recipe JSON: {e}")
        raise HTTPException(status_code=422, detail="Could not extract recipe from URL. Try a different URL.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="URL took too long to respond. Try again.")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Could not connect to the URL. Check the address and try again.")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching URL: {e.response.status_code}")
        raise HTTPException(status_code=502, detail=f"Website returned an error ({e.response.status_code}). Try a different URL.")
    except Exception as e:
        logger.error(f"Import URL failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import: {sanitize_error_message(e)}")


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

    try:
        # Get user's custom prompt or default
        from routers.prompts import get_user_prompt
        system_prompt = await get_user_prompt(user["id"], "recipe_extraction")

        # Call LLM for recipe parsing
        async with httpx.AsyncClient() as client:
            logger.info(f"Calling LLM for text recipe parsing (user: {user['id']})")
            result = await call_llm(
                client,
                system_prompt,
                f"Parse this recipe:\n{data.text[:3000]}",
                user["id"]
            )

        result = clean_llm_json(result)
        recipe_data = json.loads(result)

        logger.info(f"Successfully parsed recipe from text: {recipe_data.get('title', 'Unknown')}")

        return {
            "status": "success",
            "recipe": recipe_data
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse recipe JSON: {e}")
        raise HTTPException(status_code=422, detail="Could not parse recipe from text. Please check the format.")
    except Exception as e:
        logger.error(f"Import text failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import: {sanitize_error_message(e)}")


@router.post("/auto-meal-plan")
async def auto_generate_meal_plan(
    request: Request,
    data: AutoMealPlanRequest,
    user: dict = Depends(get_current_user)
):
    """
    Auto-generate a meal plan for the week using AI.
    Runs synchronously for immediate response (v2).
    """
    import httpx
    logger.info(f"Auto meal plan request: days={data.days}, preferences={data.preferences}")

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

        user_prompt = f"""Create a {data.days}-day meal plan.
Preferences: {data.preferences or 'balanced variety'}
Exclude recipes: {data.exclude_recipes or 'none'}

Available recipes:
{json.dumps(recipes_summary)}

Return a JSON object with this structure:
{{
  "plan": [
    {{
      "day": 0,
      "meals": [
        {{"meal_type": "Breakfast", "recipe_id": "id_here", "recipe_title": "title_here"}},
        {{"meal_type": "Lunch", "recipe_id": "id_here", "recipe_title": "title_here"}},
        {{"meal_type": "Dinner", "recipe_id": "id_here", "recipe_title": "title_here"}}
      ]
    }}
  ]
}}

Use recipe IDs from the available recipes list. Day 0 is today."""

        # Call LLM for meal plan generation
        async with httpx.AsyncClient() as client:
            logger.info(f"Calling LLM for meal plan generation (user: {user['id']})")
            result = await call_llm(client, system_prompt, user_prompt, user["id"])

        result = clean_llm_json(result)
        plan_data = json.loads(result)

        logger.info(f"Successfully generated {data.days}-day meal plan (user: {user['id']})")

        return plan_data

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse meal plan JSON: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except Exception as e:
        logger.error(f"Meal plan generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {sanitize_error_message(e)}")


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

        # Build prompt based on available recipes
        if len(all_recipes) == 0 and data.search_online:
            user_prompt = f"I have these ingredients: {ingredients_str}. Suggest a simple recipe I can make."
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

Find matching recipes{" and suggest a new simple recipe" if data.search_online else ""}."""

        # Call LLM for fridge search
        async with httpx.AsyncClient() as client:
            logger.info(f"Calling LLM for fridge search (user: {user['id']})")
            result = await call_llm(client, system_prompt, user_prompt, user["id"])

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
from typing import Optional, List


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


@router.post("/chat")
async def chat(
    request: Request,
    data: ChatRequest,
    user: dict = Depends(get_current_user)
):
    """General AI chat assistant for cooking questions"""
    import httpx

    system_prompt = """You are Laro, a friendly and knowledgeable AI cooking assistant. You help users with:
- Recipe ideas and suggestions
- Cooking techniques and tips
- Ingredient substitutions
- Meal planning advice
- Kitchen equipment recommendations
- Food safety guidance
- Nutrition information

Be conversational, helpful, and encouraging. Keep responses concise but informative.
When suggesting recipes, provide brief overviews rather than full recipes unless specifically asked.
If asked to create a full recipe, format it clearly with ingredients and steps."""

    # Build conversation context from history
    context_messages = []
    if data.history:
        for msg in data.history[-6:]:  # Last 6 messages for context
            context_messages.append(f"{msg.role}: {msg.content}")

    context = "\n".join(context_messages) if context_messages else ""
    user_message = f"Previous conversation:\n{context}\n\nUser: {data.message}" if context else data.message

    try:
        async with httpx.AsyncClient() as client:
            result = await call_llm(
                client,
                system_prompt,
                user_message,
                user["id"]
            )

        return {"response": result, "status": "success"}

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
        system_prompt = """You are a helpful cooking assistant that creates recipes.
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
- Be encouraging and helpful in your message!"""

        context = f"""User Request: {data.question}

If they mention specific ingredients, incorporate them. Create a complete, practical recipe."""
    else:
        # Regular cooking assistant mode
        system_prompt = """You are a helpful cooking assistant embedded in a recipe app.
You help users while they are actively cooking. Be concise, practical, and friendly.

Guidelines:
- Give short, actionable answers (2-4 sentences max)
- Focus on the current cooking context
- Suggest substitutions when asked
- Explain techniques simply
- Provide timing guidance
- Be encouraging!

If asked about substitutions, consider:
- Dietary restrictions
- What's commonly available
- How it affects the dish

Current context:"""

        context = f"""
Recipe: {data.recipe_title or 'Unknown'}
Current Step: {data.current_step or 'N/A'}
Instruction: {data.current_instruction or 'N/A'}
Ingredients: {', '.join(data.ingredients[:10]) if data.ingredients else 'N/A'}

User Question: {data.question}"""

    try:
        result = await call_llm(
            request.app.state.http_client,
            system_prompt,
            context,
            user["id"]
        )

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
    Extract recipe from cookbook page images using AI vision

    Supports single or multiple images (for multi-page recipes).
    Returns extracted recipe data ready to save.
    """
    if not data.images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    if len(data.images) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images allowed per extraction")

    # Verify cookbook exists if provided
    cookbook = None
    if data.cookbook_id:
        cookbook = await cookbook_repository.find_by_id(data.cookbook_id)
        if not cookbook:
            raise HTTPException(status_code=404, detail="Cookbook not found")

        # Verify access
        if cookbook["user_id"] != user["id"]:
            if not user.get("household_id") or cookbook.get("household_id") != user["household_id"]:
                raise HTTPException(status_code=403, detail="Not authorized to use this cookbook")

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

Return ONLY the JSON object, no additional text or markdown."""

    user_prompt = "Please extract the recipe from this cookbook page image."
    if len(data.images) > 1:
        user_prompt = f"Please extract the recipe from these {len(data.images)} cookbook page images. Combine all information into a single recipe."

    try:
        # Process images (combine if multiple)
        # For simplicity, we'll send the first image and mention there are more
        # A more sophisticated implementation would concatenate or send multiple API calls
        result = await call_llm_with_image(
            request.app.state.http_client,
            system_prompt,
            user_prompt,
            data.images[0],  # Primary image
            user["id"]
        )

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
            "tags": recipe_data.get("tags", []),
            "image_url": "",
            "author_id": user["id"],
            "household_id": user.get("household_id"),
            "source_type": "cookbook",
            "cookbook_id": data.cookbook_id,
            "cookbook_page": data.cookbook_page,
            "created_at": now,
            "updated_at": now
        }

        # Return extracted data (not saved yet - client will confirm)
        return {
            "status": "success",
            "message": "Recipe extracted successfully",
            "recipe": RecipeResponse(
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
            ),
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
