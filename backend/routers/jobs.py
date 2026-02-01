"""
Jobs Router - Background job status tracking
"""
from fastapi import APIRouter, HTTPException, Depends
from dependencies import get_current_user
from workers.jobs import get_job_status, cancel_job
from utils.security import sanitize_error_message
import logging

router = APIRouter(prefix="/jobs", tags=["Jobs"])
logger = logging.getLogger(__name__)


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get job status and result

    Returns:
    - status: "queued" | "in_progress" | "complete" | "failed" | "not_found"
    - result: Job result if complete
    - error: Error message if failed
    """
    try:
        status_info = await get_job_status(job_id)
        return status_info

    except Exception as e:
        logger.error(f"Error fetching job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {sanitize_error_message(e)}")


@router.delete("/{job_id}")
async def cancel_job_endpoint(
    job_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Cancel a queued or running job

    Returns:
    - success: True if cancelled
    """
    try:
        cancelled = await cancel_job(job_id)

        if cancelled:
            return {"success": True, "message": "Job cancelled"}
        else:
            raise HTTPException(status_code=404, detail="Job not found or already completed")

    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {sanitize_error_message(e)}")
