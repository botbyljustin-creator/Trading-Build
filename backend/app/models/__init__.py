"""SQLAlchemy ORM models.

Empty in Phase 1 beyond the shared declarative `Base`. Phase 2 onward adds
one module per bounded concept (e.g. `instruments.py`, `candles.py`,
`webhook_events.py`, ...) as described in ARCHITECTURE.md section 3.
Alembic autogenerate targets `Base.metadata`, so every model module added
in later phases must be imported here so migrations can see it.
"""

from app.models.base import Base

__all__ = ["Base"]
