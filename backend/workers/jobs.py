"""
Job Management Utilities
Helper functions for enqueueing and tracking Celery background jobs
"""
import logging
from typing import Optional
from celery.result import AsyncResult
from workers.celery_app import app

logger = logging.getLogger(__name__)


async def enqueue_job(
    function_name: str,
    *args,
    job_id: Optional[str] = None,
    **kwargs
):
    """
    Enqueue a background job using Celery

    Args:
        function_name: Name of the task function (e.g., 'import_recipe_from_url_task')
        *args: Positional arguments for the task
        job_id: Optional custom job ID (default: auto-generated)
        **kwargs: Keyword arguments for the task

    Returns:
        AsyncResult object with task_id for tracking

    Example:
        result = await enqueue_job(
            'import_recipe_from_url_task',
            'https://example.com/recipe',
            'user_123',
            household_id='house_abc'
        )
        print(f"Job ID: {result.id}")
    """
    # Get the task by name
    task = app.tasks.get(function_name)

    if not task:
        raise ValueError(f"Task '{function_name}' not found")

    # Apply task asynchronously
    if job_id:
        result = task.apply_async(
            args=args,
            kwargs=kwargs,
            task_id=job_id
        )
    else:
        result = task.apply_async(
            args=args,
            kwargs=kwargs
        )

    logger.info(f"Enqueued job: {function_name} (ID: {result.id})")

    # Return a simple object with job_id attribute for compatibility
    class JobResult:
        def __init__(self, task_id):
            self.job_id = task_id
            self.id = task_id

    return JobResult(result.id)


async def get_job_status(job_id: str) -> dict:
    """
    Get job status and result from Celery

    Args:
        job_id: The job ID returned from enqueue_job

    Returns:
        dict with status info:
        {
            "job_id": "abc123",
            "status": "queued" | "in_progress" | "complete" | "failed" | "not_found",
            "result": {...} if complete else None,
            "error": "..." if failed else None
        }
    """
    try:
        result = AsyncResult(job_id, app=app)

        # Check task state
        state = result.state

        if state == 'PENDING':
            # Task is queued or doesn't exist
            return {
                "job_id": job_id,
                "status": "queued",
                "result": None,
                "error": None
            }
        elif state == 'STARTED' or state == 'RETRY':
            return {
                "job_id": job_id,
                "status": "in_progress",
                "result": None,
                "error": None
            }
        elif state == 'SUCCESS':
            task_result = result.result
            return {
                "job_id": job_id,
                "status": "complete",
                "result": task_result,
                "error": None
            }
        elif state == 'FAILURE':
            error = str(result.result) if result.result else "Task failed"
            return {
                "job_id": job_id,
                "status": "failed",
                "result": None,
                "error": error
            }
        elif state == 'REVOKED':
            return {
                "job_id": job_id,
                "status": "cancelled",
                "result": None,
                "error": "Task was cancelled"
            }
        else:
            return {
                "job_id": job_id,
                "status": state.lower(),
                "result": None,
                "error": None
            }

    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        return {
            "job_id": job_id,
            "status": "error",
            "result": None,
            "error": str(e)
        }


async def cancel_job(job_id: str) -> bool:
    """
    Cancel a queued or running job

    Args:
        job_id: The job ID to cancel

    Returns:
        True if cancelled, False otherwise
    """
    try:
        result = AsyncResult(job_id, app=app)
        result.revoke(terminate=True)
        logger.info(f"Cancelled job: {job_id}")
        return True
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        return False
