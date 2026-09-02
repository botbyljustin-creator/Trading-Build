from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import JobStatus, JobType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A background job the frontend can poll for progress. Celery owns
    execution; this row is the durable, queryable record of it."""

    __tablename__ = "jobs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[JobType] = mapped_column(SAEnum(JobType, native_enum=False, length=32))
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, native_enum=False, length=16), default=JobStatus.PENDING, index=True
    )
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    progress_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    input_ref: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, doc="IDs/params identifying what this job operates on."
    )
    result_ref: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, doc="IDs of rows produced by this job, once SUCCESS."
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
