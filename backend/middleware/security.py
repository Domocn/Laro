"""
Security Middleware - Centralized security headers and validation
"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)

# Import debug utilities
try:
    from utils.debug import Loggers, log_request, log_response, debug_stats
    _debug_available = True
except ImportError:
    _debug_available = False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Implements OWASP security header recommendations:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: HSTS
    - Content-Security-Policy: CSP
    - Referrer-Policy: strict-origin-when-cross-origin
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Force HTTPS (only in production)
        if not request.url.hostname in ["localhost", "127.0.0.1"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy
        # Note: Adjust based on your frontend needs
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Global rate limiting middleware.

    Applies rate limits to all API endpoints to prevent abuse.
    More sophisticated than endpoint-specific rate limiting.
    """

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_log = {}  # ip -> list of timestamps

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/api/health", "/health"]:
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Import here to avoid circular dependency
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=1)

        # Clean old requests
        if client_ip in self.request_log:
            self.request_log[client_ip] = [
                ts for ts in self.request_log[client_ip]
                if ts > cutoff
            ]
        else:
            self.request_log[client_ip] = []

        # Check limit
        if len(self.request_log[client_ip]) >= self.requests_per_minute:
            if _debug_available:
                Loggers.security.warning(
                    "Rate limit exceeded",
                    ip=client_ip,
                    path=request.url.path,
                    requests_count=len(self.request_log[client_ip]),
                    limit=self.requests_per_minute
                )
            logger.warning(
                f"Rate limit exceeded for IP {client_ip} on {request.url.path}"
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute."
            )

        # Record this request
        self.request_log[client_ip].append(now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = self.requests_per_minute - len(self.request_log[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int((now + timedelta(minutes=1)).timestamp()))

        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Validate all incoming requests for common attack patterns.

    Checks for:
    - Excessively large requests (DoS protection)
    - Suspicious user agents
    - Invalid content types
    """

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"

        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_CONTENT_LENGTH:
            if _debug_available:
                Loggers.security.warning(
                    "Request rejected: content too large",
                    ip=client_ip,
                    content_length=content_length,
                    max_length=self.MAX_CONTENT_LENGTH
                )
            logger.warning(
                f"Request rejected: Content-Length {content_length} exceeds maximum"
            )
            raise HTTPException(
                status_code=413,
                detail=f"Request too large. Maximum size is {self.MAX_CONTENT_LENGTH} bytes."
            )

        # Check for null bytes in path (security issue)
        if "\x00" in str(request.url):
            if _debug_available:
                Loggers.security.warning(
                    "Request rejected: null byte in URL",
                    ip=client_ip,
                    path=request.url.path
                )
            logger.warning(f"Request rejected: Null byte in URL from {client_ip}")
            raise HTTPException(
                status_code=400,
                detail="Invalid request"
            )

        # Block suspicious user agents (very basic bot detection)
        user_agent = request.headers.get("user-agent", "").lower()
        suspicious_patterns = ["sqlmap", "nikto", "nmap", "masscan", "acunetix"]
        if any(pattern in user_agent for pattern in suspicious_patterns):
            if _debug_available:
                Loggers.security.warning(
                    "Suspicious user agent blocked",
                    ip=client_ip,
                    user_agent=user_agent[:100]
                )
            logger.warning(
                f"Suspicious user agent blocked: {user_agent} from {client_ip}"
            )
            raise HTTPException(
                status_code=403,
                detail="Forbidden"
            )

        return await call_next(request)


class CacheControlMiddleware(BaseHTTPMiddleware):
    """
    Add cache control headers to GET responses for improved performance.

    Implements intelligent caching:
    - Static data (categories, config): long cache
    - Dynamic data (recipes, meal plans): short cache with ETag
    - Mutations (POST, PUT, DELETE): no cache
    """

    # Paths and their cache durations in seconds
    CACHE_RULES = {
        "/api/categories": 3600,      # 1 hour - rarely changes
        "/api/config": 3600,          # 1 hour - server config
        "/api/health": 0,             # No cache - always fresh
        "/api/v1/categories": 3600,
        "/api/v1/config": 3600,
        "/api/v1/health": 0,
    }

    # Default cache duration for GET requests (5 minutes)
    DEFAULT_CACHE_DURATION = 300

    # Paths that should never be cached
    NO_CACHE_PATHS = [
        "/api/auth",
        "/api/admin",
        "/api/security",
        "/api/v1/auth",
        "/api/v1/admin",
        "/api/v1/security",
        "/ws",
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        path = request.url.path

        # Only cache GET requests
        if request.method != "GET":
            response.headers["Cache-Control"] = "no-store"
            return response

        # Check if path should never be cached
        for no_cache_path in self.NO_CACHE_PATHS:
            if path.startswith(no_cache_path):
                response.headers["Cache-Control"] = "no-store"
                return response

        # Check for specific cache rules
        cache_duration = self.CACHE_RULES.get(path)

        if cache_duration is None:
            # Default caching for API GET requests
            if path.startswith("/api/"):
                cache_duration = self.DEFAULT_CACHE_DURATION
            else:
                # Non-API paths (static files) - let nginx handle
                return response

        if cache_duration == 0:
            response.headers["Cache-Control"] = "no-store"
        else:
            # Private cache with revalidation
            response.headers["Cache-Control"] = f"private, max-age={cache_duration}, stale-while-revalidate=60"
            response.headers["Vary"] = "Authorization"

        return response


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all API requests for audit trail with user tracking.

    Logs:
    - Timestamp
    - User ID (from JWT token)
    - IP address
    - HTTP method
    - Path
    - Status code
    - Response time
    - User agent
    """

    def _extract_user_id(self, request: Request) -> str:
        """Extract user ID from JWT token in Authorization header."""
        try:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                # Decode without verification just to get user ID for logging
                # (actual verification happens in the endpoint)
                import jwt
                from config import settings
                try:
                    payload = jwt.decode(
                        token,
                        settings.jwt_secret,
                        algorithms=[settings.jwt_algorithm],
                        options={"verify_exp": False}  # Don't fail on expired for logging
                    )
                    return payload.get("sub", "unknown")
                except jwt.InvalidTokenError:
                    return "invalid_token"
            return "anonymous"
        except Exception:
            return "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from datetime import datetime, timezone

        # Start timer
        start_time = time.time()

        # Get request details
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params) if request.query_params else None
        user_agent = request.headers.get("user-agent", "unknown")[:100]

        # Extract user ID from token
        user_id = self._extract_user_id(request)

        # Log incoming request (debug mode only for detailed logging)
        if _debug_available and path not in ["/api/health", "/health"]:
            log_request(method, path, query_params=query_params)

        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time = (time.time() - start_time) * 1000  # milliseconds

        # Log the request with user ID (only log non-health-check endpoints)
        if path not in ["/api/health", "/health"]:
            log_level = logging.WARNING if response.status_code >= 400 else logging.INFO

            # Short user ID for log readability (first 8 chars)
            short_user_id = user_id[:8] if user_id not in ["anonymous", "unknown", "invalid_token"] else user_id

            logger.log(
                log_level,
                f"{method} {path} - {response.status_code} - {response_time:.2f}ms - user:{short_user_id} - ip:{client_ip}"
            )

            # Enhanced debug logging with full details
            if _debug_available:
                log_response(method, path, response.status_code, response_time)
                debug_stats.record_request(path, response.status_code, response_time)

            # Log errors with more detail for debugging
            if response.status_code >= 400:
                logger.warning(
                    f"API Error: user_id={user_id} ip={client_ip} method={method} path={path} "
                    f"status={response.status_code} time={response_time:.2f}ms ua={user_agent}"
                )

        # Add response headers for debugging
        response.headers["X-Response-Time"] = f"{response_time:.2f}ms"
        response.headers["X-Request-ID"] = f"{user_id[:8]}-{int(start_time * 1000) % 100000}"

        return response
