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
    "openai_base_url": None,
    "openai_model": "gpt-4o",
}

@router.get("")
async def get_llm_settings(user: dict = Depends(get_current_user)):
    """Get current LLM settings"""
    if settings.is_cloud:
        return {
            "provider": settings.llm_provider,
            "ollama_url": None,
            "ollama_model": settings.ollama_model,
            "openai_base_url": None,
            "openai_model": None,
            "managed": True,
            "available_providers": [],
        }

    # Check if user has custom settings
    user_settings = await llm_settings_repository.find_by_user(user["id"])

    if user_settings:
        return {
            **user_settings,
            "managed": False,
            "available_providers": ["groq", "openai", "anthropic", "ollama"],
        }

    return {
        "provider": default_llm_settings["provider"],
        "ollama_url": default_llm_settings["ollama_url"],
        "ollama_model": default_llm_settings["ollama_model"],
        "openai_base_url": default_llm_settings["openai_base_url"],
        "openai_model": default_llm_settings["openai_model"],
        "managed": False,
        "available_providers": ["groq", "openai", "anthropic", "ollama"],
    }

@router.put("")
async def update_llm_settings(llm_settings: LLMSettingsUpdate, user: dict = Depends(get_current_user)):
    """Update LLM settings for the user"""
    if settings.is_cloud:
        raise HTTPException(
            status_code=400,
            detail="AI is managed by Laro on this server. Provider settings cannot be changed.",
        )

    # Validate provider - embedded was never implemented
    if llm_settings.provider == "embedded":
        raise HTTPException(
            status_code=400,
            detail="Embedded LLM is not available. Use openai, anthropic, or ollama.",
        )

    base = (llm_settings.openai_base_url or "").strip() or None
    settings_doc = {
        "provider": llm_settings.provider,
        "ollama_url": llm_settings.ollama_url or "http://localhost:11434",
        "ollama_model": llm_settings.ollama_model or "llama3",
        "openai_base_url": base,
        "openai_model": (llm_settings.openai_model or "gpt-4o").strip() or "gpt-4o",
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
    if settings.is_cloud:
        # Prove managed cloud AI is reachable (server credentials, not user URL)
        try:
            from dependencies import call_llm
            client = request.app.state.http_client
            reply = await call_llm(
                client,
                "Reply with exactly: OK",
                "ping",
                user_id=user["id"],
            )
            ok = bool(reply and str(reply).strip())
            return {
                "success": ok,
                "message": "Laro AI is ready" if ok else "Laro AI did not respond",
                "managed": True,
            }
        except Exception as e:
            return {"success": False, "message": f"Laro AI unavailable: {e}", "managed": True}

    if llm_settings.provider == "embedded":
        return {
            "success": False,
            "message": "Embedded LLM is not available. Use OpenAI, Anthropic, or Ollama.",
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

    else:  # openai / OpenAI-compatible
        base = (llm_settings.openai_base_url or "").strip()
        model = (llm_settings.openai_model or "gpt-4o").strip() or "gpt-4o"
        if base:
            # LM Studio / local: probe models endpoint (key often optional)
            try:
                client = request.app.state.http_client
                probe = base.rstrip("/") + "/models"
                headers = {}
                if settings.openai_api_key:
                    headers["Authorization"] = f"Bearer {settings.openai_api_key}"
                resp = await client.get(probe, headers=headers, timeout=10.0)
                if resp.status_code < 500:
                    return {
                        "success": True,
                        "message": f"Reached OpenAI-compatible endpoint ({model})",
                        "base_url": base,
                    }
                return {"success": False, "message": f"Endpoint error: HTTP {resp.status_code}"}
            except Exception as e:
                return {"success": False, "message": f"Cannot reach {base}: {e}"}
        api_key = settings.openai_api_key
        if api_key:
            return {"success": True, "message": f"OpenAI API key configured (model {model})"}
        return {
            "success": False,
            "message": "No OPENAI_API_KEY in environment (required for api.openai.com).",
        }
