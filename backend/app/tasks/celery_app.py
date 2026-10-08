"""Celery application factory."""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "codeinsight",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.pipeline",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,          # only ack after task completes (safe retries)
    worker_prefetch_multiplier=1, # fair dispatch for long-running tasks
    task_routes={
        "app.tasks.pipeline.*": {"queue": "analysis"},
    },
)
