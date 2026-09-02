"""Renders internal data structures into the plain-text form passed as
`source_content`/context to LLM prompts. Kept separate from the agents so
the exact wire format is defined in one place and easy to unit test."""

from __future__ import annotations

from pydantic import BaseModel


class ChunkInput(BaseModel):
    video_id: str
    start_seconds: float
    end_seconds: float
    text: str


class RuleSummary(BaseModel):
    rule_id: str
    category: str
    natural_language_rule: str


def render_chunks(chunks: list[ChunkInput]) -> str:
    parts = [
        f"[video_id={c.video_id} start={c.start_seconds:.1f} end={c.end_seconds:.1f}]\n{c.text}"
        for c in chunks
    ]
    return "\n\n".join(parts)


def render_rule_summaries(rules: list[RuleSummary]) -> str:
    parts = [
        f"[rule_id={r.rule_id} category={r.category}]\n{r.natural_language_rule}" for r in rules
    ]
    return "\n\n".join(parts)
