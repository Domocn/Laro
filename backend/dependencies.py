"""
Dependencies module for FastAPI application
Provides authentication, database access, and LLM integration
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings
import jwt
import bcrypt
import httpx
import logging
import hashlib
import time
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

# Import debug utilities
try:
    from utils.debug import Loggers, log_auth_event, log_ai_request, debug_async
    _debug_available = True
except ImportError:
    _debug_available = False

# Import PostgreSQL database module
from database.connection import get_db, init_db, close_db
from database.repositories.user_repository import user_repository
from database.repositories.session_repository import (
    session_repository,
    login_attempt_repository,
    totp_secret_repository,
    oauth_account_repository,
    trusted_device_repository,
    oauth_state_repository,
)
from database.repositories.settings_repository import (
    system_settings_repository,
    llm_settings_repository,
    llm_cache_repository,
    custom_prompts_repository,
    user_preferences_repository,
    invite_code_repository,
    audit_log_repository,
    backup_repository,
    backup_settings_repository,
    custom_role_repository,
    voice_settings_repository,
    custom_ingredient_repository,
    share_link_repository,
)
from database.repositories.recipe_repository import (
    recipe_repository,
    recipe_share_repository,
    recipe_version_repository,
    review_repository,
)
from database.repositories.household_repository import household_repository
from database.repositories.meal_plan_repository import meal_plan_repository
from database.repositories.shopping_list_repository import shopping_list_repository
from database.repositories.cooking_repository import (
    cook_session_repository,
    recipe_feedback_repository,
    ingredient_cost_repository,
)
from database.repositories.notification_repository import (
    push_subscription_repository,
    notification_settings_repository,
)
from database.repositories.security_repository import (
    ip_allowlist_repository,
    ip_blocklist_repository,
)
from database.repositories.api_token_repository import api_token_repository
from database.repositories.cookbook_repository import cookbook_repository
from database.repositories.pantry_repository import (
    pantry_repository,
    PANTRY_CATEGORIES,
    STAPLE_INGREDIENTS,
)
from database.repositories.aisle_override_repository import aisle_override_repository
from database.repositories.support_ticket_repository import (
    support_ticket_repository,
    support_ticket_message_repository,
)

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str) -> str:
    import uuid as _uuid
    payload = {
        "user_id": user_id,
        "jti": str(_uuid.uuid4()),  # unique per issuance so sessions revoke correctly
        "exp": datetime.now(timezone.utc) + timedelta(days=30)
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    start_time = time.time()
    token = credentials.credentials
    logger.info(f"Auth attempt - token type: {'API' if token.startswith('laro_') else 'JWT'}, token length: {len(token)}")

    # Check if it's an API token (starts with "laro_")
    if token.startswith("laro_"):
        if _debug_available:
            Loggers.auth.debug("Validating API token", token_prefix="laro_***")
        token_data = await api_token_repository.validate_token(token)
        if not token_data:
            logger.warning("Auth failed: Invalid or expired API token")
            raise HTTPException(status_code=401, detail="Invalid or expired API token")

        user = await user_repository.find_by_id(token_data["user_id"])
        if not user:
            logger.warning(f"Auth failed: User not found for API token user_id={token_data['user_id']}")
            raise HTTPException(status_code=401, detail="User not found")

        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            Loggers.auth.debug("API token validated", user_id=user["id"], duration_ms=f"{duration_ms:.2f}")
        return user

    # Try Supabase JWT first (if configured)
    if settings.supabase_jwt_secret:
        try:
            if _debug_available:
                Loggers.auth.debug("Validating Supabase JWT token")
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated"
            )
            supabase_user_id = payload.get("sub")
            email = payload.get("email")
            logger.info(f"Supabase JWT decoded - sub: {supabase_user_id}, email: {email}")

            # Find user by supabase_id or email
            user = await user_repository.find_by_supabase_id(supabase_user_id)
            if not user and email:
                user = await user_repository.find_by_email(email)
                if user:
                    # Link existing user to Supabase
                    await user_repository.update(user["id"], {"supabase_id": supabase_user_id})
                    user["supabase_id"] = supabase_user_id

            if not user:
                # Auto-create user on first Supabase login
                import uuid
                from datetime import datetime, timezone
                user_metadata = payload.get("user_metadata", {})
                new_user = {
                    "id": str(uuid.uuid4()),
                    "supabase_id": supabase_user_id,
                    "email": email,
                    "name": user_metadata.get("name") or user_metadata.get("full_name") or email.split("@")[0],
                    "password": None,  # No password - Supabase handles auth
                    "role": "user",
                    "status": "active",
                    "created_at": datetime.now(timezone.utc),
                    "oauth_only": True
                }
                user = await user_repository.create(new_user)
                logger.info(f"Auto-created user from Supabase: {user['id']}")

            duration_ms = (time.time() - start_time) * 1000
            if _debug_available:
                Loggers.auth.debug("Supabase JWT validated", user_id=user["id"], duration_ms=f"{duration_ms:.2f}")
            return user
        except jwt.ExpiredSignatureError:
            logger.warning("Auth failed: Supabase token expired")
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            # Not a valid Supabase token, try legacy JWT
            pass

    # Laro JWT — must match a live session so logout / password reset actually revoke access
    try:
        if _debug_available:
            Loggers.auth.debug("Validating Laro JWT token")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        session = await session_repository.find_by_user_and_token(user_id, token)
        if not session:
            logger.warning(f"Auth failed: no live session for user_id={user_id}")
            raise HTTPException(status_code=401, detail="Session expired or revoked. Please log in again.")

        user = await user_repository.find_by_id(user_id)
        if not user:
            logger.warning(f"Auth failed: User not found for JWT user_id={user_id}")
            raise HTTPException(status_code=401, detail="User not found")

        # Touch last_active (best-effort)
        try:
            await session_repository.update_session(
                session["id"],
                {"last_active": datetime.now(timezone.utc).replace(tzinfo=None)}
            )
        except Exception:
            pass

        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            Loggers.auth.debug("Laro JWT validated", user_id=user["id"], duration_ms=f"{duration_ms:.2f}")
        return user
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        logger.warning("Auth failed: Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Auth failed: Invalid token - {type(e).__name__}: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


# LLM Helpers

async def call_embedded(
    system_prompt: str,
    user_prompt: str,
    model_name: str = None
) -> str:
    """Embedded LLM is not available in cloud deployment - use Ollama or cloud providers instead"""
    raise HTTPException(
        status_code=503,
        detail="Embedded LLM (GPT4All) is not available in cloud deployment. Please configure Ollama, OpenAI, or Anthropic as your LLM provider in Settings."
    )


async def call_openai(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
) -> str:
    """Call OpenAI or an OpenAI-compatible endpoint (e.g. LM Studio)."""
    start_time = time.time()
    model_name = (model or "gpt-4o").strip() or "gpt-4o"
    if _debug_available:
        Loggers.ai.info("Calling OpenAI API", model=model_name, base_url=base_url or "default")

    try:
        from openai import AsyncOpenAI

        api_key = settings.openai_api_key or ("lm-studio" if base_url else None)
        if not api_key and not base_url:
            if _debug_available:
                Loggers.ai.error("OpenAI API key not configured")
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        kwargs = {"api_key": api_key or "unused", "http_client": client}
        if base_url:
            kwargs["base_url"] = base_url.rstrip("/")
        openai_client = AsyncOpenAI(**kwargs)

        response = await openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            usage = getattr(response, 'usage', None)
            log_ai_request(
                "openai", model_name, "chat_completion",
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                duration_ms=duration_ms
            )

        return response.choices[0].message.content
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("openai", model_name, "chat_completion", duration_ms=duration_ms, error=str(e))
        logger.error(f"OpenAI error: {e}")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")


async def call_groq(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str
) -> str:
    """Call Groq API - extremely fast inference, no training on data"""
    start_time = time.time()
    model = settings.groq_model
    if _debug_available:
        Loggers.ai.info("Calling Groq API", model=model)

    try:
        api_key = settings.groq_api_key
        if not api_key:
            if _debug_available:
                Loggers.ai.error("Groq API key not configured")
            raise HTTPException(status_code=500, detail="Groq API key not configured")

        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout=60.0
        )

        duration_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            if _debug_available:
                log_ai_request("groq", model, "chat_completion", duration_ms=duration_ms,
                             error=f"HTTP {response.status_code}: {response.text[:200]}")
            raise HTTPException(status_code=500, detail=f"Groq error: {response.text}")

        result = response.json()

        if _debug_available:
            usage = result.get("usage", {})
            log_ai_request(
                "groq", model, "chat_completion",
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                duration_ms=duration_ms
            )

        return result["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("groq", model, "chat_completion", duration_ms=duration_ms, error="connection_failed")
        raise HTTPException(status_code=503, detail="Cannot connect to Groq API")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("groq", model, "chat_completion", duration_ms=duration_ms, error=str(e))
        logger.error(f"Groq error: {e}")
        raise HTTPException(status_code=500, detail=f"Groq AI error: {str(e)}")


async def call_anthropic(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str
) -> str:
    """Call Anthropic Claude API"""
    start_time = time.time()
    model = "claude-sonnet-4-20250514"
    if _debug_available:
        Loggers.ai.info("Calling Anthropic API", model=model)

    try:
        api_key = settings.anthropic_api_key
        if not api_key:
            if _debug_available:
                Loggers.ai.error("Anthropic API key not configured")
            raise HTTPException(status_code=500, detail="Anthropic API key not configured")

        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": model,
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            },
            timeout=120.0
        )

        duration_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            if _debug_available:
                log_ai_request("anthropic", model, "messages", duration_ms=duration_ms,
                             error=f"HTTP {response.status_code}: {response.text[:200]}")
            raise HTTPException(status_code=500, detail=f"Anthropic error: {response.text}")

        result = response.json()
        # Extract text from content blocks
        content = result.get("content", [])
        text_parts = [block.get("text", "") for block in content if block.get("type") == "text"]

        if _debug_available:
            usage = result.get("usage", {})
            log_ai_request(
                "anthropic", model, "messages",
                prompt_tokens=usage.get("input_tokens"),
                completion_tokens=usage.get("output_tokens"),
                duration_ms=duration_ms
            )

        return "".join(text_parts)
    except httpx.ConnectError:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("anthropic", model, "messages", duration_ms=duration_ms, error="connection_failed")
        raise HTTPException(status_code=503, detail="Cannot connect to Anthropic API")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("anthropic", model, "messages", duration_ms=duration_ms, error=str(e))
        logger.error(f"Anthropic error: {e}")
        raise HTTPException(status_code=500, detail=f"Claude AI error: {str(e)}")


async def call_ollama_with_config(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str,
    url: str,
    model: str,
    *,
    format_json: bool = False,
    num_predict: int = 2000,
) -> str:
    """Call Ollama (local or Cloud). Cloud uses /api/chat + Bearer API key."""
    start_time = time.time()
    base = (url or settings.ollama_url or "http://localhost:11434").rstrip("/")
    api_key = settings.ollama_api_key
    is_cloud = bool(api_key) or "ollama.com" in base
    # Reasoning models (gpt-oss) spend tokens on `thinking`; give JSON tasks room.
    predict = max(int(num_predict or 2000), 8000 if format_json else 2000)

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if _debug_available:
        Loggers.ai.info(
            "Calling Ollama API",
            model=model,
            url=base,
            cloud=is_cloud,
            format_json=format_json,
            num_predict=predict,
        )

    try:
        if is_cloud:
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {
                    "temperature": 0.2 if format_json else 0.3,
                    "num_predict": predict,
                },
            }
            if format_json:
                body["format"] = "json"
            response = await client.post(
                f"{base}/api/chat",
                headers=headers,
                json=body,
                timeout=180.0,
            )
        else:
            body = {
                "model": model,
                "prompt": f"{system_prompt}\n\nUser: {user_prompt}\n\nAssistant:",
                "stream": False,
                "options": {
                    "temperature": 0.3 if format_json else 0.7,
                    "num_predict": predict,
                },
            }
            if format_json:
                body["format"] = "json"
            response = await client.post(
                f"{base}/api/generate",
                headers=headers,
                json=body,
                timeout=180.0,
            )

        duration_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            if _debug_available:
                log_ai_request("ollama", model, "chat" if is_cloud else "generate",
                             duration_ms=duration_ms, error=f"HTTP {response.status_code}")
            raise HTTPException(status_code=500, detail=f"Ollama error: {response.text}")

        result = response.json()

        if _debug_available:
            log_ai_request(
                "ollama", model, "chat" if is_cloud else "generate",
                prompt_tokens=result.get("prompt_eval_count"),
                completion_tokens=result.get("eval_count"),
                duration_ms=duration_ms
            )

        if is_cloud:
            message = result.get("message") or {}
            content = (message.get("content") or "").strip()
            # Some reasoning models leave content empty when truncated; never
            # treat thinking as JSON, but log for diagnosis.
            if not content and _debug_available:
                thinking = message.get("thinking") or ""
                Loggers.ai.warning(
                    "Ollama returned empty content",
                    thinking_len=len(thinking),
                    done_reason=result.get("done_reason"),
                    eval_count=result.get("eval_count"),
                )
            return content
        return result.get("response", "") or ""
    except HTTPException:
        raise
    except httpx.ConnectError:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("ollama", model, "generate", duration_ms=duration_ms, error="connection_failed")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Check OLLAMA_URL / OLLAMA_API_KEY, or run ollama serve locally."
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("ollama", model, "generate", duration_ms=duration_ms, error=str(e))
        logger.error(f"Ollama error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


def _normalize_image_base64(image_base64: str) -> str:
    """Strip data-URL prefix so Ollama / Anthropic get raw base64."""
    raw = (image_base64 or "").strip()
    if "," in raw and raw.lower().startswith("data:"):
        return raw.split(",", 1)[1]
    return raw


def _ollama_vision_model(configured_model: str | None) -> str:
    """Pick a multimodal model — text-only cloud models (e.g. gpt-oss) cannot OCR receipts."""
    explicit = (getattr(settings, "ollama_vision_model", None) or "").strip()
    if explicit:
        return explicit
    name = (configured_model or "").lower()
    vision_markers = (
        "llava", "vision", "bakllava", "moondream", "minicpm",
        "qwen2-vl", "qwen2.5-vl", "qwen2.5vl", "qwen3-vl", "gemma3", "gemma4",
    )
    if any(m in name for m in vision_markers):
        return configured_model
    return "gemma4" if settings.ollama_api_key else "llava"


async def call_ollama_vision(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str,
    image_base64: str | list[str],
    url: str,
    model: str,
) -> str:
    """Vision call for Ollama local or Cloud (Bearer auth + /api/chat when cloud)."""
    start_time = time.time()
    base = (url or settings.ollama_url or "http://localhost:11434").rstrip("/")
    api_key = settings.ollama_api_key
    is_cloud = bool(api_key) or "ollama.com" in base
    vision_model = _ollama_vision_model(model)
    if isinstance(image_base64, (list, tuple)):
        imgs = [_normalize_image_base64(i) for i in image_base64 if i]
    else:
        imgs = [_normalize_image_base64(image_base64)]
    if not imgs:
        raise HTTPException(status_code=400, detail="At least one image is required for vision OCR")

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if _debug_available:
        Loggers.ai.info(
            "Calling Ollama vision API",
            model=vision_model,
            url=base,
            cloud=is_cloud,
            image_count=len(imgs),
        )

    try:
        if is_cloud:
            # Cloud requires Bearer auth; native /api/chat supports images[]
            response = await client.post(
                f"{base}/api/chat",
                headers=headers,
                json={
                    "model": vision_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": user_prompt,
                            "images": imgs,
                        },
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 4000},
                },
                timeout=180.0,
            )
        else:
            response = await client.post(
                f"{base}/api/generate",
                headers=headers,
                json={
                    "model": vision_model,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "images": imgs,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 4000},
                },
                timeout=180.0,
            )

        duration_ms = (time.time() - start_time) * 1000
        if response.status_code == 401:
            if _debug_available:
                log_ai_request(
                    "ollama", vision_model, "vision",
                    duration_ms=duration_ms, error="HTTP 401 unauthorized",
                )
            raise HTTPException(
                status_code=502,
                detail="Ollama vision unauthorized — check OLLAMA_API_KEY on the server.",
            )
        if response.status_code != 200:
            if _debug_available:
                log_ai_request(
                    "ollama", vision_model, "vision",
                    duration_ms=duration_ms,
                    error=f"HTTP {response.status_code}",
                )
            raise HTTPException(
                status_code=500,
                detail=f"Ollama vision error: {response.text[:300]}",
            )

        result = response.json()
        if _debug_available:
            log_ai_request("ollama", vision_model, "vision", duration_ms=duration_ms)

        if is_cloud:
            message = result.get("message") or {}
            return message.get("content", "") or ""
        return result.get("response", "")
    except HTTPException:
        raise
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama for vision tasks. Check OLLAMA_URL / OLLAMA_API_KEY.",
        )
    except Exception as e:
        logger.error(f"Ollama vision error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM vision error: {str(e)}")


def _coerce_vision_images(image_base64: str | list[str]) -> list[str]:
    if isinstance(image_base64, (list, tuple)):
        imgs = [_normalize_image_base64(i) for i in image_base64 if i]
    else:
        imgs = [_normalize_image_base64(image_base64)] if image_base64 else []
    if not imgs:
        raise HTTPException(status_code=400, detail="At least one image is required for vision OCR")
    return imgs


def _guess_image_media_type(image_b64: str) -> str:
    """Best-effort MIME for Anthropic/OpenAI vision parts."""
    raw = (image_b64 or "").strip()
    # Inspect decoded magic if cheap; default jpeg (common for cookbook photos)
    try:
        import base64
        head = base64.b64decode(raw[:64] + "==", validate=False)[:12]
        if head.startswith(b"\x89PNG"):
            return "image/png"
        if head.startswith(b"GIF8"):
            return "image/gif"
        if head.startswith(b"RIFF") and b"WEBP" in head:
            return "image/webp"
    except Exception:
        pass
    return "image/jpeg"


async def call_llm_with_image(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str,
    image_base64: str | list[str],
    user_id: str = None
) -> str:
    """Call LLM with one or more images for vision tasks (OCR, receipt scanning, etc.)."""
    from dotenv import load_dotenv
    load_dotenv()

    images = _coerce_vision_images(image_base64)

    # Try using emergentintegrations with universal key first
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if emergent_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

            # Cloud: never honor per-user BYO provider overrides
            provider = settings.llm_provider
            if user_id and not settings.is_cloud:
                user_settings = await llm_settings_repository.find_by_user(user_id)
                if user_settings:
                    provider = user_settings.get("provider", provider)

            # Map provider to model for vision tasks
            provider_model_map = {
                "openai": ("openai", "gpt-5.2"),
                "anthropic": ("anthropic", "claude-sonnet-4-5-20250929"),
                "gemini": ("gemini", "gemini-3-flash-preview")
            }
            llm_provider, llm_model = provider_model_map.get(provider, ("openai", "gpt-5.2"))

            chat = LlmChat(
                api_key=emergent_key,
                session_id=f"vision-{user_id or 'anon'}-{time.time()}",
                system_message=system_prompt
            ).with_model(llm_provider, llm_model)

            image_contents = [ImageContent(image_base64=img) for img in images]
            user_message = UserMessage(
                text=user_prompt,
                image_contents=image_contents
            )

            response = await chat.send_message(user_message)
            return response
        except Exception as e:
            logger.error(f"Emergent LLM vision error: {e}")
            # Fall back to direct API calls

    # Self-host only: allow per-user provider overrides (same rule as call_llm)
    provider = settings.llm_provider
    ollama_url = settings.ollama_url
    ollama_model = settings.ollama_model

    if user_id and not settings.is_cloud:
        user_settings = await llm_settings_repository.find_by_user(user_id)
        if user_settings:
            provider = user_settings.get("provider", provider)
            ollama_url = user_settings.get("ollama_url", ollama_url)
            ollama_model = user_settings.get("ollama_model", ollama_model)

    # Route to appropriate provider with vision support
    if provider == 'ollama':
        return await call_ollama_vision(
            client, system_prompt, user_prompt, images, ollama_url, ollama_model
        )

    elif provider == 'anthropic':
        api_key = settings.anthropic_api_key
        if not api_key:
            raise HTTPException(status_code=500, detail="Anthropic API key not configured")
        content_blocks = []
        for img in images:
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": _guess_image_media_type(img),
                    "data": img,
                },
            })
        content_blocks.append({"type": "text", "text": user_prompt})
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": content_blocks}],
            },
            timeout=180.0
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Anthropic vision error: {response.text}")
        result = response.json()
        content = result.get("content", [])
        text_parts = [block.get("text", "") for block in content if block.get("type") == "text"]
        return "".join(text_parts)

    else:  # openai (default)
        from openai import AsyncOpenAI
        api_key = settings.openai_api_key
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        openai_client = AsyncOpenAI(api_key=api_key, http_client=client)
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{_guess_image_media_type(img)};base64,{img}",
                },
            }
            for img in images
        ]
        user_content.append({"type": "text", "text": user_prompt})
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=4000
        )
        return response.choices[0].message.content


# Alias for callers that pass multiple page images explicitly
call_llm_with_images = call_llm_with_image


async def call_llm(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str,
    user_id: str = None,
    usage_meta: dict = None,
    *,
    format_json: bool = False,
    max_tokens: int = 2000,
) -> str:
    """Call LLM - routes to Ollama, OpenAI, or Claude based on user config.

    If usage_meta is provided, sets usage_meta['cached']=True on cache hits so
    free-tier quota is not consumed for identical repeated prompts.
    format_json: ask providers that support it (Ollama) for JSON-only output.
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    # Try using emergentintegrations with universal key first
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    
    # Get user-specific settings if available (self-host only).
    # Cloud deployments always use server-managed Ollama Cloud / env defaults —
    # never let a user override to localhost Ollama.
    provider = settings.llm_provider
    ollama_url = settings.ollama_url
    ollama_model = settings.ollama_model
    openai_base_url = None
    openai_model = "gpt-4o"

    if user_id and not settings.is_cloud:
        user_settings = await llm_settings_repository.find_by_user(user_id)
        if user_settings:
            provider = user_settings.get("provider", provider)
            ollama_url = user_settings.get("ollama_url", ollama_url)
            ollama_model = user_settings.get("ollama_model", ollama_model)
            openai_base_url = user_settings.get("openai_base_url") or None
            openai_model = user_settings.get("openai_model") or openai_model

    # Calculate Cache Key
    key_content = f"{system_prompt}|{user_prompt}|{provider}|json={format_json}|tok={max_tokens}"
    if provider == 'ollama':
        key_content += f"|{ollama_url}|{ollama_model}"
    elif provider == 'openai':
        key_content += f"|{openai_base_url or ''}|{openai_model}"

    cache_hash = hashlib.sha256(key_content.encode()).hexdigest()

    # Check cache
    try:
        cached = await llm_cache_repository.find_by_hash(cache_hash)
        if cached and cached.get("response"):
            if usage_meta is not None:
                usage_meta["cached"] = True
            return cached["response"]
    except Exception as e:
        logger.error(f"Cache lookup failed: {e}")

    if usage_meta is not None:
        usage_meta["cached"] = False

    # Try emergentintegrations first if key available and not ollama/embedded
    if emergent_key and provider not in ['ollama', 'embedded']:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            # Map provider to model
            provider_model_map = {
                "openai": ("openai", "gpt-5.2"),
                "anthropic": ("anthropic", "claude-sonnet-4-5-20250929"),
                "gemini": ("gemini", "gemini-3-flash-preview"),
                "groq": ("groq", "llama-3.3-70b-versatile")
            }
            llm_provider, llm_model = provider_model_map.get(provider, ("openai", "gpt-5.2"))
            
            chat = LlmChat(
                api_key=emergent_key,
                session_id=f"chat-{user_id or 'anon'}-{time.time()}",
                system_message=system_prompt
            ).with_model(llm_provider, llm_model)
            
            user_message = UserMessage(text=user_prompt)
            result = await chat.send_message(user_message)
            model_used = llm_model
            
            # Store in cache
            try:
                await llm_cache_repository.cache_response(
                    hash=cache_hash,
                    response=result,
                    created_at=time.time(),
                    provider=provider,
                    model=model_used
                )
            except Exception as e:
                logger.error(f"Cache update failed: {e}")
            
            return result
        except Exception as e:
            logger.error(f"Emergent LLM error, falling back: {e}")

    # Fallback: Route to appropriate provider
    if provider == 'embedded':
        # Embedded not available in cloud - fall back to error message
        result = await call_embedded(system_prompt, user_prompt)
        model_used = "embedded"
    elif provider == 'ollama':
        result = await call_ollama_with_config(
            client,
            system_prompt,
            user_prompt,
            ollama_url,
            ollama_model,
            format_json=format_json,
            num_predict=max_tokens,
        )
        model_used = ollama_model
    elif provider == 'anthropic':
        result = await call_anthropic(client, system_prompt, user_prompt)
        model_used = "claude-sonnet-4-20250514"
    elif provider == 'groq':
        result = await call_groq(client, system_prompt, user_prompt)
        model_used = settings.groq_model
    else:  # openai / OpenAI-compatible
        result = await call_openai(
            client,
            system_prompt,
            user_prompt,
            base_url=openai_base_url,
            model=openai_model,
        )
        model_used = openai_model

    # Store in cache
    try:
        await llm_cache_repository.cache_response(
            hash=cache_hash,
            response=result,
            created_at=time.time(),
            provider=provider,
            model=model_used
        )
    except Exception as e:
        logger.error(f"Cache update failed: {e}")

    return result


def clean_llm_json(text: str) -> str:
    """Strip markdown fences and extract the first JSON object/array.

    Reasoning models (e.g. gpt-oss) often wrap or trail JSON with extra text;
    callers then fail with JSONDecodeError / empty parses.
    """
    text = (text or "").strip()
    if not text:
        return ""

    if text.startswith("```"):
        newline_index = text.find("\n")
        if newline_index != -1:
            text = text[newline_index + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Fast path: already valid JSON
    try:
        json.loads(text)
        return text
    except Exception:
        pass

    # Extract first balanced {...} or [...]
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start < 0:
            continue
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except Exception:
                        break
    return text.strip()


# Export repositories for use in routers
__all__ = [
    # Auth
    'get_current_user',
    'hash_password',
    'verify_password',
    'create_token',
    'security',

    # LLM
    'call_llm',
    'call_llm_with_image',
    'clean_llm_json',

    # Repositories
    'user_repository',
    'session_repository',
    'login_attempt_repository',
    'totp_secret_repository',
    'oauth_account_repository',
    'trusted_device_repository',
    'oauth_state_repository',
    'system_settings_repository',
    'llm_settings_repository',
    'llm_cache_repository',
    'custom_prompts_repository',
    'user_preferences_repository',
    'invite_code_repository',
    'audit_log_repository',
    'backup_repository',
    'backup_settings_repository',
    'custom_role_repository',
    'voice_settings_repository',
    'custom_ingredient_repository',
    'share_link_repository',
    'recipe_repository',
    'recipe_share_repository',
    'recipe_version_repository',
    'review_repository',
    'household_repository',
    'meal_plan_repository',
    'shopping_list_repository',
    'cook_session_repository',
    'recipe_feedback_repository',
    'ingredient_cost_repository',
    'push_subscription_repository',
    'notification_settings_repository',
    'ip_allowlist_repository',
    'ip_blocklist_repository',
    'cookbook_repository',
    'pantry_repository',
    'PANTRY_CATEGORIES',
    'STAPLE_INGREDIENTS',
    'aisle_override_repository',
    'support_ticket_repository',
    'support_ticket_message_repository',
]
