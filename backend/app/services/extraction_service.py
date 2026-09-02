"""Knowledge Builder / Rule Extractor orchestration (ARCHITECTURE.md §5.2-3).

Processes one video's transcript chunks per LLM call (batched further if a
video is unusually long) and persists results with full source
traceability. Never invokes an agent on a video without an available
transcript.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.agents.knowledge_builder import extract_concepts
from app.agents.rule_extractor import extract_rules
from app.ai.base import LLMProvider
from app.ai.rendering import ChunkInput
from app.models.concept import Concept, ConceptSource
from app.models.enums import RuleStatus, TranscriptStatus
from app.models.rule import Rule, RuleSource
from app.models.source import Video
from app.schemas.concept import ExtractedConcept
from app.schemas.rule import ExtractedRule

# A chunk is ~45s of transcript; this keeps a single LLM call's input to a
# manageable size for very long videos while still giving the model enough
# surrounding context to identify a concept/rule correctly.
MAX_CHUNKS_PER_CALL = 40


def _chunks_for_video(video: Video) -> list[ChunkInput]:
    if video.transcript is None:
        return []
    return [
        ChunkInput(
            video_id=str(video.id),
            start_seconds=c.start_seconds,
            end_seconds=c.end_seconds,
            text=c.text,
        )
        for c in video.transcript.chunks
    ]


def _batches(chunks: list[ChunkInput], size: int) -> list[list[ChunkInput]]:
    return [chunks[i : i + size] for i in range(0, len(chunks), size)]


def _persist_concept(db: Session, project_id, extracted: ExtractedConcept) -> Concept:
    concept = Concept(
        project_id=project_id,
        name=extracted.name,
        description=extracted.description,
        confidence=extracted.confidence,
    )
    db.add(concept)
    db.flush()
    for source in extracted.sources:
        db.add(
            ConceptSource(
                concept_id=concept.id,
                video_id=source.video_id,
                start_seconds=source.start_seconds,
                end_seconds=source.end_seconds,
                excerpt=source.excerpt,
            )
        )
    return concept


def _persist_rule(db: Session, project_id, extracted: ExtractedRule) -> Rule:
    rule = Rule(
        project_id=project_id,
        category=extracted.category,
        natural_language_rule=extracted.natural_language_rule,
        machine_readable_rule=extracted.machine_readable_rule,
        confidence=extracted.confidence,
        status=RuleStatus.AI_ASSUMPTION if extracted.is_assumption else RuleStatus.EXTRACTED,
    )
    db.add(rule)
    db.flush()
    for source in extracted.sources:
        db.add(
            RuleSource(
                rule_id=rule.id,
                video_id=source.video_id,
                start_seconds=source.start_seconds,
                end_seconds=source.end_seconds,
                excerpt=source.excerpt,
            )
        )
    return rule


def extract_concepts_for_project(
    db: Session,
    project_id,
    provider: LLMProvider,
    progress_cb: Callable[[float, str], None] | None = None,
) -> list[Concept]:
    videos = (
        db.query(Video)
        .filter(
            Video.project_id == project_id, Video.transcript_status == TranscriptStatus.AVAILABLE
        )
        .all()
    )
    created: list[Concept] = []
    total = len(videos) or 1
    for i, video in enumerate(videos):
        for batch in _batches(_chunks_for_video(video), MAX_CHUNKS_PER_CALL):
            result = extract_concepts(provider, batch)
            for extracted in result.concepts:
                created.append(_persist_concept(db, project_id, extracted))
        db.commit()
        if progress_cb:
            progress_cb((i + 1) / total * 100.0, f"Extracted concepts from {video.title}")
    return created


def extract_rules_for_project(
    db: Session,
    project_id,
    provider: LLMProvider,
    progress_cb: Callable[[float, str], None] | None = None,
) -> list[Rule]:
    videos = (
        db.query(Video)
        .filter(
            Video.project_id == project_id, Video.transcript_status == TranscriptStatus.AVAILABLE
        )
        .all()
    )
    known_concepts = [
        c.name for c in db.query(Concept).filter(Concept.project_id == project_id).all()
    ]
    created: list[Rule] = []
    total = len(videos) or 1
    for i, video in enumerate(videos):
        for batch in _batches(_chunks_for_video(video), MAX_CHUNKS_PER_CALL):
            result = extract_rules(provider, batch, known_concepts)
            for extracted in result.rules:
                created.append(_persist_rule(db, project_id, extracted))
        db.commit()
        if progress_cb:
            progress_cb((i + 1) / total * 100.0, f"Extracted rules from {video.title}")
    return created
