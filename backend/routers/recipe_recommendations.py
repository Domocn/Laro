"""
Recipe Recommendations Router - "What should I cook?"

Home cooks describe what they have / fancy and any dietary needs; we pick the
best matches from recipes they can already see (own + household) using the
configured LLM, with a keyword-ranking fallback when AI is unavailable.

Only recipe IDs from the user's own candidate list are ever returned, so the
model can't surface (or invent) recipes the user has no access to.
"""
from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from dependencies import call_llm, clean_llm_json, get_current_user, recipe_repository
from utils.ai_quota import consume_ai_quota, is_premium_user, require_ai_quota

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])
logger = logging.getLogger(__name__)

MAX_LIBRARY = 500
MAX_CANDIDATES = 40
MAX_RESULTS = 6

_STOPWORDS = {
    "a", "an", "and", "the", "with", "of", "or", "to", "for", "in", "on", "some", "i",
    "have", "got", "want", "need", "something", "my", "me", "is", "it", "that", "any",
    "please", "make", "cook", "dinner", "lunch", "breakfast", "meal", "recipe", "recipes",
}

SYSTEM_PROMPT = """You are Laro, a friendly cooking assistant.
You choose recipes ONLY from the numbered list the user provides. Never invent recipes.
Dietary needs and allergies are hard rules: never recommend a recipe that clearly
conflicts with them (check ingredients and dietary tags).
Prefer recipes that use more of the cook's stated ingredients.
Respond with JSON only, in this exact shape:
{"recommendations": [{"id": "<recipe id from the list>", "reason": "<one short sentence>",
"missing_ingredients": ["<key ingredient the cook may still need>"]}]}
Return at most %d items, best match first. Return an empty list if nothing fits.""" % MAX_RESULTS


class RecommendationRequest(BaseModel):
    description: str = Field("", max_length=1000)
    ingredients: List[str] = Field(default_factory=list, max_length=50)
    dietary_needs: List[str] = Field(default_factory=list, max_length=20)


class Recommendation(BaseModel):
    recipe: dict
    reason: str
    missing_ingredients: List[str] = []


class RecommendationResponse(BaseModel):
    recommendations: List[Recommendation]
    used_ai: bool
    library_size: int


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z\-']+", (text or "").lower())
    return {w.rstrip("s") for w in words if len(w) > 2 and w not in _STOPWORDS}


def _ingredient_names(recipe: dict) -> List[str]:
    names = []
    for ing in recipe.get("ingredients") or []:
        if isinstance(ing, dict):
            names.append(str(ing.get("name") or ""))
        else:
            names.append(str(ing))
    return [n for n in names if n]


def _recipe_text(recipe: dict) -> str:
    parts = [recipe.get("title") or "", recipe.get("description") or "", recipe.get("category") or ""]
    parts += [str(t) for t in recipe.get("tags") or []]
    parts += [str(t) for t in recipe.get("dietary_tags") or []]
    parts += _ingredient_names(recipe)
    return " ".join(parts)


def rank_candidates(recipes: List[dict], query_tokens: set[str], limit: int = MAX_CANDIDATES) -> List[dict]:
    """Cheap keyword overlap ranking used to shortlist recipes (and as AI fallback)."""
    if not query_tokens:
        return recipes[:limit]
    scored = []
    for r in recipes:
        overlap = len(query_tokens & _tokens(_recipe_text(r)))
        scored.append((overlap, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [r for s, r in scored if s > 0][:limit]
    # Pad with unscored recipes so the model still has options for vague requests
    if len(top) < limit:
        seen = {r.get("id") for r in top}
        top += [r for _, r in scored if r.get("id") not in seen][: limit - len(top)]
    return top


def _compact(recipe: dict) -> dict:
    return {
        "id": recipe.get("id"),
        "title": recipe.get("title"),
        "ingredients": _ingredient_names(recipe)[:25],
        "tags": (recipe.get("tags") or [])[:10],
        "dietary_tags": recipe.get("dietary_tags") or [],
        "total_minutes": (recipe.get("prep_time") or 0) + (recipe.get("cook_time") or 0) or None,
    }


def _card(recipe: dict) -> dict:
    keep = ("id", "title", "description", "image_url", "category", "tags", "dietary_tags",
            "prep_time", "cook_time", "servings", "difficulty")
    return {k: recipe.get(k) for k in keep}


def parse_llm_recommendations(raw: str, allowed: dict) -> List[Recommendation]:
    """Parse model JSON, dropping any ID that isn't in the user's candidate list."""
    try:
        data = json.loads(clean_llm_json(raw or ""))
    except (ValueError, TypeError):
        return []
    items = data.get("recommendations") if isinstance(data, dict) else data
    out: List[Recommendation] = []
    seen = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("id") or "")
        if rid not in allowed or rid in seen:
            continue
        seen.add(rid)
        missing = item.get("missing_ingredients") or []
        out.append(Recommendation(
            recipe=_card(allowed[rid]),
            reason=str(item.get("reason") or "")[:300],
            missing_ingredients=[str(m)[:60] for m in missing if m][:8],
        ))
        if len(out) >= MAX_RESULTS:
            break
    return out


@router.post("", response_model=RecommendationResponse)
async def recommend_recipes(
    data: RecommendationRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    ingredients = [i.strip()[:60] for i in data.ingredients if i and i.strip()]
    dietary = [d.strip()[:60] for d in data.dietary_needs if d and d.strip()]
    description = (data.description or "").strip()
    if not (description or ingredients):
        raise HTTPException(status_code=400, detail="Tell us what you have or what you fancy.")

    recipes = await recipe_repository.find_by_household_or_author(
        user["id"], user.get("household_id"), limit=MAX_LIBRARY
    )
    if not recipes:
        return RecommendationResponse(recommendations=[], used_ai=False, library_size=0)

    query_tokens = _tokens(" ".join([description] + ingredients))
    candidates = rank_candidates(recipes, query_tokens)
    allowed = {str(r.get("id")): r for r in candidates}

    await require_ai_quota(user)
    user_prompt = (
        f"What the cook says: {description or '(nothing extra)'}\n"
        f"Ingredients they have: {', '.join(ingredients) or '(not specified)'}\n"
        f"Dietary needs / allergies: {', '.join(dietary) or 'none'}\n\n"
        f"Recipes to choose from:\n{json.dumps([_compact(r) for r in candidates], ensure_ascii=False)}"
    )
    recs: List[Recommendation] = []
    used_ai = False
    try:
        usage_meta: dict = {}
        raw = await call_llm(
            request.app.state.http_client, SYSTEM_PROMPT, user_prompt, user["id"],
            usage_meta=usage_meta, format_json=True, max_tokens=1200,
        )
        recs = parse_llm_recommendations(raw, allowed)
        used_ai = True
        if not usage_meta.get("cached") and not is_premium_user(user):
            await consume_ai_quota(user["id"])
    except HTTPException:
        raise
    except Exception as e:  # provider down / misconfigured — degrade, don't fail
        logger.warning("Recommendation LLM call failed, using keyword fallback: %s", e)

    if not used_ai:
        diet_tokens = _tokens(" ".join(dietary))
        fallback = []
        for r in rank_candidates(candidates, query_tokens, MAX_RESULTS * 2):
            if diet_tokens and not diet_tokens <= _tokens(" ".join(map(str, r.get("dietary_tags") or []))):
                continue  # can't verify diet without AI, so only show tagged matches
            fallback.append(Recommendation(recipe=_card(r), reason="Matches your ingredients", missing_ingredients=[]))
        recs = fallback[:MAX_RESULTS]

    return RecommendationResponse(recommendations=recs, used_ai=used_ai, library_size=len(recipes))
