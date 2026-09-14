"""
Google Health API router — link account + sync settings + undo nutrition logs.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from dependencies import get_current_user, recipe_repository
from services import google_health as gh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-health", tags=["Google Health"])


class CallbackBody(BaseModel):
    code: str
    state: str
    redirect_uri: Optional[str] = None


class SyncSettingsBody(BaseModel):
    sync_on_cook: bool


def _status_payload(link: Optional[dict], configured: bool) -> dict:
    if not link:
        return {
            "configured": configured,
            "linked": False,
            "sync_on_cook": False,
            "linked_at": None,
            "scopes": None,
        }
    return {
        "configured": configured,
        "linked": True,
        "sync_on_cook": bool(link.get("sync_on_cook", True)),
        "linked_at": link.get("linked_at").isoformat()
        if hasattr(link.get("linked_at"), "isoformat")
        else link.get("linked_at"),
        "scopes": link.get("scopes"),
        "google_sub": link.get("google_sub"),
    }


@router.get("/status")
async def google_health_status(user: dict = Depends(get_current_user)):
    configured = gh.is_configured()
    link = await gh.get_link(user["id"]) if configured else None
    return _status_payload(link, configured)


@router.get("/auth-url")
async def google_health_auth_url(
    redirect_uri: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    if not gh.is_configured():
        raise HTTPException(status_code=400, detail="Google Health OAuth is not configured")

    if not redirect_uri:
        redirect_uri = f"{gh.oauth_redirect_base()}/oauth/callback/google-health"
    try:
        redirect_uri = gh.validate_redirect_uri(redirect_uri)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state = await gh.create_oauth_state(user["id"], redirect_uri)
    auth_url = gh.build_auth_url(state, redirect_uri)
    return {"auth_url": auth_url, "state": state}


@router.post("/callback")
async def google_health_callback(
    body: CallbackBody,
    user: dict = Depends(get_current_user),
):
    if not gh.is_configured():
        raise HTTPException(status_code=400, detail="Google Health OAuth is not configured")

    try:
        state_row = await gh.consume_oauth_state(body.state, user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    redirect_uri = body.redirect_uri or state_row["redirect_uri"]
    try:
        redirect_uri = gh.validate_redirect_uri(redirect_uri)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        tokens = await gh.exchange_code(body.code, redirect_uri)
        await gh.upsert_link(user["id"], tokens)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Google Health link failed")
        raise HTTPException(status_code=400, detail="Failed to link Google Health") from None

    link = await gh.get_link(user["id"])
    return {"message": "Google Health linked", **_status_payload(link, True)}


@router.delete("/link")
async def google_health_unlink(user: dict = Depends(get_current_user)):
    deleted = await gh.delete_link(user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Google Health not linked")
    return {"message": "Google Health unlinked", "linked": False}


@router.patch("/settings")
async def google_health_settings(
    body: SyncSettingsBody,
    user: dict = Depends(get_current_user),
):
    link = await gh.set_sync_on_cook(user["id"], body.sync_on_cook)
    if not link:
        raise HTTPException(status_code=404, detail="Google Health not linked")
    return _status_payload(link, gh.is_configured())


@router.post("/sync/{recipe_id}")
async def google_health_manual_sync(
    recipe_id: str,
    user: dict = Depends(get_current_user),
):
    link = await gh.get_link(user["id"])
    if not link:
        raise HTTPException(status_code=400, detail="Google Health not linked")

    recipe = await recipe_repository.find_by_id(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    try:
        result = await gh.sync_recipe_to_google_health(
            user_id=user["id"],
            recipe=recipe,
            servings=1.0,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Manual Google Health sync failed")
        raise HTTPException(status_code=502, detail="Google Health sync failed") from None

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Nothing to sync (sync off or recipe has no nutrition)",
        )
    return {"message": "Synced to Google Health", "log": result}


@router.get("/logs")
async def google_health_list_logs(user: dict = Depends(get_current_user)):
    logs = await gh.list_nutrition_logs(user["id"], limit=30)
    return {"logs": logs}


@router.delete("/logs/{log_id}")
async def google_health_delete_log(
    log_id: str,
    user: dict = Depends(get_current_user),
):
    try:
        ok = await gh.delete_nutrition_log_for_user(user["id"], log_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Google Health log delete failed")
        raise HTTPException(status_code=502, detail="Failed to delete nutrition log") from None
    if not ok:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"message": "Nutrition log deleted from Google Health"}
