"""Response schemas shared by more than one route module."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobStatus, JobType


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: JobType
    status: JobStatus
    progress_pct: float
    progress_message: str | None
    result_ref: dict | None
    error_message: str | None
