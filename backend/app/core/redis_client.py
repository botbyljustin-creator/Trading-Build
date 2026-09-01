"""Redis client access.

Redis backs (in later phases) webhook-dedupe keys, caching, and the Celery
broker/result backend. `check_redis_health` mirrors `check_database_health`:
it never raises, so the health endpoint and System Health page can report
"Redis unavailable" instead of crashing.
"""

from __future__ import annotations

from functools import lru_cache

import redis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def check_redis_health() -> tuple[bool, str | None]:
    """Attempt a PING against Redis. Returns (is_healthy, error_message)."""
    try:
        client = get_redis_client()
        client.ping()
        return True, None
    except Exception as exc:  # noqa: BLE001 - deliberately broad: this is a health probe
        logger.warning("redis_health_check_failed", error=str(exc))
        return False, str(exc)
