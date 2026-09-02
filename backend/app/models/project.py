from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single strategy-research workspace: one or more sources feeding one
    or more strategies."""

    __tablename__ = "projects"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped[User] = relationship(back_populates="projects")  # noqa: F821
    sources: Mapped[list[Source]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
    strategies: Mapped[list[Strategy]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
