from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.routes.common import JobOut
from app.core.db import get_db
from app.models.enums import JobType
from app.models.project import Project
from app.models.report import Report
from app.models.strategy import Strategy, StrategyVersion
from app.security.ownership import get_owned_project, get_owned_report, get_owned_strategy_version
from app.services import job_service

router = APIRouter(prefix="/api/v1", tags=["reports"])


class ReportCreate(BaseModel):
    backtest_id: uuid.UUID | None = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    strategy_version_id: uuid.UUID
    backtest_id: uuid.UUID | None
    content_json: dict
    created_at: datetime


@router.post(
    "/strategy-versions/{version_id}/reports",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_report(
    payload: ReportCreate,
    version: StrategyVersion = Depends(get_owned_strategy_version),
    db: Session = Depends(get_db),
) -> JobOut:
    job = job_service.create_job(
        db,
        project_id=version.strategy.project_id,
        job_type=JobType.GENERATE_REPORT,
        input_ref={
            "strategy_version_id": str(version.id),
            "backtest_id": str(payload.backtest_id) if payload.backtest_id else None,
        },
    )
    from app.workers.tasks.report_tasks import generate_report_task

    generate_report_task.delay(
        str(job.id), str(version.id), str(payload.backtest_id) if payload.backtest_id else None
    )
    db.refresh(job)
    return job


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report: Report = Depends(get_owned_report)) -> Report:
    return report


@router.get("/projects/{project_id}/reports", response_model=list[ReportOut])
def list_project_reports(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> list[Report]:
    return (
        db.query(Report)
        .join(StrategyVersion, StrategyVersion.id == Report.strategy_version_id)
        .join(Strategy, Strategy.id == StrategyVersion.strategy_id)
        .filter(Strategy.project_id == project.id)
        .order_by(Report.created_at.desc())
        .all()
    )
