"""Quantification workflow (STEP 15-16): turns a DISCRETIONARY or
PARTIALLY_QUANTIFIABLE rule into candidate machine-readable definitions a
human can approve — never applied automatically, and always stored
separately from the original `Rule.natural_language_rule` so a "PROPOSED
QUANTIFICATION" can never be confused with what the creator actually said.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.rule import Rule, RuleQuantification
from app.models.user import User
from app.security.clerk import get_current_user
from app.security.ownership import get_owned_rule, get_owned_rule_quantification
from app.services.audit import record_audit

router = APIRouter(prefix="/api/v1", tags=["quantifications"])


class QuantificationProposalIn(BaseModel):
    label: str = Field(min_length=1, max_length=16, description='e.g. "A", "B", "C".')
    description: str = Field(
        min_length=1, description="Plain-language description of this proposed definition."
    )
    machine_readable_rule: dict = Field(
        description="Structured, compiler-facing definition — never presented as the creator's words."
    )


class RuleQuantificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    proposals: list[dict]
    selected_index: int | None
    user_defined_alternative: dict | None
    selected_at: datetime | None
    created_at: datetime


class ProposeQuantificationsRequest(BaseModel):
    proposals: list[QuantificationProposalIn] = Field(min_length=1)


class SelectQuantificationRequest(BaseModel):
    selected_index: int | None = None
    user_defined_alternative: dict | None = None

    @model_validator(mode="after")
    def _exactly_one_choice(self) -> SelectQuantificationRequest:
        if (self.selected_index is None) == (self.user_defined_alternative is None):
            raise ValueError(
                "Provide exactly one of selected_index (choosing a proposal) or "
                "user_defined_alternative (defining your own)."
            )
        return self


@router.post(
    "/rules/{rule_id}/quantifications",
    response_model=RuleQuantificationOut,
    status_code=status.HTTP_201_CREATED,
)
def propose_quantifications(
    payload: ProposeQuantificationsRequest,
    rule: Rule = Depends(get_owned_rule),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleQuantification:
    """Records candidate numeric/structured definitions for a rule that
    isn't fully quantifiable as-is. This never runs automatically — every
    proposal must come from a human (or, in a future version, an AI
    suggestion still surfaced as a proposal, never as fact) and none of
    them affects `Rule.natural_language_rule` or the rule's own
    `quantifiability` classification."""
    existing = (
        db.query(RuleQuantification).filter(RuleQuantification.rule_id == rule.id).one_or_none()
    )
    proposals_json = [p.model_dump() for p in payload.proposals]
    if existing is not None:
        existing.proposals = proposals_json
        existing.selected_index = None
        existing.user_defined_alternative = None
        existing.selected_at = None
        existing.selected_by_user_id = None
        quantification = existing
    else:
        quantification = RuleQuantification(rule_id=rule.id, proposals=proposals_json)
        db.add(quantification)
    db.commit()
    db.refresh(quantification)
    record_audit(
        db,
        project_id=rule.project_id,
        user_id=user.id,
        action="rule.quantifications.proposed",
        entity_type="Rule",
        entity_id=rule.id,
    )
    return quantification


@router.get("/rules/{rule_id}/quantifications", response_model=RuleQuantificationOut | None)
def get_quantifications(
    rule: Rule = Depends(get_owned_rule), db: Session = Depends(get_db)
) -> RuleQuantification | None:
    return db.query(RuleQuantification).filter(RuleQuantification.rule_id == rule.id).one_or_none()


@router.post(
    "/rule-quantifications/{quantification_id}/select", response_model=RuleQuantificationOut
)
def select_quantification(
    quantification_id: uuid.UUID,
    payload: SelectQuantificationRequest,
    quantification: RuleQuantification = Depends(get_owned_rule_quantification),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleQuantification:
    """A human picks one proposal (or writes their own) before it can ever
    reach the Strategy Compiler. Nothing here is consumed by compilation
    until this has been called."""
    if payload.selected_index is not None:
        if not (0 <= payload.selected_index < len(quantification.proposals)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"selected_index out of range (0..{len(quantification.proposals) - 1}).",
            )
        quantification.selected_index = payload.selected_index
        quantification.user_defined_alternative = None
    else:
        quantification.selected_index = None
        quantification.user_defined_alternative = payload.user_defined_alternative

    quantification.selected_at = datetime.now(UTC)
    quantification.selected_by_user_id = user.id
    db.commit()
    db.refresh(quantification)
    record_audit(
        db,
        project_id=quantification.rule.project_id,
        user_id=user.id,
        action="rule.quantification.selected",
        entity_type="RuleQuantification",
        entity_id=quantification.id,
    )
    return quantification
