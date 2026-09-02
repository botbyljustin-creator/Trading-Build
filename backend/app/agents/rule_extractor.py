"""Rule Extractor agent (ARCHITECTURE.md §5.3)."""

from __future__ import annotations

from app.ai.base import LLMProvider
from app.ai.prompts.agents import RULE_EXTRACTOR_SYSTEM_PROMPT
from app.ai.rendering import ChunkInput, render_chunks
from app.schemas.rule import RuleExtractionResult

BASE_INSTRUCTION = (
    "Extract explicit, testable trading rules from the following transcript "
    "chunks, categorized as instructed. Cite the exact video_id/start/end "
    "shown in the chunk header(s) you drew each rule from, and quote a "
    "verbatim excerpt (not a paraphrase) supporting it."
)


def extract_rules(
    provider: LLMProvider,
    chunks: list[ChunkInput],
    known_concept_names: list[str] | None = None,
) -> RuleExtractionResult:
    if not chunks:
        return RuleExtractionResult(rules=[])
    instruction = BASE_INSTRUCTION
    if known_concept_names:
        instruction += (
            " Concepts already identified in this project for context "
            f"(do not force rules onto concepts that aren't relevant here): "
            f"{', '.join(known_concept_names)}."
        )
    return provider.generate_structured(
        system_prompt=RULE_EXTRACTOR_SYSTEM_PROMPT,
        source_content=render_chunks(chunks),
        instruction=instruction,
        response_model=RuleExtractionResult,
    )
