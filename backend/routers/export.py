"""
Data Export Router - Export user data in various formats
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from models import DataExportRequest, DataExportResponse
from dependencies import (
    get_current_user, recipe_repository, cookbook_repository,
    pantry_repository, meal_plan_repository, shopping_list_repository,
    user_preferences_repository, session_repository, login_attempt_repository,
    oauth_account_repository
)
from utils.activity_logger import log_action
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid
import json
import os
import tempfile
from pathlib import Path

router = APIRouter(prefix="/export", tags=["Export"])

# Temporary export directory
EXPORT_DIR = Path(tempfile.gettempdir()) / "mise_exports"
EXPORT_DIR.mkdir(exist_ok=True)


def clean_old_exports():
    """Remove exports older than 1 hour"""
    if not EXPORT_DIR.exists():
        return

    now = datetime.now()
    for file in EXPORT_DIR.glob("*"):
        if file.is_file():
            age = now - datetime.fromtimestamp(file.stat().st_mtime)
            if age > timedelta(hours=1):
                try:
                    file.unlink()
                except OSError:
                    pass


@router.post("", response_model=DataExportResponse)
async def export_user_data(
    data: DataExportRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Export user data in requested format.

    Formats:
    - json: Machine-readable, can be re-imported
    - markdown: Human-readable, each recipe as .md file (returned as zip)

    Include options:
    - recipes: All user's recipes
    - cookbooks: Cookbook library
    - pantry: Pantry items
    - meal_plans: Meal plan data
    - shopping_lists: Shopping lists
    """
    # Clean old exports
    clean_old_exports()

    # Determine what to include
    include_all = not data.include
    include = set(data.include or [])

    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "format": data.format,
        "user": {
            "id": user["id"],
            "email": user.get("email", ""),
            "name": user.get("name", "")
        }
    }

    # Collect data based on include options
    if include_all or "recipes" in include:
        recipes = await recipe_repository.find_all_for_user(
            user_id=user["id"],
            household_id=user.get("household_id")
        )
        # Convert datetime objects to strings
        for recipe in recipes:
            for key in ["created_at", "updated_at"]:
                if key in recipe and recipe[key]:
                    recipe[key] = str(recipe[key])
        export_data["recipes"] = recipes

    if include_all or "cookbooks" in include:
        cookbooks = await cookbook_repository.find_by_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id")
        )
        for cookbook in cookbooks:
            for key in ["created_at", "updated_at"]:
                if key in cookbook and cookbook[key]:
                    cookbook[key] = str(cookbook[key])
        export_data["cookbooks"] = cookbooks

    if include_all or "pantry" in include:
        pantry_items = await pantry_repository.find_by_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id")
        )
        for item in pantry_items:
            for key in ["created_at", "updated_at", "expiry_date"]:
                if key in item and item[key]:
                    item[key] = str(item[key])
        export_data["pantry"] = pantry_items

    if include_all or "meal_plans" in include:
        meal_plans = await meal_plan_repository.find_by_household(
            user.get("household_id") or user["id"]
        )
        for plan in meal_plans:
            for key in ["created_at", "date"]:
                if key in plan and plan[key]:
                    plan[key] = str(plan[key])
        export_data["meal_plans"] = meal_plans

    if include_all or "shopping_lists" in include:
        shopping_lists = await shopping_list_repository.find_by_household(
            user.get("household_id") or user["id"]
        )
        for lst in shopping_lists:
            for key in ["created_at", "updated_at"]:
                if key in lst and lst[key]:
                    lst[key] = str(lst[key])
        export_data["shopping_lists"] = shopping_lists

    # Get user preferences
    preferences = await user_preferences_repository.find_by_user(user["id"])
    if preferences:
        export_data["user"]["preferences"] = preferences

    # Generate export file
    export_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    if data.format == "json":
        # JSON export
        file_name = f"mise_export_{export_id}.json"
        file_path = EXPORT_DIR / file_name

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        file_size = file_path.stat().st_size

        # Log data export
        await log_action(
            user, "data_exported", request,
            details={"format": "json", "include": list(include) if include else "all"}
        )

        return DataExportResponse(
            download_url=f"/api/v1/export/download/{export_id}",
            expires_at=expires_at.isoformat(),
            format="json",
            file_size=file_size
        )

    elif data.format == "markdown":
        # Markdown export - create individual recipe files in a zip
        import zipfile

        zip_name = f"mise_export_{export_id}.zip"
        zip_path = EXPORT_DIR / zip_name

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add recipes as markdown files
            if "recipes" in export_data:
                for recipe in export_data["recipes"]:
                    md_content = recipe_to_markdown(recipe)
                    safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in recipe.get("title", "recipe"))
                    zf.writestr(f"recipes/{safe_title}.md", md_content)

            # Add metadata file
            metadata = {
                "exported_at": export_data["exported_at"],
                "version": export_data["version"],
                "user": export_data["user"],
                "recipe_count": len(export_data.get("recipes", [])),
                "cookbook_count": len(export_data.get("cookbooks", [])),
                "pantry_count": len(export_data.get("pantry", [])),
            }
            zf.writestr("_metadata.json", json.dumps(metadata, indent=2))

            # Add other data as JSON files
            for key in ["cookbooks", "pantry", "meal_plans", "shopping_lists"]:
                if key in export_data and export_data[key]:
                    zf.writestr(f"{key}.json", json.dumps(export_data[key], indent=2))

        file_size = zip_path.stat().st_size

        # Log data export
        await log_action(
            user, "data_exported", request,
            details={"format": "markdown", "include": list(include) if include else "all"}
        )

        return DataExportResponse(
            download_url=f"/api/v1/export/download/{export_id}",
            expires_at=expires_at.isoformat(),
            format="markdown",
            file_size=file_size
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {data.format}. Supported formats: json, markdown"
        )


def recipe_to_markdown(recipe: dict) -> str:
    """Convert a recipe to markdown format"""
    md = []

    # Title
    md.append(f"# {recipe.get('title', 'Untitled Recipe')}")
    md.append("")

    # Description
    if recipe.get("description"):
        md.append(f"_{recipe['description']}_")
        md.append("")

    # Metadata
    meta = []
    if recipe.get("prep_time"):
        meta.append(f"**Prep Time:** {recipe['prep_time']} min")
    if recipe.get("cook_time"):
        meta.append(f"**Cook Time:** {recipe['cook_time']} min")
    if recipe.get("servings"):
        meta.append(f"**Servings:** {recipe['servings']}")
    if recipe.get("category"):
        meta.append(f"**Category:** {recipe['category']}")

    if meta:
        md.append(" | ".join(meta))
        md.append("")

    # Tags
    if recipe.get("tags"):
        md.append(f"**Tags:** {', '.join(recipe['tags'])}")
        md.append("")

    # Ingredients
    md.append("## Ingredients")
    md.append("")
    ingredients = recipe.get("ingredients", [])
    for ing in ingredients:
        if isinstance(ing, dict):
            amount = ing.get("amount", "")
            unit = ing.get("unit", "")
            name = ing.get("name", "")
            md.append(f"- {amount} {unit} {name}".strip())
        else:
            md.append(f"- {ing}")
    md.append("")

    # Instructions
    md.append("## Instructions")
    md.append("")
    instructions = recipe.get("instructions", [])
    for i, step in enumerate(instructions, 1):
        md.append(f"{i}. {step}")
    md.append("")

    # Source info
    if recipe.get("source_type") == "cookbook":
        md.append("---")
        md.append(f"*Source: Cookbook (page {recipe.get('cookbook_page', 'N/A')})*")
    elif recipe.get("source_url"):
        md.append("---")
        md.append(f"*Source: {recipe['source_url']}*")

    return "\n".join(md)


@router.get("/download/{export_id}")
async def download_export(
    export_id: str,
    user: dict = Depends(get_current_user)
):
    """Download an exported file"""
    # Look for the export file (either .json or .zip)
    json_path = EXPORT_DIR / f"mise_export_{export_id}.json"
    zip_path = EXPORT_DIR / f"mise_export_{export_id}.zip"

    if json_path.exists():
        return FileResponse(
            path=str(json_path),
            filename=f"mise_export_{datetime.now().strftime('%Y%m%d')}.json",
            media_type="application/json"
        )
    elif zip_path.exists():
        return FileResponse(
            path=str(zip_path),
            filename=f"mise_export_{datetime.now().strftime('%Y%m%d')}.zip",
            media_type="application/zip"
        )
    else:
        raise HTTPException(
            status_code=404,
            detail="Export not found or expired. Please generate a new export."
        )


@router.get("/formats")
async def get_export_formats():
    """Get available export formats"""
    return {
        "formats": [
            {
                "id": "json",
                "name": "JSON",
                "description": "Machine-readable format, can be re-imported to Laro",
                "extension": ".json"
            },
            {
                "id": "markdown",
                "name": "Markdown (ZIP)",
                "description": "Human-readable recipe files, packaged as ZIP",
                "extension": ".zip"
            }
        ],
        "include_options": [
            {"id": "recipes", "name": "Recipes", "description": "All your recipes"},
            {"id": "cookbooks", "name": "Cookbooks", "description": "Cookbook library"},
            {"id": "pantry", "name": "Pantry", "description": "Pantry/inventory items"},
            {"id": "meal_plans", "name": "Meal Plans", "description": "Meal planning data"},
            {"id": "shopping_lists", "name": "Shopping Lists", "description": "Shopping lists"}
        ]
    }


# =============================================================================
# GDPR DATA EXPORT - Users can download ALL their personal data
# =============================================================================

@router.get("/gdpr")
async def gdpr_export_my_data(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    GDPR Data Export - Download all your personal data.

    This endpoint allows users to download a complete copy of all their
    personal data stored in Laro, in compliance with GDPR Article 20
    (Right to Data Portability).
    """
    from fastapi.responses import StreamingResponse
    import io
    import zipfile
    from dependencies import (
        session_repository, login_attempt_repository, oauth_account_repository,
        user_preferences_repository
    )

    # Clean old exports
    clean_old_exports()

    # Create in-memory ZIP file
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        export_time = datetime.now(timezone.utc).isoformat()

        # 1. User profile (excluding password)
        user_data = {k: v for k, v in user.items() if k != "password"}
        zip_file.writestr("profile.json", json.dumps(user_data, indent=2, default=str))

        # 2. User preferences
        preferences = await user_preferences_repository.find_by_user(user["id"])
        if preferences:
            zip_file.writestr("preferences.json", json.dumps(preferences, indent=2, default=str))

        # 3. Recipes
        recipes = await recipe_repository.find_all_for_user(
            user_id=user["id"],
            household_id=user.get("household_id")
        )
        for recipe in recipes:
            for key in ["created_at", "updated_at"]:
                if key in recipe and recipe[key]:
                    recipe[key] = str(recipe[key])
        zip_file.writestr("recipes.json", json.dumps(recipes, indent=2, default=str))

        # 4. Cookbooks
        cookbooks = await cookbook_repository.find_by_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id")
        )
        zip_file.writestr("cookbooks.json", json.dumps(cookbooks, indent=2, default=str))

        # 5. Pantry items
        pantry_items = await pantry_repository.find_by_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id")
        )
        zip_file.writestr("pantry.json", json.dumps(pantry_items, indent=2, default=str))

        # 6. Meal plans
        meal_plans = await meal_plan_repository.find_by_household(
            user.get("household_id") or user["id"]
        )
        zip_file.writestr("meal_plans.json", json.dumps(meal_plans, indent=2, default=str))

        # 7. Shopping lists
        shopping_lists = await shopping_list_repository.find_by_household(
            user.get("household_id") or user["id"]
        )
        zip_file.writestr("shopping_lists.json", json.dumps(shopping_lists, indent=2, default=str))

        # 8. Session history (without tokens)
        try:
            sessions = await session_repository.find_by_user(user["id"])
            sessions_safe = [{k: v for k, v in s.items() if k not in ["token", "refresh_token"]} for s in sessions]
            zip_file.writestr("sessions.json", json.dumps(sessions_safe, indent=2, default=str))
        except:
            pass

        # 9. Login history
        try:
            login_history = await login_attempt_repository.find_by_user(user["id"], limit=100)
            zip_file.writestr("login_history.json", json.dumps(login_history, indent=2, default=str))
        except:
            pass

        # 10. Connected OAuth accounts
        try:
            oauth_accounts = await oauth_account_repository.find_by_user(user["id"])
            # Remove sensitive tokens
            oauth_safe = [{k: v for k, v in a.items() if "token" not in k.lower()} for a in oauth_accounts]
            zip_file.writestr("oauth_accounts.json", json.dumps(oauth_safe, indent=2, default=str))
        except:
            pass

        # README explaining the export
        readme = f"""# GDPR Data Export for {user.get('email', 'User')}

Generated: {export_time}

## Your Data

This archive contains all personal data stored about you in Laro:

- **profile.json** - Your account information
- **preferences.json** - Your app preferences and settings
- **recipes.json** - All recipes you've created
- **cookbooks.json** - Your cookbook collections
- **pantry.json** - Your pantry/inventory items
- **meal_plans.json** - Your meal planning data
- **shopping_lists.json** - Your shopping lists
- **sessions.json** - Your login sessions
- **login_history.json** - Your login attempt history
- **oauth_accounts.json** - Connected third-party accounts

## Your Rights Under GDPR

- **Right to Access** - You have the right to access your personal data (this export)
- **Right to Rectification** - You can update your data in the app
- **Right to Erasure** - You can delete your account in Settings
- **Right to Data Portability** - You can export your data (this file)

## Re-importing Your Data

The JSON files in this export can be re-imported to another Laro instance
or used with compatible recipe management software.

## Questions?

Contact the app administrator for any questions about your data.
"""
        zip_file.writestr("README.md", readme)

    zip_buffer.seek(0)

    # Log the export
    await log_action(
        user, "gdpr_data_export", request,
        details={"format": "zip"}
    )

    filename = f"laro_gdpr_export_{user.get('email', 'user').replace('@', '_')}_{datetime.now().strftime('%Y%m%d')}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
