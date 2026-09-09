"""Conversational AI must stay on food/cooking and redirect off-topic to Google."""
from routers import ai as ai_router


def test_food_topic_scope_rule_redirects_to_google():
    rule = ai_router.FOOD_TOPIC_SCOPE_RULE.lower()
    assert "only answer" in rule or "only answers" in rule or "you only answer" in rule
    assert "google" in rule
    assert "google.com/search" in rule
    assert "food" in rule and "cooking" in rule


def test_with_food_topic_scope_appends_rule():
    prompt = ai_router._with_food_topic_scope("You are a cooking helper.")
    assert prompt.startswith("You are a cooking helper.")
    assert "Topic scope" in prompt
    assert "google.com/search" in prompt


def test_chat_and_cooking_assistant_source_include_scope():
    from pathlib import Path

    src = Path(ai_router.__file__).read_text()
    # Both conversational endpoints must wrap prompts with the scope helper
    assert src.count("_with_food_topic_scope(") >= 3
