"""Unit tests for AI substitution prompt/parse helpers (no live LLM)."""
from utils.ai_substitutions import (
    build_substitution_user_prompt,
    parse_ai_substitution_response,
)


def test_build_prompt_includes_recipe_and_seed():
    prompt = build_substitution_user_prompt(
        "mashed banana",
        recipe_title="Tiramisu Breakfast Bowl",
        ingredients=[
            {"amount": "1", "unit": "piece", "name": "mashed banana"},
            {"amount": "100", "unit": "g", "name": "Greek yogurt"},
        ],
        instructions=["Mash banana", "Mix with yogurt"],
        seed_suggestions=[
            {"name": "applesauce", "reason": "binder"},
            {"name": "lemon", "reason": "fruit"},
        ],
        limit=5,
    )
    assert "Tiramisu Breakfast Bowl" in prompt
    assert "mashed banana" in prompt
    assert "applesauce" in prompt
    assert "Greek yogurt" in prompt


def test_parse_ai_json_filters_self_and_limits():
    raw = """```json
    {"suggestions":[
      {"name":"mashed banana","reason":"same"},
      {"name":"applesauce","reason":"moisture and bind for this bowl"},
      {"name":"pumpkin puree","reason":"soft binder"},
      {"name":"greek yogurt","reason":"creamy protein"}
    ]}
    ```"""
    out = parse_ai_substitution_response(raw, limit=2, exclude_names=["mashed banana"])
    assert len(out) == 2
    assert out[0]["name"].lower() == "applesauce"
    assert out[0]["source"] == "ai"
    assert "bowl" in (out[0]["reason"] or "").lower() or out[0]["reason"]


def test_parse_ai_handles_bare_list():
    raw = '[{"name":"applesauce","reason":"works here"}]'
    out = parse_ai_substitution_response(raw, limit=3, exclude_names=["banana"])
    assert out and out[0]["name"] == "applesauce"
