"""Knowledge Builder agent (ARCHITECTURE.md §5.2)."""

from __future__ import annotations

from app.ai.base import LLMProvider
from app.ai.prompts.agents import KNOWLEDGE_BUILDER_SYSTEM_PROMPT
from app.ai.rendering import ChunkInput, render_chunks
from app.schemas.concept import ConceptExtractionResult

INSTRUCTION = (
    "Identify the trading concepts actually present in the following "
    "transcript chunks. For every concept, cite the exact video_id/start/"
    "end shown in the chunk header(s) you drew it from, and quote a "
    "verbatim excerpt (not a paraphrase) from that chunk's text."
)


def extract_concepts(provider: LLMProvider, chunks: list[ChunkInput]) -> ConceptExtractionResult:
    if not chunks:
        return ConceptExtractionResult(concepts=[])
    return provider.generate_structured(
        system_prompt=KNOWLEDGE_BUILDER_SYSTEM_PROMPT,
        source_content=render_chunks(chunks),
        instruction=INSTRUCTION,
        response_model=ConceptExtractionResult,
    )
