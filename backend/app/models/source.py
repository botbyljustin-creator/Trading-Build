from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import SourceStatus, SourceType, TranscriptStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

EMBEDDING_DIM = 1536


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-submitted URL (video, playlist, or channel) and its resolution
    state. One `Source` can expand into many `Video` rows."""

    __tablename__ = "sources"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, native_enum=False, length=32)
    )
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[SourceStatus] = mapped_column(
        SAEnum(SourceStatus, native_enum=False, length=32), default=SourceStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Populated by the cost-estimation step before a large channel/playlist
    # is actually processed (Module: Cost Controls).
    estimated_video_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_transcript_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    project: Mapped[Project] = relationship(back_populates="sources")  # noqa: F821
    videos: Mapped[list[Video]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Video(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "videos"
    __table_args__ = (Index("ix_videos_project_youtube_id", "project_id", "youtube_video_id"),)

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    youtube_video_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(500))
    channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    publish_date: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    transcript_status: Mapped[TranscriptStatus] = mapped_column(
        SAEnum(TranscriptStatus, native_enum=False, length=32), default=TranscriptStatus.PENDING
    )
    transcript_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="videos")
    transcript: Mapped[Transcript | None] = relationship(
        back_populates="video", uselist=False, cascade="all, delete-orphan"
    )


class Transcript(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transcripts"

    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True
    )
    language: Mapped[str] = mapped_column(String(16), default="en")
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    full_text: Mapped[str] = mapped_column(Text)

    video: Mapped[Video] = relationship(back_populates="transcript")
    chunks: Mapped[list[TranscriptChunk]] = relationship(
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptChunk.chunk_index",
    )


class TranscriptChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transcript_chunks"
    __table_args__ = (Index("ix_transcript_chunks_video_id", "video_id"),)

    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), index=True
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    transcript: Mapped[Transcript] = relationship(back_populates="chunks")
    embedding: Mapped[Embedding | None] = relationship(
        back_populates="chunk", uselist=False, cascade="all, delete-orphan"
    )


class Embedding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "embeddings"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcript_chunks.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(128))
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    chunk: Mapped[TranscriptChunk] = relationship(back_populates="embedding")
