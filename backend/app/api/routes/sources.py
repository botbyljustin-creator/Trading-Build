from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.routes.common import JobOut
from app.core.db import get_db
from app.ingestion.url_parser import UnrecognizedYouTubeURLError, classify_youtube_url
from app.models.enums import JobType, SourceStatus, SourceType, TranscriptStatus
from app.models.project import Project
from app.models.source import Source, Video
from app.models.user import User
from app.security.clerk import get_current_user
from app.security.ownership import get_owned_project, get_owned_source, get_owned_video
from app.services import job_service
from app.services.audit import record_audit

router = APIRouter(prefix="/api/v1", tags=["sources"])


class SourceCreate(BaseModel):
    url: str = Field(min_length=1)


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: SourceType
    url: str
    title: str | None
    status: SourceStatus
    error_message: str | None
    estimated_video_count: int | None
    estimated_transcript_tokens: int | None
    estimated_cost_usd: float | None
    created_at: datetime


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    youtube_video_id: str
    title: str
    channel_name: str | None
    publish_date: datetime | None
    duration_seconds: int | None
    thumbnail_url: str | None
    url: str
    transcript_status: TranscriptStatus
    transcript_error: str | None


@router.post(
    "/projects/{project_id}/sources", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED
)
def create_source(
    payload: SourceCreate,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    try:
        source_type, _ = classify_youtube_url(payload.url)
    except UnrecognizedYouTubeURLError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    source = Source(project_id=project.id, source_type=source_type, url=payload.url)
    db.add(source)
    db.flush()
    record_audit(
        db,
        project_id=project.id,
        user_id=user.id,
        action="source.added",
        entity_type="Source",
        entity_id=source.id,
        details={"url": payload.url, "source_type": source_type.value},
    )
    db.commit()
    db.refresh(source)

    job = job_service.create_job(
        db,
        project_id=project.id,
        job_type=JobType.INGEST_SOURCE,
        input_ref={"source_id": str(source.id)},
    )
    from app.workers.tasks.ingestion_tasks import ingest_source_task

    ingest_source_task.delay(str(job.id), str(source.id))
    db.refresh(job)
    return job


@router.post(
    "/sources/{source_id}/confirm-cost", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED
)
def confirm_source_cost(
    source: Source = Depends(get_owned_source),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    if source.status != SourceStatus.READY:
        raise HTTPException(
            status_code=409,
            detail=f"Source must be READY before confirming cost (currently {source.status}).",
        )
    record_audit(
        db,
        project_id=source.project_id,
        user_id=user.id,
        action="source.cost_confirmed",
        entity_type="Source",
        entity_id=source.id,
        details={"estimated_cost_usd": source.estimated_cost_usd},
    )
    from datetime import datetime as _dt

    source.cost_confirmed_at = _dt.now(UTC)
    db.commit()

    job = job_service.create_job(
        db,
        project_id=source.project_id,
        job_type=JobType.FETCH_TRANSCRIPT,
        input_ref={"source_id": str(source.id)},
    )
    from app.workers.tasks.ingestion_tasks import ingest_source_task

    ingest_source_task.delay(str(job.id), str(source.id), True)
    db.refresh(job)
    return job


@router.get("/projects/{project_id}/sources", response_model=list[SourceOut])
def list_sources(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> list[Source]:
    return (
        db.query(Source)
        .filter(Source.project_id == project.id)
        .order_by(Source.created_at.desc())
        .all()
    )


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(source: Source = Depends(get_owned_source)) -> Source:
    return source


@router.get("/sources/{source_id}/videos", response_model=list[VideoOut])
def list_source_videos(
    source: Source = Depends(get_owned_source), db: Session = Depends(get_db)
) -> list[Video]:
    return (
        db.query(Video).filter(Video.source_id == source.id).order_by(Video.created_at.asc()).all()
    )


@router.get("/videos/{video_id}", response_model=VideoOut)
def get_video(video: Video = Depends(get_owned_video)) -> Video:
    return video


class TranscriptChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_index: int
    start_seconds: float
    end_seconds: float
    text: str


@router.get("/videos/{video_id}/transcript", response_model=list[TranscriptChunkOut])
def get_video_transcript(video: Video = Depends(get_owned_video)) -> list:
    if video.transcript is None:
        raise HTTPException(status_code=404, detail="No transcript stored for this video yet.")
    return video.transcript.chunks
