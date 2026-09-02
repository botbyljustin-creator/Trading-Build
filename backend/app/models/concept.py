from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ConceptRelationType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Concept(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A trading concept actually evidenced in the source material (never a
    concept assumed to be relevant because it's common in trading)."""

    __tablename__ = "concepts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)

    sources: Mapped[list[ConceptSource]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )
    outgoing_relations: Mapped[list[ConceptRelation]] = relationship(
        back_populates="concept",
        foreign_keys="ConceptRelation.concept_id",
        cascade="all, delete-orphan",
    )


class ConceptSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single source citation backing a `Concept` — video + timestamp +
    verbatim excerpt. Every concept must have at least one of these."""

    __tablename__ = "concept_sources"

    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), index=True
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

    concept: Mapped[Concept] = relationship(back_populates="sources")


class ConceptRelation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "concept_relations"

    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    related_concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE")
    )
    relation_type: Mapped[ConceptRelationType] = mapped_column(
        SAEnum(ConceptRelationType, native_enum=False, length=32)
    )

    concept: Mapped[Concept] = relationship(
        back_populates="outgoing_relations", foreign_keys=[concept_id]
    )
