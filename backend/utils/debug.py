"""
Debug Utilities - Comprehensive debugging and logging helpers for easy issue identification

This module provides enhanced debugging capabilities throughout the application:
- Function decorators for automatic entry/exit logging
- Context managers for debugging code blocks
- Request/response debugging
- Database query debugging
- WebSocket debugging
- Structured log formatting with context

All logs are output to stdout/stderr for Docker/Portainer visibility.

Environment Variables:
    DEBUG_MODE=true          - Enable detailed debug logging
    LOG_LEVEL=DEBUG          - Set log level (DEBUG, INFO, WARNING, ERROR)
    DEBUG_LOG_REQUESTS=true  - Log all API requests
    DEBUG_LOG_DB_QUERIES=true - Log database queries
    DEBUG_LOG_WEBSOCKETS=true - Log WebSocket events
    DEBUG_LOG_AUTH=true      - Log authentication events
    DEBUG_LOG_AI=true        - Log AI/LLM requests

Usage:
    from utils.debug import debug, debug_async, DebugContext, log_request, log_db_query

    @debug_async
    async def my_function(param1, param2):
        ...

    with DebugContext("processing_order", order_id=123):
        ...
"""

import functools
import logging
import logging.handlers
import time
import traceback
import json
import asyncio
import sys
from typing import Any, Callable, Optional, Dict, List
from datetime import datetime, timezone
from contextlib import contextmanager, asynccontextmanager
import os

# Get debug mode from environment
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
DEBUG_LEVEL = os.getenv("DEBUG_LEVEL", "INFO").upper()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_debug_logging():
    """
    Configure logging for Docker/Portainer visibility.
    All logs go to stdout/stderr with structured formatting.

    Call this early in application startup to ensure all logs are visible in Portainer.
    """
    level = getattr(logging, LOG_LEVEL, logging.INFO)

    # Custom formatter for clear, parseable logs
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Configure mise.* loggers
    for logger_name in ['mise', 'mise.debug', 'mise.auth', 'mise.db', 'mise.api',
                        'mise.websocket', 'mise.ai', 'mise.recipes', 'mise.meal_plans',
                        'mise.shopping', 'mise.admin', 'mise.security', 'mise.cache',
                        'mise.celery', 'mise.context']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)

        # Remove existing handlers
        logger.handlers = []

        # Add stdout handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(level)
        logger.addHandler(handler)

        # Prevent propagation to avoid duplicate logs
        logger.propagate = False

    # Log that debug logging is configured
    debug_logger = logging.getLogger("mise.debug")
    debug_logger.info(f"Debug logging configured: level={LOG_LEVEL}, debug_mode={DEBUG_MODE}")


# Create dedicated debug logger
debug_logger = logging.getLogger("mise.debug")


def _format_value(value: Any, max_length: int = 200) -> str:
    """Format a value for debug output, truncating if necessary."""
    try:
        if value is None:
            return "None"
        if isinstance(value, (str, int, float, bool)):
            str_val = str(value)
        elif isinstance(value, (dict, list)):
            str_val = json.dumps(value, default=str)
        else:
            str_val = repr(value)

        if len(str_val) > max_length:
            return str_val[:max_length] + "..."
        return str_val
    except Exception:
        return "<unserializable>"


def _get_caller_info() -> str:
    """Get caller file and line number for context."""
    try:
        # Go up the stack to find the actual caller
        frame = traceback.extract_stack()[-4]
        return f"{frame.filename.split('/')[-1]}:{frame.lineno}"
    except Exception:
        return "unknown"


class DebugLogger:
    """
    Enhanced logger with debug context and structured output.

    Usage:
        logger = DebugLogger("auth")
        logger.debug("User login attempt", user_id=123, email="test@example.com")
        logger.info("Login successful", user_id=123)
        logger.error("Login failed", user_id=123, reason="invalid_password")
    """

    def __init__(self, module: str):
        self.module = module
        self.logger = logging.getLogger(f"mise.{module}")
        self._context: Dict[str, Any] = {}

    def set_context(self, **kwargs):
        """Set persistent context that will be included in all log messages."""
        self._context.update(kwargs)

    def clear_context(self):
        """Clear the persistent context."""
        self._context.clear()

    def _format_message(self, message: str, **kwargs) -> str:
        """Format log message with context."""
        all_context = {**self._context, **kwargs}
        if all_context:
            context_str = " | ".join(f"{k}={_format_value(v)}" for k, v in all_context.items())
            return f"[{self.module}] {message} | {context_str}"
        return f"[{self.module}] {message}"

    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(self._format_message(message, **kwargs))

    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(self._format_message(message, **kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(self._format_message(message, **kwargs))

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message with context and optional exception info."""
        self.logger.error(self._format_message(message, **kwargs), exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = True, **kwargs):
        """Log critical message with context."""
        self.logger.critical(self._format_message(message, **kwargs), exc_info=exc_info)

    def exception(self, message: str, **kwargs):
        """Log exception with full traceback."""
        self.logger.exception(self._format_message(message, **kwargs))


# Pre-configured loggers for different modules
class Loggers:
    """Pre-configured debug loggers for different application modules."""
    auth = DebugLogger("auth")
    db = DebugLogger("db")
    api = DebugLogger("api")
    ws = DebugLogger("websocket")
    ai = DebugLogger("ai")
    recipes = DebugLogger("recipes")
    meal_plans = DebugLogger("meal_plans")
    shopping = DebugLogger("shopping")
    admin = DebugLogger("admin")
    security = DebugLogger("security")
    cache = DebugLogger("cache")
    celery = DebugLogger("celery")


def debug(func: Callable) -> Callable:
    """
    Decorator for synchronous functions that logs entry, exit, and errors.

    Usage:
        @debug
        def process_data(data):
            return data.process()
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        module = func.__module__.split('.')[-1]
        logger = DebugLogger(module)

        # Log entry
        args_str = ", ".join([_format_value(a) for a in args[:3]])  # Limit args logged
        kwargs_str = ", ".join([f"{k}={_format_value(v)}" for k, v in list(kwargs.items())[:3]])
        params = ", ".join(filter(None, [args_str, kwargs_str]))

        logger.debug(f"ENTER {func_name}({params})")

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = (time.time() - start_time) * 1000

            result_str = _format_value(result, max_length=100)
            if elapsed > 1000:
                logger.warning(f"EXIT {func_name} -> {result_str}",
                             duration_ms=f"{elapsed:.2f}", status="SLOW")
            else:
                logger.debug(f"EXIT {func_name} -> {result_str}",
                           duration_ms=f"{elapsed:.2f}")
            return result
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"ERROR {func_name}: {type(e).__name__}: {str(e)}",
                        duration_ms=f"{elapsed:.2f}", exc_info=True)
            raise

    return wrapper


def debug_async(func: Callable) -> Callable:
    """
    Decorator for async functions that logs entry, exit, and errors.

    Usage:
        @debug_async
        async def fetch_data():
            return await api.get_data()
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        func_name = func.__name__
        module = func.__module__.split('.')[-1]
        logger = DebugLogger(module)

        # Log entry
        args_str = ", ".join([_format_value(a) for a in args[:3]])
        kwargs_str = ", ".join([f"{k}={_format_value(v)}" for k, v in list(kwargs.items())[:3]])
        params = ", ".join(filter(None, [args_str, kwargs_str]))

        logger.debug(f"ENTER {func_name}({params})")

        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = (time.time() - start_time) * 1000

            result_str = _format_value(result, max_length=100)
            if elapsed > 1000:
                logger.warning(f"EXIT {func_name} -> {result_str}",
                             duration_ms=f"{elapsed:.2f}", status="SLOW")
            else:
                logger.debug(f"EXIT {func_name} -> {result_str}",
                           duration_ms=f"{elapsed:.2f}")
            return result
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"ERROR {func_name}: {type(e).__name__}: {str(e)}",
                        duration_ms=f"{elapsed:.2f}", exc_info=True)
            raise

    return wrapper


class DebugContext:
    """
    Context manager for debugging code blocks with timing and error handling.

    Usage:
        with DebugContext("processing_order", order_id=123):
            process_order()

        async with DebugContext("async_operation"):
            await async_operation()
    """

    def __init__(self, name: str, logger: Optional[DebugLogger] = None, **context):
        self.name = name
        self.logger = logger or DebugLogger("context")
        self.context = context
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"BEGIN {self.name}", **self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (time.time() - self.start_time) * 1000

        if exc_type:
            self.logger.error(
                f"FAILED {self.name}: {exc_type.__name__}: {str(exc_val)}",
                duration_ms=f"{elapsed:.2f}",
                exc_info=True,
                **self.context
            )
        else:
            if elapsed > 1000:
                self.logger.warning(
                    f"END {self.name}",
                    duration_ms=f"{elapsed:.2f}",
                    status="SLOW",
                    **self.context
                )
            else:
                self.logger.debug(
                    f"END {self.name}",
                    duration_ms=f"{elapsed:.2f}",
                    **self.context
                )

        return False  # Don't suppress exceptions

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


def log_request(method: str, path: str, user_id: Optional[str] = None,
                body: Optional[Dict] = None, query_params: Optional[Dict] = None):
    """
    Log an incoming API request with details.

    Usage:
        log_request("POST", "/api/recipes", user_id="123", body=request_data)
    """
    logger = Loggers.api
    context = {
        "method": method,
        "path": path,
    }
    if user_id:
        context["user_id"] = user_id
    if query_params:
        context["query"] = _format_value(query_params)
    if body and DEBUG_MODE:  # Only log body in debug mode for security
        context["body"] = _format_value(body)

    logger.debug("REQUEST", **context)


def log_response(method: str, path: str, status_code: int,
                 duration_ms: float, user_id: Optional[str] = None,
                 response_size: Optional[int] = None):
    """
    Log an API response with details.

    Usage:
        log_response("POST", "/api/recipes", 201, 45.5, user_id="123")
    """
    logger = Loggers.api
    context = {
        "method": method,
        "path": path,
        "status": status_code,
        "duration_ms": f"{duration_ms:.2f}",
    }
    if user_id:
        context["user_id"] = user_id
    if response_size:
        context["size_bytes"] = response_size

    if status_code >= 500:
        logger.error("RESPONSE", **context)
    elif status_code >= 400:
        logger.warning("RESPONSE", **context)
    elif duration_ms > 1000:
        logger.warning("RESPONSE (SLOW)", **context)
    else:
        logger.debug("RESPONSE", **context)


def log_db_query(operation: str, table: str, duration_ms: float,
                 rows_affected: Optional[int] = None,
                 query_params: Optional[Dict] = None,
                 error: Optional[str] = None):
    """
    Log a database query with details.

    Usage:
        log_db_query("SELECT", "users", 5.2, rows_affected=1, query_params={"id": "123"})
    """
    logger = Loggers.db
    context = {
        "operation": operation,
        "table": table,
        "duration_ms": f"{duration_ms:.2f}",
    }
    if rows_affected is not None:
        context["rows"] = rows_affected
    if query_params and DEBUG_MODE:
        context["params"] = _format_value(query_params)
    if error:
        context["error"] = error

    if error:
        logger.error("QUERY FAILED", **context)
    elif duration_ms > 100:
        logger.warning("QUERY (SLOW)", **context)
    else:
        logger.debug("QUERY", **context)


def log_ws_event(event_type: str, connection_id: Optional[str] = None,
                 user_id: Optional[str] = None, household_id: Optional[str] = None,
                 data: Optional[Dict] = None, error: Optional[str] = None):
    """
    Log a WebSocket event.

    Usage:
        log_ws_event("CONNECT", connection_id="abc123", user_id="user1")
        log_ws_event("MESSAGE", connection_id="abc123", data={"type": "ping"})
    """
    logger = Loggers.ws
    context = {"event": event_type}
    if connection_id:
        context["conn_id"] = connection_id
    if user_id:
        context["user_id"] = user_id
    if household_id:
        context["household_id"] = household_id
    if data and DEBUG_MODE:
        context["data"] = _format_value(data)
    if error:
        context["error"] = error

    if error:
        logger.error("WS_EVENT", **context)
    else:
        logger.debug("WS_EVENT", **context)


def log_auth_event(event: str, user_id: Optional[str] = None,
                   email: Optional[str] = None, ip_address: Optional[str] = None,
                   success: bool = True, reason: Optional[str] = None):
    """
    Log an authentication event.

    Usage:
        log_auth_event("LOGIN", email="user@example.com", ip_address="1.2.3.4", success=True)
        log_auth_event("LOGIN_FAILED", email="user@example.com", success=False, reason="invalid_password")
    """
    logger = Loggers.auth
    context = {"event": event, "success": success}
    if user_id:
        context["user_id"] = user_id
    if email:
        # Mask email for privacy
        if "@" in email:
            parts = email.split("@")
            masked = parts[0][:2] + "***@" + parts[1]
            context["email"] = masked
        else:
            context["email"] = "***"
    if ip_address:
        context["ip"] = ip_address
    if reason:
        context["reason"] = reason

    if success:
        logger.info("AUTH", **context)
    else:
        logger.warning("AUTH", **context)


def log_ai_request(provider: str, model: str, operation: str,
                   prompt_tokens: Optional[int] = None,
                   completion_tokens: Optional[int] = None,
                   duration_ms: Optional[float] = None,
                   error: Optional[str] = None):
    """
    Log an AI/LLM request.

    Usage:
        log_ai_request("ollama", "llama3", "recipe_extraction",
                      prompt_tokens=500, completion_tokens=200, duration_ms=1500)
    """
    logger = Loggers.ai
    context = {
        "provider": provider,
        "model": model,
        "operation": operation,
    }
    if prompt_tokens:
        context["prompt_tokens"] = prompt_tokens
    if completion_tokens:
        context["completion_tokens"] = completion_tokens
    if duration_ms:
        context["duration_ms"] = f"{duration_ms:.2f}"
    if error:
        context["error"] = error

    if error:
        logger.error("AI_REQUEST", **context)
    elif duration_ms and duration_ms > 10000:
        logger.warning("AI_REQUEST (SLOW)", **context)
    else:
        logger.info("AI_REQUEST", **context)


def log_cache_event(event: str, key: str, hit: Optional[bool] = None,
                    ttl_seconds: Optional[int] = None):
    """
    Log a cache event.

    Usage:
        log_cache_event("GET", "user:123", hit=True)
        log_cache_event("SET", "recipe:456", ttl_seconds=300)
    """
    logger = Loggers.cache
    context = {"event": event, "key": key}
    if hit is not None:
        context["hit"] = hit
    if ttl_seconds:
        context["ttl"] = ttl_seconds

    logger.debug("CACHE", **context)


def log_celery_task(task_name: str, task_id: str, status: str,
                    duration_ms: Optional[float] = None,
                    error: Optional[str] = None,
                    result: Optional[Any] = None):
    """
    Log a Celery background task.

    Usage:
        log_celery_task("import_recipe", "task-123", "STARTED")
        log_celery_task("import_recipe", "task-123", "SUCCESS", duration_ms=5000)
    """
    logger = Loggers.celery
    context = {
        "task": task_name,
        "task_id": task_id,
        "status": status,
    }
    if duration_ms:
        context["duration_ms"] = f"{duration_ms:.2f}"
    if error:
        context["error"] = error
    if result and DEBUG_MODE:
        context["result"] = _format_value(result, max_length=100)

    if status == "FAILURE" or error:
        logger.error("CELERY_TASK", **context)
    elif status in ("STARTED", "PENDING"):
        logger.debug("CELERY_TASK", **context)
    else:
        logger.info("CELERY_TASK", **context)


class RequestDebugger:
    """
    Middleware helper for debugging HTTP requests.

    Usage in FastAPI middleware:
        debugger = RequestDebugger()

        @app.middleware("http")
        async def debug_middleware(request: Request, call_next):
            request_id = debugger.start_request(request)
            response = await call_next(request)
            debugger.end_request(request_id, response)
            return response
    """

    def __init__(self):
        self._requests: Dict[str, Dict] = {}
        self._request_counter = 0

    def start_request(self, method: str, path: str,
                      user_id: Optional[str] = None,
                      headers: Optional[Dict] = None,
                      query_params: Optional[Dict] = None,
                      body: Optional[Dict] = None) -> str:
        """Start tracking a request."""
        import uuid
        request_id = str(uuid.uuid4())[:8]
        self._request_counter += 1

        self._requests[request_id] = {
            "method": method,
            "path": path,
            "user_id": user_id,
            "start_time": time.time(),
            "counter": self._request_counter,
        }

        log_request(method, path, user_id, body, query_params)
        return request_id

    def end_request(self, request_id: str, status_code: int,
                    response_size: Optional[int] = None):
        """End tracking a request and log the result."""
        if request_id not in self._requests:
            return

        req = self._requests.pop(request_id)
        duration_ms = (time.time() - req["start_time"]) * 1000

        log_response(
            req["method"],
            req["path"],
            status_code,
            duration_ms,
            req.get("user_id"),
            response_size
        )


class DebugStats:
    """
    Collect and report debug statistics.

    Usage:
        stats = DebugStats()
        stats.record_request("/api/recipes", 200, 45.5)
        stats.record_db_query("SELECT", "users", 5.2)
        print(stats.get_summary())
    """

    def __init__(self):
        self.requests: List[Dict] = []
        self.db_queries: List[Dict] = []
        self.errors: List[Dict] = []
        self.ws_events: List[Dict] = []
        self._start_time = time.time()

    def record_request(self, path: str, status: int, duration_ms: float):
        """Record an HTTP request."""
        self.requests.append({
            "path": path,
            "status": status,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        # Keep only last 1000
        if len(self.requests) > 1000:
            self.requests = self.requests[-1000:]

    def record_db_query(self, operation: str, table: str, duration_ms: float):
        """Record a database query."""
        self.db_queries.append({
            "operation": operation,
            "table": table,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        if len(self.db_queries) > 1000:
            self.db_queries = self.db_queries[-1000:]

    def record_error(self, error_type: str, message: str,
                     location: Optional[str] = None):
        """Record an error."""
        self.errors.append({
            "type": error_type,
            "message": message,
            "location": location,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        if len(self.errors) > 500:
            self.errors = self.errors[-500:]

    def get_summary(self) -> Dict:
        """Get a summary of debug statistics."""
        uptime = time.time() - self._start_time

        # Calculate request stats
        total_requests = len(self.requests)
        if total_requests > 0:
            avg_duration = sum(r["duration_ms"] for r in self.requests) / total_requests
            slow_requests = sum(1 for r in self.requests if r["duration_ms"] > 1000)
            error_requests = sum(1 for r in self.requests if r["status"] >= 400)
        else:
            avg_duration = 0
            slow_requests = 0
            error_requests = 0

        # Calculate DB stats
        total_queries = len(self.db_queries)
        if total_queries > 0:
            avg_query_time = sum(q["duration_ms"] for q in self.db_queries) / total_queries
            slow_queries = sum(1 for q in self.db_queries if q["duration_ms"] > 100)
        else:
            avg_query_time = 0
            slow_queries = 0

        return {
            "uptime_seconds": uptime,
            "debug_mode": DEBUG_MODE,
            "requests": {
                "total": total_requests,
                "avg_duration_ms": round(avg_duration, 2),
                "slow_count": slow_requests,
                "error_count": error_requests,
            },
            "database": {
                "total_queries": total_queries,
                "avg_query_ms": round(avg_query_time, 2),
                "slow_count": slow_queries,
            },
            "errors": {
                "total": len(self.errors),
                "recent": self.errors[-5:] if self.errors else []
            }
        }

    def clear(self):
        """Clear all statistics."""
        self.requests.clear()
        self.db_queries.clear()
        self.errors.clear()
        self.ws_events.clear()


# Global debug stats instance
debug_stats = DebugStats()


def get_debug_info() -> Dict:
    """
    Get comprehensive debug information about the application state.

    Returns a dictionary with:
    - Environment info
    - Debug settings
    - Statistics summary
    """
    import platform
    import sys

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "debug_mode": DEBUG_MODE,
            "debug_level": DEBUG_LEVEL,
        },
        "stats": debug_stats.get_summary()
    }


# Convenience function to quickly enable verbose debugging
def enable_verbose_debug():
    """Enable verbose debug logging for all modules."""
    logging.getLogger("mise").setLevel(logging.DEBUG)
    debug_logger.info("Verbose debug logging enabled")


def disable_verbose_debug():
    """Disable verbose debug logging."""
    logging.getLogger("mise").setLevel(logging.INFO)
    debug_logger.info("Verbose debug logging disabled")
