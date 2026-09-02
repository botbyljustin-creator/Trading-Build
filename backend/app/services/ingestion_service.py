"""Source Collector orchestration (Module 1). Thin glue between
`app.ingestion` (pure parsing/network client) and the database — kept
separate so the ingestion package itself never needs a DB session.

Channel ingestion is playlist-aware: each playlist a channel organizes its
content into becomes a `Series`, and videos are tagged with that series +
their position in it. A channel with no playlists falls back to one
"Uncategorized" series over its flat video list — an honest fallback, never
a silent merge of unrelated material into one undifferentiated pile (see
ARCHITECTURE.md's "do not flatten the channel" requirement).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion import youtube_client
from app.ingestion.chunking import chunk_transcript
from app.ingestion.cost_estimation import estimate_processing_cost_usd
from app.ingestion.url_parser import classify_youtube_url
from app.models.enums import SourceStatus, SourceType, TranscriptStatus
from app.models.series import Series
from app.models.source import Source, Transcript, TranscriptChunk, Video

logger = get_logger(__name__)

# Rough spoken-word-to-token heuristic used only for the pre-transcript cost
# estimate (~150 wpm * ~5 chars/word / 4 chars-per-token / 60 sec).
_TOKENS_PER_SECOND_OF_VIDEO = 3.125

UNCATEGORIZED_SERIES_NAME = "Uncategorized (channel has no playlists)"


def get_or_create_series(
    db: Session,
    *,
    project_id,
    source_id,
    creator_name: str,
    series_name: str,
    playlist_id: str | None,
) -> Series:
    query = db.query(Series).filter(Series.project_id == project_id)
    if playlist_id:
        existing = query.filter(Series.youtube_playlist_id == playlist_id).one_or_none()
    else:
        existing = query.filter(
            Series.source_id == source_id,
            Series.series_name == series_name,
            Series.youtube_playlist_id.is_(None),
        ).one_or_none()
    if existing is not None:
        return existing
    series = Series(
        project_id=project_id,
        source_id=source_id,
        creator_name=creator_name,
        series_name=series_name,
        youtube_playlist_id=playlist_id,
    )
    db.add(series)
    db.flush()
    return series


def _persist_videos(
    db: Session,
    source: Source,
    series: Series | None,
    video_ids: list[str],
) -> tuple[int, int, str | None]:
    """Fetches metadata for and persists any `video_ids` not already stored
    for this project. Returns (videos_added, total_duration_seconds,
    first_new_video_title)."""
    added = 0
    total_duration = 0
    first_title: str | None = None
    for position, youtube_video_id in enumerate(video_ids):
        already_exists = (
            db.query(Video)
            .filter(
                Video.project_id == source.project_id, Video.youtube_video_id == youtube_video_id
            )
            .one_or_none()
        )
        if already_exists is not None:
            continue
        meta = youtube_client.fetch_video_metadata(youtube_video_id)
        first_title = first_title or meta.title
        total_duration += meta.duration_seconds or 0
        db.add(
            Video(
                source_id=source.id,
                project_id=source.project_id,
                series_id=series.id if series is not None else None,
                position_in_series=position if series is not None else None,
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
        added += 1
    return added, total_duration, first_title


def resolve_source(db: Session, source: Source) -> None:
    """Classifies the URL, enumerates videos (grouped into series for
    playlists/channels), and fetches their metadata — but never fetches
    transcripts (that's `fetch_transcripts_for_source`, gated behind cost
    confirmation for large sources)."""
    settings = get_settings()
    source.status = SourceStatus.RESOLVING
    db.commit()

    try:
        _, identifier = classify_youtube_url(source.url)
        total_duration_seconds = 0
        first_title: str | None = None

        if source.source_type == SourceType.YOUTUBE_VIDEO:
            _, duration, title = _persist_videos(db, source, None, [identifier])
            total_duration_seconds += duration
            first_title = title

        elif source.source_type == SourceType.YOUTUBE_PLAYLIST:
            video_ids = youtube_client.list_playlist_video_ids(
                identifier, settings.max_videos_per_channel_ingest
            )
            # Creator name isn't known until we've fetched at least one
            # video's metadata; backfilled below once we have it.
            series = get_or_create_series(
                db,
                project_id=source.project_id,
                source_id=source.id,
                creator_name="Unknown",
                series_name=f"Playlist {identifier}",
                playlist_id=identifier,
            )
            _, duration, title = _persist_videos(db, source, series, video_ids)
            total_duration_seconds += duration
            first_title = title
            db.flush()
            first_video = (
                db.query(Video)
                .filter(Video.series_id == series.id)
                .order_by(Video.position_in_series)
                .first()
            )
            if first_video is not None and first_video.channel_name:
                series.creator_name = first_video.channel_name
                if first_video.title:
                    series.series_name = f"{first_video.channel_name} — Playlist {identifier}"

        else:  # YOUTUBE_CHANNEL
            channel_playlists = youtube_client.list_channel_playlists(identifier, max_playlists=25)
            creator_name = channel_playlists.channel_display_name or identifier
            remaining_budget = settings.max_videos_per_channel_ingest

            if channel_playlists.playlists:
                for playlist in channel_playlists.playlists:
                    if remaining_budget <= 0:
                        break
                    playlist_video_ids = youtube_client.list_playlist_video_ids(
                        playlist.playlist_id, remaining_budget
                    )
                    series = get_or_create_series(
                        db,
                        project_id=source.project_id,
                        source_id=source.id,
                        creator_name=creator_name,
                        series_name=playlist.title,
                        playlist_id=playlist.playlist_id,
                    )
                    added, duration, title = _persist_videos(db, source, series, playlist_video_ids)
                    remaining_budget -= added
                    total_duration_seconds += duration
                    first_title = first_title or title
            else:
                series = get_or_create_series(
                    db,
                    project_id=source.project_id,
                    source_id=source.id,
                    creator_name=creator_name,
                    series_name=UNCATEGORIZED_SERIES_NAME,
                    playlist_id=None,
                )
                video_ids = youtube_client.list_channel_video_ids(identifier, remaining_budget)
                _, duration, title = _persist_videos(db, source, series, video_ids)
                total_duration_seconds += duration
                first_title = title

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
                    content_hash=hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
                )
            )
        video.transcript_status = TranscriptStatus.AVAILABLE
        db.commit()
        if progress_cb:
            progress_cb((i + 1) / total * 100.0, f"{video.title}: transcript stored")
