"""
Celery application configuration
Broker: Redis  |  Backend: Redis  |  Workers pick up tasks from 'moodmap' queue
"""

import os
from celery import Celery
from dotenv import load_dotenv

# Force load the .env file
load_dotenv()

# Get the Redis URL from the .env file
broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "moodmap",
    broker=broker_url,
    backend=result_backend,
    include=["backend.tasks.analysis"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # One task at a time per worker (ML is memory-heavy)
    result_expires=86400,           # Results kept 24 hours
    broker_connection_retry_on_startup=True,
)