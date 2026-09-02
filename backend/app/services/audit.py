"""Append-only audit trail writer (Module: Audit Log). Every route that
mutates reproducibility-relevant state calls this in the same DB
transaction as the mutation itself."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(
    db: Session,
    *,
    project_id: uuid.UUID | str,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            project_id=project_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )
