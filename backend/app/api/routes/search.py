from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.project import Project
from app.security.ownership import get_owned_project
from app.services.search_service import RESULT_TYPES, search_knowledge

router = APIRouter(prefix="/api/v1", tags=["search"])


class SearchCitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    video_id: uuid.UUID
    video_title: str
    start_seconds: float
    end_seconds: float
    excerpt: str


class SearchResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_type: str
    id: uuid.UUID
    title: str
    snippet: str
    rank: float
    series_id: uuid.UUID | None
    status: str | None
    evidence_type: str | None
    confidence: float | None
    citations: list[SearchCitationOut]


@router.get("/projects/{project_id}/search", response_model=list[SearchResultOut])
def search(
    q: str = Query(..., min_length=1, description="Natural-language search query."),
    types: str | None = Query(
        None,
        description="Comma-separated subset of CONCEPT,RULE,TRANSCRIPT. Defaults to all three.",
    ),
    series_id: uuid.UUID | None = None,
    limit: int = Query(20, ge=1, le=100),
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
) -> list[SearchResultOut]:
    """Searches every concept, rule, and raw transcript chunk ingested for
    this project. Never returns a result without a source citation — a
    transcript hit cites itself; concept/rule hits cite the same sources
    shown on their detail views."""
    selected_types = RESULT_TYPES
    if types:
        requested = tuple(t.strip().upper() for t in types.split(",") if t.strip())
        selected_types = tuple(t for t in requested if t in RESULT_TYPES) or RESULT_TYPES

    return search_knowledge(
        db, project.id, q, types=selected_types, series_id=series_id, limit=limit
    )
