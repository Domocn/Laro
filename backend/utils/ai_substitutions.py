"""
Recipe-aware ingredient substitutions via Laro AI.

Local curated/function/food_db suggestions seed the prompt; the LLM ranks and
rewrites reasons so swaps fit THIS recipe (e.g. mashed banana → applesauce in a
breakfast bowl, not lemon just because both are fruit).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Laro, a cooking assistant. Suggest ingredient substitutions
that are appropriate for the SPECIFIC recipe given — not generic grocery swaps.

Rules:
- Match the ingredient's FUNCTION in this dish (binder, sweetener, fat, acid, protein, garnish, etc.).
- Consider the other ingredients, method, and dish style.
- Reject category-only matches that would break the recipe (e.g. lemon for mashed banana in a bowl).
- Prefer practical home-cook swaps with a short recipe-specific reason.
- Respect diet / veto notes when provided.
- Return ONLY JSON (no markdown fences):
{"suggestions":[{"name":"applesauce","reason":"Same moisture and mild sweetness for this bowl"}]}
- Give 3 to 5 suggestions. Use common ingredient names.
"""


def _format_ingredients(ingredients: Sequence[Any]) -> str:
    lines = []
    for item in ingredients or []:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = " ".join(
                str(x).strip()
                for x in (item.get("amount"), item.get("unit"), item.get("name") or item.get("ingredient"))
                if x is not None and str(x).strip()
            )
        else:
            text = str(item or "").strip()
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines) if lines else "(none listed)"


def _format_instructions(instructions: Sequence[Any], *, max_steps: int = 8) -> str:
    lines = []
    for i, step in enumerate((instructions or [])[:max_steps], 1):
        if isinstance(step, dict):
            text = step.get("text") or step.get("instruction") or step.get("step") or ""
        else:
            text = step
        text = str(text or "").strip()
        if text:
            lines.append(f"{i}. {text}")
    return "\n".join(lines) if lines else "(none listed)"


def build_substitution_user_prompt(
    ingredient: str,
    *,
    recipe_title: str = "",
    recipe_description: str = "",
    ingredients: Optional[Sequence[Any]] = None,
    instructions: Optional[Sequence[Any]] = None,
    seed_suggestions: Optional[Sequence[Dict[str, Any]]] = None,
    diet_notes: str = "",
    limit: int = 5,
) -> str:
    seeds = []
    for s in seed_suggestions or []:
        if not isinstance(s, dict):
            continue
        name = (s.get("name") or "").strip()
        if not name:
            continue
        reason = (s.get("reason") or "").strip()
        seeds.append(f"- {name}" + (f" ({reason})" if reason else ""))

    seed_block = "\n".join(seeds) if seeds else "(none)"
    return f"""Recipe: {recipe_title or "(untitled)"}
Description: {(recipe_description or "").strip() or "(none)"}

Ingredients:
{_format_ingredients(ingredients or [])}

Method (abbrev.):
{_format_instructions(instructions or [])}

Ingredient to replace: {ingredient}

Diet / preference notes: {(diet_notes or "").strip() or "(none)"}

Seed candidates (rank, filter, improve — drop bad ones, add better if needed):
{seed_block}

Return up to {max(1, min(int(limit or 5), 8))} JSON suggestions appropriate for THIS recipe.
"""


def parse_ai_substitution_response(
    raw: str,
    *,
    limit: int = 5,
    exclude_names: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Parse LLM JSON into suggestion dicts. Returns [] on failure."""
    from dependencies import clean_llm_json
    from utils.food_db import _normalize_name, find_food

    exclude = {_normalize_name(x) for x in (exclude_names or []) if x}
    try:
        cleaned = clean_llm_json(raw or "")
        data = json.loads(cleaned)
    except Exception as exc:
        logger.warning("AI substitution JSON parse failed: %s", exc)
        return []

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("suggestions") or data.get("substitutions") or data.get("swaps") or []
    else:
        return []

    out: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        if isinstance(item, str):
            name, reason = item.strip(), ""
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("ingredient") or item.get("swap") or "").strip()
            reason = str(item.get("reason") or item.get("why") or item.get("note") or "").strip()
        else:
            continue
        if not name:
            continue
        norm = _normalize_name(name)
        if not norm or norm in seen or norm in exclude:
            continue
        seen.add(norm)
        cat = None
        found = find_food(name)
        if found:
            cat = found[1].get("category")
        out.append(
            {
                "name": name,
                "reason": reason or "Fits this recipe's method and flavour",
                "category": cat,
                "source": "ai",
            }
        )
        if len(out) >= max(1, min(int(limit or 5), 8)):
            break
    return out


async def ai_rank_substitutions(
    ingredient: str,
    *,
    recipe_title: str = "",
    recipe_description: str = "",
    ingredients: Optional[Sequence[Any]] = None,
    instructions: Optional[Sequence[Any]] = None,
    seed_suggestions: Optional[Sequence[Dict[str, Any]]] = None,
    diet_notes: str = "",
    limit: int = 5,
    user: Optional[dict] = None,
    meter_quota: bool = True,
) -> Dict[str, Any]:
    """
    Ask Laro AI for recipe-appropriate swaps.

    Returns {suggestions, ai_used, ai_error?}. On failure suggestions is [].
    """
    import httpx
    from dependencies import call_llm
    from utils.food_db import _normalize_name

    name = (ingredient or "").strip()
    if not name:
        return {"suggestions": [], "ai_used": False, "ai_error": "missing_ingredient"}

    user_prompt = build_substitution_user_prompt(
        name,
        recipe_title=recipe_title,
        recipe_description=recipe_description,
        ingredients=ingredients,
        instructions=instructions,
        seed_suggestions=seed_suggestions,
        diet_notes=diet_notes,
        limit=limit,
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if meter_quota and user:
                from routers.ai import call_llm_metered

                raw = await call_llm_metered(
                    client,
                    SYSTEM_PROMPT,
                    user_prompt,
                    user,
                    format_json=True,
                    max_tokens=700,
                )
            else:
                raw = await call_llm(
                    client,
                    SYSTEM_PROMPT,
                    user_prompt,
                    (user or {}).get("id") if user else None,
                    format_json=True,
                    max_tokens=700,
                )
    except Exception as exc:
        logger.warning("AI substitution call failed for %r: %s", name, exc)
        return {"suggestions": [], "ai_used": False, "ai_error": str(exc)[:200]}

    suggestions = parse_ai_substitution_response(
        raw,
        limit=limit,
        exclude_names=[name],
    )
    # Drop self-matches / near-identical
    suggestions = [
        s
        for s in suggestions
        if _normalize_name(s.get("name") or "") != _normalize_name(name)
    ]
    return {
        "suggestions": suggestions,
        "ai_used": bool(suggestions),
        "ai_error": None if suggestions else "empty_response",
    }
