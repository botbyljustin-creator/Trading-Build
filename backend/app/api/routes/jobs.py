from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.common import JobOut
from app.core.db import get_db
from app.models.job import Job
from app.models.project import Project
from app.security.ownership import get_owned_job, get_owned_project

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job: Job = Depends(get_owned_job)) -> Job:
    return job


@router.get("/projects/{project_id}/jobs", response_model=list[JobOut])
def list_jobs(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> list[Job]:
    return (
        db.query(Job)
        .filter(Job.project_id == project.id)
        .order_by(Job.created_at.desc())
        .limit(100)
        .all()
    )
