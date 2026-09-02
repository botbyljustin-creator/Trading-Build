from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ContradictionResolution, RuleCategory, RuleStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Rule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single extracted (or user-authored) trading rule.

    `machine_readable_rule` is a best-effort structured JSON representation
    produced by the Rule Extractor; it is a *hint* for the Strategy Compiler,
    not itself authoritative — the compiler re-validates against the
    `StrategySpecification` schema.
    """

    __tablename__ = "rules"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[RuleCategory] = mapped_column(
        SAEnum(RuleCategory, native_enum=False, length=32), index=True
    )
    natural_language_rule: Mapped[str] = mapped_column(Text)
    machine_readable_rule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[RuleStatus] = mapped_column(
        SAEnum(RuleStatus, native_enum=False, length=32), default=RuleStatus.EXTRACTED, index=True
    )
    is_user_provided: Mapped[bool] = mapped_column(default=False)
    user_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    sources: Mapped[list[RuleSource]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class RuleSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rule_sources"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules.id", ondelete="CASCADE"), index=True
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE")
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transcript_chunks.id", ondelete="SET NULL"), nullable=True
    )
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    excerpt: Mapped[str] = mapped_column(Text)

    rule: Mapped[Rule] = relationship(back_populates="sources")


class Contradiction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A flagged conflict between two rules (Module 7). Never auto-resolved."""

    __tablename__ = "contradictions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    rule_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules.id", ondelete="CASCADE")
    )
    rule_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules.id", ondelete="CASCADE")
    )
    explanation: Mapped[str] = mapped_column(Text)
    resolution: Mapped[ContradictionResolution] = mapped_column(
        SAEnum(ContradictionResolution, native_enum=False, length=32),
        default=ContradictionResolution.UNRESOLVED,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    rule_a: Mapped[Rule] = relationship(foreign_keys=[rule_a_id])
    rule_b: Mapped[Rule] = relationship(foreign_keys=[rule_b_id])
