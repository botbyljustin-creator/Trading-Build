"""Manual transcript import.

Every live-fetch path in `app/ingestion/youtube_client.py` depends on
reaching youtube.com, which some environments (this one included, per a
network-policy block documented in `CURRENT_STATE.md`) cannot do. This
module is the honest workaround: it lets a user paste a transcript they
fetched themselves (e.g. via `youtube-transcript-api` or `yt-dlp` on a
machine with YouTube access) directly into the identical downstream
pipeline — chunking, source citations, concept/rule extraction all work
exactly the same on a manually-imported video as a live-fetched one.

This is not a way to fabricate a transcript. `segments` must be provided
by the caller; nothing here invents or paraphrases transcript text.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.orm import Session

from app.ingestion.chunking import TranscriptSegment, chunk_transcript
from app.models.enums import SourceStatus, SourceType, TranscriptStatus
from app.models.source import Source, Transcript, TranscriptChunk, Video
from app.services.ingestion_service import get_or_create_series

MANUAL_IMPORT_SOURCE_TITLE = "Manually Imported Videos"


def _get_or_create_manual_source(db: Session, project_id: uuid.UUID) -> Source:
    existing = (
        db.query(Source)
        .filter(Source.project_id == project_id, Source.title == MANUAL_IMPORT_SOURCE_TITLE)
        .one_or_none()
    )
    if existing is not None:
        return existing
    source = Source(
        project_id=project_id,
        source_type=SourceType.YOUTUBE_VIDEO,
        url="manual-import",
        title=MANUAL_IMPORT_SOURCE_TITLE,
        status=SourceStatus.READY,
    )
    db.add(source)
    db.flush()
    return source


def import_manual_video(
    db: Session,
    *,
    project_id: uuid.UUID,
    youtube_video_id: str,
    url: str,
    title: str,
    channel_name: str | None,
    creator_name: str,
    series_name: str | None,
    youtube_playlist_id: str | None,
    position_in_series: int | None,
    publish_date=None,
    duration_seconds: int | None = None,
    description: str | None = None,
    thumbnail_url: str | None = None,
    language: str = "en",
    is_auto_generated: bool = True,
    segments: list[TranscriptSegment],
) -> Video:
    if not segments:
        raise ValueError("At least one transcript segment is required.")

    existing_video = (
        db.query(Video)
        .filter(Video.project_id == project_id, Video.youtube_video_id == youtube_video_id)
        .one_or_none()
    )
    if existing_video is not None:
        raise ValueError(
            f"Video {youtube_video_id} already exists in this project "
            f"(id={existing_video.id}, status={existing_video.transcript_status})."
        )

    source = _get_or_create_manual_source(db, project_id)

    series = None
    if series_name:
        series = get_or_create_series(
            db,
            project_id=project_id,
            source_id=source.id,
            creator_name=creator_name,
            series_name=series_name,
            playlist_id=youtube_playlist_id,
        )

    video = Video(
        source_id=source.id,
        project_id=project_id,
        series_id=series.id if series is not None else None,
        position_in_series=position_in_series if series is not None else None,
        youtube_video_id=youtube_video_id,
        title=title,
        channel_name=channel_name or creator_name,
        publish_date=publish_date,
        duration_seconds=duration_seconds,
        description=description,
        thumbnail_url=thumbnail_url,
        url=url,
        transcript_status=TranscriptStatus.AVAILABLE,
        is_manual_import=True,
    )
    db.add(video)
    db.flush()

    full_text = " ".join(s.text for s in segments)
    transcript = Transcript(
        video_id=video.id,
        language=language,
        is_auto_generated=is_auto_generated,
        full_text=full_text,
    )
    db.add(transcript)
    db.flush()

    for idx, chunk in enumerate(chunk_transcript(segments)):
        db.add(
            TranscriptChunk(
                transcript_id=transcript.id,
                video_id=video.id,
                chunk_index=idx,
                start_seconds=chunk.start_seconds,
                end_seconds=chunk.end_seconds,
                text=chunk.text,
                content_hash=hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
            )
        )

    db.commit()
    db.refresh(video)
    return video
