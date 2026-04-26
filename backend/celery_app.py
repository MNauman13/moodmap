"""
Celery application configuration
Broker: Redis  |  Backend: Redis

Queue layout (three priority tiers):
  high    — immediate user-facing tasks: analyze_entry, run_immediate_crisis_nudge,
             run_immediate_agent_check
  default — fallback for unrouted tasks
  low     — scheduled batch work: run_nightly_agent_check

Workers must be started with all three queues to drain every tier:
  celery -A backend.celery_app worker -Q high,default,low --loglevel=info
"""

import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "moodmap",
    broker=broker_url,
    backend=result_backend,
    include=["backend.tasks.analysis", "backend.tasks.scheduler"],
)

# ── Beat schedule ───────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "run-agent-every-night": {
        "task": "backend.tasks.scheduler.run_nightly_agent_check",
        "schedule": crontab(hour=20, minute=0),
        "options": {"queue": "low"},
    }
}

# ── Task routing — maps each task to its queue tier ────────────
celery_app.conf.task_routes = {
    "backend.tasks.analysis.analyze_entry": {"queue": "high"},
    "backend.tasks.scheduler.run_immediate_crisis_nudge": {"queue": "high"},
    "backend.tasks.scheduler.run_immediate_agent_check": {"queue": "high"},
    "backend.tasks.scheduler.run_nightly_agent_check": {"queue": "low"},
}

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
    # Declare all three queues so workers and Beat know they exist
    task_queues={
        "high": {"exchange": "high", "routing_key": "high"},
        "default": {"exchange": "default", "routing_key": "default"},
        "low": {"exchange": "low", "routing_key": "low"},
    },
    task_default_queue="default",
)
