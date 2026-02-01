from fastapi import APIRouter, Depends
from models import CustomPromptsUpdate
from dependencies import get_current_user, custom_prompts_repository

router = APIRouter(prefix="/prompts", tags=["prompts"])

# Default prompts that users can customize
DEFAULT_PROMPTS = {
    "recipe_extraction": """You are a recipe extraction assistant. Extract recipe information from the provided content and return ONLY valid JSON.
Return exactly this format (no markdown, no explanation):
{
  "title": "Recipe Name",
  "description": "Brief description",
  "ingredients": [{"name": "ingredient", "amount": "1", "unit": "cup"}],
  "instructions": ["Step 1", "Step 2"],
  "prep_time": 15,
  "cook_time": 30,
  "servings": 4,
  "category": "Main Course",
  "tags": ["tag1", "tag2"]
}
Categories: Breakfast, Lunch, Dinner, Dessert, Appetizer, Snack, Beverage, Other""",

    "meal_planning": """You are a meal planning assistant. Create a balanced weekly meal plan using the available recipes.
Return ONLY valid JSON in this format:
{
  "plan": [
    {"day": 0, "meals": [
      {"meal_type": "Breakfast", "recipe_id": "id", "recipe_title": "title"},
      {"meal_type": "Lunch", "recipe_id": "id", "recipe_title": "title"},
      {"meal_type": "Dinner", "recipe_id": "id", "recipe_title": "title"}
    ]},
    ...for all 7 days (day 0 = today)
  ],
  "notes": "Brief explanation of the plan"
}
Consider variety, nutrition balance, and user preferences. Use actual recipe IDs from the provided list.""",

    "fridge_search": """You are a recipe matching assistant. Given a list of available ingredients and a list of recipes, identify which recipes can be made with the available ingredients (allowing for minor missing seasonings/staples).

Return ONLY valid JSON in this format (no markdown, no explanation):
{
  "matching_recipe_ids": ["id1", "id2"],
  "suggestions": [
    {
      "recipe_id": "id",
      "missing_ingredients": ["ingredient1"],
      "match_percentage": 90
    }
  ],
  "ai_suggestion": null
}

When asked to suggest a NEW recipe, set ai_suggestion to a recipe object like this:
{
  "title": "Recipe Name",
  "description": "Brief description",
  "ingredients": [{"name": "ingredient", "amount": "1", "unit": "cup"}],
  "instructions": ["Step 1", "Step 2"],
  "prep_time": 10,
  "cook_time": 20,
  "servings": 4
}"""
}


@router.get("")
async def get_custom_prompts(user: dict = Depends(get_current_user)):
    """Get user's custom AI prompts"""
    prompts = await custom_prompts_repository.find_by_user(user["id"])

    return {
        "recipe_extraction": prompts.get("recipe_extraction") if prompts else None,
        "meal_planning": prompts.get("meal_planning") if prompts else None,
        "fridge_search": prompts.get("fridge_search") if prompts else None,
        "defaults": DEFAULT_PROMPTS
    }


@router.put("")
async def update_custom_prompts(
    data: CustomPromptsUpdate,
    user: dict = Depends(get_current_user)
):
    """Update user's custom AI prompts"""
    update_data = {}

    if data.recipe_extraction is not None:
        update_data["recipe_extraction"] = data.recipe_extraction
    if data.meal_planning is not None:
        update_data["meal_planning"] = data.meal_planning
    if data.fridge_search is not None:
        update_data["fridge_search"] = data.fridge_search

    await custom_prompts_repository.upsert_prompts(user["id"], update_data)

    return {"success": True, "message": "Custom prompts saved"}


@router.delete("")
async def reset_custom_prompts(user: dict = Depends(get_current_user)):
    """Reset user's custom prompts to defaults"""
    await custom_prompts_repository.delete_by_user(user["id"])
    return {"success": True, "message": "Prompts reset to defaults"}


async def get_user_prompt(user_id: str, prompt_type: str) -> str:
    """Helper function to get a user's custom prompt or default"""
    prompts = await custom_prompts_repository.find_by_user(user_id)

    if prompts and prompts.get(prompt_type):
        return prompts[prompt_type]

    return DEFAULT_PROMPTS.get(prompt_type, "")
