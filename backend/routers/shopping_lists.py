"""
Shopping Lists Router - CRUD operations with live refresh support
"""
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Query
from models import ShoppingListCreate, ShoppingListResponse, ShoppingItem, ShoppingItemCreate, ShoppingItemUpdate
from dependencies import (
    get_current_user, shopping_list_repository, recipe_repository,
    pantry_repository, meal_plan_repository, call_llm_with_image, clean_llm_json,
    STAPLE_INGREDIENTS, aisle_override_repository,
)
from utils.ai_quota import require_ai_quota, consume_ai_quota, is_premium_user
from utils.grocery_aisles import assign_aisles, categorize_grocery_item, AISLE_NAMES, aisle_sort_order
from models import (
    GroceryGenerateRequest,
    GroceryGenerateResponse,
    FromMealPlanRequest,
    FromMealPlanResponse,
)
from database.websocket_manager import ws_manager, EventType
from utils.activity_logger import log_action
from utils.security import sanitize_error_message
import uuid
import base64
import json
import re
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel


class ReceiptItem(BaseModel):
    name: str
    quantity: Optional[str] = "1"
    price: Optional[str] = None


class ReceiptScanResult(BaseModel):
    items: List[ReceiptItem]
    store_name: Optional[str] = None
    total: Optional[str] = None
    date: Optional[str] = None


class ReceiptMatchResult(BaseModel):
    scanned_item: str
    matched_item: Optional[str] = None
    item_index: Optional[int] = None
    confidence: str  # "high", "medium", "low"
    auto_checked: bool = False


class SetItemAisleRequest(BaseModel):
    aisle: str
    remember: Optional[bool] = True  # teach aisle for future lists


class RemoveRecipeRequest(BaseModel):
    recipe_id: Optional[str] = None
    recipe_name: Optional[str] = None


class MarkStapleRequest(BaseModel):
    remove_from_list: Optional[bool] = True


router = APIRouter(prefix="/shopping-lists", tags=["Shopping Lists"])


def ensure_item_ids(items: List[dict]) -> List[dict]:
    """Ensure all items have unique IDs"""
    for item in items:
        if not item.get("id"):
            item["id"] = str(uuid.uuid4())
    return items


@router.post("", response_model=ShoppingListResponse)
async def create_shopping_list(data: ShoppingListCreate, request: Request, user: dict = Depends(get_current_user)):
    list_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    household_id = user.get("household_id") or user["id"]

    items = [i.model_dump() for i in data.items] if data.items else []
    items = ensure_item_ids(items)

    list_doc = {
        "id": list_id,
        "name": data.name,
        "items": items,
        "household_id": household_id,
        "created_at": now,
        "updated_at": now
    }
    await shopping_list_repository.create(list_doc)

    # Log user activity
    await log_action(
        user, "shopping_list_created", request,
        target_type="shopping_list",
        target_id=list_id,
        details={"name": data.name, "item_count": len(data.items) if data.items else 0}
    )

    # Broadcast to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_CREATED,
        data=list_doc
    )

    return ShoppingListResponse(**list_doc)


@router.get("", response_model=List[ShoppingListResponse])
async def get_shopping_lists(
    limit: Optional[int] = Query(None, ge=1, le=100, description="Max items to return"),
    offset: Optional[int] = Query(None, ge=0, description="Items to skip"),
    user: dict = Depends(get_current_user)
):
    """Get shopping lists with optional pagination for mobile optimization."""
    household_id = user.get("household_id") or user["id"]
    lists = await shopping_list_repository.find_by_household(household_id)

    # Apply pagination if specified
    if offset is not None:
        lists = lists[offset:]
    if limit is not None:
        lists = lists[:limit]

    return [ShoppingListResponse(**l) for l in lists]


@router.get("/aisles")
async def list_grocery_aisles(user: dict = Depends(get_current_user)):
    """Available grocery aisle names for teach-aisle UI."""
    return {"aisles": AISLE_NAMES}


@router.get("/aisle-overrides")
async def get_aisle_overrides(user: dict = Depends(get_current_user)):
    household_id = user.get("household_id") or user["id"]
    overrides = await aisle_override_repository.get_map_for_household(household_id)
    return {"overrides": overrides}


@router.put("/aisle-overrides")
async def set_aisle_override(
    data: SetItemAisleRequest,
    ingredient_name: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Remember aisle for an ingredient name (household-scoped)."""
    if data.aisle not in AISLE_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown aisle. Choose one of: {', '.join(AISLE_NAMES)}")
    household_id = user.get("household_id") or user["id"]
    key = normalize_ingredient(ingredient_name)
    row = await aisle_override_repository.upsert(household_id, key, data.aisle)
    return row


@router.get("/{list_id}", response_model=ShoppingListResponse)
async def get_shopping_list(list_id: str, user: dict = Depends(get_current_user)):
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    # Auth check
    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    return ShoppingListResponse(**shopping_list)


@router.put("/{list_id}", response_model=ShoppingListResponse)
async def update_shopping_list(list_id: str, data: ShoppingListCreate, user: dict = Depends(get_current_user)):
    # Auth check logic first
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    now = datetime.now(timezone.utc).isoformat()
    items = [i.model_dump() for i in data.items] if data.items else []
    items = ensure_item_ids(items)

    update_data = {
        "name": data.name,
        "items": items,
        "updated_at": now
    }

    await shopping_list_repository.update_list(list_id, update_data)
    updated = await shopping_list_repository.find_by_id(list_id)

    # Broadcast update to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_UPDATED,
        data=updated
    )

    return ShoppingListResponse(**updated)


@router.delete("/{list_id}")
async def delete_shopping_list(list_id: str, request: Request, user: dict = Depends(get_current_user)):
    # Auth check logic first
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Store name before deletion for logging
    list_name = shopping_list.get("name", "Unknown")

    await shopping_list_repository.delete_list(list_id)

    # Log user activity
    await log_action(
        user, "shopping_list_deleted", request,
        target_type="shopping_list",
        target_id=list_id,
        details={"name": list_name}
    )

    # Broadcast deletion to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_DELETED,
        data={"id": list_id}
    )

    return {"message": "Shopping list deleted"}


# =============================================================================
# ITEM-LEVEL CRUD OPERATIONS
# =============================================================================

@router.post("/{list_id}/items", response_model=ShoppingItem)
async def add_shopping_item(
    list_id: str,
    data: ShoppingItemCreate,
    user: dict = Depends(get_current_user)
):
    """Add a new item to a shopping list"""
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Create new item with ID
    new_item = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "quantity": data.quantity,
        "unit": data.unit or "",
        "category": data.category,
        "checked": False,
        "recipe_id": data.recipe_id,
        "recipe_name": data.recipe_name
    }

    items = shopping_list.get("items", [])
    items.append(new_item)
    now = datetime.now(timezone.utc).isoformat()

    await shopping_list_repository.update_list(list_id, {
        "items": items,
        "updated_at": now
    })

    # Broadcast update to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_UPDATED,
        data=await shopping_list_repository.find_by_id(list_id)
    )

    return ShoppingItem(**new_item)


@router.put("/{list_id}/items/{item_id}", response_model=ShoppingItem)
async def update_shopping_item(
    list_id: str,
    item_id: str,
    data: ShoppingItemUpdate,
    user: dict = Depends(get_current_user)
):
    """Update an item in a shopping list"""
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    items = shopping_list.get("items", [])
    item_index = None
    for i, item in enumerate(items):
        if item.get("id") == item_id:
            item_index = i
            break

    if item_index is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # Update only provided fields
    if data.name is not None:
        items[item_index]["name"] = data.name
    if data.quantity is not None:
        items[item_index]["quantity"] = data.quantity
    if data.unit is not None:
        items[item_index]["unit"] = data.unit
    if data.category is not None:
        items[item_index]["category"] = data.category
    if data.checked is not None:
        items[item_index]["checked"] = data.checked

    now = datetime.now(timezone.utc).isoformat()
    await shopping_list_repository.update_list(list_id, {
        "items": items,
        "updated_at": now
    })

    # Broadcast update
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_UPDATED,
        data=await shopping_list_repository.find_by_id(list_id)
    )

    return ShoppingItem(**items[item_index])


@router.delete("/{list_id}/items/{item_id}")
async def delete_shopping_item(
    list_id: str,
    item_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete an item from a shopping list"""
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    items = shopping_list.get("items", [])
    original_len = len(items)
    items = [item for item in items if item.get("id") != item_id]

    if len(items) == original_len:
        raise HTTPException(status_code=404, detail="Item not found")

    now = datetime.now(timezone.utc).isoformat()
    await shopping_list_repository.update_list(list_id, {
        "items": items,
        "updated_at": now
    })

    # Broadcast update
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_UPDATED,
        data=await shopping_list_repository.find_by_id(list_id)
    )

    return {"message": "Item deleted"}


@router.post("/from-recipes")
async def generate_shopping_list_from_recipes(recipe_ids: List[str], user: dict = Depends(get_current_user)):
    """Generate a shopping list from selected recipes (merged + aisle-sorted)."""
    generated = await generate_grocery_list(
        GroceryGenerateRequest(
            recipe_ids=recipe_ids,
            exclude_pantry=True,
            combine_quantities=True,
            assign_aisles=True,
            keep_pantry_items=True,
        ),
        user,
    )
    list_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    household_id = user.get("household_id") or user["id"]
    items = [item.model_dump() for item in generated.items]
    items = ensure_item_ids(items)

    list_doc = {
        "id": list_id,
        "name": f"Shopping List - {datetime.now().strftime('%b %d')}",
        "items": items,
        "household_id": household_id,
        "created_at": now,
        "updated_at": now,
    }
    await shopping_list_repository.create(list_doc)
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_CREATED,
        data=list_doc,
    )
    return ShoppingListResponse(**list_doc)


@router.post("/from-meal-plan", response_model=FromMealPlanResponse)
async def shopping_list_from_meal_plan(
    data: FromMealPlanRequest,
    user: dict = Depends(get_current_user),
):
    """
    Shop this plan — Honeydew / Plan-to-Eat style.

    Pull recipes from the meal plan date range, merge quantities, assign aisles,
    mark pantry matches for review, optionally save the list.
    """
    household_id = user.get("household_id") or user["id"]
    plans = await meal_plan_repository.find_by_household(
        household_id, data.start_date, data.end_date
    )
    if data.meal_types:
        wanted = {m.lower() for m in data.meal_types}
        plans = [p for p in plans if (p.get("meal_type") or "").lower() in wanted]

    recipe_ids = []
    seen = set()
    for plan in plans:
        # Skip note/leftover placeholders — they have nothing to shop
        entry_type = (plan.get("entry_type") or "recipe").lower()
        if entry_type != "recipe":
            continue
        rid = plan.get("recipe_id")
        if rid and rid not in seen:
            seen.add(rid)
            recipe_ids.append(rid)

    if not recipe_ids:
        raise HTTPException(
            status_code=400,
            detail="No recipes on the meal plan for that date range. Add meals first.",
        )

    list_name = data.list_name or f"Week of {data.start_date}"
    generated = await generate_grocery_list(
        GroceryGenerateRequest(
            recipe_ids=recipe_ids,
            exclude_pantry=data.exclude_pantry,
            combine_quantities=data.combine_quantities,
            assign_aisles=data.assign_aisles,
            keep_pantry_items=data.keep_pantry_items,
        ),
        user,
    )

    saved_list = None
    if data.save:
        list_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        items = [item.model_dump() for item in generated.items]
        # Default shop list: skip pantry staples (still saved with in_pantry for reference)
        if data.exclude_pantry and data.keep_pantry_items:
            items = [i for i in items if not i.get("in_pantry")]
        items = ensure_item_ids(items)
        list_doc = {
            "id": list_id,
            "name": list_name,
            "items": items,
            "household_id": household_id,
            "created_at": now,
            "updated_at": now,
        }
        await shopping_list_repository.create(list_doc)
        await ws_manager.broadcast_to_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id"),
            event_type=EventType.SHOPPING_LIST_CREATED,
            data=list_doc,
        )
        await log_action(
            user, "shopping_list_from_meal_plan", None,
            target_type="shopping_list",
            target_id=list_id,
            details={"meal_count": len(plans), "recipe_count": len(recipe_ids)},
        )
        saved_list = ShoppingListResponse(**list_doc)

    return FromMealPlanResponse(
        list=saved_list,
        items=generated.items,
        excluded_count=generated.excluded_count,
        excluded_items=generated.excluded_items,
        recipes_used=generated.recipes_used or [],
        meal_count=len(plans),
        list_name=list_name,
    )


@router.patch("/{list_id}/items/{item_index}/check")
async def check_shopping_item(
    list_id: str,
    item_index: int,
    checked: bool = True,
    user: dict = Depends(get_current_user)
):
    """Toggle check status for a shopping list item - broadcasts to all household members"""
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    items = shopping_list.get("items", [])
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="Item not found")

    items[item_index]["checked"] = checked
    now = datetime.now(timezone.utc).isoformat()

    await shopping_list_repository.update_list(list_id, {
        "items": items,
        "updated_at": now
    })

    # Broadcast item check update to all household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_ITEM_CHECKED,
        data={
            "list_id": list_id,
            "item_index": item_index,
            "item_id": items[item_index].get("id"),
            "checked": checked,
            "updated_by": user["id"],
            "updated_by_name": user.get("name"),
        }
    )

    return {
        "message": "Item updated",
        "checked": checked,
        "list_id": list_id,
        "item_index": item_index,
        "item_id": items[item_index].get("id"),
    }


@router.patch("/{list_id}/items/{item_index}/aisle")
async def set_shopping_item_aisle(
    list_id: str,
    item_index: int,
    data: SetItemAisleRequest,
    user: dict = Depends(get_current_user),
):
    """Move an item to another aisle; optionally remember for future lists."""
    if data.aisle not in AISLE_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown aisle. Choose one of: {', '.join(AISLE_NAMES)}")

    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    items = shopping_list.get("items", [])
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="Item not found")

    items[item_index]["category"] = data.aisle
    items[item_index]["sort_order"] = aisle_sort_order(data.aisle)
    items = assign_aisles(items)  # re-sort after move
    now = datetime.now(timezone.utc).isoformat()

    await shopping_list_repository.update_list(list_id, {
        "items": items,
        "updated_at": now,
    })

    if data.remember:
        key = normalize_ingredient(items[item_index].get("name", ""))
        if key:
            await aisle_override_repository.upsert(household_id, key, data.aisle)

    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_UPDATED,
        data={"id": list_id, "items": items, "updated_at": now},
    )

    return ShoppingListResponse(**{**shopping_list, "items": items, "updated_at": now})


@router.post("/{list_id}/remove-recipe")
async def remove_recipe_from_list(
    list_id: str,
    data: RemoveRecipeRequest,
    user: dict = Depends(get_current_user),
):
    """Drop all items that came from a given recipe (Honeydew-style)."""
    if not data.recipe_id and not data.recipe_name:
        raise HTTPException(status_code=400, detail="recipe_id or recipe_name required")

    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    items = shopping_list.get("items", [])
    kept = []
    removed = 0
    for item in items:
        rids = item.get("recipe_ids") or ([] if not item.get("recipe_id") else [item.get("recipe_id")])
        names = item.get("recipe_names") or ([] if not item.get("recipe_name") else [item.get("recipe_name")])
        match_id = data.recipe_id and data.recipe_id in rids
        match_name = data.recipe_name and data.recipe_name in names
        # Also match sole recipe_id / recipe_name fields
        if not match_id and data.recipe_id and item.get("recipe_id") == data.recipe_id:
            match_id = True
        if not match_name and data.recipe_name and item.get("recipe_name") == data.recipe_name:
            match_name = True

        if match_id or match_name:
            # If item was merged from multiple recipes, just drop this provenance
            if data.recipe_id and len(rids) > 1:
                new_ids = [r for r in rids if r != data.recipe_id]
                new_names = [n for i, n in enumerate(names) if i < len(rids) and rids[i] != data.recipe_id]
                # Fallback: filter names by title if parallel lists diverge
                if data.recipe_name:
                    new_names = [n for n in names if n != data.recipe_name]
                item = {
                    **item,
                    "recipe_ids": new_ids,
                    "recipe_names": new_names,
                    "recipe_id": new_ids[0] if new_ids else None,
                    "recipe_name": new_names[0] if new_names else None,
                }
                kept.append(item)
            else:
                removed += 1
        else:
            kept.append(item)

    now = datetime.now(timezone.utc).isoformat()
    await shopping_list_repository.update_list(list_id, {"items": kept, "updated_at": now})
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_UPDATED,
        data={"id": list_id, "items": kept, "updated_at": now},
    )
    return {
        "message": f"Removed {removed} item(s)",
        "removed": removed,
        "list": ShoppingListResponse(**{**shopping_list, "items": kept, "updated_at": now}),
    }


@router.post("/{list_id}/items/{item_index}/mark-staple")
async def mark_item_as_staple(
    list_id: str,
    item_index: int,
    data: MarkStapleRequest = MarkStapleRequest(),
    user: dict = Depends(get_current_user),
):
    """Treat this grocery item as a pantry staple (always on hand)."""
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    items = shopping_list.get("items", [])
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="Item not found")

    item = items[item_index]
    name = (item.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Item has no name")

    now = datetime.now(timezone.utc).isoformat()
    # Upsert pantry staple by normalized name
    existing = await pantry_repository.find_by_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
    )
    matched = None
    target_key = normalize_ingredient(name)
    for p in existing or []:
        if normalize_ingredient(p.get("name", "")) == target_key:
            matched = p
            break

    if matched:
        await pantry_repository.update_item(matched["id"], {
            "is_staple": True,
            "updated_at": now,
        })
        pantry_id = matched["id"]
    else:
        pantry_id = str(uuid.uuid4())
        await pantry_repository.create({
            "id": pantry_id,
            "user_id": user["id"],
            "household_id": user.get("household_id"),
            "name": name,
            "quantity": None,
            "unit": item.get("unit") or "",
            "category": "Other",
            "expiry_date": None,
            "notes": "Marked staple from shopping list",
            "is_staple": True,
            "created_at": now,
            "updated_at": now,
        })

    if data.remove_from_list:
        items = [it for i, it in enumerate(items) if i != item_index]
        await shopping_list_repository.update_list(list_id, {"items": items, "updated_at": now})
        await ws_manager.broadcast_to_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id"),
            event_type=EventType.SHOPPING_LIST_UPDATED,
            data={"id": list_id, "items": items, "updated_at": now},
        )

    return {
        "message": "Marked as staple",
        "pantry_id": pantry_id,
        "list": ShoppingListResponse(**{**shopping_list, "items": items, "updated_at": now})
        if data.remove_from_list else None,
    }


# =============================================================================
# RECEIPT SCANNING
# =============================================================================

def normalize_item_name(name: str) -> str:
    """Normalize item name for matching (lowercase, remove extra spaces, common abbreviations)"""
    name = name.lower().strip()
    # Remove common receipt abbreviations and extra info
    name = re.sub(r'\s+', ' ', name)  # normalize spaces
    name = re.sub(r'\d+\s*(oz|lb|kg|g|ml|l|ct|pk|pack)\b', '', name, flags=re.IGNORECASE)  # remove quantities
    name = re.sub(r'\$[\d.]+', '', name)  # remove prices
    name = name.strip()
    return name


def match_items(scanned_items: List[ReceiptItem], shopping_items: List[dict]) -> List[ReceiptMatchResult]:
    """Match scanned receipt items against shopping list items"""
    results = []

    for scanned in scanned_items:
        scanned_normalized = normalize_item_name(scanned.name)
        best_match = None
        best_index = None
        best_confidence = "low"

        for idx, shop_item in enumerate(shopping_items):
            if shop_item.get("checked", False):
                continue  # Skip already checked items

            shop_normalized = normalize_item_name(shop_item.get("name", ""))

            # Exact match
            if scanned_normalized == shop_normalized:
                best_match = shop_item.get("name")
                best_index = idx
                best_confidence = "high"
                break

            # Partial match - scanned contains shopping item or vice versa
            if scanned_normalized in shop_normalized or shop_normalized in scanned_normalized:
                if best_confidence != "high":
                    best_match = shop_item.get("name")
                    best_index = idx
                    best_confidence = "medium"

            # Word-level match
            scanned_words = set(scanned_normalized.split())
            shop_words = set(shop_normalized.split())
            common_words = scanned_words & shop_words

            if len(common_words) > 0 and best_confidence == "low":
                # Check if a significant word matches (not just "the", "a", etc.)
                significant_words = {w for w in common_words if len(w) > 2}
                if significant_words:
                    best_match = shop_item.get("name")
                    best_index = idx
                    best_confidence = "low"

        results.append(ReceiptMatchResult(
            scanned_item=scanned.name,
            matched_item=best_match,
            item_index=best_index,
            confidence=best_confidence,
            auto_checked=False
        ))

    return results


@router.post("/{list_id}/scan-receipt")
async def scan_receipt(
    request: Request,
    list_id: str,
    file: UploadFile = File(...),
    auto_check: bool = True,
    user: dict = Depends(get_current_user)
):
    """
    Scan a receipt image and match items against the shopping list.
    Optionally auto-check matched items with high confidence.
    """
    # Auth check
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Read and encode image
    contents = await file.read()
    image_base64 = base64.b64encode(contents).decode("utf-8")

    # OCR prompt for receipt extraction
    system_prompt = """You are a receipt OCR assistant. Extract grocery/shopping items from the receipt image.
Return a JSON object with this exact structure:
{
    "items": [{"name": "item name", "quantity": "1", "price": "2.99"}],
    "store_name": "Store Name or null",
    "total": "total amount or null",
    "date": "date or null"
}

Focus on extracting product names clearly. Ignore non-product lines like subtotals, tax, payment methods.
Return ONLY the JSON, no other text."""

    user_prompt = "Extract all purchased items from this receipt image."

    try:
        # Receipt OCR counts against free AI quota
        await require_ai_quota(user)
        result = await call_llm_with_image(
            request.app.state.http_client,
            system_prompt,
            user_prompt,
            image_base64,
            user["id"]
        )
        if not is_premium_user(user):
            await consume_ai_quota(user["id"])

        # Parse result
        cleaned = clean_llm_json(result)
        try:
            scan_data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                scan_data = json.loads(json_match.group())
            else:
                raise HTTPException(status_code=500, detail="Failed to parse receipt scan result")

        scanned_items = [ReceiptItem(**item) for item in scan_data.get("items", [])]

        # Match against shopping list
        matches = match_items(scanned_items, shopping_list.get("items", []))

        # Auto-check high confidence matches if enabled
        items_updated = False
        checked_indices = set()

        if auto_check:
            items = shopping_list.get("items", [])
            for match in matches:
                if match.confidence == "high" and match.item_index is not None:
                    if match.item_index not in checked_indices:
                        items[match.item_index]["checked"] = True
                        match.auto_checked = True
                        checked_indices.add(match.item_index)
                        items_updated = True

            if items_updated:
                now = datetime.now(timezone.utc).isoformat()
                await shopping_list_repository.update_list(list_id, {
                    "items": items,
                    "updated_at": now
                })

                # Broadcast update
                await ws_manager.broadcast_to_household_or_user(
                    user_id=user["id"],
                    household_id=user.get("household_id"),
                    event_type=EventType.SHOPPING_LIST_UPDATED,
                    data=await shopping_list_repository.find_by_id(list_id)
                )

        return {
            "scan_result": ReceiptScanResult(
                items=scanned_items,
                store_name=scan_data.get("store_name"),
                total=scan_data.get("total"),
                date=scan_data.get("date")
            ),
            "matches": matches,
            "auto_checked_count": len(checked_indices),
            "message": f"Scanned {len(scanned_items)} items, matched {sum(1 for m in matches if m.matched_item)} items"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Receipt scan failed: {sanitize_error_message(e)}")


@router.post("/{list_id}/apply-matches")
async def apply_receipt_matches(
    list_id: str,
    matches: List[ReceiptMatchResult],
    user: dict = Depends(get_current_user)
):
    """
    Apply selected receipt matches to check off shopping list items.
    Use this after reviewing scan results to confirm which items to check.
    """
    # Auth check
    shopping_list = await shopping_list_repository.find_by_id(list_id)
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    household_id = user.get("household_id") or user["id"]
    if shopping_list.get("household_id") != household_id and shopping_list.get("household_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    items = shopping_list.get("items", [])
    checked_count = 0

    for match in matches:
        if match.item_index is not None and 0 <= match.item_index < len(items):
            if not items[match.item_index].get("checked", False):
                items[match.item_index]["checked"] = True
                checked_count += 1

    if checked_count > 0:
        now = datetime.now(timezone.utc).isoformat()
        await shopping_list_repository.update_list(list_id, {
            "items": items,
            "updated_at": now
        })

        # Broadcast update
        await ws_manager.broadcast_to_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id"),
            event_type=EventType.SHOPPING_LIST_UPDATED,
            data=await shopping_list_repository.find_by_id(list_id)
        )

    return {
        "checked_count": checked_count,
        "message": f"Checked off {checked_count} items"
    }


# =============================================================================
# PANTRY-AWARE GROCERY LIST GENERATION
# =============================================================================

def normalize_ingredient(name: str) -> str:
    """Normalize ingredient name for comparison"""
    name = name.lower().strip()
    # Remove common modifiers
    modifiers = ['fresh', 'dried', 'frozen', 'canned', 'chopped', 'diced',
                 'minced', 'sliced', 'grated', 'large', 'small', 'medium',
                 'organic', 'ripe', 'raw', 'cooked', 'boneless', 'skinless']
    for mod in modifiers:
        name = re.sub(rf'\b{mod}\b', '', name, flags=re.IGNORECASE)
    name = ' '.join(name.split())
    return name


def parse_quantity(amount_str: str) -> float:
    """Parse a quantity string to a float"""
    if not amount_str:
        return 1.0

    amount_str = str(amount_str).strip()

    # Handle fractions
    if '/' in amount_str:
        try:
            parts = amount_str.split('/')
            if len(parts) == 2:
                whole = 0
                num_str = parts[0].strip()
                # Check for whole number + fraction (e.g., "1 1/2")
                if ' ' in num_str:
                    whole_parts = num_str.rsplit(' ', 1)
                    whole = float(whole_parts[0])
                    num_str = whole_parts[1]
                return whole + float(num_str) / float(parts[1].strip())
        except (ValueError, ZeroDivisionError):
            return 1.0

    # Handle ranges (e.g., "2-3") - take the higher value
    if '-' in amount_str:
        try:
            parts = amount_str.split('-')
            return float(parts[-1].strip())
        except ValueError:
            return 1.0

    # Try direct conversion
    try:
        return float(amount_str)
    except ValueError:
        return 1.0


def combine_quantities(items: list) -> list:
    """Combine items with the same ingredient into one entry"""
    combined = {}

    for item in items:
        key = normalize_ingredient(item["name"])

        if key in combined:
            existing = combined[key]
            if (existing.get("unit") or "").lower() == (item.get("unit") or "").lower():
                existing_qty = parse_quantity(existing["amount"])
                new_qty = parse_quantity(item.get("amount", "1"))
                total = existing_qty + new_qty
                existing["amount"] = str(round(total, 2) if total % 1 else int(total))
                existing["quantity"] = round(total, 2)
            else:
                existing["amount"] = (
                    f"{existing['amount']} {existing.get('unit', '')}, "
                    f"{item.get('amount', '')} {item.get('unit', '')}"
                ).strip()

            if item.get("recipe_id") and item["recipe_id"] not in existing["recipe_ids"]:
                existing["recipe_ids"].append(item["recipe_id"])
        else:
            amount_str = item.get("amount", "1")
            quantity = parse_quantity(amount_str)
            combined[key] = {
                "id": str(uuid.uuid4()),
                "name": item["name"],
                "quantity": quantity,
                "amount": amount_str,
                "unit": item.get("unit", ""),
                "checked": False,
                "recipe_id": item.get("recipe_id"),
                "recipe_ids": [item["recipe_id"]] if item.get("recipe_id") else [],
            }

    return list(combined.values())


@router.post("/generate", response_model=GroceryGenerateResponse)
async def generate_grocery_list(
    data: GroceryGenerateRequest,
    user: dict = Depends(get_current_user)
):
    """
    Generate a smart grocery list from recipes.

    - Merges duplicate ingredients
    - Assigns store aisles
    - Marks pantry matches (keep for review, or drop)
    """
    if not data.recipe_ids:
        raise HTTPException(status_code=400, detail="At least one recipe ID is required")

    recipes = await recipe_repository.find_by_ids(data.recipe_ids)
    if not recipes:
        raise HTTPException(status_code=404, detail="No recipes found")

    recipe_titles = {r["id"]: r.get("title") or "Recipe" for r in recipes}

    all_items = []
    for recipe in recipes:
        for ing in recipe.get("ingredients", []):
            if isinstance(ing, dict):
                name = (ing.get("name") or "").strip()
                if not name:
                    continue
                all_items.append({
                    "name": name,
                    "amount": ing.get("amount", "1") or "1",
                    "unit": ing.get("unit", "") or "",
                    "recipe_id": recipe["id"],
                    "recipe_name": recipe.get("title"),
                })
            elif isinstance(ing, str) and ing.strip():
                all_items.append({
                    "name": ing.strip(),
                    "amount": "1",
                    "unit": "",
                    "recipe_id": recipe["id"],
                    "recipe_name": recipe.get("title"),
                })

    household_id = user.get("household_id") or user["id"]
    aisle_overrides = await aisle_override_repository.get_map_for_household(household_id)

    pantry_names: set[str] = set()
    if data.exclude_pantry:
        pantry_items = await pantry_repository.find_by_household_or_user(
            user_id=user["id"],
            household_id=user.get("household_id"),
        )
        pantry_names = {normalize_ingredient(p["name"]) for p in pantry_items if p.get("name")}

    if data.combine_quantities:
        all_items = combine_quantities(all_items)
        # Restore primary recipe_name after merge
        for item in all_items:
            rids = item.get("recipe_ids") or ([item["recipe_id"]] if item.get("recipe_id") else [])
            item["recipe_ids"] = rids
            item["recipe_names"] = [recipe_titles[r] for r in rids if r in recipe_titles]
            if rids:
                item["recipe_id"] = rids[0]
                item["recipe_name"] = recipe_titles.get(rids[0])

    excluded_items = []
    shopping_dicts = []
    for item in all_items:
        amount_str = str(item.get("amount", "1"))
        try:
            quantity = float(amount_str) if amount_str and amount_str.replace(".", "", 1).isdigit() else parse_quantity(amount_str)
        except (ValueError, TypeError):
            quantity = parse_quantity(amount_str)

        in_pantry = bool(
            data.exclude_pantry and normalize_ingredient(item["name"]) in pantry_names
        )
        if in_pantry:
            excluded_items.append(item["name"])
            if not data.keep_pantry_items:
                continue

        shopping_dicts.append({
            "id": item.get("id") or str(uuid.uuid4()),
            "name": item["name"],
            "quantity": quantity,
            "amount": amount_str,
            "unit": item.get("unit", ""),
            "checked": False,
            "recipe_id": item.get("recipe_id"),
            "recipe_name": item.get("recipe_name"),
            "recipe_ids": item.get("recipe_ids") or ([item["recipe_id"]] if item.get("recipe_id") else []),
            "recipe_names": item.get("recipe_names") or [],
            "in_pantry": in_pantry,
            "category": categorize_grocery_item(item["name"], aisle_overrides),
        })

    if data.assign_aisles:
        shopping_dicts = assign_aisles(shopping_dicts, aisle_overrides)

    shopping_items = [ShoppingItem(**row) for row in shopping_dicts]
    excluded_items = sorted(set(excluded_items))

    return GroceryGenerateResponse(
        items=shopping_items,
        excluded_count=len(excluded_items),
        excluded_items=excluded_items,
        recipes_used=[{"id": r["id"], "title": r.get("title")} for r in recipes],
    )


@router.post("/generate-and-save", response_model=ShoppingListResponse)
async def generate_and_save_grocery_list(
    data: GroceryGenerateRequest,
    list_name: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Generate a pantry-aware grocery list and save it immediately.

    Combines generate + create in one step for convenience.
    """
    # Generate the list
    generated = await generate_grocery_list(data, user)

    # Create shopping list
    list_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    household_id = user.get("household_id") or user["id"]

    items = [item.model_dump() for item in generated.items]
    items = ensure_item_ids(items)

    list_doc = {
        "id": list_id,
        "name": list_name or f"Shopping List - {datetime.now().strftime('%b %d')}",
        "items": items,
        "household_id": household_id,
        "created_at": now,
        "updated_at": now
    }
    await shopping_list_repository.create(list_doc)

    # Broadcast to household members
    await ws_manager.broadcast_to_household_or_user(
        user_id=user["id"],
        household_id=user.get("household_id"),
        event_type=EventType.SHOPPING_LIST_CREATED,
        data=list_doc
    )

    return ShoppingListResponse(**list_doc)
