"""Job bookkeeping (Module: Background Job System). Celery owns execution
(`app/workers/tasks/*.py`); this module owns the durable `Job` row every
task reports progress into, so the frontend can poll `GET /jobs/{id}`
regardless of which worker process is handling it."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.enums import JobStatus, JobType
from app.models.job import Job


def create_job(
    db: Session, *, project_id: uuid.UUID, job_type: JobType, input_ref: dict | None = None
) -> Job:
    job = Job(
        project_id=project_id, job_type=job_type, input_ref=input_ref, status=JobStatus.PENDING
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_running(db: Session, job: Job) -> None:
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    db.commit()


def update_progress(
    db: Session, job: Job, *, progress_pct: float, message: str | None = None
) -> None:
    job.progress_pct = progress_pct
    if message is not None:
        job.progress_message = message
    db.commit()


def mark_success(db: Session, job: Job, *, result_ref: dict | None = None) -> None:
    job.status = JobStatus.SUCCESS
    job.progress_pct = 100.0
    job.result_ref = result_ref
    job.finished_at = datetime.now(UTC)
    db.commit()


def mark_failed(db: Session, job: Job, *, error_message: str) -> None:
    job.status = JobStatus.FAILED
    job.error_message = error_message
    job.finished_at = datetime.now(UTC)
    db.commit()
