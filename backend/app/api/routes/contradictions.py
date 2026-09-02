from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.routes.common import JobOut
from app.core.db import get_db
from app.models.enums import ContradictionResolution, JobType
from app.models.project import Project
from app.models.rule import Contradiction
from app.models.user import User
from app.security.clerk import get_current_user
from app.security.ownership import get_owned_contradiction, get_owned_project
from app.services import job_service
from app.services.audit import record_audit

router = APIRouter(prefix="/api/v1", tags=["contradictions"])


class ContradictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_a_id: uuid.UUID
    rule_b_id: uuid.UUID
    explanation: str
    resolution: ContradictionResolution
    created_at: datetime


class ContradictionResolve(BaseModel):
    resolution: ContradictionResolution


@router.post(
    "/projects/{project_id}/contradictions/detect",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def detect_contradictions(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> JobOut:
    job = job_service.create_job(db, project_id=project.id, job_type=JobType.DETECT_CONTRADICTIONS)
    from app.workers.tasks.extraction_tasks import detect_contradictions_task

    detect_contradictions_task.delay(str(job.id), str(project.id))
    db.refresh(job)
    return job


@router.get("/projects/{project_id}/contradictions", response_model=list[ContradictionOut])
def list_contradictions(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> list[Contradiction]:
    return (
        db.query(Contradiction)
        .filter(Contradiction.project_id == project.id)
        .order_by(Contradiction.created_at.desc())
        .all()
    )


@router.post("/contradictions/{contradiction_id}/resolve", response_model=ContradictionOut)
def resolve_contradiction(
    payload: ContradictionResolve,
    contradiction: Contradiction = Depends(get_owned_contradiction),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Contradiction:
    contradiction.resolution = payload.resolution
    contradiction.resolved_at = datetime.now(UTC)
    contradiction.resolved_by_user_id = user.id
    record_audit(
        db,
        project_id=contradiction.project_id,
        user_id=user.id,
        action="contradiction.resolved",
        entity_type="Contradiction",
        entity_id=contradiction.id,
        details={"resolution": payload.resolution.value},
    )
    db.commit()
    db.refresh(contradiction)
    return contradiction
