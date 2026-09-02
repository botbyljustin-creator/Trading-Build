"""Source Collector orchestration (Module 1). Thin glue between
`app.ingestion` (pure parsing/network client) and the database — kept
separate so the ingestion package itself never needs a DB session."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion import youtube_client
from app.ingestion.chunking import chunk_transcript
from app.ingestion.cost_estimation import estimate_processing_cost_usd
from app.ingestion.url_parser import classify_youtube_url
from app.models.enums import SourceStatus, SourceType, TranscriptStatus
from app.models.source import Source, Transcript, TranscriptChunk, Video

logger = get_logger(__name__)

# Rough spoken-word-to-token heuristic used only for the pre-transcript cost
# estimate (~150 wpm * ~5 chars/word / 4 chars-per-token / 60 sec).
_TOKENS_PER_SECOND_OF_VIDEO = 3.125


def resolve_source(db: Session, source: Source) -> None:
    """Classifies the URL, enumerates videos, and fetches their metadata —
    but never fetches transcripts (that's `fetch_transcripts_for_source`,
    gated behind cost confirmation for large sources)."""
    settings = get_settings()
    source.status = SourceStatus.RESOLVING
    db.commit()

    try:
        _, identifier = classify_youtube_url(source.url)
        if source.source_type == SourceType.YOUTUBE_VIDEO:
            video_ids = [identifier]
        elif source.source_type == SourceType.YOUTUBE_PLAYLIST:
            video_ids = youtube_client.list_playlist_video_ids(
                identifier, settings.max_videos_per_channel_ingest
            )
        else:
            video_ids = youtube_client.list_channel_video_ids(
                identifier, settings.max_videos_per_channel_ingest
            )

        total_duration_seconds = 0
        first_title: str | None = None
        for youtube_video_id in video_ids:
            already_exists = (
                db.query(Video)
                .filter(
                    Video.project_id == source.project_id,
                    Video.youtube_video_id == youtube_video_id,
                )
                .one_or_none()
            )
            if already_exists is not None:
                continue
            meta = youtube_client.fetch_video_metadata(youtube_video_id)
            first_title = first_title or meta.title
            total_duration_seconds += meta.duration_seconds or 0
            db.add(
                Video(
                    source_id=source.id,
                    project_id=source.project_id,
                    youtube_video_id=meta.youtube_video_id,
                    title=meta.title,
                    channel_name=meta.channel_name,
                    channel_id=meta.channel_id,
                    publish_date=meta.publish_date,
                    duration_seconds=meta.duration_seconds,
                    description=meta.description,
                    thumbnail_url=meta.thumbnail_url,
                    url=meta.url,
                )
            )
        db.commit()

        video_count = db.query(Video).filter(Video.source_id == source.id).count()
        estimated_tokens = int(total_duration_seconds * _TOKENS_PER_SECOND_OF_VIDEO)
        source.estimated_video_count = video_count
        source.estimated_transcript_tokens = estimated_tokens
        source.estimated_cost_usd = estimate_processing_cost_usd(
            estimated_tokens, settings.default_llm_provider
        )
        source.title = source.title or first_title
        source.status = SourceStatus.READY
        db.commit()
    except Exception as exc:  # noqa: BLE001 — must persist failure, never crash the worker
        logger.warning("source_resolution_failed", source_id=str(source.id), error=str(exc))
        source.status = SourceStatus.FAILED
        source.error_message = str(exc)
        db.commit()
        raise


def fetch_transcripts_for_source(
    db: Session, source: Source, progress_cb: Callable[[float, str], None] | None = None
) -> None:
    videos = db.query(Video).filter(Video.source_id == source.id).all()
    pending = [v for v in videos if v.transcript_status == TranscriptStatus.PENDING]
    total = len(pending) or 1

    for i, video in enumerate(pending):
        try:
            transcript_result = youtube_client.fetch_transcript(video.youtube_video_id)
        except youtube_client.TranscriptUnavailableError as exc:
            video.transcript_status = TranscriptStatus.TRANSCRIPT_UNAVAILABLE
            video.transcript_error = str(exc)
            db.commit()
            if progress_cb:
                progress_cb((i + 1) / total * 100.0, f"{video.title}: transcript unavailable")
            continue
        except Exception as exc:  # noqa: BLE001 — one bad video must not abort the whole source
            logger.warning("transcript_fetch_failed", video_id=str(video.id), error=str(exc))
            video.transcript_status = TranscriptStatus.FAILED
            video.transcript_error = str(exc)
            db.commit()
            if progress_cb:
                progress_cb((i + 1) / total * 100.0, f"{video.title}: fetch failed")
            continue

        full_text = " ".join(s.text for s in transcript_result.segments)
        transcript = Transcript(
            video_id=video.id,
            language=transcript_result.language,
            is_auto_generated=transcript_result.is_auto_generated,
            full_text=full_text,
        )
        db.add(transcript)
        db.flush()

        for idx, chunk in enumerate(chunk_transcript(transcript_result.segments)):
            db.add(
                TranscriptChunk(
                    transcript_id=transcript.id,
                    video_id=video.id,
                    chunk_index=idx,
                    start_seconds=chunk.start_seconds,
                    end_seconds=chunk.end_seconds,
                    text=chunk.text,
                )
            )
        video.transcript_status = TranscriptStatus.AVAILABLE
        db.commit()
        if progress_cb:
            progress_cb((i + 1) / total * 100.0, f"{video.title}: transcript stored")
