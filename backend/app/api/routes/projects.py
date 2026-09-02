from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.project import Project
from app.models.user import User
from app.security.clerk import get_current_user
from app.security.ownership import get_owned_project
from app.services.audit import record_audit

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    project = Project(owner_id=user.id, name=payload.name, description=payload.description)
    db.add(project)
    db.flush()
    record_audit(
        db,
        project_id=project.id,
        user_id=user.id,
        action="project.created",
        entity_type="Project",
        entity_id=project.id,
        details={"name": project.name},
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Project]:
    return (
        db.query(Project)
        .filter(Project.owner_id == user.id)
        .order_by(Project.created_at.desc())
        .all()
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project: Project = Depends(get_owned_project)) -> Project:
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    payload: ProjectUpdate,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    record_audit(
        db,
        project_id=project.id,
        user_id=user.id,
        action="project.updated",
        entity_type="Project",
        entity_id=project.id,
    )
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_project(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_db)
) -> None:
    db.delete(project)
    db.commit()
