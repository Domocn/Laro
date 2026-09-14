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
    'laro',
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
    # Heavy AI jobs on dedicated queue; reminders stay on default 'celery'
    'import_recipe_from_url_task': {'queue': 'laro-jobs'},
    'import_recipe_from_text_task': {'queue': 'laro-jobs'},
    'generate_meal_plan_task': {'queue': 'laro-jobs'},
    'fridge_search_task': {'queue': 'laro-jobs'},
}

# Celery Beat — run reminder sweep every minute (windows are 6 minutes wide)
# UK Open Prices catalog refreshes every 12 hours for offline cost estimates
app.conf.beat_schedule = {
    'laro-reminder-sweep': {
        'task': 'workers.tasks.run_reminder_sweep',
        'schedule': 60.0,
    },
    'laro-sync-uk-open-prices': {
        'task': 'workers.tasks.sync_uk_open_prices_task',
        'schedule': 12 * 60 * 60.0,  # every 12 hours
    },
}

if __name__ == '__main__':
    app.start()
