from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.routes.common import JobOut
from app.core.db import get_db
from app.ingestion.url_parser import UnrecognizedYouTubeURLError, classify_youtube_url
from app.models.enums import JobType, SourceStatus, SourceType, TranscriptStatus
from app.models.project import Project
from app.models.series import Series
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
    series_id: uuid.UUID | None
    position_in_series: int | None
    youtube_video_id: str
    title: str
    channel_name: str | None
    publish_date: datetime | None
    duration_seconds: int | None
    thumbnail_url: str | None
    url: str
    transcript_status: TranscriptStatus
    transcript_error: str | None
    is_manual_import: bool


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


class SeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    creator_name: str
    series_name: str
    youtube_playlist_id: str | None
    description: str | None
    video_count: int = 0


@router.get("/projects/{project_id}/series", response_model=list[SeriesOut])
def list_series(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> list[SeriesOut]:
    """Every creator/series/mentorship grouping discovered in this project
    — the hierarchy that keeps a multi-year channel's teachings from being
    flattened into one undifferentiated pile (see ARCHITECTURE.md)."""
    rows = (
        db.query(Series)
        .filter(Series.project_id == project.id)
        .order_by(Series.creator_name, Series.series_name)
        .all()
    )
    counts = dict(
        db.query(Video.series_id, func.count(Video.id))
        .filter(Video.project_id == project.id, Video.series_id.isnot(None))
        .group_by(Video.series_id)
        .all()
    )
    return [
        SeriesOut(
            id=r.id,
            creator_name=r.creator_name,
            series_name=r.series_name,
            youtube_playlist_id=r.youtube_playlist_id,
            description=r.description,
            video_count=counts.get(r.id, 0),
        )
        for r in rows
    ]


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


class ManualTranscriptSegmentIn(BaseModel):
    """Matches `youtube_transcript_api.YouTubeTranscriptApi.get_transcript()`'s
    own output shape exactly, so a JSON dump of that call can be pasted in
    with zero reformatting."""

    start: float
    duration: float = 0.0
    text: str = Field(min_length=1)


class ManualVideoImportRequest(BaseModel):
    url: str = Field(min_length=1, description="The video's YouTube URL, for citation/reference.")
    title: str = Field(min_length=1)
    creator_name: str = Field(min_length=1, description='e.g. "Inner Circle Trader".')
    channel_name: str | None = None
    series_name: str | None = Field(
        default=None, description="Playlist/mentorship/series name — omit for a standalone video."
    )
    youtube_playlist_id: str | None = None
    position_in_series: int | None = None
    publish_date: datetime | None = None
    duration_seconds: int | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    language: str = "en"
    is_auto_generated: bool = True
    segments: list[ManualTranscriptSegmentIn] = Field(min_length=1)


@router.post(
    "/projects/{project_id}/videos/manual-import",
    response_model=VideoOut,
    status_code=status.HTTP_201_CREATED,
)
def import_manual_video(
    payload: ManualVideoImportRequest,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Video:
    """Imports a transcript fetched outside StrategyForge AI — the
    workaround for environments (like this deployment's build sandbox)
    that cannot reach youtube.com directly. See README.md's "Providing ICT
    (or any) transcripts manually" section for how to produce `segments`.
    """
    try:
        source_type, youtube_video_id = classify_youtube_url(payload.url)
    except UnrecognizedYouTubeURLError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if source_type != SourceType.YOUTUBE_VIDEO:
        raise HTTPException(
            status_code=422, detail="url must identify a single video, not a playlist or channel."
        )

    from app.ingestion.chunking import TranscriptSegment
    from app.services.manual_import_service import import_manual_video as do_import

    segments = [
        TranscriptSegment(start=s.start, duration=s.duration, text=s.text) for s in payload.segments
    ]
    try:
        video = do_import(
            db,
            project_id=project.id,
            youtube_video_id=youtube_video_id,
            url=payload.url,
            title=payload.title,
            channel_name=payload.channel_name,
            creator_name=payload.creator_name,
            series_name=payload.series_name,
            youtube_playlist_id=payload.youtube_playlist_id,
            position_in_series=payload.position_in_series,
            publish_date=payload.publish_date,
            duration_seconds=payload.duration_seconds,
            description=payload.description,
            thumbnail_url=payload.thumbnail_url,
            language=payload.language,
            is_auto_generated=payload.is_auto_generated,
            segments=segments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    record_audit(
        db,
        project_id=project.id,
        user_id=user.id,
        action="video.manual_import",
        entity_type="Video",
        entity_id=video.id,
        details={"youtube_video_id": youtube_video_id, "creator_name": payload.creator_name},
    )
    db.commit()
    return video
