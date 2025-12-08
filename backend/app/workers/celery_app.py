"""Celery application configuration for async task processing."""

import logging

from celery import Celery

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Celery app
celery_app = Celery(
    "leaf",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
celery_app.conf.update(
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour (matches session TTL)
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },

    # Task tracking
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # Soft limit at 9 minutes

    # Worker settings
    worker_prefetch_multiplier=1,  # Prevent worker from grabbing multiple tasks
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (memory cleanup)

    # Retry settings
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Requeue if worker crashes
    broker_connection_retry_on_startup=True, # Retry broker connection on startup
)

# Auto-discover tasks from the tasks module
celery_app.autodiscover_tasks(["app.workers"])

logger.info("Celery app initialized with broker: %s", settings.celery_broker_url)
