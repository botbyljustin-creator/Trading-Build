"""Tests for GET /api/v1/health.

Covers the fail-safe requirement that the health endpoint reports infra
outages as data (HTTP 200, component status "error") rather than raising —
this is what lets System Health (later phases) distinguish "app is down"
from "app is up but a dependency is down".
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.routes.health import (
    ComponentHealth,
    database_health_dependency,
    redis_health_dependency,
)
from app.main import app


def test_health_all_healthy(client: TestClient) -> None:
    app.dependency_overrides[database_health_dependency] = lambda: ComponentHealth(status="ok")
    app.dependency_overrides[redis_health_dependency] = lambda: ComponentHealth(status="ok")

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["components"]["database"]["status"] == "ok"
    assert body["components"]["redis"]["status"] == "ok"
    assert body["app_name"] == "StrategyForge AI"


def test_health_reports_database_outage_without_raising(client: TestClient) -> None:
    app.dependency_overrides[database_health_dependency] = lambda: ComponentHealth(
        status="error", error="connection refused"
    )
    app.dependency_overrides[redis_health_dependency] = lambda: ComponentHealth(status="ok")

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["components"]["database"]["status"] == "error"
    assert body["components"]["database"]["error"] == "connection refused"
    assert body["components"]["redis"]["status"] == "ok"


def test_health_reports_redis_outage_without_raising(client: TestClient) -> None:
    app.dependency_overrides[database_health_dependency] = lambda: ComponentHealth(status="ok")
    app.dependency_overrides[redis_health_dependency] = lambda: ComponentHealth(
        status="error", error="timeout"
    )

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["components"]["redis"]["status"] == "error"


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "StrategyForge AI"
    assert body["docs"] == "/docs"
