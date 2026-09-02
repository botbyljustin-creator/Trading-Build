from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A StrategyForge account. `clerk_user_id` is the Clerk subject (`sub`)
    claim — the only externally-trusted identity for this row."""

    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    projects: Mapped[list[Project]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )
