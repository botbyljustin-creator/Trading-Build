from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A generated strategy report (Reporting Agent output). `content_json`
    holds the fully-rendered, already-validated sections described in
    ARCHITECTURE.md / the top-level spec's Reporting section."""

    __tablename__ = "reports"

    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategy_versions.id", ondelete="CASCADE"), index=True
    )
    backtest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtests.id", ondelete="SET NULL"), nullable=True
    )
    content_json: Mapped[dict] = mapped_column(JSONB)
