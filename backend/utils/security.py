"""
Security Utilities - Input validation, sanitization, and security helpers
"""
import re
import html
import logging
from typing import Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Maximum lengths for common fields
MAX_EMAIL_LENGTH = 255
MAX_NAME_LENGTH = 255
MAX_TITLE_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 5000
MAX_URL_LENGTH = 2048

# Allowed characters for usernames (alphanumeric, dash, underscore, dot)
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')

# Email validation (RFC 5322 simplified)
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
    r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
)

# URL validation (http/https only)
URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$',
    re.IGNORECASE
)


def validate_email(email: str) -> tuple[bool, Optional[str]]:
    """
    Validate email address format and length.

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"

    if len(email) > MAX_EMAIL_LENGTH:
        return False, f"Email must be less than {MAX_EMAIL_LENGTH} characters"

    if not EMAIL_PATTERN.match(email):
        return False, "Invalid email format"

    return True, None


def validate_name(name: str, field_name: str = "Name") -> tuple[bool, Optional[str]]:
    """
    Validate name fields (user name, recipe title, etc).

    Args:
        name: Name to validate
        field_name: Human-readable field name for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, f"{field_name} is required"

    if len(name) > MAX_NAME_LENGTH:
        return False, f"{field_name} must be less than {MAX_NAME_LENGTH} characters"

    # Check for null bytes (security issue)
    if '\x00' in name:
        return False, f"{field_name} contains invalid characters"

    return True, None


def validate_url(url: str, required: bool = False) -> tuple[bool, Optional[str]]:
    """
    Validate URL format and length.

    Args:
        url: URL to validate
        required: Whether URL is required (non-empty)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        if required:
            return False, "URL is required"
        return True, None

    if len(url) > MAX_URL_LENGTH:
        return False, f"URL must be less than {MAX_URL_LENGTH} characters"

    if not URL_PATTERN.match(url):
        return False, "Invalid URL format (must be http:// or https://)"

    return True, None


def is_safe_external_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Check if URL is safe for server-side requests (SSRF prevention).
    Blocks requests to internal/private IP ranges.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_safe, error_message)
    """
    from urllib.parse import urlparse
    import ipaddress
    import socket

    if not url:
        return False, "URL is required"

    try:
        parsed = urlparse(url)

        # Must be http or https
        if parsed.scheme not in ('http', 'https'):
            return False, "URL must use http or https"

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: no hostname"

        # Block localhost variants
        if hostname.lower() in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
            return False, "URLs to localhost are not allowed"

        # Try to resolve hostname and check IP
        try:
            ip = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip)

            # Block private/reserved IP ranges
            if ip_obj.is_private:
                return False, "URLs to private IP addresses are not allowed"
            if ip_obj.is_reserved:
                return False, "URLs to reserved IP addresses are not allowed"
            if ip_obj.is_loopback:
                return False, "URLs to loopback addresses are not allowed"
            if ip_obj.is_link_local:
                return False, "URLs to link-local addresses are not allowed"

        except socket.gaierror:
            # Could not resolve - might be fine (DNS issues), let it through
            # The actual request will fail if hostname is invalid
            pass

        return True, None

    except Exception as e:
        logger.warning(f"URL validation error: {e}")
        return False, "Invalid URL format"


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML input by escaping special characters.
    Prevents XSS attacks in user-generated content.

    Args:
        text: Text that may contain HTML

    Returns:
        HTML-escaped text safe for display
    """
    if not text:
        return ""

    return html.escape(text, quote=True)


def sanitize_sql_like_pattern(pattern: str) -> str:
    """
    Escape special characters in SQL LIKE patterns.
    Prevents SQL injection in LIKE queries.

    Args:
        pattern: User input for LIKE pattern

    Returns:
        Escaped pattern safe for SQL LIKE
    """
    if not pattern:
        return ""

    # Escape special LIKE characters
    pattern = pattern.replace('\\', '\\\\')
    pattern = pattern.replace('%', '\\%')
    pattern = pattern.replace('_', '\\_')

    return pattern


def validate_pagination(
    limit: Optional[int],
    offset: Optional[int],
    max_limit: int = 100
) -> tuple[int, int, Optional[str]]:
    """
    Validate and normalize pagination parameters.

    Args:
        limit: Maximum number of records to return
        offset: Number of records to skip
        max_limit: Maximum allowed limit

    Returns:
        Tuple of (normalized_limit, normalized_offset, error_message)
    """
    # Default values
    if limit is None:
        limit = 50
    if offset is None:
        offset = 0

    # Validate limit
    if not isinstance(limit, int) or limit < 1:
        return 50, 0, "Limit must be a positive integer"

    if limit > max_limit:
        return 50, 0, f"Limit must not exceed {max_limit}"

    # Validate offset
    if not isinstance(offset, int) or offset < 0:
        return limit, 0, "Offset must be a non-negative integer"

    return limit, offset, None


def validate_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    max_days: int = 365
) -> tuple[bool, Optional[str]]:
    """
    Validate date range for queries.

    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        max_days: Maximum allowed range in days

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not start_date or not end_date:
        return True, None

    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return False, "Invalid date format (use ISO 8601)"

    # Check logical order
    if start > end:
        return False, "Start date must be before end date"

    # Check range
    delta = end - start
    if delta.days > max_days:
        return False, f"Date range must not exceed {max_days} days"

    return True, None


def is_safe_redirect_url(url: str, allowed_hosts: List[str]) -> bool:
    """
    Check if redirect URL is safe (prevents open redirect vulnerabilities).

    Args:
        url: URL to check
        allowed_hosts: List of allowed host names

    Returns:
        True if URL is safe for redirect
    """
    if not url:
        return False

    # Reject absolute URLs to external sites
    if url.startswith('http://') or url.startswith('https://'):
        # Extract host from URL
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            return parsed.netloc in allowed_hosts
        except Exception as e:
            logger.warning(f"Failed to parse redirect URL: {e}")
            return False

    # Relative URLs are OK
    if url.startswith('/'):
        return True

    # Reject protocol-relative URLs
    if url.startswith('//'):
        return False

    return False


def validate_rating(rating: int) -> tuple[bool, Optional[str]]:
    """
    Validate recipe rating value.

    Args:
        rating: Rating value (should be 1-5)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(rating, int):
        return False, "Rating must be an integer"

    if rating < 1 or rating > 5:
        return False, "Rating must be between 1 and 5"

    return True, None


def validate_servings(servings: int) -> tuple[bool, Optional[str]]:
    """
    Validate recipe servings value.

    Args:
        servings: Number of servings

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(servings, int):
        return False, "Servings must be an integer"

    if servings < 1 or servings > 1000:
        return False, "Servings must be between 1 and 1000"

    return True, None


def validate_time(minutes: int, field_name: str = "Time") -> tuple[bool, Optional[str]]:
    """
    Validate time values (prep time, cook time).

    Args:
        minutes: Time in minutes
        field_name: Human-readable field name

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(minutes, int):
        return False, f"{field_name} must be an integer"

    if minutes < 0 or minutes > 10080:  # 1 week
        return False, f"{field_name} must be between 0 and 10080 minutes (1 week)"

    return True, None


def validate_array_length(
    arr: List,
    min_length: int = 0,
    max_length: int = 1000,
    field_name: str = "Array"
) -> tuple[bool, Optional[str]]:
    """
    Validate array length to prevent DoS attacks.

    Args:
        arr: Array to validate
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        field_name: Human-readable field name

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(arr, list):
        return False, f"{field_name} must be an array"

    if len(arr) < min_length:
        return False, f"{field_name} must have at least {min_length} items"

    if len(arr) > max_length:
        return False, f"{field_name} must not exceed {max_length} items"

    return True, None


class RateLimiter:
    """
    Simple in-memory rate limiter for API endpoints.
    For production, consider using Redis-based rate limiting.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # key: (ip, endpoint) -> List[datetime]

    def is_allowed(self, key: str) -> tuple[bool, Optional[str]]:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Unique key for rate limiting (e.g., f"{ip}:{endpoint}")

        Returns:
            Tuple of (is_allowed, error_message)
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Initialize or clean old requests
        if key not in self.requests:
            self.requests[key] = []

        # Remove old requests outside window
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > cutoff
        ]

        # Check limit
        if len(self.requests[key]) >= self.max_requests:
            return False, f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds} seconds."

        # Record this request
        self.requests[key].append(now)
        return True, None

    def cleanup_old_entries(self):
        """Remove entries that are completely outside the window"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.window_seconds * 2)

        keys_to_remove = []
        for key, timestamps in self.requests.items():
            if not timestamps or all(t < cutoff for t in timestamps):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.requests[key]


# Global rate limiters for common operations
login_rate_limiter = RateLimiter(max_requests=5, window_seconds=300)  # 5 attempts per 5 minutes
api_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)  # 100 requests per minute


# Image magic bytes for content validation
IMAGE_SIGNATURES = {
    b'\xff\xd8\xff': 'jpg',      # JPEG
    b'\x89PNG\r\n\x1a\n': 'png', # PNG
    b'GIF87a': 'gif',            # GIF87a
    b'GIF89a': 'gif',            # GIF89a
    b'RIFF': 'webp',             # WebP (starts with RIFF, contains WEBP)
}


def validate_image_content(content: bytes, claimed_extension: str) -> tuple[bool, Optional[str]]:
    """
    Validate image content by checking magic bytes.
    Prevents uploading malicious files with fake extensions.

    Args:
        content: File content bytes
        claimed_extension: The file extension claimed by the upload

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not content:
        return False, "Empty file"

    if len(content) < 8:
        return False, "File too small to be a valid image"

    # Check magic bytes
    detected_type = None

    for signature, file_type in IMAGE_SIGNATURES.items():
        if content.startswith(signature):
            detected_type = file_type
            break

    # Special handling for WebP (RIFF....WEBP)
    if content[:4] == b'RIFF' and len(content) >= 12 and content[8:12] == b'WEBP':
        detected_type = 'webp'

    if not detected_type:
        return False, "File content does not match any supported image format"

    # Normalize extensions for comparison
    claimed = claimed_extension.lower().strip('.')
    if claimed == 'jpeg':
        claimed = 'jpg'

    # Verify claimed extension matches detected type
    if detected_type != claimed:
        logger.warning(f"Image content mismatch: claimed {claimed}, detected {detected_type}")
        return False, f"File extension ({claimed}) does not match content ({detected_type})"

    return True, None


def sanitize_error_message(error: Exception, include_details: bool = False) -> str:
    """
    Sanitize error messages for client responses.
    Prevents leaking internal details in production.

    Args:
        error: The exception that occurred
        include_details: Whether to include full error details (dev mode only)

    Returns:
        Safe error message string
    """
    import os

    # In debug mode, return full error
    if include_details or os.getenv("DEBUG_MODE", "false").lower() == "true":
        return str(error)

    # Map common errors to safe messages
    error_type = type(error).__name__

    safe_messages = {
        "ConnectionError": "Service temporarily unavailable",
        "TimeoutError": "Request timed out",
        "ValueError": "Invalid input provided",
        "KeyError": "Missing required field",
        "TypeError": "Invalid data format",
        "PermissionError": "Access denied",
        "FileNotFoundError": "Resource not found",
        "JSONDecodeError": "Invalid data format",
    }

    return safe_messages.get(error_type, "An error occurred")
