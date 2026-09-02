from __future__ import annotations

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.models.job import Job
from app.models.source import Source
from app.services import ingestion_service, job_service
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="ingestion.ingest_source")
def ingest_source_task(job_id: str, source_id: str, cost_confirmed: bool = False) -> None:
    settings = get_settings()
    db = get_session_factory()()
    try:
        job = db.get(Job, job_id)
        source = db.get(Source, source_id)
        job_service.mark_running(db, job)
        try:
            ingestion_service.resolve_source(db, source)
            job_service.update_progress(
                db, job, progress_pct=40.0, message="Video metadata resolved."
            )

            cost = source.estimated_cost_usd or 0.0
            if cost > settings.large_job_cost_confirmation_threshold_usd and not cost_confirmed:
                job_service.mark_success(
                    db,
                    job,
                    result_ref={
                        "requires_cost_confirmation": True,
                        "estimated_cost_usd": cost,
                        "estimated_video_count": source.estimated_video_count,
                    },
                )
                return

            def progress(pct: float, message: str) -> None:
                job_service.update_progress(db, job, progress_pct=40.0 + pct / 2, message=message)

            ingestion_service.fetch_transcripts_for_source(db, source, progress_cb=progress)
            job_service.mark_success(
                db,
                job,
                result_ref={
                    "source_id": str(source.id),
                    "video_count": source.estimated_video_count,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("ingest_source_task_failed", job_id=job_id, error=str(exc))
            job_service.mark_failed(db, job, error_message=str(exc))
    finally:
        db.close()
