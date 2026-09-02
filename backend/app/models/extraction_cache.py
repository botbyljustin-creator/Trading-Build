from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ExtractionCache(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Caches a Knowledge Builder / Rule Extractor result keyed by the
    content hash of the exact chunk text sent to the model, plus which
    extractor and prompt version produced it. ICT (and most creators)
    repeats explanations verbatim across videos — this is what stops
    StrategyForge from re-spending LLM cost re-extracting identical text
    (Module: Control Token Cost). Not tied to any one project: identical
    transcript text should hit cache across projects too.
    """

    __tablename__ = "extraction_cache"
    __table_args__ = (
        UniqueConstraint(
            "content_hash", "extractor_name", "prompt_version", name="uq_extraction_cache_key"
        ),
    )

    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    extractor_name: Mapped[str] = mapped_column(String(64), index=True)
    prompt_version: Mapped[str] = mapped_column(String(32))
    result_json: Mapped[dict] = mapped_column(JSONB)
