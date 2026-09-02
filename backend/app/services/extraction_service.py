"""Knowledge Builder / Rule Extractor orchestration (ARCHITECTURE.md §5.2-3).

Processes one video's transcript chunks per LLM call (batched further if a
video is unusually long) and persists results with full source
traceability. Never invokes an agent on a video without an available
transcript. Results are cached by exact chunk-batch content hash
(`app.models.extraction_cache`) so re-running extraction on unchanged
content never re-spends LLM cost (Module: Control Token Cost) — this
catches the common "I clicked extract twice" / "nothing changed since last
run" case; it does not (yet) deduplicate near-identical explanations
repeated verbatim across different videos, which would need fuzzy
matching, not just hashing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.agents.knowledge_builder import extract_concepts
from app.agents.rule_extractor import extract_rules
from app.ai.base import LLMProvider
from app.ai.prompts.agents import KNOWLEDGE_BUILDER_PROMPT_VERSION, RULE_EXTRACTOR_PROMPT_VERSION
from app.ai.rendering import ChunkInput
from app.models.concept import Concept, ConceptSource
from app.models.enums import Quantifiability, RuleEvidenceType, RuleStatus, TranscriptStatus
from app.models.extraction_cache import ExtractionCache
from app.models.rule import Rule, RuleSource
from app.models.source import Video
from app.schemas.concept import ConceptExtractionResult, ExtractedConcept
from app.schemas.rule import ExtractedRule, RuleExtractionResult
from app.services.tagging import tag_instruments

# A chunk is ~45s of transcript; this keeps a single LLM call's input to a
# manageable size for very long videos while still giving the model enough
# surrounding context to identify a concept/rule correctly.
MAX_CHUNKS_PER_CALL = 40

_EVIDENCE_TO_STATUS = {
    RuleEvidenceType.AI_ASSUMPTION: RuleStatus.AI_ASSUMPTION,
}


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


def _batch_content_hash(chunks: list[ChunkInput]) -> str:
    combined = "|".join(hashlib.sha256(c.text.encode("utf-8")).hexdigest() for c in chunks)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _get_cached_result(
    db: Session, content_hash: str, extractor_name: str, prompt_version: str
) -> dict | None:
    row = (
        db.query(ExtractionCache)
        .filter(
            ExtractionCache.content_hash == content_hash,
            ExtractionCache.extractor_name == extractor_name,
            ExtractionCache.prompt_version == prompt_version,
        )
        .one_or_none()
    )
    return row.result_json if row is not None else None


def _store_cache_result(
    db: Session, content_hash: str, extractor_name: str, prompt_version: str, result_json: dict
) -> None:
    db.add(
        ExtractionCache(
            content_hash=content_hash,
            extractor_name=extractor_name,
            prompt_version=prompt_version,
            result_json=result_json,
        )
    )
    db.flush()


def _persist_concept(db: Session, project_id, extracted: ExtractedConcept) -> Concept:
    concept = Concept(
        project_id=project_id,
        name=extracted.name,
        description=extracted.description,
        confidence=extracted.confidence,
        instrument_tags=tag_instruments(extracted.name, extracted.description),
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


def _persist_rule(db: Session, project_id, video: Video, extracted: ExtractedRule) -> Rule:
    evidence_type = RuleEvidenceType(extracted.evidence_type)
    rule = Rule(
        project_id=project_id,
        series_id=video.series_id,
        category=extracted.category,
        natural_language_rule=extracted.natural_language_rule,
        machine_readable_rule=extracted.machine_readable_rule,
        confidence=extracted.confidence,
        status=_EVIDENCE_TO_STATUS.get(evidence_type, RuleStatus.EXTRACTED),
        evidence_type=evidence_type,
        quantifiability=Quantifiability(extracted.quantifiability),
        instrument_tags=tag_instruments(extracted.natural_language_rule),
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
            content_hash = _batch_content_hash(batch)
            cached = _get_cached_result(
                db, content_hash, "knowledge_builder", KNOWLEDGE_BUILDER_PROMPT_VERSION
            )
            if cached is not None:
                result = ConceptExtractionResult.model_validate(cached)
            else:
                result = extract_concepts(provider, batch)
                _store_cache_result(
                    db,
                    content_hash,
                    "knowledge_builder",
                    KNOWLEDGE_BUILDER_PROMPT_VERSION,
                    result.model_dump(mode="json"),
                )
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
            content_hash = _batch_content_hash(batch)
            cached = _get_cached_result(
                db, content_hash, "rule_extractor", RULE_EXTRACTOR_PROMPT_VERSION
            )
            if cached is not None:
                result = RuleExtractionResult.model_validate(cached)
            else:
                result = extract_rules(provider, batch, known_concepts)
                _store_cache_result(
                    db,
                    content_hash,
                    "rule_extractor",
                    RULE_EXTRACTOR_PROMPT_VERSION,
                    result.model_dump(mode="json"),
                )
            for extracted in result.rules:
                created.append(_persist_rule(db, project_id, video, extracted))
        db.commit()
        if progress_cb:
            progress_cb((i + 1) / total * 100.0, f"Extracted rules from {video.title}")
    return created
