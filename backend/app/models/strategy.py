from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import CodeLanguage, StrategyVersionStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Strategy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "strategies"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="strategies")  # noqa: F821
    versions: Mapped[list[StrategyVersion]] = relationship(
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyVersion.version_number",
    )


class StrategyVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (UniqueConstraint("strategy_id", "version_number"),)

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[StrategyVersionStatus] = mapped_column(
        SAEnum(StrategyVersionStatus, native_enum=False, length=32),
        default=StrategyVersionStatus.DRAFT,
    )
    completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    rule_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)

    strategy: Mapped[Strategy] = relationship(back_populates="versions")
    spec: Mapped[StrategySpec | None] = relationship(
        back_populates="strategy_version", uselist=False, cascade="all, delete-orphan"
    )
    generated_code: Mapped[list[GeneratedCode]] = relationship(
        back_populates="strategy_version", cascade="all, delete-orphan"
    )
    backtests: Mapped[list[Backtest]] = relationship(  # noqa: F821
        back_populates="strategy_version", cascade="all, delete-orphan"
    )


class StrategySpec(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The compiled, machine-readable `StrategySpecification` for one
    `StrategyVersion` — the single source of truth both code generators
    render from."""

    __tablename__ = "strategy_specs"

    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strategy_versions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    spec_json: Mapped[dict] = mapped_column(JSONB)

    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="spec")


class GeneratedCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generated_code"
    __table_args__ = (UniqueConstraint("strategy_version_id", "language"),)

    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategy_versions.id", ondelete="CASCADE"), index=True
    )
    language: Mapped[CodeLanguage] = mapped_column(
        SAEnum(CodeLanguage, native_enum=False, length=16)
    )
    code: Mapped[str] = mapped_column(Text)
    spec_hash: Mapped[str] = mapped_column(String(64))

    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="generated_code")
