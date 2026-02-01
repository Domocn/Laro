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
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=30)
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    start_time = time.time()
    token = credentials.credentials
    logger.info(f"Auth attempt - token type: {'API' if token.startswith('mise_') else 'JWT'}, token length: {len(token)}")

    # Check if it's an API token (starts with "mise_")
    if token.startswith("mise_"):
        if _debug_available:
            Loggers.auth.debug("Validating API token", token_prefix="mise_***")
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

    # Fallback: Legacy JWT token (for backwards compatibility)
    try:
        if _debug_available:
            Loggers.auth.debug("Validating legacy JWT token")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        logger.info(f"Legacy JWT decoded successfully - user_id: {payload.get('user_id')}")
        user = await user_repository.find_by_id(payload["user_id"])
        if not user:
            logger.warning(f"Auth failed: User not found for JWT user_id={payload['user_id']}")
            raise HTTPException(status_code=401, detail="User not found")

        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            Loggers.auth.debug("Legacy JWT validated", user_id=user["id"], duration_ms=f"{duration_ms:.2f}")
        return user
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
    user_prompt: str
) -> str:
    """Call OpenAI directly"""
    start_time = time.time()
    if _debug_available:
        Loggers.ai.info("Calling OpenAI API", model="gpt-4o")

    try:
        from openai import AsyncOpenAI

        api_key = settings.openai_api_key
        if not api_key:
            if _debug_available:
                Loggers.ai.error("OpenAI API key not configured")
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        openai_client = AsyncOpenAI(api_key=api_key, http_client=client)

        response = await openai_client.chat.completions.create(
            model="gpt-4o",
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
                "openai", "gpt-4o", "chat_completion",
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                duration_ms=duration_ms
            )

        return response.choices[0].message.content
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("openai", "gpt-4o", "chat_completion", duration_ms=duration_ms, error=str(e))
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
    model: str
) -> str:
    """Call Ollama with specific config"""
    start_time = time.time()
    if _debug_available:
        Loggers.ai.info("Calling Ollama API", model=model, url=url)

    try:
        response = await client.post(
            f"{url}/api/generate",
            json={
                "model": model,
                "prompt": f"{system_prompt}\n\nUser: {user_prompt}\n\nAssistant:",
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 2000,
                }
            },
            timeout=120.0
        )

        duration_ms = (time.time() - start_time) * 1000

        if response.status_code != 200:
            if _debug_available:
                log_ai_request("ollama", model, "generate", duration_ms=duration_ms,
                             error=f"HTTP {response.status_code}")
            raise HTTPException(status_code=500, detail=f"Ollama error: {response.text}")

        result = response.json()

        if _debug_available:
            log_ai_request(
                "ollama", model, "generate",
                prompt_tokens=result.get("prompt_eval_count"),
                completion_tokens=result.get("eval_count"),
                duration_ms=duration_ms
            )

        return result.get("response", "")
    except httpx.ConnectError:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("ollama", model, "generate", duration_ms=duration_ms, error="connection_failed")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Make sure Ollama is running locally (ollama serve)"
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        if _debug_available:
            log_ai_request("ollama", model, "generate", duration_ms=duration_ms, error=str(e))
        logger.error(f"Ollama error: {e}")
        raise HTTPException(status_code=500, detail=f"Local LLM error: {str(e)}")


async def call_llm_with_image(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str,
    image_base64: str,
    user_id: str = None
) -> str:
    """Call LLM with image for vision tasks (OCR, receipt scanning, etc.)"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Try using emergentintegrations with universal key first
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    if emergent_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
            
            # Get user-specific provider settings
            provider = settings.llm_provider
            if user_id:
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
            
            # Create image content
            image_content = ImageContent(image_base64=image_base64)
            
            # Send message with image
            user_message = UserMessage(
                text=user_prompt,
                image_contents=[image_content]
            )
            
            response = await chat.send_message(user_message)
            return response
        except Exception as e:
            logger.error(f"Emergent LLM vision error: {e}")
            # Fall back to direct API calls
    
    # Fallback: Get user-specific settings if available
    provider = settings.llm_provider
    ollama_url = settings.ollama_url
    ollama_model = settings.ollama_model

    if user_id:
        user_settings = await llm_settings_repository.find_by_user(user_id)
        if user_settings:
            provider = user_settings.get("provider", provider)
            ollama_url = user_settings.get("ollama_url", ollama_url)
            ollama_model = user_settings.get("ollama_model", ollama_model)

    # Route to appropriate provider with vision support
    if provider == 'ollama':
        # Use llava or similar vision model
        vision_model = ollama_model if 'llava' in ollama_model.lower() else 'llava'
        try:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": vision_model,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "images": [image_base64],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 2000}
                },
                timeout=120.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Ollama vision error: {response.text}")
            return response.json().get("response", "")
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Cannot connect to Ollama for vision tasks")

    elif provider == 'anthropic':
        api_key = settings.anthropic_api_key
        if not api_key:
            raise HTTPException(status_code=500, detail="Anthropic API key not configured")
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}},
                        {"type": "text", "text": user_prompt}
                    ]
                }]
            },
            timeout=120.0
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
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                    {"type": "text", "text": user_prompt}
                ]}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        return response.choices[0].message.content


async def call_llm(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_prompt: str,
    user_id: str = None
) -> str:
    """Call LLM - routes to Ollama, OpenAI, or Claude based on user config"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Try using emergentintegrations with universal key first
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    
    # Get user-specific settings if available
    provider = settings.llm_provider
    ollama_url = settings.ollama_url
    ollama_model = settings.ollama_model

    if user_id:
        user_settings = await llm_settings_repository.find_by_user(user_id)
        if user_settings:
            provider = user_settings.get("provider", provider)
            ollama_url = user_settings.get("ollama_url", ollama_url)
            ollama_model = user_settings.get("ollama_model", ollama_model)

    # Calculate Cache Key
    key_content = f"{system_prompt}|{user_prompt}|{provider}"
    if provider == 'ollama':
        key_content += f"|{ollama_url}|{ollama_model}"

    cache_hash = hashlib.sha256(key_content.encode()).hexdigest()

    # Check cache
    try:
        cached = await llm_cache_repository.find_by_hash(cache_hash)
        if cached and cached.get("response"):
            return cached["response"]
    except Exception as e:
        logger.error(f"Cache lookup failed: {e}")

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
        result = await call_ollama_with_config(client, system_prompt, user_prompt, ollama_url, ollama_model)
        model_used = ollama_model
    elif provider == 'anthropic':
        result = await call_anthropic(client, system_prompt, user_prompt)
        model_used = "claude-sonnet-4-20250514"
    elif provider == 'groq':
        result = await call_groq(client, system_prompt, user_prompt)
        model_used = settings.groq_model
    else:  # openai
        result = await call_openai(client, system_prompt, user_prompt)
        model_used = "gpt-4o"

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
    """Clean markdown code blocks from LLM response"""
    text = text.strip()
    if text.startswith("```"):
        # Find first newline to skip language identifier (e.g. ```json)
        newline_index = text.find("\n")
        if newline_index != -1:
            text = text[newline_index+1:]
        # Remove closing backticks
        if text.endswith("```"):
            text = text[:-3]
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
]
