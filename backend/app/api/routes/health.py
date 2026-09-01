"""System health endpoint.

Reports the status of every piece of infrastructure the application
depends on, without ever raising on a downstream outage — an outage is
data to report (and, in later phases, to act on: e.g. "DATA STALE" blocks
new signal approval), not a reason for this endpoint itself to fail.

The two health checks are exposed as FastAPI dependencies
(`database_health_dependency`, `redis_health_dependency`) specifically so
tests can override them via `app.dependency_overrides` instead of needing
a real Postgres/Redis instance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.db import check_database_health
from app.core.redis_client import check_redis_health

router = APIRouter(tags=["health"])

ComponentStatus = Literal["ok", "error"]
OverallStatus = Literal["ok", "degraded"]


class ComponentHealth(BaseModel):
    status: ComponentStatus
    error: str | None = None


class HealthResponse(BaseModel):
    status: OverallStatus
    app_name: str
    app_version: str
    app_env: str
    timestamp: datetime
    components: dict[str, ComponentHealth]


def database_health_dependency() -> ComponentHealth:
    healthy, error = check_database_health()
    return ComponentHealth(status="ok" if healthy else "error", error=error)


def redis_health_dependency() -> ComponentHealth:
    healthy, error = check_redis_health()
    return ComponentHealth(status="ok" if healthy else "error", error=error)


@router.get("/api/v1/health", response_model=HealthResponse)
def get_health(
    settings: Settings = Depends(get_settings),
    database: ComponentHealth = Depends(database_health_dependency),
    redis: ComponentHealth = Depends(redis_health_dependency),
) -> HealthResponse:
    components = {"database": database, "redis": redis}
    overall: OverallStatus = (
        "ok" if all(c.status == "ok" for c in components.values()) else "degraded"
    )
    return HealthResponse(
        status=overall,
        app_name=settings.app_name,
        app_version=settings.app_version,
        app_env=settings.app_env,
        timestamp=datetime.now(UTC),
        components=components,
    )
