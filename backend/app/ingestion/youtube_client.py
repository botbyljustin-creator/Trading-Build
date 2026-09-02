"""Metadata + transcript retrieval.

Uses `yt-dlp` (public page/metadata extraction) and `youtube-transcript-api`
(the public timedtext endpoint — the same captions a browser fetches, no
authentication bypass or scraping of restricted content). Per
ARCHITECTURE.md, if a transcript genuinely is not available we mark the
video `TRANSCRIPT_UNAVAILABLE` and stop — we never fabricate one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from app.core.logging import get_logger
from app.ingestion.chunking import TranscriptSegment

logger = get_logger(__name__)


@dataclass(frozen=True)
class VideoMetadata:
    youtube_video_id: str
    title: str
    channel_name: str | None
    channel_id: str | None
    publish_date: datetime | None
    duration_seconds: int | None
    description: str | None
    thumbnail_url: str | None
    url: str


@dataclass(frozen=True)
class TranscriptResult:
    segments: list[TranscriptSegment]
    language: str
    is_auto_generated: bool


class TranscriptUnavailableError(Exception):
    """The video has no accessible transcript/captions. Never caught and
    silently ignored — callers must persist `TRANSCRIPT_UNAVAILABLE`."""


def _ydl_opts(extra: dict | None = None) -> dict:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "ignoreerrors": True}
    if extra:
        opts.update(extra)
    return opts


def fetch_video_metadata(video_id: str) -> VideoMetadata:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
        info = ydl.extract_info(url, download=False)
    if info is None:
        raise ValueError(f"yt-dlp could not extract metadata for video {video_id}")

    publish_date = None
    upload_date = info.get("upload_date")
    if upload_date:
        publish_date = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=UTC)

    return VideoMetadata(
        youtube_video_id=video_id,
        title=info.get("title", f"Video {video_id}"),
        channel_name=info.get("channel") or info.get("uploader"),
        channel_id=info.get("channel_id"),
        publish_date=publish_date,
        duration_seconds=info.get("duration"),
        description=info.get("description"),
        thumbnail_url=info.get("thumbnail"),
        url=url,
    )


def list_playlist_video_ids(playlist_id: str, max_videos: int) -> list[str]:
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    with yt_dlp.YoutubeDL(_ydl_opts({"extract_flat": True, "playlistend": max_videos})) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = (info or {}).get("entries") or []
    return [e["id"] for e in entries if e and e.get("id")][:max_videos]


def list_channel_video_ids(channel_identifier: str, max_videos: int) -> list[str]:
    """`channel_identifier` is the value returned by `classify_youtube_url`
    for a CHANNEL source: `channel/<id>`, `@<handle>`, `c/<name>`, or
    `user/<name>`."""
    url = f"https://www.youtube.com/{channel_identifier}/videos"
    with yt_dlp.YoutubeDL(_ydl_opts({"extract_flat": True, "playlistend": max_videos})) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = (info or {}).get("entries") or []
    return [e["id"] for e in entries if e and e.get("id")][:max_videos]


def fetch_transcript(video_id: str) -> TranscriptResult:
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as exc:
        raise TranscriptUnavailableError(str(exc)) from exc

    transcript = None
    is_auto_generated = True
    try:
        transcript = transcript_list.find_manually_created_transcript(["en"])
        is_auto_generated = False
    except NoTranscriptFound:
        try:
            transcript = transcript_list.find_generated_transcript(["en"])
        except NoTranscriptFound:
            try:
                # Fall back to the first available transcript in any
                # language rather than failing outright — still a real,
                # creator-provided transcript, just not English.
                transcript = next(iter(transcript_list))
            except StopIteration as exc:
                raise TranscriptUnavailableError(f"No transcripts at all for {video_id}") from exc

    try:
        raw = transcript.fetch()
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as exc:
        raise TranscriptUnavailableError(str(exc)) from exc

    segments = [
        TranscriptSegment(
            start=float(s["start"]), duration=float(s.get("duration", 0.0)), text=s["text"]
        )
        for s in raw
    ]
    return TranscriptResult(
        segments=segments, language=transcript.language_code, is_auto_generated=is_auto_generated
    )
