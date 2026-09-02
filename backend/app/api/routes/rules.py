from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.routes.common import JobOut
from app.core.db import get_db
from app.models.enums import JobType, Quantifiability, RuleCategory, RuleEvidenceType, RuleStatus
from app.models.project import Project
from app.models.rule import Rule
from app.models.user import User
from app.security.clerk import get_current_user
from app.security.ownership import get_owned_project, get_owned_rule
from app.services import job_service
from app.services.audit import record_audit
from app.services.tagging import tag_instruments

router = APIRouter(prefix="/api/v1", tags=["rules"])


class RuleSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    start_seconds: float
    end_seconds: float
    excerpt: str


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    series_id: uuid.UUID | None
    category: RuleCategory
    natural_language_rule: str
    machine_readable_rule: dict | None
    confidence: float
    status: RuleStatus
    evidence_type: RuleEvidenceType
    quantifiability: Quantifiability | None
    instrument_tags: list[str]
    is_user_provided: bool
    user_note: str | None
    created_at: datetime
    sources: list[RuleSourceOut]


class RuleUpdate(BaseModel):
    natural_language_rule: str | None = None
    machine_readable_rule: dict | None = None
    user_note: str | None = None
    quantifiability: Quantifiability | None = None


class RuleCreate(BaseModel):
    category: RuleCategory
    natural_language_rule: str = Field(min_length=1)
    machine_readable_rule: dict | None = None
    quantifiability: Quantifiability | None = None


@router.post(
    "/projects/{project_id}/rules/extract",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def extract_rules(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> JobOut:
    job = job_service.create_job(db, project_id=project.id, job_type=JobType.EXTRACT_RULES)
    from app.workers.tasks.extraction_tasks import extract_rules_task

    extract_rules_task.delay(str(job.id), str(project.id))
    db.refresh(job)
    return job


@router.get("/projects/{project_id}/rules", response_model=list[RuleOut])
def list_rules(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
    rule_status: RuleStatus | None = None,
    category: RuleCategory | None = None,
    evidence_type: RuleEvidenceType | None = None,
    series_id: uuid.UUID | None = None,
    instrument: str | None = None,
) -> list[Rule]:
    query = db.query(Rule).filter(Rule.project_id == project.id)
    if rule_status is not None:
        query = query.filter(Rule.status == rule_status)
    if category is not None:
        query = query.filter(Rule.category == category)
    if evidence_type is not None:
        query = query.filter(Rule.evidence_type == evidence_type)
    if series_id is not None:
        query = query.filter(Rule.series_id == series_id)
    if instrument is not None:
        query = query.filter(Rule.instrument_tags.contains([instrument.upper()]))
    return query.order_by(Rule.created_at.desc()).all()


@router.post(
    "/projects/{project_id}/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED
)
def create_manual_rule(
    payload: RuleCreate,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Rule:
    """Lets the user directly define a rule to fill a gap the Strategy
    Auditor flagged (Module 6: "ask the user to define them"). Marked
    `is_user_provided` and `USER_CONFIRMED` immediately — it was never an
    AI claim about what the creator said, so there's nothing to approve."""
    rule = Rule(
        project_id=project.id,
        category=payload.category,
        natural_language_rule=payload.natural_language_rule,
        machine_readable_rule=payload.machine_readable_rule,
        confidence=1.0,
        status=RuleStatus.USER_CONFIRMED,
        evidence_type=RuleEvidenceType.USER_DEFINED,
        quantifiability=payload.quantifiability,
        instrument_tags=tag_instruments(payload.natural_language_rule),
        is_user_provided=True,
        reviewed_by_user_id=user.id,
        reviewed_at=datetime.now(UTC),
    )
    db.add(rule)
    db.flush()
    record_audit(
        db,
        project_id=project.id,
        user_id=user.id,
        action="rule.user_provided",
        entity_type="Rule",
        entity_id=rule.id,
        details={"category": payload.category.value},
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=RuleOut)
def update_rule(
    payload: RuleUpdate,
    rule: Rule = Depends(get_owned_rule),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Rule:
    if payload.natural_language_rule is not None:
        rule.natural_language_rule = payload.natural_language_rule
        rule.instrument_tags = tag_instruments(payload.natural_language_rule)
    if payload.machine_readable_rule is not None:
        rule.machine_readable_rule = payload.machine_readable_rule
    if payload.user_note is not None:
        rule.user_note = payload.user_note
    if payload.quantifiability is not None:
        rule.quantifiability = payload.quantifiability
    rule.status = RuleStatus.USER_MODIFIED
    rule.reviewed_by_user_id = user.id
    rule.reviewed_at = datetime.now(UTC)
    record_audit(
        db,
        project_id=rule.project_id,
        user_id=user.id,
        action="rule.edited",
        entity_type="Rule",
        entity_id=rule.id,
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/rules/{rule_id}/approve", response_model=RuleOut)
def approve_rule_endpoint(
    rule: Rule = Depends(get_owned_rule),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Rule:
    from app.services.strategy_service import approve_rule

    approve_rule(db, rule, user.id)
    record_audit(
        db,
        project_id=rule.project_id,
        user_id=user.id,
        action="rule.approved",
        entity_type="Rule",
        entity_id=rule.id,
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/rules/{rule_id}/reject", response_model=RuleOut)
def reject_rule(
    rule: Rule = Depends(get_owned_rule),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Rule:
    rule.status = RuleStatus.REJECTED
    rule.reviewed_by_user_id = user.id
    rule.reviewed_at = datetime.now(UTC)
    record_audit(
        db,
        project_id=rule.project_id,
        user_id=user.id,
        action="rule.rejected",
        entity_type="Rule",
        entity_id=rule.id,
    )
    db.commit()
    db.refresh(rule)
    return rule
