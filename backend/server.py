"""
Laro API Server - FastAPI application with PostgreSQL and WebSocket support
"""
from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import httpx
import jwt
import os
from config import settings
from database.connection import init_db, close_db
from database.websocket_manager import ws_manager, EventType
from dependencies import (
    get_current_user,
    system_settings_repository,
    recipe_share_repository,
    recipe_repository,
    user_repository,
)
from utils.debug import (
    Loggers, log_ws_event, log_request, log_response,
    debug_stats, get_debug_info, DebugContext, setup_debug_logging
)

# Initialize debug logging early for Docker/Portainer visibility
setup_debug_logging()

# Import middleware
from middleware import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    RequestValidationMiddleware,
    CacheControlMiddleware,
    AuditLoggingMiddleware
)

# Import routers
from routers import (
    auth, households, recipes, ai, meal_plans, shopping_lists,
    homeassistant, notifications, calendar, import_data, llm_settings,
    favorites, prompts, cooking, admin, security, oauth, preferences,
    roles, trusted_devices, recipe_versions, nutrition, seed,
    recipe_import, voice_cooking, cost_tracking, reviews, sharing, jobs, debug,
    api_tokens, cookbooks, pantry, export, remote_access, mobile, friends,
    subscriptions
)

# Setup Logging for Docker/Portainer visibility
import sys

# Configure root logger to output to stdout/stderr
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

# Create a formatter with timestamp and module info
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(log_level)

# Remove any existing handlers to avoid duplicates
root_logger.handlers = []

# Add stdout handler for INFO and below
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
stdout_handler.setFormatter(log_formatter)
root_logger.addHandler(stdout_handler)

# Add stderr handler for WARNING and above
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.WARNING)
stderr_handler.setFormatter(log_formatter)
root_logger.addHandler(stderr_handler)

# Configure mise.* loggers to inherit from root
for logger_name in ['mise', 'mise.auth', 'mise.db', 'mise.api', 'mise.websocket',
                    'mise.ai', 'mise.recipes', 'mise.security', 'mise.cache', 'mise.celery']:
    mise_logger = logging.getLogger(logger_name)
    mise_logger.setLevel(log_level)

logger = logging.getLogger(__name__)

# Startup state tracking for health checks
class StartupState:
    """Track server startup state for health check responses"""
    def __init__(self):
        self.is_ready = False
        self.database_ready = False
        self.database_error: str | None = None
        self.redis_ready = False

    def mark_ready(self):
        self.is_ready = True

    def mark_database_ready(self):
        self.database_ready = True
        self.database_error = None

    def mark_database_failed(self, error: str):
        self.database_error = error

startup_state = StartupState()
logger.info(f"Logging configured with level: {settings.log_level}")
logger.info(f"Debug mode: {settings.debug_mode}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("=" * 60)
    logger.info("LARO API SERVER STARTING")
    logger.info("=" * 60)
    logger.info(f"Version: {settings.version}")
    logger.info(f"Debug Mode: {settings.debug_mode}")
    logger.info(f"Log Level: {settings.log_level}")

    app.state.http_client = httpx.AsyncClient()
    Loggers.api.info("HTTP client initialized")

    # Ensure upload directory exists
    try:
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Upload directory ready: {upload_dir.resolve()}")
    except Exception as e:
        logger.warning(f"Could not create upload directory: {e}")

    # Initialize PostgreSQL database (non-blocking for health checks)
    try:
        Loggers.db.info("Initializing PostgreSQL database connection...")
        await init_db()
        Loggers.db.info("PostgreSQL database initialized successfully")
        logger.info("PostgreSQL database initialized successfully")
        startup_state.mark_database_ready()
    except Exception as e:
        Loggers.db.error(f"Failed to initialize database: {e}", exc_info=True)
        logger.error(f"Failed to initialize database: {e}")
        startup_state.mark_database_failed(str(e))
        # Don't raise - allow server to start for health checks
        # The app will be degraded but can report its status

    # Start Zeroconf service for Home Assistant discovery (optional)
    try:
        from services.zeroconf_service import start_zeroconf_service, stop_zeroconf_service
        zeroconf_enabled = os.getenv("ZEROCONF_ENABLED", "true").lower() == "true"
        if zeroconf_enabled:
            await start_zeroconf_service(port=8001, name="Laro")
    except ImportError:
        logger.debug("Zeroconf not available - HA auto-discovery disabled")
    except Exception as e:
        logger.warning(f"Zeroconf service not started: {e}")

    # Initialize Redis Pub/Sub (if enabled)
    if settings.redis_pubsub_enabled:
        try:
            Loggers.ws.info("Initializing Redis Pub/Sub...", redis_url=settings.redis_url)
            await ws_manager.initialize_redis(settings.redis_url)
            await ws_manager.start_redis_listener()
            Loggers.ws.info("Redis Pub/Sub enabled - multi-instance mode active")
            logger.info("Redis Pub/Sub enabled - multi-instance mode active")
            startup_state.redis_ready = True
        except Exception as e:
            Loggers.ws.error(f"Failed to initialize Redis Pub/Sub: {e}", exc_info=True)
            logger.error(f"Failed to initialize Redis Pub/Sub: {e}", exc_info=True)
            logger.warning("Continuing in single-instance mode")
            # Ensure Redis is fully disabled if initialization fails
            try:
                await ws_manager.shutdown()
            except Exception as e:
                logger.debug(f"Non-critical error during Redis shutdown: {e}")
    else:
        Loggers.ws.info("Redis Pub/Sub disabled - running in single-instance mode")
        logger.info("Redis Pub/Sub disabled - running in single-instance mode")

    logger.info("=" * 60)
    logger.info("LARO API SERVER READY")
    logger.info("=" * 60)
    Loggers.api.info("Server startup complete")
    startup_state.mark_ready()

    yield

    # Shutdown
    logger.info("=" * 60)
    logger.info("LARO API SERVER SHUTTING DOWN")
    logger.info("=" * 60)

    Loggers.api.info("Closing HTTP client...")
    await app.state.http_client.aclose()

    Loggers.ws.info("Shutting down WebSocket manager...")
    await ws_manager.shutdown()

    Loggers.db.info("Closing database connections...")
    await close_db()

    # Stop Zeroconf service
    try:
        from services.zeroconf_service import stop_zeroconf_service
        await stop_zeroconf_service()
        Loggers.api.debug("Zeroconf service stopped")
    except Exception:
        pass

    logger.info("Shutdown complete")


app = FastAPI(lifespan=lifespan, title="Laro API")

# GZip compression for mobile optimization (60-70% response size reduction)
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)

# CORS - must be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.cors_origins.split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware (order matters - added in reverse order of execution)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CacheControlMiddleware)
app.add_middleware(AuditLoggingMiddleware)
app.add_middleware(RequestValidationMiddleware)

# Rate limiting (configurable via environment)
rate_limit = int(os.getenv("API_RATE_LIMIT", "120"))  # requests per minute
app.add_middleware(RateLimitMiddleware, requests_per_minute=rate_limit)

logger.info(f"Security middleware enabled with rate limit: {rate_limit} req/min")

# API v1 router - all versioned endpoints
api_v1_router = APIRouter(prefix="/api/v1")

# Include routers in v1
api_v1_router.include_router(auth.router)
api_v1_router.include_router(households.router)
api_v1_router.include_router(recipes.router)
api_v1_router.include_router(ai.router)
api_v1_router.include_router(meal_plans.router)
api_v1_router.include_router(shopping_lists.router)
api_v1_router.include_router(homeassistant.router)
api_v1_router.include_router(notifications.router)
api_v1_router.include_router(calendar.router)
api_v1_router.include_router(import_data.router)
api_v1_router.include_router(llm_settings.router)
api_v1_router.include_router(favorites.router)
api_v1_router.include_router(prompts.router)
api_v1_router.include_router(cooking.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(security.router)
api_v1_router.include_router(oauth.router)
api_v1_router.include_router(preferences.router)
api_v1_router.include_router(roles.router)
api_v1_router.include_router(trusted_devices.router)
api_v1_router.include_router(recipe_versions.router)
api_v1_router.include_router(nutrition.router)
api_v1_router.include_router(seed.router)
api_v1_router.include_router(recipe_import.router)
api_v1_router.include_router(voice_cooking.router)
api_v1_router.include_router(cost_tracking.router)
api_v1_router.include_router(reviews.router)
api_v1_router.include_router(sharing.router)
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(debug.router)
api_v1_router.include_router(api_tokens.router)
api_v1_router.include_router(cookbooks.router)
api_v1_router.include_router(pantry.router)
api_v1_router.include_router(export.router)
api_v1_router.include_router(remote_access.router)
api_v1_router.include_router(mobile.router)
api_v1_router.include_router(friends.router)
api_v1_router.include_router(subscriptions.router)

# Legacy /api router for backward compatibility (mirrors v1)
api_router = APIRouter(prefix="/api")

# Include all routers in legacy path too for backward compatibility
api_router.include_router(auth.router)
api_router.include_router(households.router)
api_router.include_router(recipes.router)
api_router.include_router(ai.router)
api_router.include_router(meal_plans.router)
api_router.include_router(shopping_lists.router)
api_router.include_router(homeassistant.router)
api_router.include_router(notifications.router)
api_router.include_router(calendar.router)
api_router.include_router(import_data.router)
api_router.include_router(llm_settings.router)
api_router.include_router(favorites.router)
api_router.include_router(prompts.router)
api_router.include_router(cooking.router)
api_router.include_router(admin.router)
api_router.include_router(security.router)
api_router.include_router(oauth.router)
api_router.include_router(preferences.router)
api_router.include_router(roles.router)
api_router.include_router(trusted_devices.router)
api_router.include_router(recipe_versions.router)
api_router.include_router(nutrition.router)
api_router.include_router(seed.router)
api_router.include_router(recipe_import.router)
api_router.include_router(voice_cooking.router)
api_router.include_router(cost_tracking.router)
api_router.include_router(reviews.router)
api_router.include_router(sharing.router)
api_router.include_router(jobs.router)
api_router.include_router(debug.router)
api_router.include_router(api_tokens.router)
api_router.include_router(cookbooks.router)
api_router.include_router(pantry.router)
api_router.include_router(export.router)
api_router.include_router(remote_access.router)
api_router.include_router(mobile.router)
api_router.include_router(friends.router)
api_router.include_router(subscriptions.router)


# Shared helper functions for endpoints available on both v1 and legacy routers
async def _get_categories():
    return {
        "categories": [
            "All", "Breakfast", "Lunch", "Dinner",
            "Dessert", "Appetizer", "Snack", "Beverage", "Other"
        ]
    }


async def _get_config():
    return {
        "llm_provider": settings.llm_provider,
        "ollama_model": settings.ollama_model if settings.llm_provider == 'ollama' else None,
        "version": settings.version,
        "api_version": "v1",
        "database": "postgresql",
        "is_cloud": settings.is_cloud,
        "features": {
            "ai_import": True,
            "ai_fridge_search": True,
            "local_llm": settings.llm_provider == 'ollama',
            "live_refresh": True,
            "cookbooks": True,
            "pantry": True,
            "recipe_matching": True
        }
    }


async def _health_check():
    Loggers.api.debug("Health check requested")

    # Determine overall health status based on startup state
    if not startup_state.is_ready:
        status = "starting"
    elif not startup_state.database_ready:
        status = "degraded"
    else:
        status = "healthy"

    try:
        redis_health = await ws_manager.get_redis_health()
    except Exception as e:
        Loggers.api.error(f"Error getting Redis health: {e}")
        logger.error(f"Error getting Redis health: {e}")
        redis_health = {
            "enabled": False,
            "connected": False,
            "mode": "single-instance",
            "error": str(e)
        }

    response = {
        "status": status,
        "app": "Laro",
        "version": settings.version,
        "api_version": "v1",
        "database": {
            "type": "postgresql",
            "ready": startup_state.database_ready,
        },
        "llm_provider": settings.llm_provider,
        "websocket_connections": ws_manager.get_connection_count(),
        "redis": redis_health,
        "debug_mode": settings.debug_mode
    }

    # Include database error if present
    if startup_state.database_error:
        response["database"]["error"] = startup_state.database_error

    return response


async def _debug_info():
    if not settings.debug_mode:
        raise HTTPException(status_code=403, detail="Debug mode is not enabled")
    Loggers.api.debug("Debug info requested")
    return get_debug_info()


async def _debug_config():
    if not settings.debug_mode:
        raise HTTPException(status_code=403, detail="Debug mode is not enabled")
    return settings.get_debug_config()


async def _get_setup_status():
    status = await system_settings_repository.get_setup_status()
    return {"setup_complete": status.get("complete", False)}


async def _complete_setup():
    from datetime import datetime, timezone
    await system_settings_repository.mark_setup_complete(
        datetime.now(timezone.utc).isoformat()
    )
    return {"message": "Setup completed"}


async def _get_shared_recipe(share_id: str):
    from datetime import datetime, timezone
    share = await recipe_share_repository.find_by_id(share_id)
    if not share:
        raise HTTPException(status_code=404, detail="Shared recipe not found")

    if share.get("expires_at"):
        expires = datetime.fromisoformat(share["expires_at"].replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(status_code=410, detail="Share link has expired")

    recipe = await recipe_repository.find_by_id(share["recipe_id"])
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


async def _get_upload(filename: str):
    from fastapi.responses import FileResponse
    from pathlib import Path

    upload_dir = Path(settings.upload_dir)
    try:
        file_path = (upload_dir / filename).resolve()
        if not file_path.is_relative_to(upload_dir.resolve()):
            raise HTTPException(status_code=404, detail="File not found")
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


async def _websocket_status(user: dict):
    user_id = user["id"]
    household_id = user.get("household_id")
    return {
        "total_connections": ws_manager.get_connection_count(),
        "user_connections": ws_manager.get_user_connection_count(user_id),
        "household_connections": ws_manager.get_household_connection_count(household_id) if household_id else 0
    }


# API v1 endpoints
@api_v1_router.get("/categories")
async def get_categories_v1():
    """Get available recipe categories"""
    return await _get_categories()


@api_v1_router.get("/config")
async def get_config_v1():
    """Get server configuration for clients"""
    return await _get_config()


@api_v1_router.get("/health")
async def health_check_v1():
    """Health check endpoint for server discovery"""
    return await _health_check()


@api_v1_router.get("/debug/info")
async def debug_info_v1():
    """Get debug information (only available when DEBUG_MODE is enabled)"""
    return await _debug_info()


@api_v1_router.get("/debug/config")
async def debug_config_v1():
    """Get debug configuration (only available when DEBUG_MODE is enabled)"""
    return await _debug_config()


@api_v1_router.get("/setup/status")
async def get_setup_status_v1():
    """Check if initial setup is complete"""
    return await _get_setup_status()


@api_v1_router.post("/setup/complete")
async def complete_setup_v1():
    """Mark initial setup as complete (called by wizard)"""
    return await _complete_setup()


@api_v1_router.get("/shared/{share_id}")
async def get_shared_recipe_v1(share_id: str):
    """Get a publicly shared recipe (no auth required)"""
    return await _get_shared_recipe(share_id)


@api_v1_router.get("/uploads/{filename}")
async def get_upload_v1(filename: str):
    """Get uploaded file"""
    return await _get_upload(filename)


@api_v1_router.get("/ws/status")
async def websocket_status_v1(user: dict = Depends(get_current_user)):
    """Get WebSocket connection status for current user"""
    return await _websocket_status(user)


# Legacy /api endpoints (backward compatibility)
@api_router.get("/categories")
async def get_categories():
    """Get available recipe categories"""
    return await _get_categories()


@api_router.get("/config")
async def get_config():
    """Get server configuration for clients"""
    return await _get_config()


@api_router.get("/health")
async def health_check():
    """Health check endpoint for server discovery"""
    return await _health_check()


@api_router.get("/debug/info")
async def debug_info():
    """Get debug information (only available when DEBUG_MODE is enabled)"""
    return await _debug_info()


@api_router.get("/debug/config")
async def debug_config():
    """Get debug configuration (only available when DEBUG_MODE is enabled)"""
    return await _debug_config()


@api_router.get("/setup/status")
async def get_setup_status():
    """Check if initial setup is complete"""
    return await _get_setup_status()


@api_router.post("/setup/complete")
async def complete_setup():
    """Mark initial setup as complete (called by wizard)"""
    return await _complete_setup()


@api_router.get("/shared/{share_id}")
async def get_shared_recipe(share_id: str):
    """Get a publicly shared recipe (no auth required)"""
    return await _get_shared_recipe(share_id)


@api_router.get("/uploads/{filename}")
async def get_upload(filename: str):
    """Get uploaded file"""
    return await _get_upload(filename)


@api_router.get("/ws/status")
async def websocket_status(user: dict = Depends(get_current_user)):
    """Get WebSocket connection status for current user"""
    return await _websocket_status(user)


# WebSocket endpoint for live refresh
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    """
    WebSocket endpoint for real-time updates.
    Client should connect with token query parameter: /ws?token=<jwt_token>
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    log_ws_event("CONNECT_ATTEMPT", data={"ip": client_ip})

    # Authenticate user from token
    user_id = None
    household_id = None

    if token:
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("user_id")
            if user_id:
                user = await user_repository.find_by_id(user_id)
                if user:
                    household_id = user.get("household_id")
                    Loggers.ws.debug("Token validated", user_id=user_id, household_id=household_id)
        except jwt.InvalidTokenError as e:
            log_ws_event("AUTH_FAILED", error=f"Invalid token: {str(e)}")
            await websocket.close(code=4001)  # Authentication failed
            return

    if not user_id:
        log_ws_event("AUTH_FAILED", error="No valid user_id in token")
        await websocket.close(code=4001)  # Authentication required
        return

    # Connect and register
    connection_id = await ws_manager.connect(websocket, user_id, household_id)
    log_ws_event("CONNECTED", connection_id=connection_id, user_id=user_id, household_id=household_id)

    try:
        # Send welcome message
        await ws_manager.send_to_connection(
            connection_id,
            EventType.DATA_SYNC,
            {"message": "Connected to Laro live refresh", "user_id": user_id}
        )
        log_ws_event("WELCOME_SENT", connection_id=connection_id, user_id=user_id)

        # Listen for messages
        while True:
            try:
                data = await websocket.receive_json()
                log_ws_event("MESSAGE_RECEIVED", connection_id=connection_id, user_id=user_id, data=data)
                await ws_manager.handle_client_message(connection_id, data)
            except Exception as e:
                log_ws_event("MESSAGE_ERROR", connection_id=connection_id, error=str(e))
                logger.error(f"WebSocket message error: {e}")
                break
    except WebSocketDisconnect:
        log_ws_event("DISCONNECTED", connection_id=connection_id, user_id=user_id)
        logger.info(f"WebSocket disconnected: {connection_id}")
    finally:
        await ws_manager.disconnect(connection_id)
        log_ws_event("CLEANUP", connection_id=connection_id, user_id=user_id)


# Include both API routers
app.include_router(api_v1_router)  # Versioned API (recommended for mobile apps)
app.include_router(api_router)     # Legacy API (backward compatibility)


# Serve frontend static files (when running as combined image)
if settings.serve_frontend:
    static_dir = Path(settings.static_files_dir)

    if static_dir.exists():
        # Serve static assets (js, css, images, etc.)
        app.mount("/static", StaticFiles(directory=str(static_dir / "static")), name="static_assets")

        # Catch-all route for SPA - must be last
        @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
        async def serve_spa(request: Request, full_path: str):
            """Serve the React SPA for all non-API routes"""
            # Don't intercept API, WebSocket, or upload routes
            if full_path.startswith(("api/", "ws", "uploads/")):
                raise HTTPException(status_code=404, detail="Not found")

            # Check if requesting a static file that exists
            file_path = static_dir / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)

            # Otherwise serve index.html for SPA routing
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)

            raise HTTPException(status_code=404, detail="Not found")

        logger.info(f"Serving frontend from {static_dir}")
    else:
        logger.warning(f"Static files directory not found: {static_dir}")
