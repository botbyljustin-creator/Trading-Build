from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Series(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A creator's coherent body of material — a mentorship year, a
    playlist, an educational series — kept distinct so rules from one
    series are never silently mixed with rules from another (Module: "do
    not flatten the channel"). `creator_name` is a plain string rather than
    a separate `Creator` table: V1 doesn't need cross-project creator
    identity, and a string is enough to group and filter by creator today
    without inventing structure nothing yet uses.
    """

    __tablename__ = "series"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    creator_name: Mapped[str] = mapped_column(String(255), index=True)
    series_name: Mapped[str] = mapped_column(String(255))
    youtube_playlist_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    videos: Mapped[list[Video]] = relationship(back_populates="series")  # noqa: F821
