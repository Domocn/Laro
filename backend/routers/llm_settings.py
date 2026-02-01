from fastapi import APIRouter, Depends, HTTPException, Request
from models import LLMSettingsUpdate
from dependencies import get_current_user, llm_settings_repository
from config import settings
from datetime import datetime, timezone
import httpx

router = APIRouter(prefix="/settings/llm", tags=["LLM Settings"])

# Store LLM settings in memory (per-session) or DB for persistence
# Initialize from env
default_llm_settings = {
    "provider": settings.llm_provider,
    "ollama_url": settings.ollama_url,
    "ollama_model": settings.ollama_model,
}

@router.get("")
async def get_llm_settings(user: dict = Depends(get_current_user)):
    """Get current LLM settings"""
    # Check if user has custom settings
    user_settings = await llm_settings_repository.find_by_user(user["id"])

    if user_settings:
        return {
            **user_settings,
            "available_providers": ["groq", "openai", "anthropic", "ollama"],
        }

    return {
        "provider": default_llm_settings["provider"],
        "ollama_url": default_llm_settings["ollama_url"],
        "ollama_model": default_llm_settings["ollama_model"],
        "available_providers": ["groq", "openai", "anthropic", "ollama"],
    }

@router.put("")
async def update_llm_settings(llm_settings: LLMSettingsUpdate, user: dict = Depends(get_current_user)):
    """Update LLM settings for the user"""
    # Validate provider - embedded is not available in cloud deployment
    if llm_settings.provider == "embedded":
        raise HTTPException(
            status_code=400,
            detail="Embedded LLM is not available in cloud deployment. Please use 'openai', 'anthropic', or 'ollama'."
        )

    settings_doc = {
        "provider": llm_settings.provider,
        "ollama_url": llm_settings.ollama_url or "http://localhost:11434",
        "ollama_model": llm_settings.ollama_model or "llama3",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    await llm_settings_repository.upsert_settings(user["id"], settings_doc)

    return {"message": "LLM settings updated", "settings": {**settings_doc, "user_id": user["id"]}}

@router.post("/test")
async def test_llm_connection(
    request: Request,
    llm_settings: LLMSettingsUpdate,
    user: dict = Depends(get_current_user)
):
    """Test LLM connection with given settings"""
    if llm_settings.provider == "embedded":
        return {
            "success": False,
            "message": "Embedded LLM (GPT4All) is not available in cloud deployment. Please use OpenAI, Anthropic, or Ollama."
        }

    elif llm_settings.provider == "ollama":
        try:
            client = request.app.state.http_client
            # Test Ollama connection
            response = await client.get(f"{llm_settings.ollama_url}/api/tags", timeout=10.0)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]
                return {
                    "success": True,
                    "message": "Connected to Ollama",
                    "available_models": model_names
                }
            else:
                return {"success": False, "message": "Ollama responded with error"}
        except httpx.ConnectError:
            return {"success": False, "message": "Cannot connect to Ollama. Is it running?"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    elif llm_settings.provider == "anthropic":
        api_key = settings.anthropic_api_key
        if api_key:
            return {"success": True, "message": "Anthropic API key configured"}
        else:
            return {"success": False, "message": "No Anthropic API key configured. Set ANTHROPIC_API_KEY in environment."}

    elif llm_settings.provider == "groq":
        api_key = settings.groq_api_key
        if api_key:
            return {"success": True, "message": f"Groq API key configured. Model: {settings.groq_model}"}
        else:
            return {"success": False, "message": "No Groq API key configured. Set GROQ_API_KEY in environment. Get free key at console.groq.com"}

    else:  # openai
        api_key = settings.openai_api_key
        if api_key:
            return {"success": True, "message": "OpenAI API key configured"}
        else:
            return {"success": False, "message": "No OpenAI API key configured. Set OPENAI_API_KEY in environment."}
