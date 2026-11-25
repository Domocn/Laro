"""
"Check the numbers" before / while cooking: see the uncertain ingredient lines, fix them, and
lock the user's figures in (``adaptations.confirmed_lines``, services/confirmed_lines.py).

  GET  /recipes/{id}/check-numbers?version=&low_fodmap=   lines + sources + uncertainty + totals
  POST /recipes/{id}/check-numbers/estimate                what the user used -> line macros (not saved)
  PUT  /recipes/{id}/confirmed-lines                       save / clear confirmed lines (editors)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from dependencies import get_current_user, recipe_repository
from services import confirmed_lines as confirmed
from utils.authorization import require_recipe_edit, require_recipe_view

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recipes", tags=["Recipes"])


def _can_edit(user: dict, recipe: dict) -> bool:
    try:
        require_recipe_edit(user, recipe)
        return True
    except HTTPException:
        return False


async def _load(recipe_id: str, user: dict) -> dict:
    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    require_recipe_view(user, recipe)
    return recipe


@router.get("/{recipe_id}/check-numbers")
async def get_check_numbers(
    recipe_id: str,
    request: Request,
    version: Optional[str] = None,
    low_fodmap: bool = False,
    user: dict = Depends(get_current_user),
):
    """Lines of the chosen version / Low FODMAP list with their macros, where each came from
    ("UK label", "CoFID", "USDA", "AI estimate", "You checked", "Barcode"), which deserve a look
    and the per-serving totals they add up to (confirmed figures win)."""
    from services.version_macros import recipe_lookup

    recipe = await _load(recipe_id, user)
    client = getattr(request.app.state, "http_client", None)
    try:
        lookup = await recipe_lookup(recipe, allow_ai=True, client=client)
    except Exception:
        logger.warning("Check-numbers lookup failed for %s", recipe_id, exc_info=True)
        lookup = lambda _ing: None  # noqa: E731 - every line shows "No estimate yet"
    payload = confirmed.check_payload(recipe, lookup, version, low_fodmap)
    payload["can_edit"] = _can_edit(user, recipe)
    return payload


class LabelFigures(BaseModel):
    kcal: float = Field(ge=0, le=10000)
    protein: float = Field(ge=0, le=10000)
    carbs: float = Field(ge=0, le=10000)
    fat: float = Field(ge=0, le=10000)


class EstimateLineRequest(BaseModel):
    version: Optional[str] = None
    low_fodmap: bool = False
    index: int = Field(ge=0, le=500)
    mode: Literal["amount", "label", "barcode"] = "amount"
    # mode "amount": what was used ("30" + "g", "2" + "tbsp", "1" + "") -> food database, AI if needed
    amount: Optional[str] = Field(default=None, max_length=40)
    unit: Optional[str] = Field(default=None, max_length=40)
    # mode "label" / "barcode": figures per 100 g (or per pack) x the amount used
    label: Optional[LabelFigures] = None
    basis: Literal["100g", "pack"] = "100g"
    used_g: Optional[float] = Field(default=None, gt=0, le=10000)
    packs: Optional[float] = Field(default=None, gt=0, le=50)
    pack_g: Optional[float] = Field(default=None, gt=0, le=10000)
    barcode: Optional[str] = Field(default=None, max_length=32)


@router.post("/{recipe_id}/check-numbers/estimate")
async def estimate_checked_line(
    recipe_id: str, body: EstimateLineRequest, request: Request, user: dict = Depends(get_current_user)
):
    """Line macros for what the user says they used. Nothing is saved (PUT confirmed-lines does)."""
    from services.line_macros import estimate_line_macros, ingredient_line, resolve_line_from_db

    recipe = await _load(recipe_id, user)
    _name, _lf, ings = confirmed.choice_list(recipe, body.version, body.low_fodmap)
    if body.index >= len(ings) or not ings[body.index]["name"].strip():
        raise HTTPException(status_code=404, detail="That ingredient is not in this recipe")
    ing = ings[body.index]
    out: Dict[str, Any] = {"index": body.index, "line": ingredient_line(ing)}

    if body.mode == "amount":
        amount = (body.amount or "").strip()
        if not amount:
            raise HTTPException(status_code=422, detail="Type how much you used")
        text = confirmed.used_line(amount, body.unit, ing["name"])
        badge = resolve_line_from_db(text)
        if badge is None:
            client = getattr(request.app.state, "http_client", None)
            try:
                badge = (await estimate_line_macros([text], client=client, allow_ai=True))[0]
            except Exception:
                badge = None
        if badge is None:
            raise HTTPException(
                status_code=422,
                detail="Couldn't work that one out. Try typing the label figures instead.",
            )
        out.update({
            "used": text,
            "macros": {k: int(badge.get(k) or 0) for k in ("p", "c", "f", "cal")},
            "source": "user",
            "basis_src": badge.get("src") or "ai",
        })
        if badge.get("g") is not None:
            out["macros"]["g"] = badge["g"]
        if badge.get("food"):
            out["food"] = badge["food"]
        return out

    per: Dict[str, Any]
    if body.mode == "barcode":
        from services.nutrition_lookup import lookup_barcode_nutrition

        code = "".join(ch for ch in (body.barcode or "") if ch.isdigit())
        if not code:
            raise HTTPException(status_code=422, detail="Scan or type the barcode")
        entry = lookup_barcode_nutrition(code, prefer_uk=True)
        if not entry:
            raise HTTPException(status_code=404, detail="We couldn't find that product. Type the label figures instead.")
        per = {"kcal": entry.get("calories"), "protein": entry.get("protein"),
               "carbs": entry.get("carbs"), "fat": entry.get("fat")}
        out.update({"source": "barcode", "barcode": code, "product": entry.get("label") or code})
        basis = "100g"
    else:
        if body.label is None:
            raise HTTPException(status_code=422, detail="Type the label figures")
        per = body.label.model_dump()
        out["source"] = "user"
        basis = body.basis
    try:
        out["macros"] = confirmed.badge_from_label(
            per, basis=basis, used_g=body.used_g, packs=body.packs, pack_g=body.pack_g
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    out["basis_src"] = "label"
    return out


class ConfirmedLineIn(BaseModel):
    index: Optional[int] = Field(default=None, ge=0, le=500)
    line: Optional[str] = Field(default=None, max_length=700)
    p: int = Field(ge=0, le=1000)
    c: int = Field(ge=0, le=2000)
    f: int = Field(ge=0, le=1000)
    cal: int = Field(ge=0, le=10000)
    c_total: Optional[int] = Field(default=None, ge=0, le=2000)
    g: Optional[float] = Field(default=None, ge=0, le=100000)
    source: Literal["user", "barcode"] = "user"
    barcode: Optional[str] = Field(default=None, max_length=32)
    product: Optional[str] = Field(default=None, max_length=200)


class ConfirmedLinesRequest(BaseModel):
    version: Optional[str] = None
    low_fodmap: bool = False
    lines: List[ConfirmedLineIn] = Field(default_factory=list, max_length=100)
    clear: List[str] = Field(default_factory=list, max_length=100)


@router.put("/{recipe_id}/confirmed-lines")
async def put_confirmed_lines(
    recipe_id: str, body: ConfirmedLinesRequest, user: dict = Depends(get_current_user)
):
    """Lock the user's figures for lines of one version / Low FODMAP list (or clear them).
    Owner / household editors only. Totals for every list are recomputed from the line macros
    with the confirmed figures winning."""
    from services.recipe_macros_jobs import schedule_recipe_macros
    from services.version_macros import refresh_recipe_macros, recipe_lookup
    from utils.recipe_fields import prepare_recipe_for_response

    recipe = await _load(recipe_id, user)
    require_recipe_edit(user, recipe)
    try:
        adaptations = confirmed.merge_lines(
            recipe.get("adaptations"), recipe, body.version, body.low_fodmap,
            [line.model_dump(exclude_none=True) for line in body.lines], body.clear,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    updated = {**recipe, "adaptations": adaptations or None}
    macros = await refresh_recipe_macros(updated, recipe.get("adaptations"), allow_ai=False)
    fields = dict(macros["fields"])
    fields["adaptations"] = fields.get("adaptations", adaptations or None)
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    await recipe_repository.update_recipe(recipe_id, fields)
    if not macros["complete"]:
        schedule_recipe_macros([recipe_id], user)

    fresh = await recipe_repository.find_by_id(recipe_id) or {**updated, **fields}
    try:
        from database.websocket_manager import EventType, ws_manager

        await ws_manager.broadcast_to_household_or_user(
            user_id=user["id"], household_id=user.get("household_id"),
            event_type=EventType.RECIPE_UPDATED, data=prepare_recipe_for_response(fresh),
        )
    except Exception:
        logger.debug("Confirmed-lines broadcast failed for %s", recipe_id, exc_info=True)
    lookup = await recipe_lookup(fresh, allow_ai=False)
    payload = confirmed.check_payload(fresh, lookup, body.version, body.low_fodmap)
    payload["can_edit"] = True
    payload["confirmed_lines"] = confirmed.confirmed_of(fresh.get("adaptations"))
    return payload
