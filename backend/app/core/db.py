"""SQLAlchemy engine/session management.

A single process-wide engine is created lazily from `Settings.database_url`.
`get_db` is a FastAPI dependency that yields a session per-request and
always closes it. `check_database_health` never raises — it is used by the
`/api/v1/health` endpoint and, later, the System Health dashboard page,
both of which must be able to report "database unavailable" rather than
crash when Postgres is down (fail-safe design: a health check that itself
fails ungracefully is useless).
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session, closes it after the request."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def check_database_health() -> tuple[bool, str | None]:
    """Attempt a trivial query against Postgres.

    Returns (is_healthy, error_message). Never raises.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - deliberately broad: this is a health probe
        logger.warning("database_health_check_failed", error=str(exc))
        return False, str(exc)
