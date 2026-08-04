"""
Debug Router - Provides debugging utilities for Home Assistant add-on
Designed to make bug reporting easy for non-technical users
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, EmailStr
from pathlib import Path
import os
import logging
from typing import Optional
from datetime import datetime, timezone
from dependencies import get_current_user
from database.repositories.api_token_repository import api_token_repository, hash_token
from utils.security import sanitize_error_message
from services.email import (
    send_verification_email,
    send_password_reset_email,
    send_new_login_notification,
    send_password_changed_notification,
    send_2fa_enabled_notification,
    send_2fa_disabled_notification,
    send_account_locked_notification,
    send_account_deletion_email,
    send_account_deleted_notification,
    send_subscription_welcome_email,
    send_billing_issue_email,
    send_subscription_expired_email,
    send_subscription_cancelled_email,
)

# Import debug utilities
try:
    from utils.debug import debug_stats, get_debug_info, Loggers
    _debug_utils_available = True
except ImportError:
    _debug_utils_available = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])

# Log directory path
LOG_DIR = Path("/var/log/laro")

# Only allow access if running in Home Assistant add-on or debug mode
def is_debug_enabled():
    """Check if debug mode is enabled"""
    return (
        os.getenv("LARO_HA_ADDON") == "true" or
        os.getenv("DEBUG_MODE", "false").lower() == "true"
    )


@router.get("/logs")
async def list_logs(user: dict = Depends(get_current_user)):
    """List available log files"""
    if not is_debug_enabled():
        raise HTTPException(status_code=403, detail="Debug mode not enabled")

    # Require admin role
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if not LOG_DIR.exists():
        return {"logs": []}

    log_files = []
    for log_file in LOG_DIR.glob("*.log"):
        try:
            stat = log_file.stat()
            log_files.append({
                "name": log_file.name,
                "size": stat.st_size,
                "modified": stat.st_mtime
            })
        except Exception as e:
            logger.debug(f"Failed to read log file {log_file}: {e}")
            continue

    return {
        "logs": sorted(log_files, key=lambda x: x["modified"], reverse=True),
        "log_dir": str(LOG_DIR)
    }


@router.get("/logs/{log_name}")
async def get_log(
    log_name: str,
    lines: Optional[int] = Query(100, description="Number of lines to return from end of file"),
    user: dict = Depends(get_current_user)
):
    """Get contents of a specific log file"""
    if not is_debug_enabled():
        raise HTTPException(status_code=403, detail="Debug mode not enabled")

    # Require admin role
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Security: Prevent path traversal
    if ".." in log_name or "/" in log_name:
        raise HTTPException(status_code=400, detail="Invalid log name")

    log_path = LOG_DIR / log_name

    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        # Read last N lines efficiently
        with open(log_path, 'rb') as f:
            # Seek to end of file
            f.seek(0, 2)
            file_size = f.tell()

            # If file is small, just read it all
            if file_size < 10000:
                f.seek(0)
                content = f.read().decode('utf-8', errors='replace')
                log_lines = content.split('\n')
            else:
                # Read last chunk of file
                chunk_size = min(file_size, lines * 200)  # Estimate 200 bytes per line
                f.seek(max(0, file_size - chunk_size))
                content = f.read().decode('utf-8', errors='replace')
                log_lines = content.split('\n')

            # Return last N lines
            if len(log_lines) > lines:
                log_lines = log_lines[-lines:]

            return {
                "log_name": log_name,
                "lines": log_lines,
                "total_size": file_size
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log: {sanitize_error_message(e, include_details=True)}")


@router.get("/status")
async def debug_status(user: dict = Depends(get_current_user)):
    """Get debug status and configuration"""
    if not is_debug_enabled():
        raise HTTPException(status_code=403, detail="Debug mode not enabled")

    # Require admin role
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return {
        "debug_mode": os.getenv("DEBUG_MODE", "false"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "uvicorn_log_level": os.getenv("UVICORN_LOG_LEVEL", "info"),
        "celery_log_level": os.getenv("CELERY_LOG_LEVEL", "info"),
        "is_ha_addon": os.getenv("LARO_HA_ADDON") == "true",
        "log_directory": str(LOG_DIR),
        "python_version": os.sys.version,
        "environment": {
            "DATABASE_URL": "***" if os.getenv("DATABASE_URL") else None,
            "REDIS_URL": os.getenv("REDIS_URL"),
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER"),
            "REDIS_PUBSUB_ENABLED": os.getenv("REDIS_PUBSUB_ENABLED")
        }
    }


@router.get("/bug-report")
async def get_bug_report(user: dict = Depends(get_current_user)):
    """
    Generate a bug report with system info and recent errors.
    Designed to be easy for non-technical users to copy and share.
    """
    if not is_debug_enabled():
        raise HTTPException(status_code=403, detail="Debug mode not enabled")

    # Require admin role
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    from config import settings

    # Get debug info if available
    debug_info = {}
    recent_errors = []
    stats = {}

    if _debug_utils_available:
        try:
            debug_info = get_debug_info()
            stats = debug_stats.get_summary()
            recent_errors = stats.get("errors", {}).get("recent", [])
        except Exception as e:
            logger.error(f"Error getting debug info: {e}")

    # Build the bug report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "laro_version": settings.version,
        "system_info": {
            "python_version": os.sys.version.split()[0],
            "debug_mode": settings.debug_mode,
            "log_level": settings.log_level,
            "is_ha_addon": os.getenv("LARO_HA_ADDON") == "true",
            "llm_provider": settings.llm_provider,
            "redis_enabled": settings.redis_pubsub_enabled,
        },
        "performance": {
            "total_requests": stats.get("requests", {}).get("total", 0),
            "avg_response_ms": stats.get("requests", {}).get("avg_duration_ms", 0),
            "slow_requests": stats.get("requests", {}).get("slow_count", 0),
            "error_count": stats.get("requests", {}).get("error_count", 0),
        },
        "database": {
            "total_queries": stats.get("database", {}).get("total_queries", 0),
            "avg_query_ms": stats.get("database", {}).get("avg_query_ms", 0),
            "slow_queries": stats.get("database", {}).get("slow_count", 0),
        },
        "recent_errors": recent_errors[-10:] if recent_errors else [],
        "instructions": (
            "To report a bug:\n"
            "1. Copy this entire response\n"
            "2. Go to https://github.com/Domocn/Laro/issues/new\n"
            "3. Paste this in the issue description\n"
            "4. Describe what you were doing when the error occurred\n"
            "5. Include any screenshots from Portainer logs if available"
        )
    }

    return report


@router.get("/recent-errors")
async def get_recent_errors(
    limit: int = Query(20, description="Number of recent errors to return"),
    user: dict = Depends(get_current_user)
):
    """Get recent errors for quick debugging"""
    if not is_debug_enabled():
        raise HTTPException(status_code=403, detail="Debug mode not enabled")

    # Require admin role
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if not _debug_utils_available:
        return {"errors": [], "message": "Debug utilities not available"}

    try:
        stats = debug_stats.get_summary()
        errors = stats.get("errors", {}).get("recent", [])

        return {
            "total_errors": stats.get("errors", {}).get("total", 0),
            "errors": errors[-limit:] if errors else [],
            "tip": "Check Portainer logs for more detailed error information"
        }
    except Exception as e:
        logger.error(f"Error getting recent errors: {e}")
        return {"errors": [], "error": str(e)}


class TestEmailRequest(BaseModel):
    email: EmailStr


@router.post("/test-emails")
async def send_test_emails(
    request: TestEmailRequest,
    user: dict = Depends(get_current_user)
):
    """
    Send all email templates to a specified email address for testing.
    Requires admin access.
    """
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    email = request.email
    name = user.get("name", "Test User")
    results = {}

    # 1. Verification email
    try:
        results["verification"] = await send_verification_email(email, name, "test-verification-token-12345")
    except Exception as e:
        results["verification"] = f"Error: {str(e)}"

    # 2. Password reset email
    try:
        results["password_reset"] = await send_password_reset_email(email, "test-reset-token-12345")
    except Exception as e:
        results["password_reset"] = f"Error: {str(e)}"

    # 3. New login notification
    try:
        results["new_login"] = await send_new_login_notification(
            email,
            device="Chrome on Windows 10",
            ip_address="192.168.1.100",
            location="San Francisco, CA",
            timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:
        results["new_login"] = f"Error: {str(e)}"

    # 4. Password changed notification
    try:
        results["password_changed"] = await send_password_changed_notification(email)
    except Exception as e:
        results["password_changed"] = f"Error: {str(e)}"

    # 5. 2FA enabled notification
    try:
        results["2fa_enabled"] = await send_2fa_enabled_notification(email)
    except Exception as e:
        results["2fa_enabled"] = f"Error: {str(e)}"

    # 6. 2FA disabled notification
    try:
        results["2fa_disabled"] = await send_2fa_disabled_notification(email)
    except Exception as e:
        results["2fa_disabled"] = f"Error: {str(e)}"

    # 7. Account locked notification
    try:
        results["account_locked"] = await send_account_locked_notification(email, 30)
    except Exception as e:
        results["account_locked"] = f"Error: {str(e)}"

    # 8. Account deletion email
    try:
        results["account_deletion"] = await send_account_deletion_email(email, "test-deletion-token-12345")
    except Exception as e:
        results["account_deletion"] = f"Error: {str(e)}"

    # 9. Account deleted notification
    try:
        results["account_deleted"] = await send_account_deleted_notification(email)
    except Exception as e:
        results["account_deleted"] = f"Error: {str(e)}"

    # 10. Subscription welcome email
    try:
        results["subscription_welcome"] = await send_subscription_welcome_email(email, name)
    except Exception as e:
        results["subscription_welcome"] = f"Error: {str(e)}"

    # 11. Billing issue email
    try:
        results["billing_issue"] = await send_billing_issue_email(email, name)
    except Exception as e:
        results["billing_issue"] = f"Error: {str(e)}"

    # 12. Subscription expired email
    try:
        results["subscription_expired"] = await send_subscription_expired_email(email, name)
    except Exception as e:
        results["subscription_expired"] = f"Error: {str(e)}"

    # 13. Subscription cancelled email
    try:
        results["subscription_cancelled"] = await send_subscription_cancelled_email(email, name, "February 28, 2026")
    except Exception as e:
        results["subscription_cancelled"] = f"Error: {str(e)}"

    # Count successes
    success_count = sum(1 for v in results.values() if v is True)

    return {
        "message": f"Sent {success_count} of {len(results)} test emails to {email}",
        "results": results
    }
