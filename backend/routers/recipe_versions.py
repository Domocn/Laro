"""
Recipe Versioning Router - Track recipe changes and allow rollback
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from dependencies import get_current_user, recipe_repository, recipe_version_repository, user_repository
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/recipes", tags=["Recipe Versioning"])

# =============================================================================
# MODELS
# =============================================================================

class VersionCompare(BaseModel):
    version_a: int
    version_b: int

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def create_recipe_version(recipe_id: str, recipe_data: dict, user_id: str, change_note: str = None):
    """Create a new version snapshot of a recipe"""
    # Get next version number
    new_version = await recipe_version_repository.get_next_version_number(recipe_id)

    # Create version document
    version_doc = {
        "id": str(uuid.uuid4()),
        "recipe_id": recipe_id,
        "version": new_version,
        "data": recipe_data,
        "change_note": change_note,
        "created_by": user_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await recipe_version_repository.create_version(version_doc)

    # Update recipe with current version
    await recipe_repository.update_recipe(recipe_id, {"current_version": new_version})

    return new_version

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/{recipe_id}/versions")
async def list_recipe_versions(
    recipe_id: str,
    user: dict = Depends(get_current_user)
):
    """List all versions of a recipe"""
    # Verify recipe exists and user has access
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    versions = await recipe_version_repository.find_by_recipe(recipe_id)

    # Add user names (without full data for listing)
    for version in versions:
        version.pop("data", None)  # Remove full data for listing
        creator = await user_repository.find_by_id(version["created_by"])
        version["created_by_name"] = creator["name"] if creator else "Unknown"

    return {
        "recipe_id": recipe_id,
        "current_version": recipe.get("current_version", 1),
        "versions": versions
    }

@router.get("/{recipe_id}/versions/{version}")
async def get_recipe_version(
    recipe_id: str,
    version: int,
    user: dict = Depends(get_current_user)
):
    """Get a specific version of a recipe"""
    version_doc = await recipe_version_repository.get_version(recipe_id, version)

    if not version_doc:
        raise HTTPException(status_code=404, detail="Version not found")

    # Add creator name
    creator = await user_repository.find_by_id(version_doc["created_by"])
    version_doc["created_by_name"] = creator["name"] if creator else "Unknown"

    return version_doc

@router.post("/{recipe_id}/versions/{version}/restore")
async def restore_recipe_version(
    recipe_id: str,
    version: int,
    user: dict = Depends(get_current_user)
):
    """Restore a recipe to a specific version"""
    # Get the version to restore
    version_doc = await recipe_version_repository.get_version(recipe_id, version)

    if not version_doc:
        raise HTTPException(status_code=404, detail="Version not found")

    # Get current recipe
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Check permission
    if recipe.get("author_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    # Save current state as new version before restoring
    current_data = {k: v for k, v in recipe.items() if k not in ["current_version"]}
    await create_recipe_version(
        recipe_id,
        current_data,
        user["id"],
        f"Auto-saved before restoring to version {version}"
    )

    # Restore the old version data
    restored_data = version_doc["data"]
    restored_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await recipe_repository.update_recipe(recipe_id, restored_data)

    # Create a new version for the restore
    new_version = await create_recipe_version(
        recipe_id,
        restored_data,
        user["id"],
        f"Restored from version {version}"
    )

    return {
        "message": f"Recipe restored to version {version}",
        "new_version": new_version
    }

@router.post("/{recipe_id}/versions/compare")
async def compare_recipe_versions(
    recipe_id: str,
    data: VersionCompare,
    user: dict = Depends(get_current_user)
):
    """Compare two versions of a recipe"""
    version_a = await recipe_version_repository.get_version(recipe_id, data.version_a)
    version_b = await recipe_version_repository.get_version(recipe_id, data.version_b)

    if not version_a or not version_b:
        raise HTTPException(status_code=404, detail="One or both versions not found")

    # Calculate differences
    differences = []
    data_a = version_a.get("data", {})
    data_b = version_b.get("data", {})

    # Compare key fields
    compare_fields = ["title", "description", "ingredients", "instructions", "prep_time", "cook_time", "servings", "tags"]

    for field in compare_fields:
        val_a = data_a.get(field)
        val_b = data_b.get(field)

        if val_a != val_b:
            differences.append({
                "field": field,
                "version_a": val_a,
                "version_b": val_b
            })

    return {
        "recipe_id": recipe_id,
        "version_a": {
            "version": data.version_a,
            "created_at": version_a.get("created_at")
        },
        "version_b": {
            "version": data.version_b,
            "created_at": version_b.get("created_at")
        },
        "differences": differences,
        "has_changes": len(differences) > 0
    }
