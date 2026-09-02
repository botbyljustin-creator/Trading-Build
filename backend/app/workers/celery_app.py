"""Celery application (Module: Background Job System).

Run the worker with: `celery -A app.workers.celery_app worker --loglevel=info`
(see README.md — the `worker` service in docker-compose.yml runs exactly
this). Every task here is a thin wrapper: it opens its own DB session (a
Celery worker is a separate process from the API), updates the
corresponding `Job` row via `app.services.job_service`, and delegates the
actual work to `app.services.*` — the same functions the API layer could
call directly for a synchronous/test path.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "strategyforge",
    broker=settings.effective_celery_broker_url,
    backend=settings.effective_celery_result_backend_url,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Imported after `celery_app` is defined (each task module does
# `from app.workers.celery_app import celery_app`) so every `@celery_app.task`
# actually registers when the worker starts with `-A app.workers.celery_app`.
from app.workers.tasks import (  # noqa: E402,F401
    backtest_tasks,
    extraction_tasks,
    ingestion_tasks,
    report_tasks,
)
