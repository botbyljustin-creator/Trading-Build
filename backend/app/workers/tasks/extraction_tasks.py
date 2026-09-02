from __future__ import annotations

from app.ai.factory import get_llm_provider
from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.models.job import Job
from app.services import extraction_service, job_service
from app.services.audit import record_audit
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="extraction.extract_concepts")
def extract_concepts_task(job_id: str, project_id: str) -> None:
    db = get_session_factory()()
    try:
        job = db.get(Job, job_id)
        job_service.mark_running(db, job)
        try:
            provider = get_llm_provider()
            concepts = extraction_service.extract_concepts_for_project(
                db,
                project_id,
                provider,
                progress_cb=lambda pct, msg: job_service.update_progress(
                    db, job, progress_pct=pct, message=msg
                ),
            )
            record_audit(
                db,
                project_id=project_id,
                user_id=None,
                action="concept.extracted",
                entity_type="Project",
                details={"concepts_created": len(concepts)},
            )
            db.commit()
            job_service.mark_success(db, job, result_ref={"concepts_created": len(concepts)})
        except Exception as exc:  # noqa: BLE001
            logger.error("extract_concepts_task_failed", job_id=job_id, error=str(exc))
            job_service.mark_failed(db, job, error_message=str(exc))
    finally:
        db.close()


@celery_app.task(name="extraction.extract_rules")
def extract_rules_task(job_id: str, project_id: str) -> None:
    db = get_session_factory()()
    try:
        job = db.get(Job, job_id)
        job_service.mark_running(db, job)
        try:
            provider = get_llm_provider()
            rules = extraction_service.extract_rules_for_project(
                db,
                project_id,
                provider,
                progress_cb=lambda pct, msg: job_service.update_progress(
                    db, job, progress_pct=pct, message=msg
                ),
            )
            record_audit(
                db,
                project_id=project_id,
                user_id=None,
                action="rule.extracted",
                entity_type="Project",
                details={"rules_created": len(rules)},
            )
            db.commit()
            job_service.mark_success(db, job, result_ref={"rules_created": len(rules)})
        except Exception as exc:  # noqa: BLE001
            logger.error("extract_rules_task_failed", job_id=job_id, error=str(exc))
            job_service.mark_failed(db, job, error_message=str(exc))
    finally:
        db.close()


@celery_app.task(name="extraction.detect_contradictions")
def detect_contradictions_task(job_id: str, project_id: str) -> None:
    from app.services import contradiction_service

    db = get_session_factory()()
    try:
        job = db.get(Job, job_id)
        job_service.mark_running(db, job)
        try:
            provider = get_llm_provider()
            contradictions = contradiction_service.detect_contradictions_for_project(
                db, project_id, provider
            )
            record_audit(
                db,
                project_id=project_id,
                user_id=None,
                action="contradiction.detected",
                entity_type="Project",
                details={"contradictions_found": len(contradictions)},
            )
            db.commit()
            job_service.mark_success(
                db, job, result_ref={"contradictions_found": len(contradictions)}
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("detect_contradictions_task_failed", job_id=job_id, error=str(exc))
            job_service.mark_failed(db, job, error_message=str(exc))
    finally:
        db.close()
