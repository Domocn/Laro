"""
Celery Application Configuration
Async task queue for heavy AI operations
"""
import os
from celery import Celery
from config import settings

# Parse Redis URL
REDIS_URL = settings.redis_url

# Create Celery app
app = Celery(
    'mise',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['workers.tasks']
)

# Celery configuration
app.conf.update(
    # Result backend settings
    result_expires=3600,  # Keep results for 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster'
    },

    # Task settings
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,

    # Worker settings
    worker_prefetch_multiplier=1,  # Take one task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks

    # Broker connection settings (Celery 6.0 compatibility)
    broker_connection_retry_on_startup=True,  # Retry broker connection on startup

    # Task execution
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Reject if worker dies

    # Time limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=360,  # 6 minutes hard limit

    # Retry policy
    task_default_retry_delay=30,  # Wait 30 seconds before retry
    task_max_retries=3,
)

# Task routes (optional - for multiple queues)
app.conf.task_routes = {
    'workers.tasks.*': {'queue': 'mise-jobs'},
}

if __name__ == '__main__':
    app.start()
