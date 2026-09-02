from __future__ import annotations

import pytest

from app.ingestion.chunking import TranscriptSegment, chunk_transcript
from app.ingestion.cost_estimation import (
    estimate_processing_cost_usd,
    estimate_tokens_from_char_count,
)
from app.ingestion.url_parser import UnrecognizedYouTubeURLError, classify_youtube_url
from app.models.enums import SourceType


@pytest.mark.parametrize(
    "url,expected_type,expected_id",
    [
        ("https://www.youtube.com/watch?v=abc123XYZ_-", SourceType.YOUTUBE_VIDEO, "abc123XYZ_-"),
        ("https://youtu.be/abc123XYZ_-", SourceType.YOUTUBE_VIDEO, "abc123XYZ_-"),
        ("https://www.youtube.com/shorts/abc123XYZ_-", SourceType.YOUTUBE_VIDEO, "abc123XYZ_-"),
        ("https://www.youtube.com/embed/abc123XYZ_-", SourceType.YOUTUBE_VIDEO, "abc123XYZ_-"),
        (
            "https://www.youtube.com/playlist?list=PL12345",
            SourceType.YOUTUBE_PLAYLIST,
            "PL12345",
        ),
        (
            "https://www.youtube.com/channel/UC12345",
            SourceType.YOUTUBE_CHANNEL,
            "channel/UC12345",
        ),
        ("https://www.youtube.com/@SomeTrader", SourceType.YOUTUBE_CHANNEL, "@SomeTrader"),
        ("https://www.youtube.com/c/SomeTrader", SourceType.YOUTUBE_CHANNEL, "c/SomeTrader"),
        ("https://www.youtube.com/user/SomeTrader", SourceType.YOUTUBE_CHANNEL, "user/SomeTrader"),
        ("https://m.youtube.com/watch?v=abc123XYZ_-", SourceType.YOUTUBE_VIDEO, "abc123XYZ_-"),
    ],
)
def test_classify_youtube_url(url, expected_type, expected_id):
    source_type, identifier = classify_youtube_url(url)
    assert source_type == expected_type
    assert identifier == expected_id


def test_classify_rejects_non_youtube_url():
    with pytest.raises(UnrecognizedYouTubeURLError):
        classify_youtube_url("https://vimeo.com/12345")


def test_classify_rejects_unrecognized_youtube_path():
    with pytest.raises(UnrecognizedYouTubeURLError):
        classify_youtube_url("https://www.youtube.com/feed/trending")


def test_chunk_transcript_groups_to_target_length():
    segments = [
        TranscriptSegment(start=float(i * 5), duration=5.0, text=f"word{i}") for i in range(20)
    ]
    chunks = chunk_transcript(segments, target_chunk_seconds=20.0)
    assert len(chunks) > 1
    # No text is dropped.
    assert sum(len(c.text.split()) for c in chunks) == 20
    # Chunks are contiguous and non-overlapping.
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert a.end_seconds == b.start_seconds


def test_chunk_transcript_empty_input():
    assert chunk_transcript([]) == []


def test_cost_estimate_scales_with_tokens():
    small = estimate_processing_cost_usd(1_000)
    large = estimate_processing_cost_usd(100_000)
    assert large > small
    assert estimate_tokens_from_char_count(4000) == 1000
