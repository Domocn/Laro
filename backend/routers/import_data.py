from fastapi import APIRouter, HTTPException, Depends, Request
from models import ImportPlatformRequest
from dependencies import get_current_user, recipe_repository
from utils.activity_logger import log_action
from utils.security import sanitize_error_message
import json
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/import", tags=["Import"])


@router.post("/platform")
async def import_from_platform(data: ImportPlatformRequest, request: Request, user: dict = Depends(get_current_user)):
    """Import recipes from other platforms (Paprika, Cookmate, JSON)"""
    imported = []
    errors = []

    try:
        recipes_data = json.loads(data.data)

        if data.platform == 'paprika':
            # Paprika format
            for r in recipes_data if isinstance(recipes_data, list) else [recipes_data]:
                try:
                    recipe = {
                        "title": r.get("name", "Untitled"),
                        "description": r.get("description", ""),
                        "ingredients": [{"name": i, "amount": "", "unit": ""} for i in r.get("ingredients", "").split("\n") if i.strip()],
                        "instructions": [s for s in r.get("directions", "").split("\n") if s.strip()],
                        "prep_time": int(r.get("prep_time", "0").split()[0]) if r.get("prep_time") and r.get("prep_time").split() else 0,
                        "cook_time": int(r.get("cook_time", "0").split()[0]) if r.get("cook_time") and r.get("cook_time").split() else 0,
                        "servings": int(r.get("servings", 4)) if r.get("servings") else 4,
                        "category": r.get("categories", ["Other"])[0] if r.get("categories") else "Other",
                        "tags": r.get("categories", []),
                        "image_url": r.get("photo_url", ""),
                    }
                    imported.append(recipe)
                except Exception as e:
                    errors.append(f"Failed to parse recipe: {str(e)}")

        elif data.platform == 'cookmate':
            # Cookmate/Recipe Keeper format
            for r in recipes_data if isinstance(recipes_data, list) else [recipes_data]:
                try:
                    recipe = {
                        "title": r.get("title", r.get("name", "Untitled")),
                        "description": r.get("description", ""),
                        "ingredients": [{"name": i.get("name", i), "amount": i.get("amount", ""), "unit": i.get("unit", "")}
                                       for i in r.get("ingredients", [])],
                        "instructions": r.get("instructions", r.get("directions", [])),
                        "prep_time": r.get("prep_time", 0),
                        "cook_time": r.get("cook_time", 0),
                        "servings": r.get("servings", 4),
                        "category": r.get("category", "Other"),
                        "tags": r.get("tags", []),
                        "image_url": r.get("image", ""),
                    }
                    imported.append(recipe)
                except Exception as e:
                    errors.append(f"Failed to parse recipe: {str(e)}")

        elif data.platform == 'json':
            # Generic JSON format (Laro native)
            for r in recipes_data if isinstance(recipes_data, list) else [recipes_data]:
                imported.append(r)

        # Save imported recipes
        saved_count = 0
        for recipe in imported:
            recipe_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()

            recipe_doc = {
                "id": recipe_id,
                "title": recipe.get("title", "Untitled"),
                "description": recipe.get("description", ""),
                "ingredients": recipe.get("ingredients", []),
                "instructions": recipe.get("instructions", []),
                "prep_time": recipe.get("prep_time", 0),
                "cook_time": recipe.get("cook_time", 0),
                "servings": recipe.get("servings", 4),
                "category": recipe.get("category", "Other"),
                "tags": recipe.get("tags", []),
                "image_url": recipe.get("image_url", ""),
                "author_id": user["id"],
                "household_id": user.get("household_id"),
                "created_at": now,
                "updated_at": now
            }
            await recipe_repository.create(recipe_doc)
            saved_count += 1

        # Log data import
        await log_action(
            user, "data_imported", request,
            details={"platform": data.platform, "recipe_count": saved_count}
        )

        return {
            "imported": saved_count,
            "errors": errors,
            "message": f"Successfully imported {saved_count} recipes"
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {sanitize_error_message(e)}")
