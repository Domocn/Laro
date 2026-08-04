"""
Voice Cooking Router - Text-to-speech and voice control for cooking mode
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from dependencies import get_current_user, recipe_repository, voice_settings_repository
from datetime import datetime, timezone

router = APIRouter(prefix="/voice", tags=["Voice Cooking"])

# =============================================================================
# MODELS
# =============================================================================

class TextToSpeechRequest(BaseModel):
    text: str
    language: Optional[str] = "en-US"
    rate: Optional[float] = 1.0

class VoiceCommand(BaseModel):
    command: str
    recipe_id: Optional[str] = None
    current_step: Optional[int] = None

class VoiceSettings(BaseModel):
    enabled: bool = True
    auto_read_steps: bool = True
    voice_language: str = "en-US"
    speech_rate: float = 1.0
    voice_commands_enabled: bool = True

# =============================================================================
# VOICE COMMAND MAPPINGS
# =============================================================================

VOICE_COMMANDS = {
    "next": ["next", "next step", "continue", "go on", "forward"],
    "previous": ["previous", "back", "go back", "last step"],
    "repeat": ["repeat", "again", "say again", "what was that"],
    "first": ["first", "start over", "beginning", "go to start"],
    "last": ["last", "final step", "finish"],
    "start_timer": ["start timer", "set timer", "timer on"],
    "stop_timer": ["stop timer", "cancel timer", "timer off"],
    "timer_status": ["how much time", "time left", "timer status"],
    "ingredients": ["ingredients", "what do i need", "show ingredients"],
    "current_step": ["current step", "where am i", "what step"],
    "help": ["help", "commands", "what can i say"],
}

SUPPORTED_LANGUAGES = {
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "es-ES": "Spanish",
    "fr-FR": "French",
    "de-DE": "German",
    "it-IT": "Italian",
    "pt-BR": "Portuguese",
    "zh-CN": "Chinese",
    "ja-JP": "Japanese",
    "ko-KR": "Korean",
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_voice_command(text: str) -> tuple:
    """Parse voice input to identify command"""
    text = text.lower().strip()

    for command, phrases in VOICE_COMMANDS.items():
        for phrase in phrases:
            if phrase in text:
                return command, phrase

    return None, None

def format_step_for_speech(step_text: str, step_num: int, total_steps: int) -> str:
    """Format a cooking step for text-to-speech"""
    return f"Step {step_num} of {total_steps}. {step_text}"

def format_ingredients_for_speech(ingredients: list) -> str:
    """Format ingredients list for text-to-speech"""
    lines = ["Here are the ingredients:"]
    for ing in ingredients:
        if isinstance(ing, dict):
            amount = ing.get("amount", "")
            unit = ing.get("unit", "")
            name = ing.get("name", "")
            lines.append(f"{amount} {unit} {name}".strip())
        else:
            lines.append(str(ing))
    return ". ".join(lines)

def get_command_description(command: str) -> str:
    """Get description for a voice command"""
    descriptions = {
        "next": "Go to the next cooking step",
        "previous": "Go back to the previous step",
        "repeat": "Read the current step again",
        "first": "Go to the first step",
        "last": "Go to the last step",
        "start_timer": "Start a timer for the current step",
        "stop_timer": "Stop the active timer",
        "timer_status": "Check remaining time on timer",
        "ingredients": "Read the list of ingredients",
        "current_step": "Tell me which step I'm on",
        "help": "List available voice commands",
    }
    return descriptions.get(command, "")

def estimate_step_duration(step_text: str) -> int:
    """Estimate duration of a cooking step in minutes"""
    import re

    time_patterns = [
        (r'(\d+)\s*hour', 60),
        (r'(\d+)\s*hr', 60),
        (r'(\d+)\s*minute', 1),
        (r'(\d+)\s*min', 1),
        (r'(\d+)-(\d+)\s*minute', 1),
    ]

    total_minutes = 0
    for pattern, multiplier in time_patterns:
        matches = re.findall(pattern, step_text.lower())
        for match in matches:
            if isinstance(match, tuple):
                total_minutes += int(match[-1]) * multiplier
            else:
                total_minutes += int(match) * multiplier

    return total_minutes if total_minutes > 0 else 5

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/languages")
async def get_supported_languages():
    """Get list of supported TTS languages"""
    return {
        "languages": [
            {"code": code, "name": name}
            for code, name in SUPPORTED_LANGUAGES.items()
        ]
    }

@router.get("/commands")
async def get_voice_commands():
    """Get list of available voice commands"""
    commands = []
    for command, phrases in VOICE_COMMANDS.items():
        commands.append({
            "command": command,
            "phrases": phrases,
            "description": get_command_description(command)
        })
    return {"commands": commands}

@router.post("/tts/prepare")
async def prepare_tts(
    data: TextToSpeechRequest,
    user: dict = Depends(get_current_user)
):
    """Prepare text for speech synthesis (client-side TTS)"""
    text = data.text.strip()

    replacements = {
        "tbsp": "tablespoon",
        "tsp": "teaspoon",
        "oz": "ounce",
        "lb": "pound",
        "min": "minute",
        "hr": "hour",
        "°F": "degrees Fahrenheit",
        "°C": "degrees Celsius",
    }

    for abbrev, full in replacements.items():
        text = text.replace(abbrev, full)

    return {
        "text": text,
        "language": data.language,
        "rate": data.rate,
        "tts_provider": "browser",
        "note": "Use browser's speechSynthesis API with these parameters"
    }

@router.post("/command")
async def process_voice_command(
    data: VoiceCommand,
    user: dict = Depends(get_current_user)
):
    """Process a voice command and return action"""
    command, matched_phrase = parse_voice_command(data.command)

    if not command:
        return {
            "understood": False,
            "action": None,
            "response": "I didn't understand that. Say 'help' for available commands.",
            "speak": True
        }

    response = {
        "understood": True,
        "command": command,
        "matched_phrase": matched_phrase,
        "action": None,
        "response": "",
        "speak": True
    }

    if command == "next":
        response["action"] = {"type": "navigate", "direction": "next"}
        response["response"] = "Moving to next step"
    elif command == "previous":
        response["action"] = {"type": "navigate", "direction": "previous"}
        response["response"] = "Going back"
    elif command == "repeat":
        response["action"] = {"type": "repeat"}
        response["response"] = ""
    elif command == "first":
        response["action"] = {"type": "navigate", "step": 0}
        response["response"] = "Going to first step"
    elif command == "last":
        response["action"] = {"type": "navigate", "step": -1}
        response["response"] = "Going to final step"
    elif command == "start_timer":
        response["action"] = {"type": "timer", "operation": "start"}
        response["response"] = "Starting timer"
    elif command == "stop_timer":
        response["action"] = {"type": "timer", "operation": "stop"}
        response["response"] = "Timer stopped"
    elif command == "timer_status":
        response["action"] = {"type": "timer", "operation": "status"}
        response["response"] = ""
    elif command == "ingredients":
        response["action"] = {"type": "show_ingredients"}
        response["response"] = ""
    elif command == "current_step":
        step = data.current_step or 0
        response["action"] = {"type": "info"}
        response["response"] = f"You are on step {step + 1}"
    elif command == "help":
        response["action"] = {"type": "help"}
        response["response"] = "You can say: next, previous, repeat, ingredients, start timer, or help"

    return response

@router.get("/settings")
async def get_voice_settings(user: dict = Depends(get_current_user)):
    """Get user's voice cooking settings"""
    settings = await voice_settings_repository.find_by_user(user["id"])

    if not settings:
        return VoiceSettings().model_dump()

    settings.pop("user_id", None)
    return settings

@router.put("/settings")
async def update_voice_settings(
    data: VoiceSettings,
    user: dict = Depends(get_current_user)
):
    """Update user's voice cooking settings"""
    settings = data.model_dump()
    settings["user_id"] = user["id"]
    settings["updated_at"] = datetime.now(timezone.utc).isoformat()

    await voice_settings_repository.upsert_settings(user["id"], settings)

    return {"message": "Voice settings updated"}

@router.post("/recipe/{recipe_id}/prepare-steps")
async def prepare_recipe_for_voice(
    recipe_id: str,
    user: dict = Depends(get_current_user)
):
    """Prepare all recipe steps for voice guidance"""
    recipe = await recipe_repository.find_by_id(recipe_id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    instructions = recipe.get("instructions", [])
    total_steps = len(instructions)

    prepared_steps = []
    for i, step in enumerate(instructions):
        prepared_steps.append({
            "step_number": i + 1,
            "total_steps": total_steps,
            "original_text": step,
            "speech_text": format_step_for_speech(step, i + 1, total_steps),
            "estimated_duration": estimate_step_duration(step)
        })

    ingredients_speech = format_ingredients_for_speech(recipe.get("ingredients", []))

    return {
        "recipe_id": recipe_id,
        "title": recipe.get("title"),
        "steps": prepared_steps,
        "ingredients_speech": ingredients_speech,
        "total_steps": total_steps
    }
