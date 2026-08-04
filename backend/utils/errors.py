"""
Standardized Error Responses - Consistent error handling across the API
"""
from fastapi import HTTPException, status
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class APIError(HTTPException):
    """
    Base API error with standardized format.

    All API errors should use this format for consistency:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "details": {...}  # Optional additional info
        }
    }
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.details = details or {}

        super().__init__(
            status_code=status_code,
            detail={
                "error": {
                    "code": code,
                    "message": message,
                    "details": self.details
                }
            }
        )


# ============================================================================
# Authentication & Authorization Errors (401, 403)
# ============================================================================

class UnauthorizedError(APIError):
    """User is not authenticated"""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message=message
        )


class InvalidCredentialsError(APIError):
    """Invalid username or password"""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message=message
        )


class InvalidTokenError(APIError):
    """JWT token is invalid or expired"""

    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN",
            message=message
        )


class ForbiddenError(APIError):
    """User doesn't have permission"""

    def __init__(self, message: str = "You don't have permission to access this resource"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=message
        )


class AccountLockedError(APIError):
    """Account is locked due to failed login attempts"""

    def __init__(self, minutes_remaining: int):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="ACCOUNT_LOCKED",
            message=f"Account locked due to too many failed login attempts. Try again in {minutes_remaining} minutes.",
            details={"unlock_in_minutes": minutes_remaining}
        )


# ============================================================================
# Resource Errors (404, 409, 410)
# ============================================================================

class NotFoundError(APIError):
    """Resource not found"""

    def __init__(self, resource: str, identifier: Optional[str] = None):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"

        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=message,
            details={"resource": resource, "identifier": identifier}
        )


class AlreadyExistsError(APIError):
    """Resource already exists"""

    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="ALREADY_EXISTS",
            message=f"{resource} with {field} '{value}' already exists",
            details={"resource": resource, "field": field, "value": value}
        )


class ResourceExpiredError(APIError):
    """Resource has expired"""

    def __init__(self, resource: str):
        super().__init__(
            status_code=status.HTTP_410_GONE,
            code="RESOURCE_EXPIRED",
            message=f"{resource} has expired",
            details={"resource": resource}
        )


# ============================================================================
# Validation Errors (400, 422)
# ============================================================================

class ValidationError(APIError):
    """Input validation failed"""

    def __init__(self, field: str, message: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=f"Validation failed: {message}",
            details={"field": field, "error": message}
        )


class InvalidInputError(APIError):
    """Invalid input format"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_INPUT",
            message=message,
            details=details
        )


class MissingFieldError(APIError):
    """Required field is missing"""

    def __init__(self, field: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MISSING_FIELD",
            message=f"Required field '{field}' is missing",
            details={"field": field}
        )


# ============================================================================
# Rate Limiting (429)
# ============================================================================

class RateLimitError(APIError):
    """Rate limit exceeded"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            details={"retry_after_seconds": retry_after}
        )


# ============================================================================
# Server Errors (500, 503)
# ============================================================================

class InternalServerError(APIError):
    """Internal server error"""

    def __init__(self, message: str = "An internal server error occurred"):
        # Log the error but don't expose details to client
        logger.error(f"Internal server error: {message}")

        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="An internal server error occurred. Please try again later."
        )


class ServiceUnavailableError(APIError):
    """Service temporarily unavailable"""

    def __init__(self, service: str):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SERVICE_UNAVAILABLE",
            message=f"{service} is temporarily unavailable. Please try again later.",
            details={"service": service}
        )


class DatabaseError(APIError):
    """Database operation failed"""

    def __init__(self, operation: str):
        logger.error(f"Database error during {operation}")

        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="DATABASE_ERROR",
            message="Database operation failed. Please try again later.",
            details={"operation": operation}
        )


# ============================================================================
# Business Logic Errors (400, 403)
# ============================================================================

class InsufficientPermissionsError(APIError):
    """User doesn't have required permissions"""

    def __init__(self, required_permission: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_PERMISSIONS",
            message=f"You need '{required_permission}' permission to perform this action",
            details={"required_permission": required_permission}
        )


class QuotaExceededError(APIError):
    """User exceeded their quota"""

    def __init__(self, resource: str, limit: int):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="QUOTA_EXCEEDED",
            message=f"You have exceeded your {resource} quota of {limit}",
            details={"resource": resource, "limit": limit}
        )


class InvalidOperationError(APIError):
    """Operation is not allowed in current state"""

    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_OPERATION",
            message=message
        )


# ============================================================================
# Helper Functions
# ============================================================================

def handle_database_error(error: Exception, operation: str):
    """
    Handle database errors with appropriate logging and response.

    Args:
        error: The caught exception
        operation: Description of the operation that failed

    Raises:
        DatabaseError: With sanitized error message
    """
    logger.error(f"Database error during {operation}: {str(error)}", exc_info=True)
    raise DatabaseError(operation)


def handle_unexpected_error(error: Exception, context: str):
    """
    Handle unexpected errors with logging.

    Args:
        error: The caught exception
        context: Description of where the error occurred

    Raises:
        InternalServerError: With generic message (hides implementation details)
    """
    logger.error(f"Unexpected error in {context}: {str(error)}", exc_info=True)
    raise InternalServerError(f"Error in {context}")
