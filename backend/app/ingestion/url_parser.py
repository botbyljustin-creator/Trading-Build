"""YouTube URL classification (Module 1: identify video/playlist/channel).

Pure string parsing, no network calls — fully unit-testable and the first
thing that runs on a submitted URL.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.models.enums import SourceType


class UnrecognizedYouTubeURLError(ValueError):
    pass


def classify_youtube_url(url: str) -> tuple[SourceType, str]:
    """Returns `(SourceType, identifier)`.

    `identifier` is a bare video id for VIDEO, a bare playlist id for
    PLAYLIST, and one of `channel/<id>`, `@<handle>`, `c/<name>`, or
    `user/<name>` for CHANNEL (the ingestion client dispatches on this
    prefix since each channel URL style resolves differently).
    """
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")
    path = parsed.path
    query = parse_qs(parsed.query)
    segments = [s for s in path.split("/") if s]

    if host == "youtu.be":
        if segments:
            return SourceType.YOUTUBE_VIDEO, segments[0]
        raise UnrecognizedYouTubeURLError(f"Could not extract a video id from: {url}")

    if host != "youtube.com" and not host.endswith(".youtube.com"):
        raise UnrecognizedYouTubeURLError(f"Not a recognized YouTube URL: {url}")

    if path == "/watch" and "v" in query:
        return SourceType.YOUTUBE_VIDEO, query["v"][0]

    if segments and segments[0] == "shorts" and len(segments) > 1:
        return SourceType.YOUTUBE_VIDEO, segments[1]

    if segments and segments[0] == "embed" and len(segments) > 1:
        return SourceType.YOUTUBE_VIDEO, segments[1]

    if path == "/playlist" and "list" in query:
        return SourceType.YOUTUBE_PLAYLIST, query["list"][0]

    if segments and segments[0] == "channel" and len(segments) > 1:
        return SourceType.YOUTUBE_CHANNEL, f"channel/{segments[1]}"

    if segments and segments[0].startswith("@"):
        return SourceType.YOUTUBE_CHANNEL, segments[0]

    if segments and segments[0] == "c" and len(segments) > 1:
        return SourceType.YOUTUBE_CHANNEL, f"c/{segments[1]}"

    if segments and segments[0] == "user" and len(segments) > 1:
        return SourceType.YOUTUBE_CHANNEL, f"user/{segments[1]}"

    raise UnrecognizedYouTubeURLError(f"Could not classify YouTube URL: {url}")
