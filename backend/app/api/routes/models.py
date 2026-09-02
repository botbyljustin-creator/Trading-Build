from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.project import Project
from app.security.ownership import get_owned_project
from app.services.readiness_service import compute_model_readiness

router = APIRouter(prefix="/api/v1", tags=["models"])


class ModelReadinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    series_id: uuid.UUID | None
    series_name: str
    creator_name: str | None
    total_rules: int
    explicit_rules: int
    fully_quantifiable_rules: int
    partially_quantifiable_rules: int
    discretionary_rules: int
    nasdaq_relevant_rules: int
    categories_present: list[str]
    categories_missing: list[str]
    unresolved_contradictions: int
    score: float
    score_breakdown: dict[str, float]


@router.get("/projects/{project_id}/models/readiness", response_model=list[ModelReadinessOut])
def get_model_readiness(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> list[ModelReadinessOut]:
    """Ranks every series (candidate 'model') in this project by how close
    its current rule set is to backtestable — never by backtesting
    everything at once (STEP 17). An empty or missing category lowers the
    score; it is never filled in with an invented rule."""
    return compute_model_readiness(db, project.id)
