from fastapi import APIRouter, HTTPException, Depends
from dependencies import get_current_user, user_repository, recipe_repository

router = APIRouter(prefix="/favorites", tags=["favorites"])

@router.get("")
async def get_favorites(user: dict = Depends(get_current_user)):
    """Get all favorite recipe IDs for the current user"""
    return {"favorites": user.get("favorites", [])}

@router.post("/{recipe_id}")
async def add_favorite(recipe_id: str, user: dict = Depends(get_current_user)):
    """Add a recipe to favorites"""
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    await user_repository.add_favorite(user["id"], recipe_id)
    return {"message": "Added to favorites", "is_favorite": True}

@router.delete("/{recipe_id}")
async def remove_favorite(recipe_id: str, user: dict = Depends(get_current_user)):
    """Remove a recipe from favorites"""
    await user_repository.remove_favorite(user["id"], recipe_id)
    return {"message": "Removed from favorites", "is_favorite": False}
