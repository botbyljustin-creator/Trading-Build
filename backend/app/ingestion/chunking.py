"""Groups raw transcript segments (as returned by the captions API, usually
a few seconds each) into larger timestamped chunks sized for LLM context
and embeddings (Module 1: "break transcripts into timestamped chunks")."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    duration: float
    text: str


@dataclass(frozen=True)
class Chunk:
    start_seconds: float
    end_seconds: float
    text: str


def chunk_transcript(
    segments: list[TranscriptSegment], target_chunk_seconds: float = 45.0
) -> list[Chunk]:
    """Greedily accumulates consecutive segments until `target_chunk_seconds`
    of coverage is reached, then starts a new chunk. Never drops a segment's
    text and never lets a chunk's timestamps overlap the next chunk's."""
    if not segments:
        return []

    chunks: list[Chunk] = []
    texts: list[str] = []
    chunk_start: float | None = None
    chunk_end: float | None = None

    for seg in segments:
        if chunk_start is None:
            chunk_start = seg.start
        texts.append(seg.text)
        chunk_end = seg.start + seg.duration
        if (chunk_end - chunk_start) >= target_chunk_seconds:
            chunks.append(Chunk(chunk_start, chunk_end, " ".join(texts).strip()))
            texts = []
            chunk_start = None
            chunk_end = None

    if texts:
        chunks.append(Chunk(chunk_start, chunk_end, " ".join(texts).strip()))

    return chunks
