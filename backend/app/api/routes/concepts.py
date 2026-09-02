from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.routes.common import JobOut
from app.core.db import get_db
from app.models.concept import Concept
from app.models.enums import JobType
from app.models.project import Project
from app.security.ownership import get_owned_project
from app.services import job_service

router = APIRouter(prefix="/api/v1", tags=["concepts"])


class ConceptSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    start_seconds: float
    end_seconds: float
    excerpt: str


class ConceptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    confidence: float
    created_at: datetime
    sources: list[ConceptSourceOut]


@router.post(
    "/projects/{project_id}/concepts/extract",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def extract_concepts(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> JobOut:
    job = job_service.create_job(db, project_id=project.id, job_type=JobType.EXTRACT_CONCEPTS)
    from app.workers.tasks.extraction_tasks import extract_concepts_task

    extract_concepts_task.delay(str(job.id), str(project.id))
    db.refresh(job)
    return job


@router.get("/projects/{project_id}/concepts", response_model=list[ConceptOut])
def list_concepts(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> list[Concept]:
    return (
        db.query(Concept)
        .filter(Concept.project_id == project.id)
        .order_by(Concept.created_at.desc())
        .all()
    )
