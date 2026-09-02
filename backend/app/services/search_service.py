"""Natural-language search across everything ingested for a project —
concepts, extracted rules, and raw transcript text — with every hit
carrying a citation back to the video + timestamp it came from.

Deliberately built on Postgres full-text search (`to_tsvector` /
`plainto_tsquery`) rather than the pgvector `embeddings` table: semantic
search would require calling an embeddings API on every chunk, which this
project treats as a real cost (see extraction_service's content-hash
caching) and which this sandbox can't reach anyway (youtube.com and most
external hosts are network-blocked here). Full-text search needs no
external call and already answers "where did X get mentioned" — the
question this feature exists to answer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.concept import Concept, ConceptSource
from app.models.rule import Rule
from app.models.source import TranscriptChunk, Video

RESULT_TYPES = ("CONCEPT", "RULE", "TRANSCRIPT")


@dataclass
class SearchCitation:
    video_id: uuid.UUID
    video_title: str
    start_seconds: float
    end_seconds: float
    excerpt: str


@dataclass
class SearchResult:
    result_type: str
    id: uuid.UUID
    title: str
    snippet: str
    rank: float
    series_id: uuid.UUID | None = None
    status: str | None = None
    evidence_type: str | None = None
    confidence: float | None = None
    citations: list[SearchCitation] = field(default_factory=list)


def _rank_expr(query: str, *columns):
    combined = columns[0] if len(columns) == 1 else func.concat(*_interleave_space(columns))
    vector = func.to_tsvector("english", combined)
    tsquery = func.plainto_tsquery("english", query)
    return vector, tsquery, func.ts_rank(vector, tsquery)


def _interleave_space(columns):
    out = []
    for i, col in enumerate(columns):
        if i:
            out.append(" ")
        out.append(col)
    return out


def _video_titles(db: Session, video_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not video_ids:
        return {}
    rows = db.query(Video.id, Video.title).filter(Video.id.in_(video_ids)).all()
    return {row.id: row.title for row in rows}


def _search_concepts(
    db: Session, project_id: uuid.UUID, query: str, series_id: uuid.UUID | None, limit: int
) -> list[SearchResult]:
    vector, tsquery, rank = _rank_expr(query, Concept.name, Concept.description)
    q = db.query(Concept, rank.label("rank")).filter(
        Concept.project_id == project_id, vector.op("@@")(tsquery)
    )
    if series_id is not None:
        q = (
            q.join(ConceptSource, ConceptSource.concept_id == Concept.id)
            .join(Video, Video.id == ConceptSource.video_id)
            .filter(Video.series_id == series_id)
            .distinct()
        )
    rows = q.order_by(rank.desc()).limit(limit).all()

    video_ids = {s.video_id for concept, _ in rows for s in concept.sources}
    titles = _video_titles(db, video_ids)

    results = []
    for concept, rank_value in rows:
        citations = [
            SearchCitation(
                video_id=s.video_id,
                video_title=titles.get(s.video_id, "Unknown video"),
                start_seconds=s.start_seconds,
                end_seconds=s.end_seconds,
                excerpt=s.excerpt,
            )
            for s in concept.sources
        ]
        results.append(
            SearchResult(
                result_type="CONCEPT",
                id=concept.id,
                title=concept.name,
                snippet=concept.description,
                rank=float(rank_value),
                confidence=concept.confidence,
                citations=citations,
            )
        )
    return results


def _search_rules(
    db: Session, project_id: uuid.UUID, query: str, series_id: uuid.UUID | None, limit: int
) -> list[SearchResult]:
    vector, tsquery, rank = _rank_expr(query, Rule.natural_language_rule)
    q = db.query(Rule, rank.label("rank")).filter(
        Rule.project_id == project_id, vector.op("@@")(tsquery)
    )
    if series_id is not None:
        q = q.filter(Rule.series_id == series_id)
    rows = q.order_by(rank.desc()).limit(limit).all()

    video_ids = {s.video_id for rule, _ in rows for s in rule.sources}
    titles = _video_titles(db, video_ids)

    results = []
    for rule, rank_value in rows:
        citations = [
            SearchCitation(
                video_id=s.video_id,
                video_title=titles.get(s.video_id, "Unknown video"),
                start_seconds=s.start_seconds,
                end_seconds=s.end_seconds,
                excerpt=s.excerpt,
            )
            for s in rule.sources
        ]
        results.append(
            SearchResult(
                result_type="RULE",
                id=rule.id,
                title=rule.category.value,
                snippet=rule.natural_language_rule,
                rank=float(rank_value),
                series_id=rule.series_id,
                status=rule.status.value,
                evidence_type=rule.evidence_type.value,
                confidence=rule.confidence,
                citations=citations,
            )
        )
    return results


def _search_transcripts(
    db: Session, project_id: uuid.UUID, query: str, series_id: uuid.UUID | None, limit: int
) -> list[SearchResult]:
    vector, tsquery, rank = _rank_expr(query, TranscriptChunk.text)
    q = (
        db.query(TranscriptChunk, rank.label("rank"), Video)
        .join(Video, Video.id == TranscriptChunk.video_id)
        .filter(Video.project_id == project_id, vector.op("@@")(tsquery))
    )
    if series_id is not None:
        q = q.filter(Video.series_id == series_id)
    rows = q.order_by(rank.desc()).limit(limit).all()

    results = []
    for chunk, rank_value, video in rows:
        results.append(
            SearchResult(
                result_type="TRANSCRIPT",
                id=chunk.id,
                title=video.title,
                snippet=chunk.text,
                rank=float(rank_value),
                series_id=video.series_id,
                citations=[
                    SearchCitation(
                        video_id=video.id,
                        video_title=video.title,
                        start_seconds=chunk.start_seconds,
                        end_seconds=chunk.end_seconds,
                        excerpt=chunk.text,
                    )
                ],
            )
        )
    return results


_SEARCHERS = {
    "CONCEPT": _search_concepts,
    "RULE": _search_rules,
    "TRANSCRIPT": _search_transcripts,
}


def search_knowledge(
    db: Session,
    project_id: uuid.UUID,
    query: str,
    *,
    types: tuple[str, ...] = RESULT_TYPES,
    series_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[SearchResult]:
    """Full-text search over concepts, rules, and raw transcript chunks for
    one project, merged and ranked together. Every result carries at least
    one citation back to a real video + timestamp — there is no result type
    that can appear without one."""
    if not query or not query.strip():
        return []

    results: list[SearchResult] = []
    for result_type in types:
        searcher = _SEARCHERS.get(result_type)
        if searcher is None:
            continue
        results.extend(searcher(db, project_id, query, series_id, limit))

    results.sort(key=lambda r: r.rank, reverse=True)
    return results[:limit]
