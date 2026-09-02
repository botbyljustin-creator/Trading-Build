from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.enums import CodeLanguage, StrategyVersionStatus
from app.models.project import Project
from app.models.strategy import GeneratedCode, Strategy, StrategyVersion
from app.models.user import User
from app.schemas.strategy_spec import StrategySpecification
from app.security.clerk import get_current_user
from app.security.ownership import get_owned_project, get_owned_strategy, get_owned_strategy_version
from app.services.audit import record_audit
from app.services.strategy_service import (
    RulesNotCompilableError,
    UnresolvedContradictionsError,
    compile_strategy_version,
    generate_code_for_version,
)
from app.strategy.versioning import diff_specs

router = APIRouter(prefix="/api/v1", tags=["strategies"])


class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class StrategyVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    label: str | None
    change_summary: str | None
    status: StrategyVersionStatus
    completeness_score: float | None
    missing_fields: list | None
    rule_ids: list[str]
    created_at: datetime


class StrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    versions: list[StrategyVersionOut]


class CompileRequest(BaseModel):
    rule_ids: list[uuid.UUID] = Field(min_length=1)


class GeneratedCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    language: CodeLanguage
    code: str
    spec_hash: str


@router.post(
    "/projects/{project_id}/strategies",
    response_model=StrategyOut,
    status_code=status.HTTP_201_CREATED,
)
def create_strategy(
    payload: StrategyCreate,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Strategy:
    strategy = Strategy(project_id=project.id, name=payload.name, description=payload.description)
    db.add(strategy)
    db.flush()
    record_audit(
        db,
        project_id=project.id,
        user_id=user.id,
        action="strategy.created",
        entity_type="Strategy",
        entity_id=strategy.id,
    )
    db.commit()
    db.refresh(strategy)
    return strategy


@router.get("/projects/{project_id}/strategies", response_model=list[StrategyOut])
def list_strategies(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> list[Strategy]:
    return (
        db.query(Strategy)
        .filter(Strategy.project_id == project.id)
        .order_by(Strategy.created_at.desc())
        .all()
    )


@router.get("/strategies/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy: Strategy = Depends(get_owned_strategy)) -> Strategy:
    return strategy


@router.post(
    "/strategies/{strategy_id}/versions/compile",
    response_model=StrategyVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def compile_version(
    payload: CompileRequest,
    strategy: Strategy = Depends(get_owned_strategy),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StrategyVersion:
    try:
        version = compile_strategy_version(db, strategy, payload.rule_ids)
    except RulesNotCompilableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnresolvedContradictionsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        db,
        project_id=strategy.project_id,
        user_id=user.id,
        action="strategy.compiled",
        entity_type="StrategyVersion",
        entity_id=version.id,
        details={
            "version_number": version.version_number,
            "completeness_score": version.completeness_score,
        },
    )
    db.commit()
    return version


@router.get("/strategy-versions/{version_id}", response_model=StrategyVersionOut)
def get_strategy_version(
    version: StrategyVersion = Depends(get_owned_strategy_version),
) -> StrategyVersion:
    return version


@router.get("/strategy-versions/{version_id}/spec")
def get_strategy_version_spec(
    version: StrategyVersion = Depends(get_owned_strategy_version),
) -> dict:
    if version.spec is None:
        raise HTTPException(
            status_code=404, detail="This version has not been compiled with a spec."
        )
    return version.spec.spec_json


@router.get("/strategy-versions/{from_id}/compare/{to_id}")
def compare_versions(
    from_id: uuid.UUID,
    to_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    from app.security.ownership import get_owned_strategy_version as _owned

    from_version = _owned(from_id, db, user)
    to_version = _owned(to_id, db, user)
    if from_version.spec is None or to_version.spec is None:
        raise HTTPException(
            status_code=400, detail="Both versions must have a compiled spec to compare."
        )
    from_spec = StrategySpecification.model_validate(from_version.spec.spec_json)
    to_spec = StrategySpecification.model_validate(to_version.spec.spec_json)
    return {
        "from_version": from_version.version_number,
        "to_version": to_version.version_number,
        "changes": diff_specs(from_spec, to_spec),
    }


@router.post("/strategy-versions/{version_id}/generate-code", response_model=list[GeneratedCodeOut])
def generate_code(
    version: StrategyVersion = Depends(get_owned_strategy_version),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GeneratedCode]:
    try:
        rows = generate_code_for_version(db, version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(
        db,
        project_id=version.strategy.project_id,
        user_id=user.id,
        action="code.generated",
        entity_type="StrategyVersion",
        entity_id=version.id,
    )
    db.commit()
    return rows


@router.get("/strategy-versions/{version_id}/code", response_model=list[GeneratedCodeOut])
def get_generated_code(
    version: StrategyVersion = Depends(get_owned_strategy_version), db: Session = Depends(get_db)
) -> list[GeneratedCode]:
    return db.query(GeneratedCode).filter(GeneratedCode.strategy_version_id == version.id).all()
